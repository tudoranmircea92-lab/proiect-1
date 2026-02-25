from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

from .validators import parse_float


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def infer_process_file_time(path: Path) -> datetime | None:
    m = re.match(r"(\d{14})_", path.name)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%d%H%M%S")


def parse_process_file(path: Path) -> tuple[list[dict], dict]:
    rows = _read_csv_rows(path)
    process_time = infer_process_file_time(path)
    normalized: list[dict] = []
    for row in rows:
        rec = dict(row)
        rec["event_time"] = process_time
        rec["plate"] = str(row.get("glassId", "")).strip()
        rec["Location"] = int(parse_float(row.get("Location")) or 0)
        rec["active"] = str(row.get("status", "")).strip().lower() not in {"off", "0", "false"}

        for metric in ["Power", "Current", "Voltage", "ProcessSpeed"]:
            rec[f"nom{metric}"] = parse_float(row.get(f"nom{metric}"))
            rec[f"act{metric}"] = parse_float(row.get(f"act{metric}"))
            n = rec[f"nom{metric}"]
            a = rec[f"act{metric}"]
            rec[f"delta{metric}"] = (a - n) if (a is not None and n is not None) else None

        rec["actVacuumPressure"] = parse_float(row.get("actVacuumPressure"))

        for i in range(1, 6):
            rec[f"nomMainGas{i}"] = parse_float(row.get(f"nomMainGas{i}"))
            rec[f"actMainGas{i}"] = parse_float(row.get(f"actMainGas{i}"))
            n = rec[f"nomMainGas{i}"]
            a = rec[f"actMainGas{i}"]
            rec[f"deltaMainGas{i}"] = (a - n) if (a is not None and n is not None) else None

        for i in range(1, 4):
            rec[f"nomRampGas{i}"] = parse_float(row.get(f"nomRampGas{i}"))
            rec[f"actRampGas{i}"] = parse_float(row.get(f"actRampGas{i}"))
            n = rec[f"nomRampGas{i}"]
            a = rec[f"actRampGas{i}"]
            rec[f"deltaRampGas{i}"] = (a - n) if (a is not None and n is not None) else None

        rec["material_raw"] = str(row.get("material", "")).strip()
        rec["nomGasSegment"] = int(parse_float(row.get("nomGasSegment")) or 0)
        rec["nomSegGasType"] = str(row.get("nomSegGasType", "")).strip()

        seg_count = rec["nomGasSegment"] if rec["nomGasSegment"] in {5, 10, 11} else 11
        seg_vals: list[float] = []
        for s in range(1, seg_count + 1):
            v = parse_float(row.get(f"Seg{s}"))
            if v is not None:
                seg_vals.append(v)
        rec["seg_sum"] = sum(seg_vals) if seg_vals else 0.0
        rec["seg_mean"] = (sum(seg_vals) / len(seg_vals)) if seg_vals else 0.0
        rec["seg_max"] = max(seg_vals) if seg_vals else 0.0
        rec["seg_range"] = (max(seg_vals) - min(seg_vals)) if len(seg_vals) > 1 else 0.0
        rec["seg_active_count"] = len([v for v in seg_vals if v > 0])

        normalized.append(rec)

    core = {
        "plate": normalized[0]["plate"] if normalized else "",
        "event_time": process_time,
        "process_file_time": process_time,
        "product": rows[0].get("product") if rows else None,
        "glassWidth": parse_float(rows[0].get("glassWidth")) if rows else None,
        "glassLength": parse_float(rows[0].get("glassLength")) if rows else None,
        "glassThickness": parse_float(rows[0].get("glassThickness")) if rows else None,
        "glassState": rows[0].get("glassState") if rows else None,
        "nomProcessSpeed_mm": parse_float(rows[0].get("nomProcessSpeed")) if rows else None,
        "actProcessSpeed_mm": parse_float(rows[0].get("actProcessSpeed")) if rows else None,
    }
    n, a = core["nomProcessSpeed_mm"], core["actProcessSpeed_mm"]
    core["deltaProcessSpeed_mm"] = (a - n) if (a is not None and n is not None) else None
    return normalized, core
