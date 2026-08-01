import re
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger("Importer.Parser")

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

def natural_file_sort_key(fname: str):
    base = Path(fname).name.lower()
    if base in ('cubierta.xhtml', 'titulo.xhtml', 'info.xhtml', 'sinopsis.xhtml'):
        return (-2, 0, base)
    if 'dedicatoria' in base or 'aten' in base or 'portada' in base:
        return (-1, 0, base)
    nums = re.findall(r'\d+', base)
    if nums:
        return (0, int(nums[0]), base)
    return (1, 0, base)

def parse_opf_metadata(z_file, opf_filename: str) -> Dict[str, Any]:
    meta = {
        "title": None,
        "author": None,
        "publisher": None,
        "year": None,
        "language": "es",
        "description": None,
        "isbn": None,
        "genre": None,
        "series": None,
        "volume": None,
        "soup_opf": None
    }
    try:
        soup_opf = BeautifulSoup(z_file.read(opf_filename).decode('utf-8', errors='ignore'), 'html.parser')
        meta["soup_opf"] = soup_opf
        
        t_elem = soup_opf.find(['dc:title', 'title'])
        if t_elem and t_elem.text.strip():
            meta["title"] = t_elem.text.strip()

        a_elem = soup_opf.find(['dc:creator', 'creator'])
        if a_elem and a_elem.text.strip():
            meta["author"] = a_elem.text.strip()

        p_elem = soup_opf.find(['dc:publisher', 'publisher'])
        if p_elem and p_elem.text.strip():
            meta["publisher"] = p_elem.text.strip()

        d_elem = soup_opf.find(['dc:date', 'date'])
        if d_elem and d_elem.text.strip():
            year_match = re.search(r'\d{4}', d_elem.text.strip())
            if year_match:
                meta["year"] = year_match.group(0)

        l_elem = soup_opf.find(['dc:language', 'language'])
        if l_elem and l_elem.text.strip():
            meta["language"] = l_elem.text.strip()

        desc_elem = soup_opf.find(['dc:description', 'description'])
        if desc_elem and desc_elem.text.strip():
            meta["description"] = desc_elem.text.strip()

        id_elem = soup_opf.find(['dc:identifier', 'identifier'])
        if id_elem and id_elem.text.strip():
            meta["isbn"] = id_elem.text.strip()

        subj_elem = soup_opf.find(['dc:subject', 'subject'])
        if subj_elem and subj_elem.text.strip():
            meta["genre"] = subj_elem.text.strip()

        s_meta = soup_opf.find('meta', attrs={'name': 'calibre:series'}) or soup_opf.find('meta', attrs={'property': 'belongs-to-collection'})
        if s_meta and (s_meta.get('content') or s_meta.text.strip()):
            meta["series"] = (s_meta.get('content') or s_meta.text.strip()).strip()

        v_meta = soup_opf.find('meta', attrs={'name': 'calibre:series_index'}) or soup_opf.find('meta', attrs={'property': 'group-position'})
        if v_meta and (v_meta.get('content') or v_meta.text.strip()):
            try:
                meta["volume"] = int(float((v_meta.get('content') or v_meta.text.strip()).strip()))
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Could not parse content.opf metadata: {e}")

    return meta
