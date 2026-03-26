from __future__ import annotations

"""Parsers for Optoplex online color CSV files."""

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


OPTOPLEX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})_Plate-(\d+)\.csv$")


@dataclass(slots=True)
class OptoplexParseResult:
    plate_id: str
    file_time: datetime | None
    source_path: Path
    measurements: list[dict[str, Any]]
    spectra: dict[str, list[tuple[float, float]]]  # device -> [(lambda, value)]


def _f(v: Any) -> float | None:
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def parse_optoplex_file(path: Path) -> OptoplexParseResult:
    m = OPTOPLEX_RE.match(path.name)
    plate_id = m.group(2) if m else ""
    file_time = datetime.strptime(m.group(1), "%Y-%m-%d-%H-%M-%S") if m else None

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = [line for line in text.splitlines() if line.strip()]
    marker = next((i for i, x in enumerate(lines) if x.lower().startswith("measurement values")), -1)
    if marker < 0 or marker + 1 >= len(lines):
        return OptoplexParseResult(plate_id, file_time, path, [], {})

    header = next(csv.reader([lines[marker + 1]], delimiter=";"))
    norm = [h.strip().lower().replace("*", "") for h in header]

    def idx(*names: str) -> int | None:
        for n in names:
            if n in norm:
                return norm.index(n)
        return None

    i_plate = idx("plate", "plateid", "glassid")
    i_device = idx("device", "measurementunit")
    i_pos = idx("position")
    i_l = idx("l")
    i_a = idx("a")
    i_b = idx("b")
    i_y = idx("y")

    measurements: list[dict[str, Any]] = []
    for line in lines[marker + 2 :]:
        if line.lower().startswith("spectrum"):
            break
        parts = next(csv.reader([line], delimiter=";"))
        if len(parts) < len(header):
            parts += [""] * (len(header) - len(parts))
        p = str(parts[i_plate]).strip() if i_plate is not None else ""
        if p:
            plate_id = p
        measurements.append(
            {
                "plate_id": plate_id,
                "position": int(_f(parts[i_pos]) or 0) if i_pos is not None else None,
                "device": str(parts[i_device]).strip() if i_device is not None else "",
                "L": _f(parts[i_l]) if i_l is not None else None,
                "a": _f(parts[i_a]) if i_a is not None else None,
                "b": _f(parts[i_b]) if i_b is not None else None,
                "Y": _f(parts[i_y]) if i_y is not None else None,
            }
        )

    return OptoplexParseResult(plate_id, file_time, path, measurements, spectra={})
