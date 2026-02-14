from __future__ import annotations

import re
from typing import Iterable, List, Sequence


KNOB_PATTERN = re.compile(r"^c\d+\.(pwr|m[123]g|s\d+g)$")


def detect_available_knobs(columns: Sequence[str]) -> List[str]:
    return [col for col in columns if KNOB_PATTERN.match(col)]


def detect_used_compartments(columns: Iterable[str]) -> List[str]:
    used = set()
    for col in columns:
        if "." in col and col.startswith("c"):
            comp, _ = col.split(".", 1)
            used.add(comp)
    return sorted(used)


def default_feature_columns(columns: Sequence[str], target: str) -> List[str]:
    ignore = {target, "product", "day", "plate_id"}
    return [c for c in columns if c not in ignore]
