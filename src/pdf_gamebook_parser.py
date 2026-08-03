"""Layout-aware, deterministic parser for digital gamebook PDFs.

The parser deliberately produces the same node/choice shape consumed by
``PDFImporter``.  It keeps PDF geometry until sections are identified, which
is essential to distinguish a section heading from a page number or an item
reference.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import median
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import fitz


_SECTION_RE = re.compile(
    r"^\s*(?:(?:secci[oó]n|section|§)\s*)?(\d{1,4})(?:\s*[.:-]\s*.*)?$",
    re.IGNORECASE,
)
_CHOICE_RE = re.compile(
    r"(?P<label>[^.!?]{0,240}?(?:turn\s+to|go\s+to|proceed\s+to|continue\s+at|"
    r"pasa\s+a(?:l)?|ve\s+a(?:l)?|dir[ií]gete\s+a(?:l)?|acude\s+a(?:l)?|"
    r"salta\s+a(?:l)?)\s+(?:(?:la|el)\s+)?(?:p[aá]gina|secci[oó]n|"
    r"section|paragraph|n[uú]mero)?\s*(?P<number>\d{1,4})\b)",
    re.IGNORECASE,
)
_NON_NARRATIVE_BOUNDARY_RE = re.compile(
    r"^(?:ap[ée]ndices?|appendix|glossary|action chart|combat record|"
    r"special items|tabla de la suerte|reglas de combate)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PDFLine:
    page: int
    order: int
    text: str
    bbox: Tuple[float, float, float, float]
    size: float
    font: str
    bold: bool


@dataclass(frozen=True)
class SectionHeading:
    number: int
    line_index: int
    page: int
    bbox: Tuple[float, float, float, float]


class GamebookPDFParser:
    """Extract sections and choices from a text-based, digitally generated PDF."""

    def __init__(self, document: fitz.Document):
        self.document = document
        self._lines: List[PDFLine] = []
        self._headings: List[SectionHeading] = []
        self._all_headings: List[SectionHeading] = []
        self.supplements: List[Dict[str, Any]] = []

    def parse(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        self._lines = self._extract_ordered_lines()
        self._lines = self._remove_repeated_marginal_text(self._lines)
        self._all_headings = self._find_headings(self._lines)
        self._headings = self._select_adventure_headings(self._all_headings)
        sections = self._build_sections()
        self._add_link_choices(sections)
        self.supplements = self._build_supplements()
        endings = self._find_endings(sections)
        known_nodes = {section["id"] for section in sections}
        broken_targets = sorted({
            choice["target_node"]
            for section in sections
            for choice in section["choices"]
            if choice["target_node"] not in known_nodes
        })
        report = {
            "detected_sections": len(sections),
            "broken_targets": broken_targets,
            "orphan_nodes": self._find_orphans(sections),
        }
        return sections, endings, report

    def _build_supplements(self) -> List[Dict[str, Any]]:
        if not self._headings:
            return self._supplement_blocks(self._lines, "front_matter", "Antes de empezar")

        first_heading = self._headings[0]
        last_heading = self._headings[-1]
        front_lines = self._lines[:first_heading.line_index]
        back_start = self._find_non_narrative_boundary(last_heading.line_index)
        back_lines = self._lines[back_start:]
        supplements = self._supplement_blocks(front_lines, "front_matter", "Antes de empezar")
        supplements.extend(self._supplement_blocks(back_lines, "back_matter", "Material adicional"))

        counters: Counter[str] = Counter()
        for order, item in enumerate(supplements, 1):
            counters[item["category"]] += 1
            prefix = {
                "front_matter": "front",
                "reference": "reference",
                "back_matter": "back",
            }[item["category"]]
            item["id"] = f"{prefix}_{counters[item['category']]:03d}"
            item["order"] = order
            item["audio"] = f"audios/supplements/{item['id']}.mp3"
        return supplements

    def _supplement_blocks(
        self,
        lines: List[PDFLine],
        default_category: str,
        default_title: str,
    ) -> List[Dict[str, Any]]:
        if not lines:
            return []
        body_size = self._body_size(lines)
        blocks: List[Dict[str, Any]] = []
        title = default_title
        content: List[PDFLine] = []

        def flush() -> None:
            nonlocal content
            text_lines = [line for line in content if not line.text.strip().isdigit()]
            text = self._reconstruct_text(text_lines).strip()
            if len(text) < 40:
                content = []
                return
            category = self._supplement_category(title, default_category)
            pages = sorted({line.page + 1 for line in text_lines})
            blocks.append({
                "category": category,
                "title": title,
                "text": text,
                "images": [],
                "source_pages": pages,
            })
            content = []

        for line in lines:
            cleaned = re.sub(r"\s+", " ", line.text).strip()
            is_heading = (
                3 < len(cleaned) <= 100
                and not cleaned.isdigit()
                and (line.bold or line.size >= body_size * 1.18)
                and (cleaned.isupper() or line.size >= body_size * 1.3)
            )
            if is_heading:
                flush()
                title = cleaned.title() if cleaned.isupper() else cleaned
            else:
                content.append(line)
        flush()
        return blocks

    @staticmethod
    def _supplement_category(title: str, default_category: str) -> str:
        normalized = title.lower()
        reference_terms = (
            "regla", "cómo jugar", "como jugar", "how to play", "glosario", "glossary",
            "tabla", "chart", "ficha", "character sheet", "combate", "combat",
            "disciplina", "equipment", "equipo", "magia", "magic",
        )
        return "reference" if any(term in normalized for term in reference_terms) else default_category

    def _extract_ordered_lines(self) -> List[PDFLine]:
        all_lines: List[PDFLine] = []
        order = 0
        for page_number, page in enumerate(self.document):
            page_lines: List[PDFLine] = []
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    spans = line.get("spans", [])
                    text = "".join(span.get("text", "") for span in spans).strip()
                    if not text or not spans:
                        continue
                    font = " ".join(span.get("font", "") for span in spans)
                    page_lines.append(PDFLine(
                        page=page_number,
                        order=0,
                        text=text,
                        bbox=tuple(line["bbox"]),
                        size=max(float(span.get("size", 0)) for span in spans),
                        font=font,
                        bold=("bold" in font.lower() or "demi" in font.lower()),
                    ))

            for line in self._reading_order(page_lines, page.rect.width):
                all_lines.append(PDFLine(
                    page=line.page, order=order, text=line.text, bbox=line.bbox,
                    size=line.size, font=line.font, bold=line.bold,
                ))
                order += 1
        return all_lines

    @staticmethod
    def _reading_order(lines: List[PDFLine], page_width: float) -> List[PDFLine]:
        """Read a two-column page down the left column, then down the right."""
        long_lines = [line for line in lines if len(line.text) >= 2]
        split_left = [line for line in long_lines if line.bbox[0] < page_width * .45]
        split_right = [line for line in long_lines if line.bbox[0] > page_width * .55]
        if len(split_left) >= 3 and len(split_right) >= 3:
            midpoint = page_width / 2
            left = sorted((line for line in lines if line.bbox[0] < midpoint), key=lambda line: line.bbox[1])
            right = sorted((line for line in lines if line.bbox[0] >= midpoint), key=lambda line: line.bbox[1])
            return left + right
        return sorted(lines, key=lambda line: (line.bbox[1], line.bbox[0]))

    def _remove_repeated_marginal_text(self, lines: List[PDFLine]) -> List[PDFLine]:
        occurrences: Counter[str] = Counter()
        page_heights = {number: page.rect.height for number, page in enumerate(self.document)}
        for line in lines:
            height = page_heights[line.page]
            in_margin = line.bbox[1] < height * .09 or line.bbox[3] > height * .91
            normalized = re.sub(r"\s+", " ", line.text).strip().lower()
            if in_margin and len(normalized) > 3 and not normalized.isdigit():
                occurrences[normalized] += 1
        repeated = {text for text, count in occurrences.items() if count >= 3}
        return [
            line for line in lines
            if re.sub(r"\s+", " ", line.text).strip().lower() not in repeated
        ]

    @staticmethod
    def _body_size(lines: Iterable[PDFLine]) -> float:
        sizes = [line.size for line in lines if len(line.text) > 12 and line.size > 0]
        return median(sizes) if sizes else 12.0

    def _find_headings(self, lines: List[PDFLine]) -> List[SectionHeading]:
        body_size = self._body_size(lines)
        headings: List[SectionHeading] = []
        for index, line in enumerate(lines):
            match = _SECTION_RE.match(line.text)
            if not match:
                continue
            number = int(match.group(1))
            if not 0 < number <= 2000:
                continue
            page_height = self.document[line.page].rect.height
            margin_number = line.bbox[1] < page_height * .08 or line.bbox[3] > page_height * .92
            styled_heading = line.bold or line.size >= body_size * 1.12
            # A plain number in a margin is a page number.  A bold heading at
            # the top is legitimate (as in Bloodsword), hence the style check.
            if not styled_heading or (margin_number and not line.bold):
                continue
            headings.append(SectionHeading(number, index, line.page, line.bbox))
        return headings

    @staticmethod
    def _select_adventure_headings(headings: List[SectionHeading]) -> List[SectionHeading]:
        """Keep the first printed 1..N sequence, ignoring contents and appendices.

        Gamebooks normally print their numbered sections in ascending order,
        whereas a contents page or a cross-reference appendix repeats those
        same numbers.  A ``1`` followed soon by ``2`` and ``3`` is a reliable,
        layout-independent start marker in the three representative books.
        """
        start = next((
            index for index, heading in enumerate(headings)
            if heading.number == 1
            and {2, 3}.issubset({candidate.number for candidate in headings[index + 1:index + 16]})
        ), None)
        if start is None:
            return headings
        seed = headings[start:start + 16]
        anchors = [heading.bbox[0] for heading in seed if heading.number in {1, 2, 3}]
        selected: List[SectionHeading] = []
        seen_numbers = set()
        for heading in headings[start:]:
            # The initial 1, 2 and 3 establish one or two column positions.
            # A reference number in the outer margin is then excluded without
            # rejecting a legitimate left-column heading.
            if anchors:
                tolerance = max(42.0, max(anchors) * .22)
                if min(abs(heading.bbox[0] - anchor) for anchor in anchors) > tolerance:
                    continue
            if selected and heading.number <= selected[-1].number:
                continue
            if heading.number in seen_numbers:
                continue
            seen_numbers.add(heading.number)
            selected.append(heading)
        return selected

    def _build_sections(self) -> List[Dict[str, Any]]:
        if not self._headings:
            return []
        sections: List[Dict[str, Any]] = []
        for position, heading in enumerate(self._headings):
            if position + 1 < len(self._headings):
                end = self._headings[position + 1].line_index
            else:
                next_heading = next(
                    (candidate.line_index for candidate in self._all_headings if candidate.line_index > heading.line_index),
                    len(self._lines),
                )
                end = min(next_heading, self._find_non_narrative_boundary(heading.line_index))
            text = self._reconstruct_text(self._lines[heading.line_index + 1:end])
            if not text:
                continue
            node_id = f"sec_{heading.number:03d}"
            sections.append({
                "id": node_id,
                "display_number": heading.number,
                "text": text,
                "choices": self._text_choices(text),
                "_heading": heading,
            })
        return sections

    def _find_non_narrative_boundary(self, start: int) -> int:
        """Avoid appending character sheets, glossaries and appendices to the last node."""
        for index, line in enumerate(self._lines[start + 1:], start + 1):
            if _NON_NARRATIVE_BOUNDARY_RE.match(line.text.strip()):
                return index
        return len(self._lines)

    @staticmethod
    def _reconstruct_text(lines: List[PDFLine]) -> str:
        paragraphs: List[str] = []
        for line in lines:
            text = re.sub(r"\s+", " ", line.text).strip()
            if not text:
                continue
            if paragraphs and paragraphs[-1].endswith("-") and text[:1].islower():
                paragraphs[-1] = paragraphs[-1][:-1] + text
            else:
                paragraphs.append(text)
        return "\n".join(paragraphs)

    @staticmethod
    def _text_choices(text: str) -> List[Dict[str, Any]]:
        choices: List[Dict[str, Any]] = []
        seen_targets = set()
        for match in _CHOICE_RE.finditer(text):
            number = int(match.group("number"))
            node_id = f"sec_{number:03d}"
            if node_id in seen_targets:
                continue
            seen_targets.add(node_id)
            choices.append({
                "choice_id": len(choices) + 1,
                "text": match.group("label").strip(),
                "target_node": node_id,
                "target_display_number": number,
            })
        return choices

    def _add_link_choices(self, sections: List[Dict[str, Any]]) -> None:
        if not sections:
            return
        headings_by_page: Dict[int, List[SectionHeading]] = {}
        for heading in self._headings:
            headings_by_page.setdefault(heading.page, []).append(heading)

        for page_number, page in enumerate(self.document):
            for link in page.get_links():
                if link.get("kind") not in (fitz.LINK_GOTO, fitz.LINK_NAMED):
                    continue
                target_page = link.get("page")
                named_number = re.search(r"(\d{1,4})", link.get("nameddest", ""))
                if named_number:
                    exact_number = int(named_number.group(1))
                    target = next((heading for heading in self._headings if heading.number == exact_number), None)
                    if target is None:
                        continue
                else:
                    if target_page is None or target_page not in headings_by_page:
                        continue
                    target_y = (link.get("to") or fitz.Point(0, 0)).y
                    target = min(headings_by_page[target_page], key=lambda h: abs(h.bbox[1] - target_y))
                source = self._section_for_link(sections, page_number, link["from"].y0)
                if source is None:
                    continue
                target_node = f"sec_{target.number:03d}"
                if any(choice["target_node"] == target_node for choice in source["choices"]):
                    continue
                source["choices"].append({
                    "choice_id": len(source["choices"]) + 1,
                    "text": "Ir a la sección " + str(target.number),
                    "target_node": target_node,
                    "target_display_number": target.number,
                })

        for section in sections:
            section.pop("_heading", None)

    @staticmethod
    def _section_for_link(sections: List[Dict[str, Any]], page: int, y: float) -> Optional[Dict[str, Any]]:
        candidates = [section for section in sections if section["_heading"].page < page or (
            section["_heading"].page == page and section["_heading"].bbox[1] <= y
        )]
        return candidates[-1] if candidates else None

    @staticmethod
    def _find_endings(sections: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "node_id": section["id"],
                "label": f"Final de la aventura (Sección {section['display_number']})",
                "is_good_ending": None,
            }
            for section in sections if not section["choices"]
        ]

    @staticmethod
    def _find_orphans(sections: List[Dict[str, Any]]) -> List[str]:
        if not sections:
            return []
        start = sections[0]["id"]
        graph = {section["id"]: {choice["target_node"] for choice in section["choices"]} for section in sections}
        reachable, pending = set(), [start]
        while pending:
            node = pending.pop()
            if node in reachable or node not in graph:
                continue
            reachable.add(node)
            pending.extend(graph[node] - reachable)
        return sorted(set(graph) - reachable)
