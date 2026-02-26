from __future__ import annotations

import csv
import logging
import re
from datetime import datetime
from pathlib import Path

from .validators import parse_float


logger = logging.getLogger(__name__)


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


def _find_col(header: list[str], *candidates: str) -> int | None:
    normalized = [h.strip().lower().replace("*", "").replace(" ", "") for h in header]
    for cand in candidates:
        c = cand.strip().lower().replace("*", "").replace(" ", "")
        if c in normalized:
            return normalized.index(c)
    return None


def parse_optoplex_file(path: Path, device_map: dict[str, str]) -> tuple[list[dict], dict]:
    text = _read_with_fallback(path)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    file_time = infer_optoplex_file_time(path)
    plate_from_name = path.stem.split("Plate-")[-1]

    marker_idx = next((i for i, ln in enumerate(lines) if ln.strip().lower() == "measurement values"), None)
    if marker_idx is None or marker_idx + 1 >= len(lines):
        logger.warning(
            "Optoplex parse produced 0 rows: measurement_values_found=%s spectrum_start=%s parsed_rows=0 mapped_cols={} file=%s",
            marker_idx is not None,
            None,
            path,
        )
        return [], {"plate": plate_from_name, "optoplex_file_time": file_time, "event_time": file_time}

    header = next(csv.reader([lines[marker_idx + 1]], delimiter=";"))
    spectrum_idx: int | None = None
    data_lines: list[str] = []
    for i, ln in enumerate(lines[marker_idx + 2 :], start=marker_idx + 2):
        first = next(csv.reader([ln], delimiter=";"))[0].strip().lower()
        if first == "spectrum" or first.startswith("spectrum"):
            spectrum_idx = i
            break
        data_lines.append(ln)

    idx_stamp = _find_col(header, "stamp", "date", "datetime")
    idx_plate = _find_col(header, "plate", "plateid", "glassid")
    idx_device = _find_col(header, "device", "measurementunit", "unit")
    idx_pos = _find_col(header, "position", "pos")
    idx_y = _find_col(header, "y")
    idx_l = _find_col(header, "l", "l*")
    idx_a = _find_col(header, "a", "a*")
    idx_b = _find_col(header, "b", "b*")
    idx_rt = _find_col(header, "rtglass", "rt", "rt glass")
    idx_res = _find_col(header, "resistance")
    idx_dist = _find_col(header, "distance")

    mapped_cols = {
        "stamp": idx_stamp,
        "plate": idx_plate,
        "device": idx_device,
        "position": idx_pos,
        "Y": idx_y,
        "L": idx_l,
        "a": idx_a,
        "b": idx_b,
        "RT": idx_rt,
        "Resistance": idx_res,
        "Distance": idx_dist,
    }

    rows: list[dict] = []
    plate_detected = plate_from_name
    for ln in data_lines:
        parts = next(csv.reader([ln], delimiter=";"))
        if len(parts) < len(header):
            parts += [""] * (len(header) - len(parts))

        if idx_pos is None:
            continue
        pos = parse_float(parts[idx_pos])
        if pos is None:
            continue

        raw_plate = parts[idx_plate].strip() if idx_plate is not None and idx_plate < len(parts) else ""
        if raw_plate:
            plate_detected = raw_plate

        device_raw = parts[idx_device].strip() if idx_device is not None and idx_device < len(parts) else ""
        stamp_raw = parts[idx_stamp].strip() if idx_stamp is not None and idx_stamp < len(parts) else ""
        stamp = file_time
        if stamp_raw:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
                try:
                    stamp = datetime.strptime(stamp_raw, fmt)
                    break
                except ValueError:
                    pass

        rows.append(
            {
                "plate": plate_detected,
                "optoplex_file_time": file_time,
                "stamp": stamp,
                "device_raw": device_raw,
                "device_norm": _norm_device(device_raw, device_map),
                "position": int(pos),
                "Y": parse_float(parts[idx_y]) if idx_y is not None and idx_y < len(parts) else None,
                "L": parse_float(parts[idx_l]) if idx_l is not None and idx_l < len(parts) else None,
                "a": parse_float(parts[idx_a]) if idx_a is not None and idx_a < len(parts) else None,
                "b": parse_float(parts[idx_b]) if idx_b is not None and idx_b < len(parts) else None,
                "RT": parse_float(parts[idx_rt]) if idx_rt is not None and idx_rt < len(parts) else None,
                "Resistance": parse_float(parts[idx_res]) if idx_res is not None and idx_res < len(parts) else None,
                "Distance": parse_float(parts[idx_dist]) if idx_dist is not None and idx_dist < len(parts) else None,
            }
        )

    if not rows:
        logger.warning(
            "Optoplex parse produced 0 rows: measurement_values_found=%s spectrum_start=%s parsed_rows=%s mapped_cols=%s file=%s",
            True,
            spectrum_idx,
            len(rows),
            mapped_cols,
            path,
        )
    else:
        logger.debug(
            "Optoplex parse success: measurement_values_found=%s spectrum_start=%s parsed_rows=%s mapped_cols=%s file=%s",
            True,
            spectrum_idx,
            len(rows),
            mapped_cols,
            path,
        )

    return rows, {"plate": plate_detected, "optoplex_file_time": file_time, "event_time": file_time}
