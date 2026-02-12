from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional


from glass_processor_constants import (
    FINAL_COLS,
    KEEP_COMPS,
    NO_ROUND,
    SRC_AR,
    SRC_DATE,
    SRC_LOC,
    SRC_N2,
    SRC_NOMGASSEG,
    SRC_O2,
    SRC_PLATE,
)
from glass_processor_discovery import list_files_by_days
from glass_processor_parsing import (
    find_col_idx,
    parse_comp_to_int,
    round2_str,
    safe_get,
    sniff_delim_from_line,
    to_date_ymd,
)


def stream_to_tmp_csv(
    input_root: Path,
    start_d: date,
    end_d: date,
    pattern: str,
    tmp_csv: Path,
    flush_rows: int = 200_000,
) -> int:
    files = list_files_by_days(input_root, start_d, end_d, pattern)
    if not files:
        raise SystemExit(f"No files matched in range: {start_d}..{end_d} under {input_root} / {pattern}")

    tmp_csv.parent.mkdir(parents=True, exist_ok=True)

    buffers: Dict[str, List[str]] = {c: [] for c in FINAL_COLS}
    total = 0

    def flush(writer: csv.writer) -> None:
        n = len(next(iter(buffers.values()))) if buffers else 0
        if n == 0:
            return
        writer.writerows(zip(*(buffers[c] for c in FINAL_COLS)))
        for c in FINAL_COLS:
            buffers[c].clear()

    with open(tmp_csv, "w", newline="", encoding="utf-8") as wf:
        w = csv.writer(wf)
        w.writerow(FINAL_COLS)

        for fi, f in enumerate(files, start=1):
            with open(f, "r", encoding="utf-8", errors="replace", newline="") as rf:
                first_line = rf.readline()
                if not first_line:
                    continue
                delim = sniff_delim_from_line(first_line)
                rf.seek(0)

                r = csv.reader(rf, delimiter=delim)
                try:
                    header = next(r)
                except StopIteration:
                    continue

                # Required columns
                idx_date = find_col_idx(header, SRC_DATE)
                idx_plate = find_col_idx(header, SRC_PLATE)
                idx_loc = find_col_idx(header, SRC_LOC)
                idx_nomseg = find_col_idx(header, SRC_NOMGASSEG)

                if idx_date is None or idx_plate is None or idx_loc is None:
                    print(f"[SKIP] {f} missing required columns (optoplexGTime/glassId/Location)")
                    continue
                if idx_nomseg is None:
                    print(f"[SKIP] {f} missing required column (nomGasSegment) - add it in raw export")
                    continue

                # Regular column indices
                idx_map: Dict[str, Optional[int]] = {
                    "nomGasSegment": idx_nomseg,
                    "nomProcessSpeed_mm": find_col_idx(header, "nomProcessSpeed_mm"),
                    "glassThickness": find_col_idx(header, "glassThickness"),
                    "actTargetMaterial1": find_col_idx(header, "actTargetMaterial1"),
                    "actPower": find_col_idx(header, "actPower"),
                    "actPowerPMF": find_col_idx(header, "actPowerPMF"),
                    "actCurrent": find_col_idx(header, "actCurrent"),
                    "actCurrentIMF": find_col_idx(header, "actCurrentIMF"),
                    "actSigmaCurrent": find_col_idx(header, "actSigmaCurrent"),
                    "actVoltage": find_col_idx(header, "actVoltage"),
                    "actVoltageUMF": find_col_idx(header, "actVoltageUMF"),
                    "actSigmaVoltage": find_col_idx(header, "actSigmaVoltage"),
                    "actArcRate1": find_col_idx(header, "actArcRate1"),
                    "actFreq": find_col_idx(header, "actFreq"),
                    "actVacuumPressure": find_col_idx(header, "actVacuumPressure"),
                    "actHArc": find_col_idx(header, "actHArc"),
                    "actSArc": find_col_idx(header, "actSArc"),
                    "actSArcB": find_col_idx(header, "actSArcB"),
                    "actWaterFlowShielding": find_col_idx(header, "actWaterFlowShielding"),
                    "actWaterFlowSurround": find_col_idx(header, "actWaterFlowSurround"),
                }

                for k in range(1, 12):
                    col = f"actSegGas{k}Flow"
                    idx_map[col] = find_col_idx(header, col)

                # Main gases -> renamed
                idx_ar = find_col_idx(header, SRC_AR)
                idx_n2 = find_col_idx(header, SRC_N2)
                idx_o2 = find_col_idx(header, SRC_O2)

                for row in r:
                    comp_int = parse_comp_to_int(safe_get(row, idx_loc))
                    if comp_int is None or comp_int not in KEEP_COMPS:
                        continue

                    # base keys
                    buffers["date"].append(to_date_ymd(safe_get(row, idx_date)))
                    buffers["plate"].append(safe_get(row, idx_plate))
                    buffers["comp"].append(str(comp_int))

                    # nomGasSegment (as-is, no rounding)
                    buffers["nomGasSegment"].append(safe_get(row, idx_nomseg))

                    # regular columns (everything else except keys and renamed gases)
                    for col in FINAL_COLS:
                        if col in ("date", "plate", "comp", "nomGasSegment", "Ar_flow", "N2_flow", "O2_flow"):
                            continue
                        v = safe_get(row, idx_map.get(col))
                        if col not in NO_ROUND:
                            v = round2_str(v)
                        buffers[col].append(v)

                    # renamed gases (rounded to 2 decimals)
                    buffers["Ar_flow"].append(round2_str(safe_get(row, idx_ar)))
                    buffers["N2_flow"].append(round2_str(safe_get(row, idx_n2)))
                    buffers["O2_flow"].append(round2_str(safe_get(row, idx_o2)))

                    total += 1
                    if total % flush_rows == 0:
                        flush(w)
                        print(f"[FLUSH] rows={total:,} | files_done={fi}")

            if fi % 25 == 0 or fi == len(files):
                print(f"[PROGRESS] files_done={fi}/{len(files)} | rows={total:,}")

        flush(w)

    print(f"[OK] tmp CSV built: {tmp_csv} | rows={total:,}")
    return total


def tmp_csv_to_excel(tmp_csv: Path, out_xlsx: Path) -> None:
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise SystemExit("Missing dependency: pandas (and openpyxl engine) is required for Excel export.") from exc

    df = pd.read_csv(tmp_csv, dtype=str)
    out_xlsx.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="ALL", index=False)
    print(f"[OK] Excel written: {out_xlsx} | rows={len(df):,}")
