import os
import re
import json
import zipfile
import shutil
import logging
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

logger = logging.getLogger("Importer")

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
                        title = t_elem.text.strip()
                    a_elem = soup_opf.find(['dc:creator', 'creator'])
                    if a_elem and a_elem.text.strip():
                        author = a_elem.text.strip()
                    l_elem = soup_opf.find(['dc:language', 'language'])
                    if l_elem and l_elem.text.strip():
                        language = l_elem.text.strip().lower()[:2]
                except Exception:
                    pass

            html_files = [f for f in namelist if f.endswith(('.html', '.xhtml'))]

            return {
                "suggested_title": title,
                "suggested_author": author,
                "suggested_language": language,
                "suggested_start_node": "sec_001",
                "total_sections": len(html_files)
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
        tier_id: int = 1
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
            title = meta.get("title") or self.epub_path.stem
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
                h1 = soup.find('h1')
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
            valid_xhtml_files = [
                f for f in xhtml_files 
                if Path(f).name.lower() not in ('cubierta.xhtml', 'info.xhtml', 'sinopsis.xhtml', 'titulo.xhtml')
            ]

            for fname in valid_xhtml_files:
                base_name = Path(fname).name
                node_id = file_to_node_id[fname]
                content = z.read(fname).decode('utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'html.parser')

                h1 = soup.find('h1')
                display_num = node_id_to_num.get(node_id)
                heading_title = h1.get_text().strip() if h1 else (f"Página {display_num}" if display_num else base_name)

                paragraphs = []
                for p in soup.find_all('p'):
                    if p.get('class') and 'cubierta' in p.get('class'):
                        continue
                    text_p = p.get_text().strip()
                    if text_p:
                        paragraphs.append(text_p)

                full_text = "\n\n".join(paragraphs)

                node_images = []
                for img in soup.find_all('img'):
                    src = img.get('src', '')
                    img_name = Path(src).name
                    if img_name in image_map:
                        node_images.append(image_map[img_name])

                choices = []
                choice_idx = 1
                for a in soup.find_all('a'):
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
                    "images": node_images,
                    "audio": audio_rel_path,
                    "audio_options": audio_options_rel_path,
                    "choices": choices
                }
                nodes[node_id] = node_data

            # Add sequential linear continuation choice for pages with 0 choices
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
            start_node_id = start_node_override or start_node_id

            book_json_data = {
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
                "narrator_id": 2 if final_language == "en" else 1,
                "features": {
                    "inventory": False,
                    "dice": False,
                    "combat": False,
                    "variables": False
                },
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
                generate_nodes_audio(self.tts_manager, nodes, output_dir, language=final_language, tts_engine=tts_engine, voice_name=voice_name)

            return book_json_path
