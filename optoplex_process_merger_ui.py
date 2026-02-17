from __future__ import annotations

import argparse
import hashlib
import json
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, W, Button, Checkbutton, DoubleVar, Entry, Frame, IntVar, Label, StringVar, Tk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from tkinter.ttk import Combobox, Progressbar
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ==========================
# Optoplex color parser bits
# ==========================
DEVICE_SYNONYMS = {
    "RG": [r"\brg\b", r"reflection\s*glass", r"rt\s*glass", r"refl\s*glass", r"glass\s*reflection"],
    "T": [r"\bt\b", r"transmission", r"rt\s*trans", r"\btrans\b"],
    "RF": [r"\brf\b", r"reflection\s*film", r"rt\s*coating", r"refl\s*film", r"film\s*reflection", r"coating\s*reflection"],
    "ABS": [r"\babs\b", r"absorptance", r"rt\s*absorption", r"rt\s*absorbtion", r"absorption", r"absorbance"],
}
_COMPILED_SYNONYMS = {k: [re.compile(p, re.IGNORECASE) for p in pats] for k, pats in DEVICE_SYNONYMS.items()}

DEV_ORDER = ["RG", "T", "RF", "ABS"]
METRICS = [("L*", "L"), ("a*", "a"), ("b*", "b")]
DEV_TO_BLOCK = {"RG": 0, "T": 1, "RF": 2, "ABS": 3}

THICK_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*mm\b", re.IGNORECASE)
THICK_TOKEN_RE = re.compile(r"\s*\b\d+(?:[.,]\d+)?\s*mm\b\s*", re.IGNORECASE)
META_DATAFILE_RE = re.compile(r"^\s*datafile\s*created\s*(?:\t+|;|\s{2,})\s*(.+?)\s*$", re.IGNORECASE)
META_PRODUCT_RE = re.compile(r"^\s*product\s*(?:\t+|;|\s{2,})\s*(.+?)\s*$", re.IGNORECASE)
HEADER_PREFIX = "stamp;plate;device;position"
DATEISH_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2};")


@dataclass
class Meas:
    plate: int
    device: str
    position_mm: int
    L: Optional[float]
    a: Optional[float]
    b: Optional[float]


@dataclass
class MergeConfig:
    optoplex_dir: Path
    process_dir: Path
    output_path: Path
    output_format: str
    recursive: bool
    year_filter: Optional[str]
    compression: str
    merge_how: str
    use_cache_read: bool = True
    use_cache_write: bool = True
    cache_dir: Optional[Path] = None
    ml_ready: bool = True


CACHE_VERSION = "v1"


def normalize_device(raw: str) -> Optional[str]:
    s = (raw or "").strip()
    if not s:
        return None
    up = s.upper()
    if up in {"RG", "T", "RF", "ABS"}:
        return up
    for canon, pats in _COMPILED_SYNONYMS.items():
        if any(p.search(s) for p in pats):
            return canon
    return None


def to_float(x: str) -> Optional[float]:
    x = (x or "").strip()
    if not x or x.lower() in {"nan", "none"}:
        return None
    try:
        return float(x.replace(",", "."))
    except Exception:
        return None


def to_int(x: str) -> Optional[int]:
    x = (x or "").strip()
    if not x or x.lower() in {"nan", "none"}:
        return None
    try:
        return int(float(x.replace(",", ".")))
    except Exception:
        return None


def parse_dt_ddmmyyyy(x: str) -> Optional[datetime]:
    x = (x or "").strip()
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(x, fmt)
        except Exception:
            pass
    return None


def extract_metadata(lines: List[str]) -> Tuple[Optional[datetime], Optional[str], Optional[float]]:
    file_ts: Optional[datetime] = None
    product: Optional[str] = None
    thickness_mm: Optional[float] = None

    for ln in lines[:220]:
        s = (ln or "").strip().replace("\ufeff", "")
        if not s:
            continue
        m1 = META_DATAFILE_RE.match(s)
        if m1 and file_ts is None:
            file_ts = parse_dt_ddmmyyyy(m1.group(1))
            continue
        m2 = META_PRODUCT_RE.match(s)
        if m2 and product is None:
            raw = m2.group(1).strip()
            m = THICK_RE.search(raw)
            if m:
                thickness_mm = float(m.group(1).replace(",", "."))
            product = THICK_TOKEN_RE.sub(" ", raw).strip()
            product = re.sub(r"\s{2,}", " ", product)
    return file_ts, product, thickness_mm


def extract_measurements_optoplex(lines: List[str]) -> List[Meas]:
    out: List[Meas] = []
    hdr_idx = None
    for i, ln in enumerate(lines[:1200]):
        if (ln or "").strip().lower().startswith(HEADER_PREFIX):
            hdr_idx = i
            break
    if hdr_idx is None:
        return out

    cols = lines[hdr_idx].rstrip("\n").split(";")
    try:
        idx_plate = [j for j, c in enumerate(cols) if c.strip().lower() == "plate"][0]
        idx_device = [j for j, c in enumerate(cols) if c.strip().lower() == "device"][0]
        idx_pos = [j for j, c in enumerate(cols) if c.strip().lower() == "position"][0]
    except Exception:
        return out

    L_idx = [j for j, c in enumerate(cols) if c.strip() == "L*"]
    a_idx = [j for j, c in enumerate(cols) if c.strip() == "a*"]
    b_idx = [j for j, c in enumerate(cols) if c.strip() == "b*"]

    for i in range(hdr_idx + 1, len(lines)):
        ln = (lines[i] or "").strip()
        if not ln or not DATEISH_RE.match(ln):
            continue
        parts = lines[i].rstrip("\n").split(";")
        plate = to_int(parts[idx_plate] if idx_plate < len(parts) else "")
        dev = normalize_device(parts[idx_device] if idx_device < len(parts) else "")
        pos = to_int(parts[idx_pos] if idx_pos < len(parts) else "")
        if plate is None or dev is None or pos is None:
            continue

        block = DEV_TO_BLOCK.get(dev)
        Li = L_idx[block] if block is not None and block < len(L_idx) else None
        ai = a_idx[block] if block is not None and block < len(a_idx) else None
        bi = b_idx[block] if block is not None and block < len(b_idx) else None

        out.append(
            Meas(
                plate=int(plate),
                device=dev,
                position_mm=int(pos),
                L=to_float(parts[Li] if Li is not None and Li < len(parts) else ""),
                a=to_float(parts[ai] if ai is not None and ai < len(parts) else ""),
                b=to_float(parts[bi] if bi is not None and bi < len(parts) else ""),
            )
        )
    return out


def uniform9_interpolate(x_mm: np.ndarray, y: np.ndarray) -> np.ndarray:
    if x_mm.size == 0:
        return np.full(9, np.nan, dtype=np.float32)
    order = np.argsort(x_mm)
    x = x_mm[order].astype(float)
    yv = y[order].astype(float)
    mask = ~np.isnan(yv)
    x, yv = x[mask], yv[mask]
    if x.size == 0:
        return np.full(9, np.nan, dtype=np.float32)
    if x.size == 1:
        return np.full(9, float(yv[0]), dtype=np.float32)
    x_t = np.linspace(float(x.min()), float(x.max()), 9)
    return np.interp(x_t, x, yv).astype(np.float32)


def build_color_row(day: datetime.date, file_ts: datetime, plate: int, product: str, thickness_mm: Optional[float], df_plate: pd.DataFrame) -> Dict[str, object]:
    row: Dict[str, object] = {
        "day": day,
        "file_ts": file_ts,
        "plate": plate,
        "product": product,
        "thickness_mm": thickness_mm,
    }
    for dev in DEV_ORDER:
        d = df_plate[df_plate["device"] == dev]
        x = d["position_mm"].to_numpy(dtype=float)
        for _, short in METRICS:
            y = d[short].to_numpy(dtype=float)
            y9 = uniform9_interpolate(x, y)
            for i in range(9):
                row[f"{short}_{dev}_p{i + 1}"] = float(y9[i]) if not np.isnan(y9[i]) else np.nan
            row[f"{short}_{dev}_mean"] = float(np.nanmean(y9)) if not np.all(np.isnan(y9)) else np.nan
            row[f"{short}_{dev}_std"] = float(np.nanstd(y9, ddof=0)) if not np.all(np.isnan(y9)) else np.nan
    return row


# =========================
# Process parser/pivot bits
# =========================
_COMP_RE = re.compile(r"(\d+)$")


def _extract_comp(location: str) -> Optional[int]:
    if not isinstance(location, str):
        return None
    m = _COMP_RE.search(location.strip()) or re.search(r"(\d+)", location)
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _parse_optoplex_gtime(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.strip().str.replace(r"\D+", "", regex=True).str.slice(0, 14)
    return pd.to_datetime(s, format="%Y%m%d%H%M%S", errors="coerce")


def _safe_float32(x: pd.Series) -> pd.Series:
    return pd.to_numeric(x, errors="coerce").astype("float32")


def _safe_int64(x: pd.Series) -> pd.Series:
    return pd.to_numeric(x, errors="coerce").astype("Int64")


def _first_existing_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _compute_ramp_features(seg_mat: np.ndarray, num_ramps: np.ndarray) -> Dict[str, np.ndarray]:
    n = seg_mat.shape[0]
    R = np.clip(num_ramps, 0, 11).astype(np.int32)
    gas_total = seg_mat.sum(axis=1).astype(np.float32)

    gas_mean = np.zeros(n, dtype=np.float32)
    maskR = R > 0
    gas_mean[maskR] = gas_total[maskR] / R[maskR]

    eps = np.float32(1e-6)
    gas_std = np.zeros(n, dtype=np.float32)
    front_back = np.zeros(n, dtype=np.float32)
    max_over_mean = np.zeros(n, dtype=np.float32)

    if maskR.any():
        idx = np.arange(11)[None, :]
        active = idx < R[:, None]
        vals = np.where(active, seg_mat, 0.0).astype(np.float32)

        cnt = np.where(R > 0, R, 1).astype(np.float32)
        s1 = vals.sum(axis=1)
        s2 = (vals * vals).sum(axis=1)
        mean = s1 / cnt
        var = np.maximum(s2 / cnt - mean * mean, 0.0)
        gas_std[maskR] = np.sqrt(var[maskR])

        half = (R + 1) // 2
        front = idx < half[:, None]
        back = (idx >= half[:, None]) & (idx < R[:, None])
        front_sum = np.where(front, seg_mat, 0.0).sum(axis=1)
        back_sum = np.where(back, seg_mat, 0.0).sum(axis=1)
        front_back[maskR] = front_sum[maskR] / (back_sum[maskR] + eps)

        vmax = np.max(np.where(active, seg_mat, -np.inf), axis=1)
        max_over_mean[maskR] = vmax[maskR] / (gas_mean[maskR] + eps)

    return {
        "gasTotal": gas_total,
        "gasMean": gas_mean,
        "gasStd": gas_std,
        "gasCV": gas_std / (gas_mean + eps),
        "frontBackRatio": front_back,
        "segMaxOverMean": max_over_mean,
    }


def _norm_target(value: object) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None

    su = s.upper()
    # treat placeholders / non-material markers as empty
    empty_tokens = {"NAN", "NONE", "NULL", "N/A", "NA", "-", "--", "---", "0", "0.0", "EMPTY"}
    if su in empty_tokens:
        return None
    return su


def _prepare_long(df: pd.DataFrame) -> pd.DataFrame:
    """
    Minimal process long format (no explosive derived features):
    keys: ts, plate, comp
    globals: glassThickness_mm, nomProcessSpeed_mm, actProcessSpeed_mm, actVacuumPressure, actFreq
    per-comp: pwr/voltage/current, seg gas flows, material gas flows, target info
    """
    comp = df["Location"].map(_extract_comp)
    base = pd.DataFrame(
        {
            "ts": _parse_optoplex_gtime(df["optoplexGTime"]),
            "plate": _safe_int64(df["glassId"]),
            "comp": _safe_int64(comp),
        }
    )

    # global plate-level columns (kept as single columns after wide pivot)
    if "glassThickness" in df.columns:
        base["glassThickness_mm"] = _safe_float32(df["glassThickness"])
    if "nomProcessSpeed_mm" in df.columns:
        base["nomProcessSpeed_mm"] = _safe_float32(df["nomProcessSpeed_mm"])
    elif "nomProcessSpeed" in df.columns:
        base["nomProcessSpeed_mm"] = _safe_float32(df["nomProcessSpeed"])
    if "actProcessSpeed_mm" in df.columns:
        base["actProcessSpeed_mm"] = _safe_float32(df["actProcessSpeed_mm"])
    elif "actProcessSpeed" in df.columns:
        base["actProcessSpeed_mm"] = _safe_float32(df["actProcessSpeed"])
    if "actVacuumPressure" in df.columns:
        base["actVacuumPressure"] = _safe_float32(df["actVacuumPressure"])
    if "actFreq" in df.columns:
        base["actFreq"] = _safe_float32(df["actFreq"])

    # per-comp minimal numeric core
    if "actPower" in df.columns:
        base["pwr"] = _safe_float32(df["actPower"])
    if "actVoltageUMF" in df.columns:
        base["voltage"] = _safe_float32(df["actVoltageUMF"])
    if "actCurrentIMF" in df.columns:
        base["current"] = _safe_float32(df["actCurrentIMF"])

    # per-comp segment gas
    for i in range(1, 12):
        src = f"actSegGas{i}Flow"
        if src in df.columns:
            base[f"s{i}g"] = _safe_float32(df[src])

    # per-comp material/main gas (supports multiple source naming conventions)
    gas_sources = {
        "mainGas1": ["Ar_flow", "mainGas1", "mainGas1Flow", "actMainGas1Flow"],
        "mainGas2": ["N2_flow", "mainGas2", "mainGas2Flow", "actMainGas2Flow"],
        "mainGas3": ["O2_flow", "mainGas3", "mainGas3Flow", "actMainGas3Flow"],
    }
    legacy_alias = {"mainGas1": "m1g", "mainGas2": "m2g", "mainGas3": "m3g"}
    for tgt, candidates in gas_sources.items():
        src = _first_existing_column(df, candidates)
        if src:
            v = _safe_float32(df[src])
            base[tgt] = v
            base[legacy_alias[tgt]] = v

    # target info
    if "actTargetMaterial1" in df.columns:
        base["actTargetMaterial1"] = df["actTargetMaterial1"].map(_norm_target)
    if "actTarget2KWH" in df.columns:
        base["kwh2"] = _safe_float32(df["actTarget2KWH"])
    if "actTarget1KWH" in df.columns:
        base["kwh1"] = _safe_float32(df["actTarget1KWH"])
    if "actTargetMaterial2" in df.columns:
        base["actTargetMaterial2"] = df["actTargetMaterial2"].map(_norm_target)

    base["plate"] = base["plate"].astype("Int64")
    base["comp"] = base["comp"].astype("Int64")
    base["ts"] = pd.to_datetime(base["ts"], errors="coerce")

    # filter rows with keys
    base = base.dropna(subset=["ts", "plate", "comp"]).copy()
    return base


def _pivot_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    d_all = long_df.dropna(subset=["ts", "plate", "comp"]).copy()
    d_all["comp"] = d_all["comp"].astype(int)

    # Global columns: one column each, not per compartment
    global_cols = [
        c
        for c in [
            "glassThickness_mm",
            "nomProcessSpeed_mm",
            "actProcessSpeed_mm",
            "actVacuumPressure",
            "actFreq",
        ]
        if c in d_all.columns
    ]

    if global_cols:
        global_df = d_all.groupby(["ts", "plate"], as_index=False)[global_cols].mean()
    else:
        global_df = d_all[["ts", "plate"]].drop_duplicates().copy()

    # Relevant compartments ONLY: with real actTargetMaterial1/actTargetMaterial2
    d = d_all
    relevant = set()
    if "actTargetMaterial1" in d_all.columns or "actTargetMaterial2" in d_all.columns:
        m1 = d_all["actTargetMaterial1"].notna() if "actTargetMaterial1" in d_all.columns else pd.Series(False, index=d_all.index)
        m2 = d_all["actTargetMaterial2"].notna() if "actTargetMaterial2" in d_all.columns else pd.Series(False, index=d_all.index)
        relevant = set(d_all.loc[m1 | m2, "comp"].astype(int).tolist())

    # if no relevant compartments => keep only global columns
    if not relevant:
        return _round_process_columns(global_df.copy())

    d = d_all[d_all["comp"].isin(relevant)].copy()

    # Build per-comp values (minimal set)
    keep_candidates = ["pwr", "voltage", "current"] + [f"s{i}g" for i in range(1, 12)] + ["mainGas1", "mainGas2", "mainGas3", "m1g", "m2g", "m3g", "actTargetMaterial1", "kwh1", "actTargetMaterial2", "kwh2"]
    value_cols = [c for c in keep_candidates if c in d.columns]

    if not value_cols:
        return _round_process_columns(global_df.copy())

    # keep actTargetMaterial2/kwh2 ONLY for compartments that have real target2
    comps_with_tar2 = set()
    if "actTargetMaterial2" in d.columns:
        comps_with_tar2 = set(d.loc[d["actTargetMaterial2"].notna(), "comp"].astype(int).tolist())

    # aggregate per (ts, plate, comp)
    agg = {}
    for c in value_cols:
        if c in {"actTargetMaterial1", "actTargetMaterial2"}:
            agg[c] = "first"
        else:
            agg[c] = "mean"

    per_comp = d.groupby(["ts", "plate", "comp"], as_index=False).agg(agg)

    # remove actTargetMaterial2/kwh2 rows for comps without real target2
    if "actTargetMaterial2" in per_comp.columns:
        mask_tar2_comp = per_comp["comp"].isin(comps_with_tar2)
        per_comp.loc[~mask_tar2_comp, "actTargetMaterial2"] = pd.NA
        if "kwh2" in per_comp.columns:
            per_comp.loc[~mask_tar2_comp, "kwh2"] = pd.NA

    wide = per_comp.set_index(["ts", "plate", "comp"])[value_cols].unstack("comp")
    wide.columns = [f"c{comp}.{feat}" for feat, comp in wide.columns]
    wide = wide.reset_index().copy()

    out = global_df.merge(wide, on=["ts", "plate"], how="left")

    # generic filter: keep only allowed c{comp}.<minimal>
    allowed_suffix = set(["pwr", "voltage", "current", "mainGas1", "mainGas2", "mainGas3", "m1g", "m2g", "m3g", "actTargetMaterial1", "kwh1", "actTargetMaterial2", "kwh2"] + [f"s{i}g" for i in range(1, 12)])
    keep_cols = []
    for c in out.columns:
        if not c.startswith("c") or "." not in c:
            keep_cols.append(c)
            continue
        suffix = c.split(".", 1)[1]
        if suffix in allowed_suffix:
            keep_cols.append(c)
    out = out[keep_cols]
    out = _cleanup_target_columns(out)
    out = _round_process_columns(out)
    return out


def _cleanup_target_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Drop target/kwh columns when corresponding target material is missing."""
    drop_cols = []
    by_comp = {}
    for c in df.columns:
        if not c.startswith("c") or "." not in c:
            continue
        comp, feat = c.split(".", 1)
        by_comp.setdefault(comp, {})[feat] = c

    for comp, feats in by_comp.items():
        m1_col = feats.get("actTargetMaterial1")
        m2_col = feats.get("actTargetMaterial2")
        k1_col = feats.get("kwh1")
        k2_col = feats.get("kwh2")

        has_m1 = bool(m1_col) and df[m1_col].notna().any()
        has_m2 = bool(m2_col) and df[m2_col].notna().any()

        if m1_col and not has_m1:
            drop_cols.append(m1_col)
        if k1_col and not has_m1:
            drop_cols.append(k1_col)

        if m2_col and not has_m2:
            drop_cols.append(m2_col)
        if k2_col and not has_m2:
            drop_cols.append(k2_col)

    if drop_cols:
        df = df.drop(columns=sorted(set(drop_cols)), errors="ignore")
    return df


def _round_process_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Round process numeric columns to 2 decimals, except vacuum."""
    keep_full_precision = {"actVacuumPressure"}
    for c in df.columns:
        if c in keep_full_precision:
            continue
        if c.startswith("c") and "." in c:
            suffix = c.split(".", 1)[1]
            if suffix.startswith("actTargetMaterial"):
                continue
        if pd.api.types.is_numeric_dtype(df[c]):
            df[c] = df[c].round(2)
    return df


def _file_signature(path: Path) -> str:
    st = path.stat()
    return f"{st.st_size}:{st.st_mtime_ns}"


def _cache_key(path: Path) -> str:
    return hashlib.sha1(str(path.resolve()).encode("utf-8")).hexdigest()


def _cache_paths(cache_dir: Path, kind: str, source_path: Path) -> Tuple[Path, Path]:
    key = _cache_key(source_path)
    base = cache_dir / kind
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{key}.pkl", base / f"{key}.json"


def _load_cached_df(cache_dir: Path, kind: str, source_path: Path, extra: Optional[Dict[str, object]] = None) -> Optional[pd.DataFrame]:
    pkl_path, meta_path = _cache_paths(cache_dir, kind, source_path)
    if not pkl_path.exists() or not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        expected = {
            "version": CACHE_VERSION,
            "signature": _file_signature(source_path),
            "extra": extra or {},
        }
        if meta != expected:
            return None
        return pd.read_pickle(pkl_path)
    except Exception:
        return None


def _store_cached_df(cache_dir: Path, kind: str, source_path: Path, df: pd.DataFrame, extra: Optional[Dict[str, object]] = None) -> None:
    pkl_path, meta_path = _cache_paths(cache_dir, kind, source_path)
    meta = {
        "version": CACHE_VERSION,
        "signature": _file_signature(source_path),
        "extra": extra or {},
    }
    df.to_pickle(pkl_path)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")


# ===========
# Merge logic
# ===========
def _matches_year(path: Path, year: Optional[str]) -> bool:
    if not year:
        return True
    y = year.strip()
    if not y:
        return True
    return y in path.parts


def find_files(root: Path, pattern: str, recursive: bool, year: Optional[str]) -> List[Path]:
    iterator = root.rglob(pattern) if recursive else root.glob(pattern)
    return sorted([p for p in iterator if p.is_file() and _matches_year(p, year)])


def load_color_dataset(files: List[Path], log, progress=None, progress_base: float = 0.0, progress_span: float = 0.0, cache_dir: Optional[Path] = None, use_cache_read: bool = True, use_cache_write: bool = True) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    total = max(len(files), 1)
    cache_hits = 0
    for idx, fp in enumerate(files, start=1):
        cache_extra = {"kind": "color"}
        cached = _load_cached_df(cache_dir, "color", fp, cache_extra) if (use_cache_read and cache_dir) else None
        if cached is not None:
            rows.extend(cached.to_dict("records"))
            cache_hits += 1
            if progress:
                progress(progress_base + progress_span * idx / total, f"Color parsing {idx}/{len(files)}")
            continue

        raw_lines = fp.read_text(encoding="utf-8", errors="ignore").splitlines(True)
        file_ts, product, thickness_mm = extract_metadata(raw_lines)
        if not file_ts or not product:
            if progress:
                progress(progress_base + progress_span * idx / total, f"Color parsing {idx}/{len(files)}")
            continue
        meas = extract_measurements_optoplex(raw_lines)
        if not meas:
            if progress:
                progress(progress_base + progress_span * idx / total, f"Color parsing {idx}/{len(files)}")
            continue

        dfm = pd.DataFrame([m.__dict__ for m in meas])
        dfm = dfm.groupby(["plate", "device", "position_mm"], as_index=False)[["L", "a", "b"]].mean()
        file_rows: List[Dict[str, object]] = []
        for plate, dplate in dfm.groupby("plate", as_index=False):
            file_rows.append(build_color_row(file_ts.date(), file_ts, int(plate), product, thickness_mm, dplate))
        rows.extend(file_rows)
        if use_cache_write and cache_dir and file_rows:
            _store_cached_df(cache_dir, "color", fp, pd.DataFrame(file_rows), cache_extra)
        if progress:
            progress(progress_base + progress_span * idx / total, f"Color parsing {idx}/{len(files)}")

    if not rows:
        raise RuntimeError("Nu s-au putut extrage date color (Optoplex).")
    out = pd.DataFrame(rows)
    out["plate"] = pd.to_numeric(out["plate"], errors="coerce").astype("Int64")
    out["day"] = pd.to_datetime(out["day"], errors="coerce").dt.date
    log(f"Color rows: {len(out)}")
    if use_cache_read and cache_dir:
        log(f"Color cache hits: {cache_hits}/{len(files)}")
    return out


def load_process_dataset(files: List[Path], log, progress=None, progress_base: float = 0.0, progress_span: float = 0.0, cache_dir: Optional[Path] = None, use_cache_read: bool = True, use_cache_write: bool = True) -> pd.DataFrame:
    longs: List[pd.DataFrame] = []
    total = max(len(files), 1)
    cache_hits = 0
    cache_extra = {"kind": "process_long"}
    for idx, fp in enumerate(files, start=1):
        cached = _load_cached_df(cache_dir, "process", fp, cache_extra) if (use_cache_read and cache_dir) else None
        if cached is not None:
            longs.append(cached)
            cache_hits += 1
            if progress:
                progress(progress_base + progress_span * idx / total, f"Process parsing {idx}/{len(files)}")
            continue

        raw = pd.read_csv(fp, sep=";", engine="c", low_memory=False)
        if not {"Location", "glassId", "optoplexGTime"}.issubset(raw.columns):
            if progress:
                progress(progress_base + progress_span * idx / total, f"Process parsing {idx}/{len(files)}")
            continue
        long_one = _prepare_long(raw)
        longs.append(long_one)
        if use_cache_write and cache_dir:
            _store_cached_df(cache_dir, "process", fp, long_one, cache_extra)
        if progress:
            progress(progress_base + progress_span * idx / total, f"Process parsing {idx}/{len(files)}")

    if not longs:
        raise RuntimeError("Nu s-au putut extrage date process (glassFile).")

    long_all = pd.concat(longs, ignore_index=True)
    long_all = long_all.sort_values(["ts", "plate", "comp"]).groupby(["ts", "plate", "comp"], as_index=False).first()
    wide = _pivot_wide(long_all)
    # De-fragment before adding/sorting key columns to avoid pandas PerformanceWarning
    wide = wide.copy()
    comp_cols = [c for c in wide.columns if c.startswith("c") and "." in c]
    rel_comps = sorted({int(c.split(".", 1)[0][1:]) for c in comp_cols if c.split(".", 1)[0][1:].isdigit()})
    log(f"Relevant compartments in output: {len(rel_comps)}")
    if use_cache_read and cache_dir:
        log(f"Process cache hits: {cache_hits}/{len(files)}")

    wide["day"] = pd.to_datetime(wide["ts"], errors="coerce").dt.date
    wide["plate"] = pd.to_numeric(wide["plate"], errors="coerce").astype("Int64")

    # Reduce to one row /(day, plate): keep first chronological snapshot for merge stability
    wide = wide.sort_values(["day", "plate", "ts"]).groupby(["day", "plate"], as_index=False).first()
    log(f"Process rows (day,plate): {len(wide)}")
    return wide


def _format_for_ml(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize merged dataset for ML-friendly training/serving use."""
    out = df.copy()

    if "day" in out.columns:
        day_dt = pd.to_datetime(out["day"], errors="coerce")
        out["day"] = day_dt.dt.date
        out["dayOfWeek"] = day_dt.dt.dayofweek.astype("Int64")
        out["month"] = day_dt.dt.month.astype("Int64")
        out["weekOfYear"] = day_dt.dt.isocalendar().week.astype("Int64")

    if "plate" in out.columns:
        out["plate"] = pd.to_numeric(out["plate"], errors="coerce").astype("Int64")

    categorical_cols = [c for c in out.columns if c in {"product"} or c.endswith("actTargetMaterial1") or c.endswith("actTargetMaterial2")]
    for c in categorical_cols:
        out[c] = out[c].astype("string")

    # Keep a stable, deterministic column order for reproducible ML pipelines.
    priority = [c for c in ["day", "plate", "file_ts", "product", "dayOfWeek", "month", "weekOfYear"] if c in out.columns]
    rest = sorted([c for c in out.columns if c not in priority])
    out = out[priority + rest]
    return out


def run_merge(cfg: MergeConfig, log, progress=None) -> Path:
    if progress:
        progress(0.01, "Scanning files")
    color_files = find_files(cfg.optoplex_dir, "*.csv", cfg.recursive, cfg.year_filter)
    proc_files = find_files(cfg.process_dir, "*_glassFile.csv", cfg.recursive, cfg.year_filter)
    log(f"Optoplex files: {len(color_files)}")
    log(f"Glass/process files: {len(proc_files)}")
    if progress:
        progress(0.08, "Files scanned")

    cache_dir = cfg.cache_dir or (cfg.output_path.parent / ".merge_cache")
    if cfg.use_cache_read or cfg.use_cache_write:
        log(f"Cache dir: {cache_dir}")
        log(f"Cache read/write: {cfg.use_cache_read}/{cfg.use_cache_write}")
    color_df = load_color_dataset(
        color_files,
        log,
        progress=progress,
        progress_base=0.08,
        progress_span=0.42,
        cache_dir=cache_dir,
        use_cache_read=cfg.use_cache_read,
        use_cache_write=cfg.use_cache_write,
    )
    proc_df = load_process_dataset(
        proc_files,
        log,
        progress=progress,
        progress_base=0.50,
        progress_span=0.40,
        cache_dir=cache_dir,
        use_cache_read=cfg.use_cache_read,
        use_cache_write=cfg.use_cache_write,
    )
    if progress:
        progress(0.92, "Merging datasets")

    merged = color_df.merge(proc_df, on=["day", "plate"], how=cfg.merge_how, suffixes=("", "_process"))
    merged = merged.sort_values(["day", "plate"]).reset_index(drop=True)
    if cfg.ml_ready:
        merged = _format_for_ml(merged)
        log("Applied ML-ready formatting (types + calendar features + stable column order).")
    log(f"Merged rows: {len(merged)}")

    out = cfg.output_path
    out.parent.mkdir(parents=True, exist_ok=True)

    if cfg.output_format == "parquet":
        if out.suffix.lower() != ".parquet":
            out = out.with_suffix(".parquet")
        merged.to_parquet(out, index=False, compression=cfg.compression)
    else:
        if out.suffix.lower() != ".csv":
            out = out.with_suffix(".csv")
        merged.to_csv(out, index=False)

    log(f"[OK] Saved: {out}")
    if progress:
        progress(1.0, "Done")
    return out


# ========
# UI layer
# ========
class MergerApp:
    def __init__(self, root: Tk):
        self.root = root
        root.title("Optoplex + GlassFile Merger")
        root.geometry("980x620")

        self.opt_dir = StringVar()
        self.proc_dir = StringVar()
        self.out_path = StringVar()
        self.year_filter = StringVar(value="")
        self.format_var = StringVar(value="parquet")
        self.comp_var = StringVar(value="snappy")
        self.merge_var = StringVar(value="inner")
        self.recursive_var = IntVar(value=1)
        self.cache_read_var = IntVar(value=1)
        self.cache_write_var = IntVar(value=1)
        self.cache_dir_var = StringVar(value="")
        self.ml_ready_var = IntVar(value=1)
        self.progress_var = DoubleVar(value=0.0)
        self.status_var = StringVar(value="Ready")
        self.run_btn: Optional[Button] = None

        self._build_form()

    def _build_row(self, parent: Frame, label: str, var: StringVar, browse_cmd):
        row = Frame(parent)
        row.pack(fill=BOTH, padx=8, pady=4)
        Label(row, text=label, width=22, anchor=W).pack(side=LEFT)
        Entry(row, textvariable=var).pack(side=LEFT, fill=BOTH, expand=True, padx=6)
        Button(row, text="Browse", command=browse_cmd).pack(side=RIGHT)

    def _build_form(self):
        top = Frame(self.root)
        top.pack(fill=BOTH, padx=8, pady=8)

        self._build_row(top, "Optoplex folder", self.opt_dir, self._pick_opt_dir)
        self._build_row(top, "Glass/process folder", self.proc_dir, self._pick_proc_dir)
        self._build_row(top, "Output file", self.out_path, self._pick_out_file)
        self._build_row(top, "Cache folder (optional)", self.cache_dir_var, self._pick_cache_dir)

        row = Frame(top)
        row.pack(fill=BOTH, padx=8, pady=4)
        Label(row, text="Year filter (optional)", width=22, anchor=W).pack(side=LEFT)
        Entry(row, textvariable=self.year_filter, width=12).pack(side=LEFT, padx=6)
        Checkbutton(row, text="Recursive scan (rglob)", variable=self.recursive_var).pack(side=LEFT, padx=12)

        row_cache = Frame(top)
        row_cache.pack(fill=BOTH, padx=8, pady=4)
        Label(row_cache, text="Cache options", width=22, anchor=W).pack(side=LEFT)
        Checkbutton(row_cache, text="Use cache (read)", variable=self.cache_read_var).pack(side=LEFT, padx=6)
        Checkbutton(row_cache, text="Save cache (write)", variable=self.cache_write_var).pack(side=LEFT, padx=6)
        Checkbutton(row_cache, text="ML-ready format", variable=self.ml_ready_var).pack(side=LEFT, padx=6)

        row2 = Frame(top)
        row2.pack(fill=BOTH, padx=8, pady=4)
        Label(row2, text="Output format", width=22, anchor=W).pack(side=LEFT)
        Combobox(row2, textvariable=self.format_var, values=["parquet", "csv"], width=12, state="readonly").pack(side=LEFT, padx=6)

        Label(row2, text="Compression", width=12, anchor=W).pack(side=LEFT, padx=(16, 0))
        Combobox(row2, textvariable=self.comp_var, values=["snappy", "zstd", "gzip"], width=12, state="readonly").pack(side=LEFT, padx=6)

        Label(row2, text="Merge type", width=10, anchor=W).pack(side=LEFT, padx=(16, 0))
        Combobox(row2, textvariable=self.merge_var, values=["inner", "left", "outer"], width=10, state="readonly").pack(side=LEFT, padx=6)

        self.run_btn = Button(top, text="Run merge", command=self._start_run)
        self.run_btn.pack(anchor=W, padx=8, pady=8)

        pframe = Frame(top)
        pframe.pack(fill=BOTH, padx=8, pady=4)
        Progressbar(pframe, variable=self.progress_var, maximum=100.0).pack(side=LEFT, fill=BOTH, expand=True)
        Label(pframe, textvariable=self.status_var, width=28, anchor=W).pack(side=LEFT, padx=8)

        self.log_box = ScrolledText(self.root, height=22)
        self.log_box.pack(fill=BOTH, expand=True, padx=10, pady=8)

    def _pick_opt_dir(self):
        d = filedialog.askdirectory(title="Select Optoplex root folder")
        if d:
            self.opt_dir.set(d)

    def _pick_proc_dir(self):
        d = filedialog.askdirectory(title="Select glass/process root folder")
        if d:
            self.proc_dir.set(d)

    def _pick_out_file(self):
        p = filedialog.asksaveasfilename(title="Output merged file", defaultextension=".parquet")
        if p:
            self.out_path.set(p)

    def _pick_cache_dir(self):
        d = filedialog.askdirectory(title="Select cache folder")
        if d:
            self.cache_dir_var.set(d)

    def _log(self, msg: str):
        self.log_box.insert(END, msg + "\n")
        self.log_box.see(END)
        self.root.update_idletasks()

    def _set_progress(self, ratio: float, status: str):
        pct = max(0.0, min(100.0, ratio * 100.0))
        self.progress_var.set(pct)
        self.status_var.set(f"{status} ({pct:.1f}%)")
        self.root.update_idletasks()

    def _set_running(self, running: bool):
        if self.run_btn:
            self.run_btn.config(state="disabled" if running else "normal")

    def _start_run(self):
        opt_dir_raw = self.opt_dir.get().strip()
        proc_dir_raw = self.proc_dir.get().strip()
        out_path_raw = self.out_path.get().strip()

        if not opt_dir_raw or not proc_dir_raw or not out_path_raw:
            messagebox.showerror("Invalid input", "Completează folderele de input și fișierul de output.")
            return

        cache_dir_raw = self.cache_dir_var.get().strip()
        cfg = MergeConfig(
            optoplex_dir=Path(opt_dir_raw),
            process_dir=Path(proc_dir_raw),
            output_path=Path(out_path_raw),
            output_format=self.format_var.get(),
            recursive=bool(self.recursive_var.get()),
            year_filter=self.year_filter.get().strip() or None,
            compression=self.comp_var.get(),
            merge_how=self.merge_var.get(),
            use_cache_read=bool(self.cache_read_var.get()),
            use_cache_write=bool(self.cache_write_var.get()),
            cache_dir=Path(cache_dir_raw) if cache_dir_raw else None,
            ml_ready=bool(self.ml_ready_var.get()),
        )

        if not cfg.optoplex_dir.exists() or not cfg.process_dir.exists() or cfg.output_path.is_dir():
            messagebox.showerror("Invalid input", "Verifică folderele de input și fișierul de output.")
            return
        if cfg.cache_dir and cfg.cache_dir.exists() and not cfg.cache_dir.is_dir():
            messagebox.showerror("Invalid input", "Calea de cache trebuie să fie un folder valid.")
            return

        self._set_running(True)
        self._set_progress(0.0, "Starting")

        def ui_progress(ratio: float, status: str):
            self.root.after(0, lambda: self._set_progress(ratio, status))

        def worker():
            try:
                out = run_merge(cfg, self._log, progress=ui_progress)
                self.root.after(0, lambda: messagebox.showinfo("Done", f"Merge finalizat.\n{out}"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"[ERROR] {e}"))
                self.root.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.root.after(0, lambda: self._set_running(False))

        threading.Thread(target=worker, daemon=True).start()


def main() -> None:
    ap = argparse.ArgumentParser(description="Merge Optoplex color + glass process into one wide dataset.")
    ap.add_argument("--gui", action="store_true", help="Launch desktop UI")
    ap.add_argument("--optoplex-dir", type=str, help="Root folder for Optoplex CSV files")
    ap.add_argument("--process-dir", type=str, help="Root folder for *_glassFile.csv files")
    ap.add_argument("--out", type=str, help="Merged output file path")
    ap.add_argument("--format", choices=["parquet", "csv"], default="parquet")
    ap.add_argument("--compression", choices=["snappy", "zstd", "gzip"], default="snappy")
    ap.add_argument("--merge-how", choices=["inner", "left", "outer"], default="inner")
    ap.add_argument("--year", type=str, default="", help="Optional path-part year filter, ex: 2025")
    ap.add_argument("--cache-dir", type=str, default="", help="Optional cache directory path")
    ap.add_argument("--no-cache-read", action="store_true", help="Disable reading from cache")
    ap.add_argument("--no-cache-write", action="store_true", help="Disable writing cache")
    ap.add_argument("--no-ml-ready", action="store_true", help="Disable ML-ready formatting")
    ap.add_argument("--no-recursive", action="store_true", help="Disable recursive file scan")
    args = ap.parse_args()

    if args.gui or not (args.optoplex_dir and args.process_dir and args.out):
        root = Tk()
        MergerApp(root)
        root.mainloop()
        return

    cfg = MergeConfig(
        optoplex_dir=Path(args.optoplex_dir),
        process_dir=Path(args.process_dir),
        output_path=Path(args.out),
        output_format=args.format,
        recursive=not args.no_recursive,
        year_filter=args.year or None,
        compression=args.compression,
        merge_how=args.merge_how,
        use_cache_read=not args.no_cache_read,
        use_cache_write=not args.no_cache_write,
        cache_dir=Path(args.cache_dir) if args.cache_dir else None,
        ml_ready=not args.no_ml_ready,
    )
    run_merge(cfg, print)


if __name__ == "__main__":
    main()
