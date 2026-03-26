from __future__ import annotations

"""Local lightweight cache metadata keyed by source file path + mtime + size."""

import hashlib
import json
from pathlib import Path
from typing import Any


class CacheService:
    def __init__(self, root: Path | None = None):
        self.root = root or Path("C:/db/cache_fast")
        self.root.mkdir(parents=True, exist_ok=True)
        self.manifest_path = self.root / "manifest.json"
        if not self.manifest_path.exists():
            self.manifest_path.write_text("{}", encoding="utf-8")

    def _load_manifest(self) -> dict[str, Any]:
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _save_manifest(self, data: dict[str, Any]) -> None:
        self.manifest_path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str), encoding="utf-8")

    def _key(self, source_path: Path) -> str:
        st = source_path.stat()
        token = f"{source_path.resolve()}|{st.st_size}|{int(st.st_mtime)}"
        return hashlib.sha1(token.encode("utf-8")).hexdigest()

    def get_cached_json(self, source_path: Path) -> dict[str, Any] | None:
        manifest = self._load_manifest()
        key = self._key(source_path)
        target = manifest.get(key)
        if not target:
            return None
        path = self.root / target
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def put_cached_json(self, source_path: Path, payload: dict[str, Any]) -> Path:
        manifest = self._load_manifest()
        key = self._key(source_path)
        rel = f"{key}.json"
        path = self.root / rel
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        manifest[key] = rel
        self._save_manifest(manifest)
        return path
