from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd


_COMP_RE = re.compile(r"(\d+)")


def _norm_material(value: object) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    su = s.upper()
    empty_tokens = {"NAN", "NONE", "NULL", "N/A", "NA", "-", "--", "---", "0", "0.0", "EMPTY"}
    if su in empty_tokens:
        return None
    return su


def _extract_compartment(location: object) -> Optional[int]:
    if location is None:
        return None
    m = _COMP_RE.search(str(location))
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def _first_existing_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if c in df.columns:
            return c
    return None


def _parse_optoplex_time_to_day(series: pd.Series) -> pd.Series:
    s = (
        series.astype(str)
        .str.replace(r"\D+", "", regex=True)
        .str.slice(0, 14)
    )
    dt = pd.to_datetime(s, format="%Y%m%d%H%M%S", errors="coerce")
    return dt.dt.strftime("%Y-%m-%d")


def _read_glass_csv(fp: Path) -> Optional[pd.DataFrame]:
    try:
        try:
            return pd.read_csv(
                fp,
                sep=";",
                engine="python",
                on_bad_lines="skip",
                encoding="utf-8",
                encoding_errors="ignore",
            )
        except TypeError:
            return pd.read_csv(
                fp,
                sep=";",
                engine="python",
                on_bad_lines="skip",
                encoding="utf-8",
            )
    except Exception:
        return None


def _build_file_plate_frame(
    raw: pd.DataFrame,
    keep_material_only: bool,
    include_seg_gas: bool,
    include_material_gas: bool,
) -> Tuple[Optional[pd.DataFrame], Set[int]]:
    required = {"glassId", "optoplexGTime", "Location"}
    if not required.issubset(raw.columns):
        return None, set()

    working = pd.DataFrame(
        {
            "day": _parse_optoplex_time_to_day(raw["optoplexGTime"]),
            "plate": pd.to_numeric(raw["glassId"], errors="coerce").astype("Int64"),
            "comp": raw["Location"].map(_extract_compartment).astype("Int64"),
        }
    )

    if "actFreq" in raw.columns:
        working["actFreq"] = pd.to_numeric(raw["actFreq"], errors="coerce")
    if "actVacuumPressure" in raw.columns:
        working["actVacuumPressure"] = pd.to_numeric(raw["actVacuumPressure"], errors="coerce")
    if "nomProcessSpeed_mm" in raw.columns:
        working["nomProcessSpeed_mm"] = pd.to_numeric(raw["nomProcessSpeed_mm"], errors="coerce")
    elif "nomProcessSpeed" in raw.columns:
        working["nomProcessSpeed_mm"] = pd.to_numeric(raw["nomProcessSpeed"], errors="coerce")

    if "actTargetMaterial1" in raw.columns:
        working["actTargetMaterial1"] = raw["actTargetMaterial1"].map(_norm_material)
    else:
        working["actTargetMaterial1"] = None

    if "actTargetMaterial2" in raw.columns:
        working["actTargetMaterial2"] = raw["actTargetMaterial2"].map(_norm_material)
    else:
        working["actTargetMaterial2"] = None

    if "actTarget1KWH" in raw.columns:
        working["actTarget1KWH"] = pd.to_numeric(raw["actTarget1KWH"], errors="coerce")
    if "actTarget2KWH" in raw.columns:
        working["actTarget2KWH"] = pd.to_numeric(raw["actTarget2KWH"], errors="coerce")

    if "actPower" in raw.columns:
        working["actPower"] = pd.to_numeric(raw["actPower"], errors="coerce")
    if "actVoltageUMF" in raw.columns:
        working["actVoltageUMF"] = pd.to_numeric(raw["actVoltageUMF"], errors="coerce")
    if "actCurrentIMF" in raw.columns:
        working["actCurrentIMF"] = pd.to_numeric(raw["actCurrentIMF"], errors="coerce")

    if include_seg_gas:
        for i in range(1, 12):
            src = f"actSegGas{i}Flow"
            if src in raw.columns:
                working[src] = pd.to_numeric(raw[src], errors="coerce")

    if include_material_gas:
        gas_sources = {
            "mainGas1": ["Ar_flow", "mainGas1", "mainGas1Flow", "actMainGas1Flow"],
            "mainGas2": ["N2_flow", "mainGas2", "mainGas2Flow", "actMainGas2Flow"],
            "mainGas3": ["O2_flow", "mainGas3", "mainGas3Flow", "actMainGas3Flow"],
        }
        for tgt, candidates in gas_sources.items():
            src = _first_existing_column(raw, candidates)
            if src:
                working[tgt] = pd.to_numeric(raw[src], errors="coerce")

    working = working.dropna(subset=["day", "plate", "comp"]).copy()
    if working.empty:
        return None, set()

    keys = ["day", "plate"]
    globals_cols = [c for c in ["actFreq", "actVacuumPressure", "nomProcessSpeed_mm"] if c in working.columns]
    if not globals_cols:
        plate_global = working[keys].drop_duplicates().copy()
    else:
        agg_globals = {c: "mean" for c in globals_cols}
        plate_global = working.groupby(keys, as_index=False).agg(agg_globals)

    # Detect relevant compartments by material presence
    if keep_material_only:
        mat1_non_empty = working["actTargetMaterial1"].notna()
        mat2_non_empty = working["actTargetMaterial2"].notna()
        rel = working.loc[mat1_non_empty | mat2_non_empty, "comp"].dropna().astype(int)
        relevant_comps = set(rel.tolist())
    else:
        relevant_comps = set(working["comp"].dropna().astype(int).tolist())

    comp_frames: List[pd.DataFrame] = []

    for comp in sorted(relevant_comps):
        dcomp = working[working["comp"] == comp]
        if dcomp.empty:
            continue

        feature_map: Dict[str, str] = {}

        if "actPower" in dcomp.columns:
            feature_map["actPower"] = f"c{comp}.pwr"
        if "actVoltageUMF" in dcomp.columns:
            feature_map["actVoltageUMF"] = f"c{comp}.voltage"
        if "actCurrentIMF" in dcomp.columns:
            feature_map["actCurrentIMF"] = f"c{comp}.current"

        if include_seg_gas:
            for i in range(1, 12):
                src = f"actSegGas{i}Flow"
                if src in dcomp.columns:
                    feature_map[src] = f"c{comp}.s{i}g"

        if include_material_gas:
            gas_map = {"mainGas1": "mainGas1", "mainGas2": "mainGas2", "mainGas3": "mainGas3"}
            legacy_alias = {"mainGas1": "m1g", "mainGas2": "m2g", "mainGas3": "m3g"}
            for src, target in gas_map.items():
                if src in dcomp.columns:
                    feature_map[src] = f"c{comp}.{target}"
                    feature_map[f"{src}__legacy"] = f"c{comp}.{legacy_alias[src]}"

        feature_map["actTargetMaterial1"] = f"c{comp}.actTargetMaterial1"
        if "actTarget1KWH" in dcomp.columns:
            feature_map["actTarget1KWH"] = f"c{comp}.kwh1"
        has_real_t2 = False
        if "actTargetMaterial2" in dcomp.columns:
            has_real_t2 = dcomp["actTargetMaterial2"].notna().any()
            if has_real_t2:
                feature_map["actTargetMaterial2"] = f"c{comp}.actTargetMaterial2"
        if "actTarget2KWH" in dcomp.columns and has_real_t2:
            feature_map["actTarget2KWH"] = f"c{comp}.kwh2"

        # Expand legacy aliases to duplicate main gas columns in output.
        for synthetic_key in [k for k in feature_map if k.endswith("__legacy")]:
            src = synthetic_key.replace("__legacy", "")
            if src in dcomp.columns:
                dcomp = dcomp.copy()
                dcomp[synthetic_key] = dcomp[src]

        use_cols = [c for c in feature_map if c in dcomp.columns]
        if not use_cols:
            continue

        agg: Dict[str, str] = {}
        for c in use_cols:
            if c in {"actTargetMaterial1", "actTargetMaterial2"}:
                agg[c] = "first"
            else:
                agg[c] = "mean"

        comp_agg = dcomp.groupby(keys, as_index=False).agg(agg)
        comp_agg = comp_agg.rename(columns=feature_map)
        comp_frames.append(comp_agg)

    base = plate_global.set_index(keys)
    pieces = [base]
    for cf in comp_frames:
        pieces.append(cf.set_index(keys))

    final = pd.concat(pieces, axis=1).reset_index()
    return final, relevant_comps


def _cleanup_target_columns(df: pd.DataFrame) -> pd.DataFrame:
    drop_cols = []
    by_comp = {}
    for c in df.columns:
        if not c.startswith("c") or "." not in c:
            continue
        comp, feat = c.split(".", 1)
        by_comp.setdefault(comp, {})[feat] = c

    for _, feats in by_comp.items():
        m1 = feats.get("actTargetMaterial1")
        m2 = feats.get("actTargetMaterial2")
        k1 = feats.get("kwh1")
        k2 = feats.get("kwh2")

        has_m1 = bool(m1) and df[m1].notna().any()
        has_m2 = bool(m2) and df[m2].notna().any()

        if m1 and not has_m1:
            drop_cols.append(m1)
        if k1 and not has_m1:
            drop_cols.append(k1)
        if m2 and not has_m2:
            drop_cols.append(m2)
        if k2 and not has_m2:
            drop_cols.append(k2)

    if drop_cols:
        df = df.drop(columns=sorted(set(drop_cols)), errors="ignore")
    return df


def _round_process_columns(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.columns:
        if c == "actVacuumPressure":
            continue
        if c.startswith("c") and "." in c and c.split(".", 1)[1].startswith("actTargetMaterial"):
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            df[c] = df[c].round(2)
    return df


def build_process_parquet(
    input_dir: Path,
    output_file: Path,
    keep_material_only: bool,
    include_seg_gas: bool,
    include_material_gas: bool,
) -> None:
    files = sorted(input_dir.rglob("*_glassFile.csv"))
    if not files:
        raise SystemExit(f"No *_glassFile.csv files found under: {input_dir}")

    read_ok = 0
    skipped_bad = 0
    detected_relevant: Set[int] = set()
    parts: List[pd.DataFrame] = []

    for fp in files:
        raw = _read_glass_csv(fp)
        if raw is None:
            skipped_bad += 1
            continue

        out_df, relevant = _build_file_plate_frame(
            raw=raw,
            keep_material_only=keep_material_only,
            include_seg_gas=include_seg_gas,
            include_material_gas=include_material_gas,
        )
        if out_df is None or out_df.empty:
            skipped_bad += 1
            continue

        read_ok += 1
        detected_relevant.update(relevant)
        parts.append(out_df)

    if not parts:
        raise SystemExit("No valid process rows produced. All files were skipped or empty.")

    merged = pd.concat(parts, ignore_index=True, sort=False)
    merged = merged.sort_values(["day", "plate"]).groupby(["day", "plate"], as_index=False).first()
    merged = _cleanup_target_columns(merged)
    merged = _round_process_columns(merged)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(output_file, index=False)

    print(f"files ok / skipped: {read_ok} / {skipped_bad}")
    print(f"relevant compartments detected: {len(detected_relevant)}")
    print(f"final shape: {merged.shape}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fast, robust, ML-ready process parquet generator from *glassFile.csv (minimal columns)."
    )
    parser.add_argument("--input", required=True, help="Input folder (recursive scan for *_glassFile.csv)")
    parser.add_argument("--output", required=True, help="Output process.parquet path")

    parser.add_argument(
        "--keep-material-only",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Keep only relevant compartments based on actTargetMaterial1/2 presence (default: true).",
    )
    parser.add_argument(
        "--include-seg-gas",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Include segment gas c{comp}.s1g..s11g if available (default: true).",
    )
    parser.add_argument(
        "--include-material-gas",
        default=True,
        action=argparse.BooleanOptionalAction,
        help="Include material gas c{comp}.mainGas1..mainGas3 (+ legacy c{comp}.m1g..m3g) from available gas columns (default: true).",
    )

    args = parser.parse_args()

    build_process_parquet(
        input_dir=Path(args.input),
        output_file=Path(args.output),
        keep_material_only=bool(args.keep_material_only),
        include_seg_gas=bool(args.include_seg_gas),
        include_material_gas=bool(args.include_material_gas),
    )


if __name__ == "__main__":
    main()
