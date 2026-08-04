from html import escape
from pathlib import Path

from bs4 import BeautifulSoup


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


def build_epub_supplements(archive, ordered_files, story_files, image_map):
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
        soup = BeautifulSoup(archive.read(filename).decode("utf-8", errors="ignore"), "html.parser")
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

        title_lower = title.lower()
        if base_name in ("preliminares.xhtml", "preliminares.html") or any(term in title_lower for term in FRONT_MATTER_TERMS):
            category = "front_matter"
        elif base_name in ("finales.xhtml", "finales.html"):
            category = "back_matter"
        elif any(term in title_lower for term in REFERENCE_TERMS):
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
