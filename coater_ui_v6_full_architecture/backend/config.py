from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


@dataclass(frozen=True)
class AppConfig:
    dataset_path: str
    models_dir: str
    artifacts_dir: str
    optimizer: Dict[str, Any]


_CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def load_config(path: Path | None = None) -> AppConfig:
    config_path = path or _CONFIG_PATH
    data = json.loads(config_path.read_text(encoding="utf-8"))
    return AppConfig(
        dataset_path=data.get("dataset_path", "./data/dataset.csv"),
        models_dir=data.get("models_dir", "./models"),
        artifacts_dir=data.get("artifacts_dir", "./artifacts"),
        optimizer=data.get("optimizer", {}),
    )
