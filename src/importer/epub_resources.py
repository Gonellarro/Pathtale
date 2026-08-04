import shutil
from pathlib import Path
from typing import Dict, Iterable, Optional


IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")


class EPUBResourceExtractor:
    """Extracts image resources and resolves the book cover from an EPUB."""

    @staticmethod
    def extract_images(archive, names: Iterable[str], images_dir: Path) -> Dict[str, str]:
        images_dir.mkdir(parents=True, exist_ok=True)
        image_map: Dict[str, str] = {}
        for name in names:
            if not name.lower().endswith(IMAGE_EXTENSIONS):
                continue
            image_filename = Path(name).name
            target_path = images_dir / image_filename
            with archive.open(name) as source, open(target_path, "wb") as target:
                shutil.copyfileobj(source, target)
            relative_path = f"images/{image_filename}"
            image_map[image_filename] = relative_path
            image_map[name] = relative_path
        return image_map

    @staticmethod
    def detect_cover(soup_opf, image_map: Dict[str, str]) -> Optional[str]:
        if soup_opf:
            try:
                meta_cover = soup_opf.find("meta", attrs={"name": "cover"})
                if meta_cover and meta_cover.get("content"):
                    item = soup_opf.find("item", attrs={"id": meta_cover["content"]})
                    if item and item.get("href"):
                        cover = image_map.get(Path(item["href"]).name)
                        if cover:
                            return cover

                item_prop = soup_opf.find("item", attrs={"properties": "cover-image"})
                if item_prop and item_prop.get("href"):
                    cover = image_map.get(Path(item_prop["href"]).name)
                    if cover:
                        return cover
            except Exception:
                # Metadata is optional in EPUB; filename/fallback detection below
                # still provides a usable cover.
                pass

        for keyword in ("cover", "cubierta", "portada", "front"):
            for filename, relative_path in image_map.items():
                if keyword in Path(filename).name.lower():
                    return relative_path

        return image_map.get("01.jpg") or image_map.get("00.jpg") or next(iter(image_map.values()), None)
