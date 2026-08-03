import os
import re
import json
import zipfile
import shutil
import logging
from html import escape
from pathlib import Path
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from config import BOOKS_DIR
from src.tts import TTSManager
from src.importer.epub_parser import (
    sanitize_book_id, extract_number_from_filename, natural_file_sort_key, parse_opf_metadata
)
from src.importer.ending_detector import detect_ending_nodes
from src.importer.tts_pipeline import generate_nodes_audio
from src.importer.tts_pipeline import generate_supplements_audio

logger = logging.getLogger("Importer")

REFERENCE_TERMS = (
    "regla", "cómo jugar", "como jugar", "how to play", "glosario", "glossary",
    "tabla", "chart", "ficha", "character sheet", "combate", "combat",
    "disciplina", "equipment", "equipo", "magia", "magic",
)
FRONT_MATTER_TERMS = (
    "introducción", "introduccion", "prólogo", "prologo", "sinopsis", "dedicatoria",
    "preliminar", "preliminares", "atención", "atencion", "créditos", "creditos",
    "presentación", "presentacion",
)


def _local_name(element) -> str:
    """Return an HTML/XML tag name without a namespace prefix."""
    return (getattr(element, "name", "") or "").rsplit(":", 1)[-1].lower()


def _find_local(soup, names):
    names = {name.lower() for name in names}
    return next((element for element in soup.find_all(True) if _local_name(element) in names), None)


def _find_all_local(soup, names):
    names = {name.lower() for name in names}
    return [element for element in soup.find_all(True) if _local_name(element) in names]


RICH_INLINE_TAGS = {"strong", "b", "em", "i", "u", "mark", "sub", "sup", "small"}


def _serialize_rich_text(element) -> str:
    """Preserve safe inline formatting while stripping source-specific markup/attrs."""
    output = []
    for child in element.children:
        if not getattr(child, "name", None):
            output.append(escape(str(child)))
            continue
        tag = _local_name(child)
        if tag == "br":
            output.append("<br>")
        else:
            inner = _serialize_rich_text(child)
            if tag in RICH_INLINE_TAGS:
                normalized = "strong" if tag == "b" else "em" if tag == "i" else tag
                output.append(f"<{normalized}>{inner}</{normalized}>")
            else:
                output.append(inner)
    return "".join(output).strip()


def _clean_epub_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return title
    return re.sub(r"\s*\.(?:pdf|epub)$", "", title.strip(), flags=re.IGNORECASE)

def build_epub_supplements(z_file, ordered_files, story_files, image_map):
    """Convert non-story XHTML resources into ordered supplemental material."""
    if not story_files:
        return []
    first_story = ordered_files.index(story_files[0])
    last_story = ordered_files.index(story_files[-1])
    counters = {"front_matter": 0, "reference": 0, "back_matter": 0}
    supplements = []

    for index, filename in enumerate(ordered_files):
        if filename in story_files:
            continue
        base_name = Path(filename).name.lower()
        if base_name in ("cubierta.xhtml", "titulo.xhtml"):
            continue
        soup = BeautifulSoup(z_file.read(filename).decode("utf-8", errors="ignore"), "html.parser")
        title = next((
            element.get_text(" ", strip=True)
            for element in _find_all_local(soup, ["h1", "h2", "h3", "title"])
            if element.get_text(" ", strip=True)
        ), Path(filename).stem.replace("_", " ").title())
        text_parts = []
        rich_parts = []
        for element in _find_all_local(soup, ["p", "li", "blockquote"]):
            text = element.get_text(" ", strip=True)
            if text:
                text_parts.append(text)
                rich_parts.append(f"<p>{_serialize_rich_text(element)}</p>")
        text = "\n\n".join(text_parts)
        images = []
        for image in _find_all_local(soup, ["img"]):
            image_name = Path(image.get("src", "")).name
            if image_name in image_map and image_map[image_name] not in images:
                images.append(image_map[image_name])
        if len(text) < 40 and not images:
            continue

        if base_name in ("preliminares.xhtml", "preliminares.html") or any(term in title.lower() for term in FRONT_MATTER_TERMS):
            category = "front_matter"
        elif base_name in ("finales.xhtml", "finales.html"):
            category = "back_matter"
        elif any(term in title.lower() for term in REFERENCE_TERMS):
            category = "reference"
        elif index < first_story:
            category = "front_matter"
        elif index > last_story:
            category = "back_matter"
        else:
            category = "reference"
        counters[category] += 1
        prefix = {"front_matter": "front", "reference": "reference", "back_matter": "back"}[category]
        item_id = f"{prefix}_{counters[category]:03d}"
        supplements.append({
            "id": item_id,
            "order": len(supplements) + 1,
            "category": category,
            "title": title,
            "text": text,
            "text_html": "\n".join(rich_parts),
            "images": images,
            "audio": f"audios/supplements/{item_id}.mp3",
            "source_file": Path(filename).name,
        })
    category_order = {"front_matter": 0, "reference": 1, "back_matter": 2}
    supplements.sort(key=lambda item: (category_order.get(item["category"], 9), item["order"]))
    for order, item in enumerate(supplements, 1):
        item["order"] = order
    return supplements

class EPUBImporter:
    def __init__(self, epub_path: Path, tts_manager: Optional[TTSManager] = None):
        self.epub_path = Path(epub_path)
        self.tts_manager = tts_manager or TTSManager()

    def inspect(self) -> Dict[str, Any]:
        """Fast pre-flight analysis of EPUB metadata without audio synthesis or DB seeding."""
        with zipfile.ZipFile(self.epub_path, 'r') as z:
            namelist = z.namelist()
            title = self.epub_path.stem
            author = "Desconocido"
            language = "es"

            opf_file = next((name for name in namelist if name.endswith('.opf')), None)
            if opf_file:
                try:
                    soup_opf = BeautifulSoup(z.read(opf_file).decode('utf-8', errors='ignore'), 'html.parser')
                    t_elem = soup_opf.find(['dc:title', 'title'])
                    if t_elem and t_elem.text.strip():
                        title = _clean_epub_title(t_elem.text.strip())
                    a_elem = soup_opf.find(['dc:creator', 'creator'])
                    if a_elem and a_elem.text.strip():
                        author = a_elem.text.strip()
                    l_elem = soup_opf.find(['dc:language', 'language'])
                    if l_elem and l_elem.text.strip():
                        language = l_elem.text.strip().lower()[:2]
                except Exception:
                    pass

            html_files = [f for f in namelist if f.endswith(('.html', '.xhtml'))]
            normalized_sections = sorted(
                [f for f in html_files if "/secciones/" in f.lower() and re.search(r"seccion-\d+", Path(f).stem, re.IGNORECASE)],
                key=natural_file_sort_key,
            )
            first_section = extract_number_from_filename(Path(normalized_sections[0]).name) if normalized_sections else 1

            return {
                "suggested_title": title,
                "suggested_author": author,
                "suggested_language": language,
                "suggested_start_node": f"sec_{first_section:03d}",
                "total_sections": len(normalized_sections) if normalized_sections else len(html_files)
            }

    def process(
        self,
        generate_audios: bool = True,
        title: Optional[str] = None,
        author: Optional[str] = None,
        language: Optional[str] = None,
        start_node: Optional[str] = None,
        tts_engine: str = "auto",
        voice_name: Optional[str] = None,
        tier_id: int = 1,
        narrator_id: Optional[int] = None
    ) -> Path:
        title_override = title
        author_override = author
        language_override = language
        start_node_override = start_node

        if not self.epub_path.exists():
            raise FileNotFoundError(f"EPUB file not found: {self.epub_path}")

        logger.info(f"Processing EPUB: {self.epub_path.name}")
        
        with zipfile.ZipFile(self.epub_path, 'r') as z:
            namelist = z.namelist()
            opf_file = next((name for name in namelist if name.endswith('.opf')), None)
            
            meta = parse_opf_metadata(z, opf_file) if opf_file else {}
            title = _clean_epub_title(meta.get("title")) or self.epub_path.stem
            author = meta.get("author")
            publisher = meta.get("publisher")
            year = meta.get("year")
            language = meta.get("language") or "es"
            description = meta.get("description")
            isbn = meta.get("isbn")
            genre = meta.get("genre")
            series = meta.get("series")
            volume = meta.get("volume")
            soup_opf = meta.get("soup_opf")

            book_id = sanitize_book_id(title)
            output_dir = BOOKS_DIR / book_id
            images_dir = output_dir / "images"
            audios_dir = output_dir / "audios"
            output_dir.mkdir(parents=True, exist_ok=True)
            images_dir.mkdir(parents=True, exist_ok=True)
            audios_dir.mkdir(parents=True, exist_ok=True)

            # Copy all image files from EPUB to images_dir
            image_map = {}
            for name in namelist:
                if name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg')):
                    img_filename = Path(name).name
                    target_img_path = images_dir / img_filename
                    with z.open(name) as src, open(target_img_path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)
                    image_map[img_filename] = f"images/{img_filename}"
                    image_map[name] = f"images/{img_filename}"

            # Step 1: Discover all XHTML/HTML files naturally sorted by embedded page numbers
            raw_xhtml_files = [n for n in namelist if n.endswith(('.xhtml', '.html'))]
            xhtml_files = sorted(raw_xhtml_files, key=natural_file_sort_key)
            file_to_node_id = {}
            node_id_to_num = {}

            for fname in xhtml_files:
                base_name = Path(fname).name
                content = z.read(fname).decode('utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'html.parser')
                h1 = _find_local(soup, ['h1', 'h2', 'h3'])
                h1_text = h1.get_text().strip() if h1 else ""

                if h1_text.isdigit():
                    num = int(h1_text)
                    node_id = f"sec_{num:03d}"
                    node_id_to_num[node_id] = num
                else:
                    file_num = extract_number_from_filename(base_name)
                    if file_num is not None:
                        node_id = f"sec_{file_num:03d}"
                        node_id_to_num[node_id] = file_num
                    else:
                        node_id = f"sec_{sanitize_book_id(base_name)}"

                file_to_node_id[fname] = node_id
                file_to_node_id[base_name] = node_id

            # Step 2: Build Nodes
            nodes = {}
            content_xhtml_files = [
                f for f in xhtml_files
                if Path(f).name.lower() not in ('cubierta.xhtml', 'titulo.xhtml', 'nav.xhtml')
            ]
            normalized_sections = [
                f for f in content_xhtml_files
                if "/secciones/" in f.lower() and re.search(r"seccion-\d+", Path(f).stem, re.IGNORECASE)
            ]
            is_normalized = bool(normalized_sections)
            valid_xhtml_files = sorted(normalized_sections, key=natural_file_sort_key) if is_normalized else []
            if not is_normalized:
                for filename in content_xhtml_files:
                    content = z.read(filename).decode('utf-8', errors='ignore')
                    soup = BeautifulSoup(content, 'html.parser')
                    heading = _find_local(soup, ['h1', 'h2', 'h3'])
                    heading_text = heading.get_text(" ", strip=True) if heading else ""
                    if re.fullmatch(r"\d{1,4}(?:f\d+)?", heading_text, re.IGNORECASE):
                        valid_xhtml_files.append(filename)
            # Preserve compatibility with EPUBs whose story files do not use
            # numeric headings or filenames.
            if not valid_xhtml_files:
                valid_xhtml_files = content_xhtml_files
            supplements = build_epub_supplements(
                z, content_xhtml_files, valid_xhtml_files, image_map
            )

            for fname in valid_xhtml_files:
                base_name = Path(fname).name
                node_id = file_to_node_id[fname]
                content = z.read(fname).decode('utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'html.parser')

                h1 = _find_local(soup, ['h1', 'h2', 'h3'])
                display_num = node_id_to_num.get(node_id)
                heading_title = h1.get_text().strip() if h1 else (f"Página {display_num}" if display_num else base_name)

                paragraphs = []
                rich_paragraphs = []
                for p in _find_all_local(soup, ['p']):
                    if p.get('class') and 'cubierta' in p.get('class'):
                        continue
                    text_p = p.get_text().strip()
                    if text_p:
                        paragraphs.append(text_p)
                        rich_paragraphs.append(f"<p>{_serialize_rich_text(p)}</p>")

                full_text = "\n\n".join(paragraphs)

                node_images = []
                for img in _find_all_local(soup, ['img']):
                    src = img.get('src', '')
                    img_name = Path(src).name
                    if img_name in image_map:
                        node_images.append(image_map[img_name])

                choices = []
                choice_idx = 1
                for a in _find_all_local(soup, ['a']):
                    href = a.get('href', '')
                    if not href or href.startswith('#') or 'notas' in href:
                        continue
                    target_file = Path(href).name.split('#')[0]
                    target_node_id = file_to_node_id.get(target_file) or file_to_node_id.get(href)
                    if target_node_id and target_node_id != node_id:
                        choice_text = a.get_text().strip()
                        target_num = node_id_to_num.get(target_node_id)
                        choices.append({
                            "choice_id": choice_idx,
                            "text": choice_text,
                            "target_node": target_node_id,
                            "target_display_number": target_num
                        })
                        choice_idx += 1

                audio_rel_path = f"audios/{node_id}.mp3"
                audio_options_rel_path = f"audios/{node_id}_options.mp3" if choices else None

                node_data = {
                    "id": node_id,
                    "display_number": display_num,
                    "title": heading_title,
                    "text": full_text,
                    "text_html": "\n".join(rich_paragraphs),
                    "images": node_images,
                    "audio": audio_rel_path,
                    "audio_options": audio_options_rel_path,
                    "choices": choices
                }
                nodes[node_id] = node_data

            # Add sequential linear continuation choice for pages with 0 choices
            if not is_normalized:
                for i in range(len(valid_xhtml_files) - 1):
                    cur_file = valid_xhtml_files[i]
                    next_file = valid_xhtml_files[i + 1]
                    cur_id = file_to_node_id.get(cur_file)
                    next_id = file_to_node_id.get(next_file)

                    if cur_id and next_id and cur_id in nodes:
                        if len(nodes[cur_id]["choices"]) == 0:
                            next_title = nodes[next_id].get("title") or ""
                            nodes[cur_id]["choices"].append({
                                "choice_id": 1,
                                "text": f"Continuar leyendo ({next_title})" if next_title else "Continuar a la siguiente página",
                                "target_node": next_id,
                                "target_display_number": nodes[next_id].get("display_number")
                            })
                            nodes[cur_id]["audio_options"] = f"audios/{cur_id}_options.mp3"

            if valid_xhtml_files:
                start_node_id = file_to_node_id[valid_xhtml_files[0]]
            elif nodes:
                start_node_id = sorted(nodes.keys())[0]
            else:
                start_node_id = "sec_001"

            # Smart Cover Detection
            cover_image_path = None
            if opf_file and soup_opf:
                try:
                    meta_cover = soup_opf.find('meta', attrs={'name': 'cover'})
                    if meta_cover and meta_cover.get('content'):
                        cover_id = meta_cover['content']
                        item = soup_opf.find('item', attrs={'id': cover_id})
                        if item and item.get('href'):
                            fname = Path(item['href']).name
                            if fname in image_map:
                                cover_image_path = image_map[fname]
                    if not cover_image_path:
                        item_prop = soup_opf.find('item', attrs={'properties': 'cover-image'})
                        if item_prop and item_prop.get('href'):
                            fname = Path(item_prop['href']).name
                            if fname in image_map:
                                cover_image_path = image_map[fname]
                except Exception as e:
                    logger.warning(f"Error parsing OPF cover: {e}")

            if not cover_image_path:
                for kw in ['cover', 'cubierta', 'portada', 'front']:
                    for img_fname, img_rel in image_map.items():
                        if kw in Path(img_fname).name.lower():
                            cover_image_path = img_rel
                            break
                    if cover_image_path:
                        break

            if not cover_image_path:
                cover_image_path = image_map.get("01.jpg") or image_map.get("00.jpg") or (list(image_map.values())[0] if image_map else None)

            total_sections = len(nodes)
            total_words = sum(len(n.get('text', '').split()) for n in nodes.values())
            est_duration_minutes = max(5, round(total_words / 180)) if total_words > 0 else (total_sections * 2)

            endings_detected = detect_ending_nodes(nodes, start_node_id)

            final_title = title_override or title
            final_author = author_override or author or "Desconocido"
            final_language = (language_override or language or "es").lower()[:2]
            if start_node_override and start_node_override in nodes:
                start_node_id = start_node_override
            elif start_node_override and start_node_override not in nodes:
                logger.warning(
                    "Requested start node '%s' does not exist; keeping detected start node '%s'.",
                    start_node_override, start_node_id,
                )

            final_narrator_id = narrator_id or (2 if final_language == "en" else 1)

            book_json_data = {
                "ir_version": "1.1",
                "book_id": book_id,
                "title": final_title,
                "author": final_author,
                "publisher": publisher,
                "year": year,
                "language": final_language,
                "description": description or f"Aventura interactiva basada en {title}.",
                "isbn": isbn,
                "genre": genre or "Ficción Interactiva",
                "series": series,
                "volume": volume,
                "estimated_duration": f"{est_duration_minutes} minutos",
                "cover_image": cover_image_path,
                "total_sections": total_sections,
                "start_node": start_node_id,
                "tier_id": tier_id,
                "narrator_id": final_narrator_id,
                "features": {
                    "inventory": False,
                    "dice": False,
                    "combat": False,
                    "variables": False
                },
                "supplements": supplements,
                "nodes": nodes
            }

            book_json_path = output_dir / "book.json"
            with open(book_json_path, 'w', encoding='utf-8') as f:
                json.dump(book_json_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Imported {total_sections} nodes with extended metadata to {book_json_path}")

            try:
                from src.db import Database
                db = Database()
                db.upsert_book(book_json_data)
                if endings_detected:
                    db.register_book_endings(book_id, endings_detected)
                    logger.info(f"Registered {len(endings_detected)} ending nodes in database for '{book_id}'.")
            except Exception as e:
                logger.warning(f"Could not seed book in database: {e}")

            if generate_audios:
                generate_nodes_audio(self.tts_manager, nodes, output_dir, language=final_language, tts_engine=tts_engine, voice_name=voice_name, narrator_id=final_narrator_id)
                generate_supplements_audio(
                    self.tts_manager, supplements, output_dir,
                    language=final_language, tts_engine=tts_engine,
                    voice_name=voice_name, narrator_id=final_narrator_id,
                )

            return book_json_path
