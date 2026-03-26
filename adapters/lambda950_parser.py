from __future__ import annotations

"""Parser for Lambda950 XML/FXML operator files (offline measurements)."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


POSITIONS_MM = {"L1": 802, "L2": 1605, "L3": 2407}


@dataclass(slots=True)
class LambdaParseResult:
    plate_id: str
    measure_time: datetime | None
    source_path: Path
    positions: dict[str, dict[str, Any]]
    metadata: dict[str, Any]


def _txt(node: ET.Element | None, tag: str) -> str | None:
    if node is None:
        return None
    child = node.find(f".//{tag}")
    return child.text.strip() if child is not None and child.text else None


def parse_lambda950_file(path: Path) -> LambdaParseResult:
    root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    plate_id = _txt(root, "ID") or ""
    date_txt = _txt(root, "DATE")
    measure_time = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d"):
        try:
            if date_txt:
                measure_time = datetime.strptime(date_txt, fmt)
                break
        except ValueError:
            continue

    positions: dict[str, dict[str, Any]] = {}
    for node in root.findall(".//MEASUREMENT"):
        p = _txt(node, "POSITION") or ""
        if not p:
            continue
        positions[p] = {
            "position_mm": POSITIONS_MM.get(p),
            "L": _txt(node, "L"),
            "a": _txt(node, "A"),
            "b": _txt(node, "B"),
            "T": _txt(node, "T"),
            "R1": _txt(node, "R1"),
            "R2": _txt(node, "R2"),
        }

    return LambdaParseResult(
        plate_id=plate_id,
        measure_time=measure_time,
        source_path=path,
        positions=positions,
        metadata={"plate_id": plate_id, "date": date_txt},
    )
