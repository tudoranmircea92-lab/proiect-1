from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEVICE_MAP = {
    "reflection glass": "Reflection Glass",
    "rg": "Reflection Glass",
    "reflection film": "Reflection Film",
    "rf": "Reflection Film",
    "transmission": "Transmission",
    "absorptance": "Absorptance",
}


@dataclass
class DataRepository:
    dataset_path: Optional[Path] = None

    def __post_init__(self) -> None:
        self._cache: Dict[Tuple[str, float], List[Dict[str, Any]]] = {}

    def set_path(self, path: str) -> None:
        self.dataset_path = Path(path)

    def _cache_key(self, path: Path) -> Tuple[str, float]:
        return (str(path.resolve()), path.stat().st_mtime)

    def load(self, required_columns: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        if self.dataset_path is None or not self.dataset_path.exists():
            return []

        key = self._cache_key(self.dataset_path)
        rows = self._cache.get(key)
        if rows is None:
            rows = self._load_from_disk(self.dataset_path)
            self._cache = {key: rows}

        if not required_columns:
            return rows
        keep = set(required_columns)
        return [{k: v for k, v in row.items() if k in keep} for row in rows]

    def _load_from_disk(self, path: Path) -> List[Dict[str, Any]]:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            with path.open("r", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        elif suffix == ".parquet":
            try:
                import pandas as pd  # type: ignore
            except Exception as exc:
                raise RuntimeError(
                    "Parquet support requires pandas+pyarrow installed"
                ) from exc
            df = pd.read_parquet(path)
            rows = df.fillna("").to_dict(orient="records")
        else:
            raise RuntimeError(f"Unsupported format: {suffix}. Use .parquet or .csv")

        return [self._normalize_row(row) for row in rows]

    def _normalize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        for k, v in row.items():
            key = str(k).strip()
            out[key] = v

        out["device"] = self._normalize_device(
            out.get("device") or out.get("Device") or out.get("device_type") or ""
        )
        out["day"] = self._normalize_date(out.get("day") or out.get("date") or out.get("Date") or "")
        if "plate_id" not in out:
            out["plate_id"] = str(out.get("plate") or out.get("Plate") or "")
        out["plate_id"] = str(out.get("plate_id", ""))

        normalized = {}
        for k, v in out.items():
            nk = self._normalize_compartment_key(k)
            normalized[nk] = v
        return normalized

    def _normalize_date(self, value: Any) -> str:
        txt = str(value).strip()
        if not txt:
            return ""
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(txt, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        if len(txt) >= 10 and txt[4] in "-/":
            return txt[:10].replace("/", "-")
        return txt

    def _normalize_device(self, value: Any) -> str:
        txt = str(value).strip()
        if not txt:
            return ""
        return DEVICE_MAP.get(txt.lower(), txt)

    def _normalize_compartment_key(self, key: str) -> str:
        lower = key.lower().replace("_", "").replace("-", "")
        if lower.startswith("compartment"):
            digits = "".join(ch for ch in lower if ch.isdigit())
            if digits:
                return f"c{int(digits)}"
        return key

    def summarize(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not rows:
            return {
                "rows": 0,
                "columns": [],
                "date_min": None,
                "date_max": None,
                "date_count": 0,
                "devices": [],
                "compartments": [],
                "plates_count": 0,
                "segment_count": 0,
            }

        columns = sorted({k for r in rows for k in r.keys()})
        dates = sorted({str(r.get("day", "")) for r in rows if r.get("day")})
        devices = sorted({str(r.get("device", "")) for r in rows if r.get("device")})
        comps = self._detect_compartments(columns)
        plates = {str(r.get("plate_id", "")) for r in rows if r.get("plate_id")}

        seg_count = 0
        for c in columns:
            l = c.lower()
            if "actseggas" in l and "flow" in l:
                digits = "".join(ch for ch in l if ch.isdigit())
                if digits:
                    seg_count = max(seg_count, int(digits))

        return {
            "rows": len(rows),
            "columns": columns,
            "date_min": dates[0] if dates else None,
            "date_max": dates[-1] if dates else None,
            "date_count": len(dates),
            "dates": dates,
            "devices": devices,
            "compartments": comps,
            "plates_count": len(plates),
            "segment_count": seg_count,
            "dataset_path": str(self.dataset_path) if self.dataset_path else None,
        }

    def _detect_compartments(self, columns: List[str]) -> List[str]:
        comps = set()
        for c in columns:
            if c.startswith("c") and "." in c:
                left = c.split(".", 1)[0]
                if left[1:].isdigit():
                    comps.add(left)
        return sorted(comps)

    def filter_for_run(
        self,
        rows: List[Dict[str, Any]],
        date: str,
        plate: str,
        device: Optional[str],
        compartments: List[str],
    ) -> List[Dict[str, Any]]:
        out = rows[:]
        if date:
            out = [r for r in out if str(r.get("day", "")) == date]
        if plate:
            out = [r for r in out if str(r.get("plate_id", "")) == str(plate)]
        if device:
            out = [r for r in out if str(r.get("device", "")) == device]

        if compartments and out:
            keep_prefixes = tuple(f"{c}." for c in compartments)
            fixed = {"product", "day", "plate_id", "device", "a_star_RG_mean", "b_star_RG_mean", "L_star_RG_mean"}
            final: List[Dict[str, Any]] = []
            for r in out:
                nr = {}
                for k, v in r.items():
                    if k in fixed or not (k.startswith("c") and "." in k) or k.startswith(keep_prefixes):
                        nr[k] = v
                final.append(nr)
            out = final
        return out

    def get_context(
        self,
        rows: List[Dict[str, Any]],
        date: str,
        plate: str,
        device: Optional[str],
        strategy: str = "latest",
    ) -> Dict[str, Any]:
        filtered = self.filter_for_run(rows, date, plate, device, [])
        warnings: List[str] = []
        if not filtered:
            warnings.append("No rows for selected context")
            return {"rows": [], "count": 0, "warnings": warnings, "available_compartments": []}

        if strategy == "mean" and len(filtered) > 1:
            agg: Dict[str, Any] = {}
            keys = sorted({k for r in filtered for k in r.keys()})
            for k in keys:
                values = []
                for r in filtered:
                    try:
                        values.append(float(r.get(k, "")))
                    except Exception:
                        pass
                if values:
                    agg[k] = round(sum(values) / len(values), 6)
                else:
                    agg[k] = filtered[-1].get(k, "")
            rows_out = [agg]
        else:
            rows_out = [filtered[-1]]

        for row in rows_out:
            for k, v in row.items():
                if v in ("", None):
                    warnings.append(f"Missing value: {k}")

        return {
            "rows": rows_out,
            "count": len(filtered),
            "warnings": sorted(set(warnings)),
            "available_compartments": self._detect_compartments(sorted({k for r in filtered for k in r.keys()})),
        }
