import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import fitz  # PyMuPDF
from config import BOOKS_DIR
from src.db import Database
from src.tts import TTSManager

logger = logging.getLogger("PDFImporter")

def sanitize_book_id(text: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9_]', '_', text.lower())
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned or "pdf_gamebook"

class PDFImporter:
    """
    Imports Gamebook PDFs into PathTale's Intermediate Representation (IR JSON)
    and seeds the database and TTS audio files.
    """
    def __init__(self, pdf_path: Path, tts_manager: Optional[TTSManager] = None):
        self.pdf_path = Path(pdf_path)
        self.tts_manager = tts_manager or TTSManager()
        self.db = Database()

    def process(self, generate_audios: bool = False) -> Path:
        logger.info(f"📖 Starting PDF Gamebook import for: {self.pdf_path.name}")
        doc = fitz.open(self.pdf_path)

        # 1. Extract Metadata
        meta = doc.metadata or {}
        raw_title = meta.get("title") or self.pdf_path.stem.replace('_', ' ').replace('-', ' ').title()
        raw_author = meta.get("author") or "Desconocido"
        book_id = sanitize_book_id(raw_title)

        # Output directory for the imported book
        book_dir = BOOKS_DIR / book_id
        book_dir.mkdir(parents=True, exist_ok=True)
        audios_dir = book_dir / "audios"
        audios_dir.mkdir(exist_ok=True)

        # 2. Extract Document Pages & Text Blocks with font metrics
        pages_data = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text_instances = []
            blocks = page.get_text("dict")["blocks"]
            for b in blocks:
                if b.get("type") == 0:  # text block
                    for line in b["lines"]:
                        for span in line["spans"]:
                            text_instances.append({
                                "text": span["text"],
                                "size": span["size"],
                                "font": span["font"],
                                "flags": span["flags"],
                                "bbox": span["bbox"]
                            })
            
            # Extract PDF link annotations
            links = []
            for link in page.get_links():
                if link.get("kind") == fitz.LINK_GOTO:
                    links.append({
                        "from_rect": link.get("from"),
                        "page_target": link.get("page")
                    })

            pages_data.append({
                "page_num": page_num + 1,
                "text_instances": text_instances,
                "full_text": page.get_text("text"),
                "links": links
            })

        # 3. Detect Section Nodes (Heuristic Header Search)
        raw_sections, detected_endings = self._extract_sections_and_endings(pages_data)

        # 4. Resolve Choices & Nodes
        nodes_dict = {}
        for sec in raw_sections:
            node_id = sec["id"]
            nodes_dict[node_id] = {
                "id": node_id,
                "display_number": sec["display_number"],
                "title": f"Sección {sec['display_number']}",
                "text": sec["text"].strip(),
                "audio": f"audios/{node_id}.mp3",
                "choices": sec["choices"]
            }

        start_node_id = f"sec_{str(raw_sections[0]['display_number']).zfill(3)}" if raw_sections else "sec_001"
        cover_image = self._extract_or_generate_cover(doc, book_dir)

        book_json_data = {
            "book_id": book_id,
            "title": raw_title,
            "author": raw_author,
            "language": "en" if "turn to" in doc[0].get_text().lower() else "es",
            "description": f"Librojuego importado en PDF ({len(raw_sections)} secciones).",
            "genre": "Aventura",
            "series": "PDF Gamebooks",
            "volume": 1,
            "estimated_duration": f"{max(15, len(raw_sections) * 2)} min",
            "cover_image": cover_image,
            "total_sections": len(raw_sections),
            "start_node": start_node_id,
            "nodes": nodes_dict
        }

        # Save book.json
        json_path = book_dir / "book.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(book_json_data, f, ensure_ascii=False, indent=2)

        # Seed in SQLite database
        self.db.upsert_book(book_json_data)
        self.db.register_book_endings(book_id, detected_endings)

        # 5. Generate TTS Audios if requested
        if generate_audios:
            logger.info(f"🎙️ Generating Piper TTS audios for '{book_id}'...")
            for node_id, node_data in nodes_dict.items():
                out_audio = book_dir / node_data["audio"]
                if not out_audio.exists():
                    try:
                        self.tts_manager.text_to_speech(node_data["text"], out_audio)
                    except Exception as e:
                        logger.warning(f"Failed audio synthesis for {node_id}: {e}")

        logger.info(f"✅ Successfully imported PDF book '{raw_title}' ({book_id}) with {len(nodes_dict)} sections.")
        return json_path

    def _extract_sections_and_endings(self, pages_data: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Parses sequential section headers and extracts narrative text and choices.
        """
        full_document_text = "\n".join([p["full_text"] for p in pages_data])
        lines = [line.strip() for line in full_document_text.splitlines() if line.strip()]

        # Pattern for standalone section headers (e.g. "1", "117", "570")
        header_regex = re.compile(r"^\s*(\d{1,4})\s*$")

        sections = []
        current_num = None
        current_lines = []

        for line in lines:
            match = header_regex.match(line)
            if match:
                num = int(match.group(1))
                # Validate reasonable section progression (e.g. not page numbers or stat numbers)
                if num > 0 and num <= 2000:
                    if current_num is not None:
                        sections.append(self._build_section_object(current_num, current_lines))
                    current_num = num
                    current_lines = []
                    continue

            if current_num is not None:
                current_lines.append(line)

        if current_num is not None:
            sections.append(self._build_section_object(current_num, current_lines))

        # Detect terminal ending nodes and choices (deduplicated)
        endings = []
        seen_ending_nodes = set()
        for sec in sections:
            if len(sec["choices"]) == 0 and sec["id"] not in seen_ending_nodes:
                seen_ending_nodes.add(sec["id"])
                endings.append({
                    "node_id": sec["id"],
                    "label": f"Final de la aventura (Sección {sec['display_number']})",
                    "is_good_ending": None
                })

        return sections, endings

    def _build_section_object(self, sec_num: int, lines: List[str]) -> Dict[str, Any]:
        node_id = f"sec_{str(sec_num).zfill(3)}"
        full_text = "\n".join(lines)

        # Choice patterns (English & Spanish)
        choice_patterns = [
            # English: "turn to 232" or "If you fight, turn to 45"
            re.compile(r"([^.\n]*?\bturn\s+to\s+(\d+)\.?)", re.IGNORECASE),
            # Spanish: "pasa a la página 40" or "ve a la sección 12"
            re.compile(r"([^.\n]*?\b(?:pasa|ve|dirígete)\s+a\s+(?:la\s+)?(?:página|sección|número)?\s*(\d+)\.?)", re.IGNORECASE)
        ]

        choices = []
        choice_id = 1
        seen_targets = set()

        for line in lines:
            for pattern in choice_patterns:
                for match in pattern.finditer(line):
                    choice_sentence = match.group(1).strip()
                    target_num = int(match.group(2))
                    target_node = f"sec_{str(target_num).zfill(3)}"

                    if target_node not in seen_targets:
                        seen_targets.add(target_node)
                        choices.append({
                            "choice_id": choice_id,
                            "text": choice_sentence,
                            "target_node": target_node
                        })
                        choice_id += 1

        return {
            "id": node_id,
            "display_number": sec_num,
            "text": full_text,
            "choices": choices
        }

    def _extract_or_generate_cover(self, doc: fitz.Document, book_dir: Path) -> str:
        """Extracts the first image from PDF or renders the first page as a cover JPEG."""
        cover_filename = "cover.jpg"
        cover_path = book_dir / cover_filename

        try:
            # Try rendering page 1 as high-res cover image
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            pix.save(str(cover_path))
            return f"/assets/books/{book_dir.name}/{cover_filename}"
        except Exception as e:
            logger.warning(f"Could not render PDF cover image: {e}")
            return "/assets/cover_placeholder.jpg"
