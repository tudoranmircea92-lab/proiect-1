from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Any


DEFAULT_DEVICE_MAP = {
    "reflection glass": "RG",
    "transmission": "T",
    "reflection film": "RF",
    "absorptance": "ABS",
    "nagy measurement unit": "NAGY",
}

DEFAULT_MATERIAL_MAP = {
    "ag": "silver",
    "silver": "silver",
    "si3n4": "nitride",
    "aln": "nitride",
    "sio2": "oxide",
    "snox": "oxide",
}

DEFAULT_GAS_MAP = {
    "o2": "reactive_oxidation",
    "n2": "reactive_nitridation",
    "ar": "inert",
    "he": "inert",
}

DEFAULT_ZONE_MAP = {
    "default": {
        "z1_pre_dielectric": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "z2_silver_stack_1": [11, 12, 13, 14, 15],
        "z3_mid_dielectric": [16, 17, 18, 19, 20, 21, 22, 23],
        "z4_silver_stack_2": [24, 25, 26, 27, 28],
        "z5_top_dielectric_tail": [29, 30, 31, 32, 33, 34, 35, 36],
    }
}

REQUIRED_PROCESS_COLUMNS = ["Location", "glassId"]

THRESHOLDS = {
    "silver_risk_pressure": 0.008,
    "delta_power_warn": 10.0,
}


@dataclass(slots=True)
class LiveDBConfig:
    optoplex_dir: Path
    process_dir: Path
    db_path: Path
    poll_seconds: int = 10
    match_window_minutes: int = 10
    backfill: bool = False
    archive_dir: Path | None = None
    log_file: Path | None = None
    one_shot: bool = False
    max_retries: int = 3
    device_map: dict[str, str] = field(default_factory=lambda: DEFAULT_DEVICE_MAP.copy())
    material_map: dict[str, str] = field(default_factory=lambda: DEFAULT_MATERIAL_MAP.copy())
    gas_map: dict[str, str] = field(default_factory=lambda: DEFAULT_GAS_MAP.copy())
    zone_map: dict[str, dict[str, list[int]]] = field(default_factory=lambda: DEFAULT_ZONE_MAP.copy())
    required_columns: list[str] = field(default_factory=lambda: REQUIRED_PROCESS_COLUMNS.copy())
    thresholds: dict[str, Any] = field(default_factory=lambda: THRESHOLDS.copy())

    @property
    def match_window(self) -> timedelta:
        return timedelta(minutes=self.match_window_minutes)

    def get_zone_mapping(self, product: str | None) -> dict[str, list[int]]:
        if product and product in self.zone_map:
            return self.zone_map[product]
        return self.zone_map["default"]
