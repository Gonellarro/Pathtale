import os
import re
import zipfile
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
from src.importer.tts_pipeline import generate_supplements_audio
from src.importer.normalized_epub_validator import NormalizedEPUBValidator
from src.importer.epub_resources import EPUBResourceExtractor
from src.importer.epub_story_parser import EPUBStoryParser
from src.importer.epub_supplements import build_epub_supplements
from src.importer.book_publisher import BookPublisher

logger = logging.getLogger("Importer")

def _local_name(element) -> str:
    """Return an HTML/XML tag name without a namespace prefix."""
    return (getattr(element, "name", "") or "").rsplit(":", 1)[-1].lower()


def _find_local(soup, names):
    names = {name.lower() for name in names}
    return next((element for element in soup.find_all(True) if _local_name(element) in names), None)


def _find_all_local(soup, names):
    names = {name.lower() for name in names}
    return [element for element in soup.find_all(True) if _local_name(element) in names]


def _clean_epub_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return title
    return re.sub(r"\s*\.epub$", "", title.strip(), flags=re.IGNORECASE)

class EPUBImporter:
    def __init__(self, epub_path: Path, tts_manager: Optional[TTSManager] = None):
        self.epub_path = Path(epub_path)
        self.tts_manager = tts_manager or TTSManager()

    def inspect(self) -> Dict[str, Any]:
        """Fast pre-flight analysis of EPUB metadata without audio synthesis or DB seeding."""
        with zipfile.ZipFile(self.epub_path, 'r') as z:
            namelist = z.namelist()
            validation = NormalizedEPUBValidator.inspect_archive(z)
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
            normalized_sections = sorted(validation["section_files"], key=natural_file_sort_key)
            first_section = extract_number_from_filename(Path(normalized_sections[0]).name) if normalized_sections else 1

            return {
                "suggested_title": title,
                "suggested_author": author,
                "suggested_language": language,
                "suggested_start_node": f"sec_{first_section:03d}",
                "total_sections": len(normalized_sections),
                "is_normalized": validation["is_normalized"],
                "validation_errors": validation["errors"],
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

        NormalizedEPUBValidator.validate(self.epub_path)

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

            image_map = EPUBResourceExtractor.extract_images(z, namelist, images_dir)

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
            content_xhtml_files = [
                f for f in xhtml_files
                if Path(f).name.lower() not in ('cubierta.xhtml', 'titulo.xhtml', 'nav.xhtml')
            ]
            normalized_sections = [
                f for f in content_xhtml_files
                if "/secciones/" in f.lower() and re.search(r"seccion-\d+", Path(f).stem, re.IGNORECASE)
            ]
            valid_xhtml_files = sorted(normalized_sections, key=natural_file_sort_key)
            supplements = build_epub_supplements(
                z, content_xhtml_files, valid_xhtml_files, image_map
            )
            nodes = EPUBStoryParser(
                z, file_to_node_id, node_id_to_num, image_map
            ).parse(valid_xhtml_files)

            if valid_xhtml_files:
                start_node_id = file_to_node_id[valid_xhtml_files[0]]
            elif nodes:
                start_node_id = sorted(nodes.keys())[0]
            else:
                start_node_id = "sec_001"

            cover_image_path = EPUBResourceExtractor.detect_cover(soup_opf, image_map)

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

            book_json_data = BookPublisher().build_document(
                book_id=book_id,
                title=final_title,
                author=final_author,
                language=final_language,
                description=description,
                publisher=publisher,
                year=year,
                isbn=isbn,
                genre=genre,
                series=series,
                volume=volume,
                cover_image=cover_image_path,
                start_node=start_node_id,
                tier_id=tier_id,
                narrator_id=final_narrator_id,
                supplements=supplements,
                nodes=nodes,
            )
            try:
                from src.db import Database
                database = Database()
            except Exception as exc:
                logger.warning("Could not initialize database for '%s': %s", book_id, exc)
                database = None
            book_json_path = BookPublisher(database).publish(output_dir, book_json_data, endings_detected)

            if generate_audios:
                generate_nodes_audio(self.tts_manager, nodes, output_dir, language=final_language, tts_engine=tts_engine, voice_name=voice_name, narrator_id=final_narrator_id)
                generate_supplements_audio(
                    self.tts_manager, supplements, output_dir,
                    language=final_language, tts_engine=tts_engine,
                    voice_name=voice_name, narrator_id=final_narrator_id,
                )

            return book_json_path
