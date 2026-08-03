import re
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

import fitz  # PyMuPDF
from config import BOOKS_DIR
from src.db import Database
from src.tts import TTSManager
from src.pdf_gamebook_parser import GamebookPDFParser
from src.importer.tts_pipeline import generate_supplements_audio

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

    def inspect(self) -> Dict[str, Any]:
        """Fast pre-flight analysis of PDF metadata and section structure without audio synthesis or DB seeding."""
        doc = fitz.open(self.pdf_path)
        meta = doc.metadata or {}
        raw_title = meta.get("title") or self.pdf_path.stem.replace('_', ' ').replace('-', ' ').title()
        raw_author = meta.get("author") or "Desconocido"

        sample_pages = []
        for page_num in range(min(15, len(doc))):
            sample_pages.append(doc[page_num].get_text("text"))

        sample_text = " ".join([p[:500] for p in sample_pages]).lower()
        english_indicators = ["turn to", "if you", " the ", " with ", "you are", "of the"]
        spanish_indicators = ["pasa a", "ve a", " el ", " la ", "con el", "eres un"]
        en_score = sum(1 for ind in english_indicators if ind in sample_text)
        es_score = sum(1 for ind in spanish_indicators if ind in sample_text)
        detected_lang = "en" if en_score > es_score else "es"

        parser = GamebookPDFParser(doc)
        sections, _, report = parser.parse()
        suggested_start = sections[0]["id"] if sections else "sec_001"

        return {
            "suggested_title": raw_title,
            "suggested_author": raw_author,
            "suggested_language": detected_lang,
            "suggested_start_node": suggested_start,
            "total_sections": len(sections) or len(doc),
            "supplement_count": len(parser.supplements),
            "supplement_categories": {
                category: sum(1 for item in parser.supplements if item["category"] == category)
                for category in ("front_matter", "reference", "back_matter")
            },
            "validation": report,
        }

    def process(
        self,
        generate_audios: bool = False,
        title: Optional[str] = None,
        author: Optional[str] = None,
        language: Optional[str] = None,
        start_node: Optional[str] = None,
        tts_engine: str = "auto",
        voice_name: Optional[str] = None,
        tier_id: int = 1,
        narrator_id: Optional[int] = None,
    ) -> Path:
        logger.info(f"📖 Starting PDF Gamebook import for: {self.pdf_path.name}")
        doc = fitz.open(self.pdf_path)

        # 1. Extract Metadata
        meta = doc.metadata or {}
        raw_title = title or meta.get("title") or self.pdf_path.stem.replace('_', ' ').replace('-', ' ').title()
        raw_author = author or meta.get("author") or "Desconocido"
        book_id = sanitize_book_id(raw_title)

        # Output directory for the imported book
        book_dir = BOOKS_DIR / book_id
        book_dir.mkdir(parents=True, exist_ok=True)
        audios_dir = book_dir / "audios"
        audios_dir.mkdir(exist_ok=True)

        # 2. Parse layout before flattening text.  This keeps headers, columns
        # and internal PDF links available to the section/choice detector.
        parser = GamebookPDFParser(doc)
        raw_sections, detected_endings, parse_report = parser.parse()
        supplements = parser.supplements
        logger.info(
            "PDF parser found %s sections (%s broken targets, %s orphan nodes).",
            parse_report["detected_sections"], len(parse_report["broken_targets"]),
            len(parse_report["orphan_nodes"]),
        )
        if not raw_sections:
            logger.warning("No section numbers detected in PDF. Creating single default section.")
            raw_sections = [{
                "id": "sec_001",
                "display_number": 1,
                "text": "\n".join(page.get_text("text") for page in doc),
                "choices": []
            }]

        nodes_dict = {}
        for sec in raw_sections:
            sec_id = sec["id"]
            nodes_dict[sec_id] = {
                "id": sec_id,
                "display_number": sec["display_number"],
                "title": f"Sección {sec['display_number']}",
                "text": sec["text"],
                "audio": f"audios/{sec_id}.mp3",
                "choices": sec["choices"]
            }

        # Determine start node
        start_node_id = start_node or (f"sec_{str(raw_sections[0]['display_number']).zfill(3)}" if raw_sections else "sec_001")

        # 4. Extract Images & Cover
        embedded_images = self._extract_images(doc, book_dir)
        for supplement in supplements:
            source_pages = set(supplement.get("source_pages", []))
            supplement["images"] = [
                image["path"] for image in embedded_images if image["page"] in source_pages
            ]
        cover_image = self._extract_or_generate_cover(doc, book_dir)

        final_lang = (language or self.inspect().get("suggested_language") or "es").lower()[:2]
        final_narrator_id = narrator_id or (2 if final_lang == "en" else 1)

        book_json_data = {
            "ir_version": "1.1",
            "book_id": book_id,
            "title": raw_title,
            "author": raw_author,
            "language": final_lang,
            "cover_image": cover_image,
            "total_sections": len(raw_sections),
            "start_node": start_node_id,
            "tier_id": tier_id,
            "narrator_id": final_narrator_id,
            "supplements": supplements,
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
            narrator_info = self.db.get_narrator_by_id(final_narrator_id) if final_narrator_id else None
            narrator_name = narrator_info.get("display_name") if narrator_info else (voice_name or tts_engine)
            logger.info(f"🎙️ Generating TTS audios for '{book_id}' ({final_lang}, narrator='{narrator_name}')...")
            for node_id, node_data in nodes_dict.items():
                out_audio = book_dir / node_data["audio"]
                if not out_audio.exists():
                    try:
                        if narrator_info:
                            self.tts_manager.generate_audio_by_narrator(node_data["text"], out_audio, narrator_info, language=final_lang)
                        else:
                            self.tts_manager.generate_audio(
                                node_data["text"],
                                out_audio,
                                language=final_lang,
                                tts_engine=tts_engine,
                                voice_name=voice_name
                            )
                    except Exception as e:
                        logger.warning(f"Failed audio synthesis for {node_id}: {e}")
            generate_supplements_audio(
                self.tts_manager, supplements, book_dir, language=final_lang,
                tts_engine=tts_engine, voice_name=voice_name,
                narrator_id=final_narrator_id,
            )

        logger.info(f"✅ Successfully imported PDF book '{raw_title}' ({book_id}) with {len(nodes_dict)} sections, {len(embedded_images)} images.")
        return json_path

    def _extract_or_generate_cover(self, doc: fitz.Document, book_dir: Path) -> str:
        """Extract a cover image, falling back to the first embedded image.

        A PDF does not have a standard cover field.  We therefore prefer an
        image on its first page, then the first usable embedded image anywhere
        in the document, and only render page one when the PDF contains none.
        """
        image_xrefs = list(doc[0].get_images(full=True))
        if not image_xrefs:
            image_xrefs = [
                image for page in doc for image in page.get_images(full=True)
            ]

        for image in image_xrefs:
            try:
                extracted = doc.extract_image(image[0])
                image_bytes = extracted.get("image", b"")
                extension = extracted.get("ext", "").lower()
                if len(image_bytes) < 5000 or extension not in {"jpg", "jpeg", "png", "webp"}:
                    continue
                cover_filename = f"cover.{extension}"
                (book_dir / cover_filename).write_bytes(image_bytes)
                return cover_filename
            except Exception as e:
                logger.warning("Could not extract PDF cover image xref %s: %s", image[0], e)

        try:
            cover_filename = "cover.jpg"
            pix = doc[0].get_pixmap(dpi=150)
            pix.save(str(book_dir / cover_filename))
            return cover_filename
        except Exception as e:
            logger.warning(f"Could not render PDF cover image: {e}")
            return ""

    def _extract_images(self, doc: fitz.Document, book_dir: Path) -> List[Dict[str, Any]]:
        """Extracts embedded images from PDF pages and saves them to images/ folder."""
        images_dir = book_dir / "images"
        images_dir.mkdir(exist_ok=True)
        saved_images = []
        img_counter = 1

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            image_list = page.get_images(full=True)
            for img in image_list:
                xref = img[0]
                try:
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    if len(image_bytes) > 5000:  # Skip tiny icons/logos
                        img_name = f"img_{str(img_counter).zfill(3)}.{image_ext}"
                        img_path = images_dir / img_name
                        if not img_path.exists():
                            with open(img_path, "wb") as f:
                                f.write(image_bytes)
                        saved_images.append({
                            "path": f"images/{img_name}",
                            "page": page_idx + 1,
                        })
                        img_counter += 1
                except Exception as e:
                    logger.warning(f"Could not extract image xref {xref}: {e}")

        return saved_images
