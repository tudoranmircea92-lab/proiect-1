from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


class ModelRegistry:
    def __init__(self, models_dir: str):
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def save_metadata(self, name: str, payload: Dict[str, Any]) -> Path:
        path = self.models_dir / f"{name}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return path

    def load_metadata(self, name: str) -> Dict[str, Any] | None:
        path = self.models_dir / f"{name}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))
