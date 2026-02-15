from __future__ import annotations

from pathlib import Path

from app.services.io_utils import read_json, write_json

CONFIG_PATH = Path("backend/app/data/machine_config.json")


def load_machine_config() -> dict:
    cfg = read_json(CONFIG_PATH)
    if cfg:
        return cfg
    default = {
        "compartments": {
            "c4": {
                "c4.pwr": {"min": 0, "max": 100, "step": 1},
                "c4.m1g": {"min": 0, "max": 200, "step": 1},
                "c4.m2g": {"min": 0, "max": 200, "step": 1},
                "c4.m3g": {"min": 0, "max": 200, "step": 1},
                **{f"c4.s{i}g": {"min": 0, "max": 100, "step": 1} for i in range(1, 12)},
            }
        }
    }
    write_json(CONFIG_PATH, default)
    return default


def save_machine_config(config: dict) -> dict:
    write_json(CONFIG_PATH, config)
    return config
