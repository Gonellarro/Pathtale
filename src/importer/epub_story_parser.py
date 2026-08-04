from html import escape
from pathlib import Path
from typing import Any, Dict, Iterable

from bs4 import BeautifulSoup


RICH_INLINE_TAGS = {"strong", "b", "em", "i", "u", "mark", "sub", "sup", "small"}


def _local_name(element) -> str:
    return (getattr(element, "name", "") or "").rsplit(":", 1)[-1].lower()


def _find_all_local(soup, names):
    names = {name.lower() for name in names}
    return [element for element in soup.find_all(True) if _local_name(element) in names]


def _serialize_rich_text(element) -> str:
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


class EPUBStoryParser:
    """Converts normalized section XHTML files into PathTale nodes."""

    def __init__(self, archive, file_to_node_id: Dict[str, str], node_id_to_num: Dict[str, int], image_map: Dict[str, str]):
        self.archive = archive
        self.file_to_node_id = file_to_node_id
        self.node_id_to_num = node_id_to_num
        self.image_map = image_map

    def parse(self, section_files: Iterable[str]) -> Dict[str, Dict[str, Any]]:
        nodes: Dict[str, Dict[str, Any]] = {}
        for filename in section_files:
            base_name = Path(filename).name
            node_id = self.file_to_node_id[filename]
            soup = BeautifulSoup(self.archive.read(filename).decode("utf-8", errors="ignore"), "html.parser")

            heading = next(iter(_find_all_local(soup, ["h1", "h2", "h3"])), None)
            display_number = self.node_id_to_num.get(node_id)
            title = heading.get_text().strip() if heading else (
                f"Página {display_number}" if display_number else base_name
            )

            paragraphs = []
            rich_paragraphs = []
            for paragraph in _find_all_local(soup, ["p"]):
                if paragraph.get("class") and "cubierta" in paragraph.get("class"):
                    continue
                text = paragraph.get_text().strip()
                if text:
                    paragraphs.append(text)
                    rich_paragraphs.append(f"<p>{_serialize_rich_text(paragraph)}</p>")

            images = []
            for image in _find_all_local(soup, ["img"]):
                image_name = Path(image.get("src", "")).name
                if image_name in self.image_map:
                    images.append(self.image_map[image_name])

            choices = []
            for choice_index, link in enumerate(_find_all_local(soup, ["a"]), 1):
                href = link.get("href", "")
                if not href or href.startswith("#") or "notas" in href:
                    continue
                target_file = Path(href).name.split("#")[0]
                target_node_id = self.file_to_node_id.get(target_file) or self.file_to_node_id.get(href)
                if not target_node_id or target_node_id == node_id:
                    continue
                choices.append({
                    "choice_id": len(choices) + 1,
                    "text": link.get_text().strip(),
                    "target_node": target_node_id,
                    "target_display_number": self.node_id_to_num.get(target_node_id),
                })

            nodes[node_id] = {
                "id": node_id,
                "display_number": display_number,
                "title": title,
                "text": "\n\n".join(paragraphs),
                "text_html": "\n".join(rich_paragraphs),
                "images": images,
                "audio": f"audios/{node_id}.mp3",
                "audio_options": f"audios/{node_id}_options.mp3" if choices else None,
                "choices": choices,
            }
        return nodes
