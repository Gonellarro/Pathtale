import json
from pathlib import Path
from typing import Any, Dict, Optional

from config import DATA_DIR


class AudioCatalogError(ValueError):
    pass


class AudioCatalog:
    """Resolves reusable music/FX assets without copying them into books."""

    def __init__(self, catalog_path: Path = DATA_DIR / "audios" / "catalog.json"):
        self.catalog_path = Path(catalog_path)
        self.root = self.catalog_path.parent
        self._data: Optional[Dict[str, Any]] = None

    @property
    def data(self) -> Dict[str, Any]:
        if self._data is None:
            try:
                self._data = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise AudioCatalogError(f"No se pudo cargar el catálogo de audio: {self.catalog_path}") from exc
        return self._data

    def get_asset(self, asset_id: str) -> Dict[str, Any]:
        asset = next((item for item in self.data.get("assets", []) if item.get("asset_id") == asset_id), None)
        if not asset:
            raise AudioCatalogError(f"Asset de audio desconocido: {asset_id}")
        relative = str(asset.get("file", "")).lstrip("/")
        path = (self.root / relative).resolve()
        if not str(path).startswith(str(self.root.resolve())) or not path.is_file():
            raise AudioCatalogError(f"Archivo de audio no encontrado para '{asset_id}'")
        return {**asset, "path": path}

    def public_url(self, asset_id: str) -> str:
        self.get_asset(asset_id)
        return f"/api/audio-assets/{asset_id}"
