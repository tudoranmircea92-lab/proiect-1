from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

from .validators import parse_float


MEASURE_BLOCKS = {
    "Reflection Glass",
    "Transmission",
    "Reflection Film",
    "Absorptance",
    "NAGY Measurement Unit",
}


def _read_with_fallback(path: Path) -> str:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="latin-1", errors="replace")


def infer_optoplex_file_time(path: Path) -> datetime | None:
    m = re.match(r"(\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2})_Plate-(.+)\.csv", path.name)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y-%m-%d-%H-%M-%S")


def _norm_device(raw: str, device_map: dict[str, str]) -> str:
    key = raw.strip().lower()
    return device_map.get(key, raw.strip())


def parse_optoplex_file(path: Path, device_map: dict[str, str]) -> tuple[list[dict], dict]:
    text = _read_with_fallback(path)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    file_time = infer_optoplex_file_time(path)
    plate = path.stem.split("Plate-")[-1]

    rows: list[dict] = []
    current_device: str | None = None
    reader = csv.reader(lines, delimiter=";")
    for parts in reader:
        first = parts[0].strip() if parts else ""
        if first in MEASURE_BLOCKS:
            current_device = first
            continue
        if first.startswith("Spectrum"):
            current_device = None
            continue
        if not current_device:
            continue
        if first.lower() in {"position", "pos"}:
            continue
        if len(parts) < 9:
            continue
        pos = parse_float(parts[0])
        if pos is None:
            continue
        rows.append(
            {
                "plate": plate,
                "optoplex_file_time": file_time,
                "stamp": file_time,
                "device_raw": current_device,
                "device_norm": _norm_device(current_device, device_map),
                "position": int(pos),
                "Y": parse_float(parts[1]),
                "L": parse_float(parts[2]),
                "a": parse_float(parts[3]),
                "b": parse_float(parts[4]),
                "RT": parse_float(parts[5]),
                "Resistance": parse_float(parts[6]),
                "Distance": parse_float(parts[7]),
            }
        )

    return rows, {"plate": plate, "optoplex_file_time": file_time, "event_time": file_time}
