from __future__ import annotations

import re
from typing import Iterable

MANDATORY_COLUMN = "product_name"
PLATE_COLUMN = "plate"
TIMESTAMP_CANDIDATES = ["timestamp", "process_ts", "color_ts", "datetime"]

CONTROLLABLE_SUFFIXES = [
    "pwr",
    "m1g",
    "m2g",
    "m3g",
    *[f"s{i}g" for i in range(1, 12)],
]

NON_CONTROLLABLE_HINTS = {
    "actVacuumPressure",
    "actProcessSpeed_mm",
    "nomProcessSpeed_mm",
    "actFreq",
}

PROCESS_CONTEXT_SUFFIXES = {"voltage", "current", "ppmf", "imf", "umf"}

LEAKAGE_COLUMNS = {"product_name", "plate", "process_ts", "color_ts", "timestamp", "datetime"}

COMPARTMENT_PATTERN = re.compile(r"^(c\d+)\.")


def detect_compartments(columns: Iterable[str]) -> list[str]:
    found = set()
    for col in columns:
        m = COMPARTMENT_PATTERN.match(col)
        if m:
            found.add(m.group(1))
    return sorted(found, key=lambda x: int(x[1:]) if x[1:].isdigit() else x)


def is_controllable_column(column: str) -> bool:
    m = COMPARTMENT_PATTERN.match(column)
    if not m:
        return False
    suffix = column.split(".", 1)[1]
    return suffix in CONTROLLABLE_SUFFIXES


def is_process_context_column(column: str) -> bool:
    if column in NON_CONTROLLABLE_HINTS:
        return True
    m = COMPARTMENT_PATTERN.match(column)
    if not m:
        return False
    suffix = column.split(".", 1)[1]
    return suffix in PROCESS_CONTEXT_SUFFIXES
