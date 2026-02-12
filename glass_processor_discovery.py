from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import List


def iter_day_folders(root: Path, start_d: date, end_d: date) -> List[Path]:
    """Return existing day folders root/YYYY/MM/DD for inclusive [start_d, end_d]."""
    out: List[Path] = []
    d = start_d
    while d <= end_d:
        p = root / f"{d.year:04d}" / f"{d.month:02d}" / f"{d.day:02d}"
        if p.exists():
            out.append(p)
        d += timedelta(days=1)
    return out


def list_files_by_days(root: Path, start_d: date, end_d: date, pattern: str) -> List[Path]:
    """
    Build file list scanning day folders in chronological order.
    Inside each day folder, we DO NOT sort (keeps filesystem enumeration order).
    """
    files: List[Path] = []
    day_dirs = iter_day_folders(root, start_d, end_d)
    if not day_dirs:
        raise SystemExit(f"No day folders found in range under: {root}")

    for day_dir in day_dirs:
        for f in day_dir.glob(pattern):  # no sorting
            if f.is_file():
                files.append(f)

    return files
