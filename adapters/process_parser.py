from __future__ import annotations

"""Parsers for process CSV files produced by coater process PLC exports."""

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


PLATE_RE = re.compile(r"^(\d{14})_(\d+)_")


@dataclass(slots=True)
class ProcessParseResult:
    plate_id: str
    file_time: datetime | None
    source_path: Path
    rows: list[dict[str, Any]]
    metadata: dict[str, Any]


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    txt = str(value).strip().replace(",", ".")
    if not txt:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def infer_plate_and_time(path: Path) -> tuple[str, datetime | None]:
    m = PLATE_RE.match(path.name)
    if not m:
        return "", None
    return m.group(2), datetime.strptime(m.group(1), "%Y%m%d%H%M%S")


def parse_process_file(path: Path) -> ProcessParseResult:
    plate_id, file_time = infer_plate_and_time(path)
    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        raw_rows = list(csv.DictReader(handle, delimiter=";"))

    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(raw_rows, start=1):
        rec: dict[str, Any] = dict(row)
        rec["row_idx"] = idx
        rec["plate_id"] = str(row.get("glassId") or plate_id).strip()
        rec["event_time"] = file_time
        loc = str(row.get("Location", "")).strip()
        rec["Location"] = int(re.search(r"(\d+)", loc).group(1)) if re.search(r"(\d+)", loc) else None
        for metric in ("Power", "Current", "Voltage"):
            rec[f"nom{metric}"] = _to_float(row.get(f"nom{metric}"))
            rec[f"act{metric}"] = _to_float(row.get(f"act{metric}"))
            n = rec[f"nom{metric}"]
            a = rec[f"act{metric}"]
            rec[f"delta{metric}"] = (a - n) if n is not None and a is not None else None
        rec["actVacuumPressure"] = _to_float(row.get("actVacuumPressure"))
        for i in range(1, 6):
            rec[f"actMainGas{i}"] = _to_float(row.get(f"actMainGas{i}"))
            rec[f"nomMainGas{i}"] = _to_float(row.get(f"nomMainGas{i}"))
        rows.append(rec)

    metadata = {
        "plate_id": plate_id or (rows[0]["plate_id"] if rows else ""),
        "product": raw_rows[0].get("product") if raw_rows else None,
        "glassThickness": _to_float(raw_rows[0].get("glassThickness")) if raw_rows else None,
        "file_time": file_time,
    }
    return ProcessParseResult(
        plate_id=metadata["plate_id"], file_time=file_time, source_path=path, rows=rows, metadata=metadata
    )
