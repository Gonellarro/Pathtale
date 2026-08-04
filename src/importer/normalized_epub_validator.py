from pathlib import Path
import re
import zipfile
from typing import Any, Dict, List


SECTION_PATH_RE = re.compile(r"(?:^|/)secciones/seccion-(\d+)\.(?:xhtml|html)$", re.IGNORECASE)


class NormalizedEPUBValidator:
    """Validates the stable EPUB contract produced by the normalizer."""

    @classmethod
    def inspect(cls, epub_path: Path) -> Dict[str, Any]:
        try:
            with zipfile.ZipFile(epub_path, "r") as archive:
                return cls.inspect_archive(archive)
        except (OSError, zipfile.BadZipFile) as exc:
            return {
                "is_normalized": False,
                "errors": [f"El fichero no es un EPUB ZIP válido: {exc}"],
                "section_files": [],
                "section_numbers": [],
            }

    @classmethod
    def inspect_archive(cls, archive: zipfile.ZipFile) -> Dict[str, Any]:
        names = archive.namelist()
        errors: List[str] = []

        opf_files = [name for name in names if name.lower().endswith(".opf")]
        if not opf_files:
            errors.append("Falta el archivo OPF del EPUB.")

        section_matches = []
        for name in names:
            match = SECTION_PATH_RE.search(name)
            if match:
                section_matches.append((name, int(match.group(1))))

        section_matches.sort(key=lambda item: item[1])
        if not section_matches:
            errors.append("Faltan archivos secciones/seccion-N.xhtml.")

        numbers = [number for _, number in section_matches]
        duplicates = sorted({number for number in numbers if numbers.count(number) > 1})
        if duplicates:
            errors.append("Hay números de sección duplicados: " + ", ".join(map(str, duplicates)) + ".")

        return {
            "is_normalized": not errors,
            "errors": errors,
            "section_files": [name for name, _ in section_matches],
            "section_numbers": numbers,
            "opf_file": opf_files[0] if opf_files else None,
        }

    @classmethod
    def validate(cls, epub_path: Path) -> Dict[str, Any]:
        report = cls.inspect(epub_path)
        if not report["is_normalized"]:
            raise ValueError(
                "El EPUB no cumple el formato normalizado requerido por PathTale: "
                + " ".join(report["errors"])
            )
        return report
