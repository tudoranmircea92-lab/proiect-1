from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.app.data.schema_contract import (
    DATE_CANDIDATES,
    FILE_TS_CANDIDATES,
    PLATE_KEY_CANDIDATES,
    TIME_CANDIDATES,
    TRAINING_ROW_DEFINITION,
    detect_target_columns,
    is_knob_column,
)
from backend.app.services.io_utils import load_table


def _find_first(columns: list[str], candidates: list[str]) -> str | None:
    for c in candidates:
        if c in columns:
            return c
    lowered = {c.lower(): c for c in columns}
    for c in candidates:
        if c.lower() in lowered:
            return lowered[c.lower()]
    return None


def _coerce_keys(df: pd.DataFrame, plate_col: str | None, ts_col: str | None, date_col: str | None, time_col: str | None) -> pd.DataFrame:
    out = df.copy()
    if plate_col and plate_col != 'plate':
        out = out.rename(columns={plate_col: 'plate'})
    if ts_col:
        if ts_col != 'file_ts':
            out = out.rename(columns={ts_col: 'file_ts'})
        out['file_ts'] = pd.to_datetime(out['file_ts'], errors='coerce')
    else:
        if date_col and date_col != 'date':
            out = out.rename(columns={date_col: 'date'})
        if time_col and time_col != 'time':
            out = out.rename(columns={time_col: 'time'})
        if 'date' in out.columns:
            out['date'] = out['date'].astype(str)
        if 'time' in out.columns:
            out['time'] = out['time'].astype(str)
    if 'plate' in out.columns:
        out['plate'] = out['plate'].astype(str)
    return out


def detect_schema_metadata(df: pd.DataFrame, dataset_name: str) -> dict:
    cols = df.columns.tolist()
    plate_col = _find_first(cols, PLATE_KEY_CANDIDATES)
    ts_col = _find_first(cols, FILE_TS_CANDIDATES)
    date_col = _find_first(cols, DATE_CANDIDATES)
    time_col = _find_first(cols, TIME_CANDIDATES)

    dataset_kind = 'wide' if len(cols) > 300 else 'long'
    role = 'color' if len(detect_target_columns(cols)) >= 3 else 'process'

    target_cols = detect_target_columns(cols)
    key_cols = [c for c in ['plate', 'file_ts', 'date', 'time'] if c in _coerce_keys(df.head(1), plate_col, ts_col, date_col, time_col).columns]

    knob_cols = sorted([c for c in cols if is_knob_column(c)])
    feature_cols = [c for c in cols if c not in set([plate_col, ts_col, date_col, time_col]) and c not in set(target_cols)]

    return {
        'dataset_name': dataset_name,
        'dataset_role': role,
        'dataset_kind': dataset_kind,
        'rows': int(len(df)),
        'cols': int(len(cols)),
        'key_columns_detected': {'plate': plate_col, 'file_ts': ts_col, 'date': date_col, 'time': time_col},
        'keys_found': [k for k, v in {'plate': plate_col, 'file_ts': ts_col, 'date': date_col, 'time': time_col}.items() if v],
        'feature_count': int(len(feature_cols)),
        'detected_knobs': knob_cols,
        'detected_targets': target_cols,
        'training_row_definition': TRAINING_ROW_DEFINITION,
    }


def split_process_color_paths(paths: list[str]) -> tuple[str | None, str | None]:
    process = None
    color = None
    for p in paths:
        low = Path(p).name.lower()
        if 'color' in low and color is None:
            color = p
        elif process is None:
            process = p
    if process is None and paths:
        process = paths[0]
    if color is None and len(paths) > 1:
        color = paths[1]
    return process, color


def load_process(source_path: str, mode: str = 'auto') -> pd.DataFrame:
    df = load_table(source_path)
    md = detect_schema_metadata(df, 'process')
    if mode != 'auto' and md['dataset_kind'] != mode:
        raise ValueError(f'Process dataset mode mismatch: expected {mode}, detected {md["dataset_kind"]}')
    keys = md['key_columns_detected']
    return _coerce_keys(df, keys['plate'], keys['file_ts'], keys['date'], keys['time'])


def load_color(color_path: str, mode: str = 'auto') -> pd.DataFrame:
    df = load_table(color_path)
    md = detect_schema_metadata(df, 'color')
    if mode != 'auto' and md['dataset_kind'] != mode:
        raise ValueError(f'Color dataset mode mismatch: expected {mode}, detected {md["dataset_kind"]}')
    keys = md['key_columns_detected']
    out = _coerce_keys(df, keys['plate'], keys['file_ts'], keys['date'], keys['time'])
    targets = detect_target_columns(out.columns.tolist())
    keep = [c for c in ['plate', 'file_ts', 'date', 'time'] if c in out.columns] + targets
    return out[keep].copy()


def _merge_key_strategy(process_df: pd.DataFrame, color_df: pd.DataFrame, key_strategy: str) -> tuple[list[str], str]:
    if key_strategy in {'auto', 'plate+file_ts'} and {'plate', 'file_ts'}.issubset(process_df.columns) and {'plate', 'file_ts'}.issubset(color_df.columns):
        return ['plate', 'file_ts'], 'plate+file_ts'
    if {'plate', 'date', 'time'}.issubset(process_df.columns) and {'plate', 'date', 'time'}.issubset(color_df.columns):
        return ['plate', 'date', 'time'], 'plate+date+time'
    raise ValueError('No compatible merge key strategy found. Need plate+file_ts or plate+date+time')


def build_training_table(process_df: pd.DataFrame, color_df: pd.DataFrame, key_strategy: str = 'auto') -> tuple[pd.DataFrame, dict]:
    join_keys, selected_strategy = _merge_key_strategy(process_df, color_df, key_strategy)

    before_proc = len(process_df)
    before_col = len(color_df)

    proc = process_df.dropna(subset=['plate']).copy()
    col = color_df.dropna(subset=['plate']).copy()

    merged = proc.merge(col, on=join_keys, how='inner', suffixes=('', '_y'))
    merged = merged.loc[:, ~merged.columns.duplicated()]

    targets = detect_target_columns(merged.columns.tolist())
    drop_reasons = {
        'process_rows_input': int(before_proc),
        'color_rows_input': int(before_col),
        'process_rows_after_plate_filter': int(len(proc)),
        'color_rows_after_plate_filter': int(len(col)),
        'merged_rows': int(len(merged)),
        'dropped_due_to_unmatched_keys': int(max(0, min(len(proc), len(col)) - len(merged))),
    }

    if not targets:
        raise ValueError('No target columns detected in merged training table')

    return merged, {
        'key_strategy': selected_strategy,
        'join_keys': join_keys,
        'targets': targets,
        'dropped_rows': drop_reasons,
    }
