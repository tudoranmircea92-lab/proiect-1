from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

DEVICE_COLUMNS = ["device", "Device", "device_type"]


@dataclass
class DataRepository:
    dataset_path: Optional[Path] = None

    def set_path(self, path: str) -> None:
        self.dataset_path = Path(path)

    def load(self) -> List[Dict[str, str]]:
        if self.dataset_path is None or not self.dataset_path.exists():
            return []
        with self.dataset_path.open("r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def summarize(self, rows: List[Dict[str, str]]) -> Dict[str, Any]:
        if not rows:
            return {"rows": 0, "columns": [], "dates": [], "devices": [], "compartments": []}
        columns = list(rows[0].keys())
        dates = sorted({r.get("day", "") for r in rows if r.get("day")})
        devices = self._detect_devices(rows)
        compartments = self._detect_compartments(columns)
        return {
            "rows": len(rows),
            "columns": columns,
            "dates": dates,
            "devices": devices,
            "compartments": compartments,
            "dataset_path": str(self.dataset_path) if self.dataset_path else None,
        }

    def get_context(self, rows: List[Dict[str, str]], date: str, plate: str, device: Optional[str]) -> Dict[str, Any]:
        filtered = self.filter_for_run(rows, date, plate, device, [])
        warnings: List[str] = []
        if not filtered:
            warnings.append("No rows for selected context")
        if filtered and "a_star_RG_mean" not in filtered[0]:
            warnings.append("Target reference column a_star_RG_mean missing")
        return {
            "rows": filtered[:5],
            "warnings": warnings,
            "available_compartments": self._detect_compartments(list(rows[0].keys()) if rows else []),
        }

    def filter_for_run(
        self,
        rows: List[Dict[str, str]],
        date: str,
        plate: str,
        device: Optional[str],
        compartments: List[str],
    ) -> List[Dict[str, str]]:
        out = rows[:]
        if date:
            out = [r for r in out if str(r.get("day", "")) == date]
        if plate:
            out = [r for r in out if str(r.get("plate_id", "")) == str(plate)]

        if device:
            for c in DEVICE_COLUMNS:
                if out and c in out[0]:
                    out = [r for r in out if str(r.get(c, "")) == device]
                    break

        if compartments and out:
            keep_prefixes = tuple(f"{c}." for c in compartments)
            keep_static = {"product", "day", "plate_id", "device", "Device", "device_type", "a_star_RG_mean", "b_star_RG_mean"}
            filtered_out = []
            for r in out:
                nr = {}
                for k, v in r.items():
                    if k in keep_static or not k.startswith("c") or k.startswith(keep_prefixes):
                        nr[k] = v
                filtered_out.append(nr)
            out = filtered_out
        return out

    def _detect_devices(self, rows: List[Dict[str, str]]) -> List[str]:
        for c in DEVICE_COLUMNS:
            if rows and c in rows[0]:
                return sorted({r.get(c, "") for r in rows if r.get(c)})
        return []

    def _detect_compartments(self, columns: List[str]) -> List[str]:
        comps = set()
        for c in columns:
            if c.startswith("c") and "." in c:
                comps.add(c.split(".", 1)[0])
        return sorted(comps)
