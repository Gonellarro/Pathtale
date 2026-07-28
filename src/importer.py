import os
import re
import json
import zipfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup
from config import BOOKS_DIR
from src.tts import TTSManager

logger = logging.getLogger("Importer")

def sanitize_book_id(title: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9]', '_', title.lower())
    cleaned = re.sub(r'_+', '_', cleaned).strip('_')
    return cleaned or "book"

def extract_number_from_filename(filename: str) -> Optional[int]:
    match = re.search(r'epl(\d+)', filename)
    if match:
        return int(match.group(1))
    match_num = re.search(r'(\d+)', filename)
    if match_num:
        return int(match_num.group(1))
    return None

class EPUBImporter:
    def __init__(self, epub_path: Path, tts_manager: Optional[TTSManager] = None):
        self.epub_path = Path(epub_path)
        self.tts_manager = tts_manager or TTSManager()

    def process(self, generate_audios: bool = True) -> Path:
        if not self.epub_path.exists():
            raise FileNotFoundError(f"EPUB file not found: {self.epub_path}")

        logger.info(f"Processing EPUB: {self.epub_path.name}")
        
        with zipfile.ZipFile(self.epub_path, 'r') as z:
            namelist = z.namelist()
            
            # Detect title & author from content.opf if available
            title = self.epub_path.stem
            author = "Unknown"
            opf_file = next((name for name in namelist if name.endswith('.opf')), None)
            if opf_file:
                try:
                    soup_opf = BeautifulSoup(z.read(opf_file).decode('utf-8'), 'html.parser')
                    title_elem = soup_opf.find('dc:title') or soup_opf.find('title')
                    author_elem = soup_opf.find('dc:creator') or soup_opf.find('creator')
                    if title_elem and title_elem.text:
                        title = title_elem.text.strip()
                    if author_elem and author_elem.text:
                        author = author_elem.text.strip()
                except Exception as e:
                    logger.warning(f"Could not parse content.opf: {e}")

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

            # Step 1: Discover all XHTML/HTML files and map filenames to section IDs
            xhtml_files = [n for n in namelist if n.endswith(('.xhtml', '.html'))]
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
            start_node_id = "sec_002" # Default CYOA start page if page 2 exists

            for fname in xhtml_files:
                base_name = Path(fname).name
                node_id = file_to_node_id[fname]
                content = z.read(fname).decode('utf-8', errors='ignore')
                soup = BeautifulSoup(content, 'html.parser')

                # Skip meta pages like info, cubierta, titulo, notas unless they have story content
                if base_name in ('cubierta.xhtml', 'info.xhtml', 'sinopsis.xhtml', 'titulo.xhtml'):
                    continue

                h1 = soup.find('h1')
                display_num = node_id_to_num.get(node_id)
                heading_title = h1.get_text().strip() if h1 else (f"Página {display_num}" if display_num else base_name)

                # Collect paragraph texts
                paragraphs = []
                for p in soup.find_all('p'):
                    # Skip cover image paragraph or note links
                    if p.get('class') and 'cubierta' in p.get('class'):
                        continue
                    text_p = p.get_text().strip()
                    if text_p:
                        paragraphs.append(text_p)

                full_text = "\n\n".join(paragraphs)

                # Collect images
                node_images = []
                for img in soup.find_all('img'):
                    src = img.get('src', '')
                    img_name = Path(src).name
                    if img_name in image_map:
                        node_images.append(image_map[img_name])

                # Collect choices
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

                # If no h1 digit but file is epl02, set start_node
                if node_id == "sec_002" or (display_num == 2 and start_node_id == "sec_002"):
                    start_node_id = node_id

                audio_rel_path = f"audios/{node_id}.mp3"
                node_data = {
                    "id": node_id,
                    "display_number": display_num,
                    "title": heading_title,
                    "text": full_text,
                    "images": node_images,
                    "audio": audio_rel_path,
                    "choices": choices
                }
                nodes[node_id] = node_data

            # Sort nodes by ID or display number
            if "sec_002" in nodes:
                start_node_id = "sec_002"
            elif nodes:
                start_node_id = min(nodes.keys())

            book_json_data = {
                "book_id": book_id,
                "title": title,
                "author": author,
                "cover_image": image_map.get("01.jpg") or image_map.get("00.jpg") or (list(image_map.values())[0] if image_map else None),
                "start_node": start_node_id,
                "nodes": nodes
            }

            book_json_path = output_dir / "book.json"
            with open(book_json_path, 'w', encoding='utf-8') as f:
                json.dump(book_json_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Imported {len(nodes)} nodes to {book_json_path}")

            # Generate audios with TTS if requested
            if generate_audios:
                logger.info(f"Generating TTS audio for {len(nodes)} nodes...")
                for n_id, n_data in nodes.items():
                    audio_path = output_dir / n_data["audio"]
                    if not audio_path.exists():
                        # Read text for TTS
                        tts_text = f"{n_data['title']}.\n\n{n_data['text']}"
                        self.tts_manager.generate_audio(tts_text, audio_path)

            return book_json_path
