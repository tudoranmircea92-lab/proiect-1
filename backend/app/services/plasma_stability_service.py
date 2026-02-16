from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from app.models.schemas import PlasmaStabilityRequest
from app.services.json_sanitize import sanitize_jsonable


@dataclass
class PlasmaComputationResult:
    summary: dict[str, float]
    per_cathode: list[dict[str, Any]]
    timeseries: dict[str, list[dict[str, Any]]]
    mode_used: str


class PlasmaStabilityService:
    def __init__(self) -> None:
        self.cache: dict[str, PlasmaComputationResult] = {}
        self.last_result: PlasmaComputationResult | None = None

    def _cache_key(self, req: PlasmaStabilityRequest, dataset_shape: tuple[int, int]) -> str:
        payload = {
            "path_or_dataset_id": req.path_or_dataset_id,
            "mode": req.mode,
            "date_from": req.date_from,
            "date_to": req.date_to,
            "time_from": req.time_from,
            "time_to": req.time_to,
            "active_threshold": req.active_threshold,
            "metrics": sorted(req.metrics),
            "rolling_window_sec": req.rolling_window_sec,
            "agg": req.agg,
            "weights": req.weights,
            "show_inactive": req.show_inactive,
            "shape": dataset_shape,
        }
        return json.dumps(payload, sort_keys=True)

    @staticmethod
    def _safe_cv(series: pd.Series) -> float | None:
        eps = 1e-12
        vals = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
        vals = vals[np.isfinite(vals)]
        if vals.size < 2:
            return None
        mean = float(np.nanmean(vals))
        std = float(np.nanstd(vals, ddof=0))
        return float(std / max(abs(mean), eps)) if np.isfinite(std) else None

    @staticmethod
    def _parse_cathode(col: str) -> str | None:
        m = re.match(r"^(c\d+)\.", col)
        return m.group(1) if m else None

    def _load_external_if_requested(self, req: PlasmaStabilityRequest, fallback_df: pd.DataFrame) -> pd.DataFrame:
        if not req.path_or_dataset_id:
            return fallback_df

        candidate = Path(req.path_or_dataset_id)
        if not candidate.exists() or candidate.name in {"loaded", "current"}:
            return fallback_df

        if candidate.suffix.lower() in {".parquet", ".pq"}:
            return pd.read_parquet(candidate)
        if candidate.suffix.lower() == ".csv":
            return pd.read_csv(candidate)
        raise ValueError("Unsupported file extension in path_or_dataset_id. Use parquet/csv.")

    def _resolve_time_column(self, df: pd.DataFrame) -> str | None:
        for c in ["ts", "file_ts", "timestamp", "time", "datetime"]:
            if c in df.columns:
                return c
        return None

    def _filter_by_date_time(self, df: pd.DataFrame, req: PlasmaStabilityRequest) -> pd.DataFrame:
        time_col = self._resolve_time_column(df)
        if not time_col:
            if "day" in df.columns:
                d = pd.to_datetime(df["day"], errors="coerce")
            else:
                return df.copy()
        else:
            d = pd.to_datetime(df[time_col], errors="coerce")

        date_from = pd.to_datetime(req.date_from)
        date_to = pd.to_datetime(req.date_to) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        mask = (d >= date_from) & (d <= date_to)

        if req.time_from and req.time_to:
            t_from = datetime.strptime(req.time_from, "%H:%M").time()
            t_to = datetime.strptime(req.time_to, "%H:%M").time()
            tod = d.dt.time
            mask = mask & tod.apply(lambda x: x is not pd.NaT and t_from <= x <= t_to)

        out = df.loc[mask].copy()
        out.replace([np.inf, -np.inf], np.nan, inplace=True)
        if out.empty:
            raise ValueError("No records found for selected date/time range.")
        return out

    def _compute_uniformity(self, row: pd.Series, value_cols: list[str], active_cols: list[str]) -> float:
        values = []
        for c in value_cols:
            pwr_col = c.replace(".current", ".pwr") if ".current" in c else c
            if pwr_col in active_cols and float(row.get(pwr_col, 0.0) or 0.0) <= 0:
                continue
            v = row.get(c, None)
            if pd.notna(v):
                values.append(float(v))
        if len(values) < 2:
            return 0.0
        return float(np.std(values) / (abs(np.mean(values)) + 1e-9))

    def _wide_metrics(self, df: pd.DataFrame, req: PlasmaStabilityRequest) -> PlasmaComputationResult:
        pwr_cols = [c for c in df.columns if re.match(r"^c\d+\.pwr$", c)]
        current_cols = [c for c in df.columns if re.match(r"^c\d+\.(current|curr)$", c)]
        voltage_cols = [c for c in df.columns if re.match(r"^c\d+\.(voltage|volt)$", c)]

        cathodes = sorted(list({self._parse_cathode(c) for c in pwr_cols if self._parse_cathode(c)}))
        sigma_cols = [c for c in df.columns if "sigma" in c.lower()]

        per_cathode = []
        for cathode in cathodes:
            p_col = f"{cathode}.pwr"
            cands_cur = [c for c in current_cols if c.startswith(f"{cathode}.")]
            cands_volt = [c for c in voltage_cols if c.startswith(f"{cathode}.")]
            cur_col = cands_cur[0] if cands_cur else None
            volt_col = cands_volt[0] if cands_volt else None

            active_mask = df[p_col].fillna(0.0) > req.active_threshold
            active_rate = float(active_mask.mean()) if len(df) else 0.0
            active_df = df[active_mask] if not req.show_inactive else df
            sample_count = int(len(active_df))

            if sample_count < 1:
                per_cathode.append({"cathode_id": cathode, "cv_current": None, "cv_power": None, "ripple_current": None, "ripple_power": None, "active_rate": 0.0, "sample_count": 0, "n_active_samples": 0})
                continue

            sigma_current_cols = [c for c in sigma_cols if cathode in c and "current" in c.lower()]
            sigma_power_cols = [c for c in sigma_cols if cathode in c and "power" in c.lower()]

            cv_current = None
            cv_power = None
            ripple_current = None
            ripple_power = None

            if sigma_current_cols:
                v = pd.to_numeric(active_df[sigma_current_cols[0]], errors="coerce").to_numpy(dtype=float)
                v = v[np.isfinite(v)]
                cv_current = float(np.nanmean(v)) if v.size else None
                ripple_current = cv_current
            elif cur_col and cur_col in active_df.columns:
                cv_current = self._safe_cv(active_df[cur_col].fillna(0.0))
                ripple_current = cv_current

            if sigma_power_cols:
                v = pd.to_numeric(active_df[sigma_power_cols[0]], errors="coerce").to_numpy(dtype=float)
                v = v[np.isfinite(v)]
                cv_power = float(np.nanmean(v)) if v.size else None
                ripple_power = cv_power
            else:
                cv_power = self._safe_cv(active_df[p_col].fillna(0.0))
                ripple_power = cv_power

            per_cathode.append(
                {
                    "cathode_id": cathode,
                    "cv_current": cv_current,
                    "cv_power": cv_power,
                    "ripple_current": ripple_current,
                    "ripple_power": ripple_power,
                    "active_rate": active_rate,
                    "sample_count": sample_count,
                    "n_active_samples": sample_count,
                }
            )

        vacuum_col = "actVacuumPressure" if "actVacuumPressure" in df.columns else None
        vacuum_cv = self._safe_cv(df[vacuum_col].fillna(0.0)) if vacuum_col else 0.0

        uni_cur_vals, uni_pwr_vals = [], []
        for _, row in df.iterrows():
            if current_cols:
                uni_cur_vals.append(self._compute_uniformity(row, current_cols, pwr_cols))
            if pwr_cols:
                pwr_vals = [float(row.get(c, 0.0) or 0.0) for c in pwr_cols if float(row.get(c, 0.0) or 0.0) > req.active_threshold]
                if len(pwr_vals) > 1:
                    uni_pwr_vals.append(float(np.std(pwr_vals) / (abs(np.mean(pwr_vals)) + 1e-9)))
                else:
                    uni_pwr_vals.append(0.0)

        agg_fn = np.mean if req.agg == "mean" else np.median
        uniformity_cv_current = float(agg_fn(uni_cur_vals)) if uni_cur_vals else 0.0
        uniformity_cv_power = float(agg_fn(uni_pwr_vals)) if uni_pwr_vals else 0.0

        def _agg_metric(name: str) -> float:
            vals = [float(x[name]) for x in per_cathode if x.get(name) is not None and np.isfinite(float(x[name]))]
            return float(agg_fn(vals)) if vals else 0.0

        score = (
            req.weights.get("cv_power", 1.0) * _agg_metric("cv_power")
            + req.weights.get("cv_current", 1.0) * _agg_metric("cv_current")
            + req.weights.get("ripple_power", 0.5) * _agg_metric("ripple_power")
            + req.weights.get("ripple_current", 0.5) * _agg_metric("ripple_current")
            + req.weights.get("vacuum_cv", 0.5) * float(vacuum_cv or 0.0)
            + req.weights.get("uniformity_cv_power", 0.7) * uniformity_cv_power
            + req.weights.get("uniformity_cv_current", 0.7) * uniformity_cv_current
        )

        summary = {
            "overall_stability_score": float(score),
            "vacuum_cv": float(vacuum_cv) if vacuum_cv is not None else None,
            "uniformity_cv_current": float(uniformity_cv_current),
            "uniformity_cv_power": float(uniformity_cv_power),
            "active_cathodes_count": float(sum(1 for r in per_cathode if r["active_rate"] > 0)),
        }

        return PlasmaComputationResult(summary=summary, per_cathode=per_cathode, timeseries={}, mode_used="wide_auto")

    def _timeseries_metrics(self, df: pd.DataFrame, req: PlasmaStabilityRequest) -> PlasmaComputationResult:
        ts_col = self._resolve_time_column(df)
        if not ts_col:
            raise ValueError("Timeseries mode requested but no timestamp column found.")

        cathode_col = next((c for c in ["cathode", "compartment", "cathode_id"] if c in df.columns), None)
        if not cathode_col:
            raise ValueError("Timeseries mode requested but no cathode identifier column found.")

        power_col = next((c for c in ["power", "pwr", "actPower"] if c in df.columns), None)
        current_col = next((c for c in ["current", "curr", "actCurrent"] if c in df.columns), None)
        vacuum_col = next((c for c in ["pressure", "vacuum", "actVacuumPressure"] if c in df.columns), None)

        if not power_col and not current_col:
            raise ValueError("Timeseries data missing power/current columns.")

        work = df.copy()
        work[ts_col] = pd.to_datetime(work[ts_col], errors="coerce")
        work = work.dropna(subset=[ts_col])
        if work.empty:
            raise ValueError("No valid timestamp records in timeseries dataset.")

        per_cathode = []
        ts_out: dict[str, list[dict[str, Any]]] = {}

        for cathode, g in work.groupby(cathode_col):
            g = g.sort_values(ts_col).copy()
            if power_col:
                g["active"] = g[power_col].fillna(0.0) > req.active_threshold
            else:
                g["active"] = True

            if not req.show_inactive:
                g = g[g["active"]]
            if g.empty:
                continue

            g = g.set_index(ts_col)
            roll = g.rolling(f"{req.rolling_window_sec}s", min_periods=2)

            if current_col:
                g["cv_current"] = (roll[current_col].std() / (roll[current_col].mean().abs() + 1e-9)).fillna(0.0)
                g["ripple_current"] = g["cv_current"]
            else:
                g["cv_current"] = 0.0
                g["ripple_current"] = 0.0

            if power_col:
                g["cv_power"] = (roll[power_col].std() / (roll[power_col].mean().abs() + 1e-9)).fillna(0.0)
                g["ripple_power"] = g["cv_power"]
            else:
                g["cv_power"] = 0.0
                g["ripple_power"] = 0.0

            agg_fn = np.mean if req.agg == "mean" else np.median
            per_cathode.append(
                {
                    "cathode_id": str(cathode),
                    "cv_current": float(np.nanmean(g["cv_current"])) if len(g) else None,
                    "cv_power": float(np.nanmean(g["cv_power"])) if len(g) else None,
                    "ripple_current": float(np.nanmean(g["ripple_current"])) if len(g) else None,
                    "ripple_power": float(np.nanmean(g["ripple_power"])) if len(g) else None,
                    "active_rate": float(g["active"].mean()) if "active" in g else 1.0,
                    "sample_count": int(len(g)),
                }
            )

            reset = g.reset_index()
            downsample_step = max(1, int(len(reset) / 300))
            reset = reset.iloc[::downsample_step]
            ts_out[str(cathode)] = [
                {
                    "ts": r[ts_col].isoformat() if pd.notna(r[ts_col]) else None,
                    "cv_power": float(r["cv_power"]),
                    "cv_current": float(r["cv_current"]),
                    "ripple_power": float(r["ripple_power"]),
                    "ripple_current": float(r["ripple_current"]),
                }
                for _, r in reset.iterrows()
            ]

        vacuum_cv = self._safe_cv(work[vacuum_col].fillna(0.0)) if vacuum_col else 0.0
        agg_fn = np.mean if req.agg == "mean" else np.median
        vals_cur = [float(x["cv_current"]) for x in per_cathode if x.get("cv_current") is not None]
        vals_pwr = [float(x["cv_power"]) for x in per_cathode if x.get("cv_power") is not None]
        uniformity_cv_current = float(agg_fn(vals_cur)) if vals_cur else 0.0
        uniformity_cv_power = float(agg_fn(vals_pwr)) if vals_pwr else 0.0

        def _agg_metric(name: str) -> float:
            vals = [float(x[name]) for x in per_cathode if x.get(name) is not None]
            return float(agg_fn(vals)) if vals else 0.0

        score = (
            req.weights.get("cv_power", 1.0) * _agg_metric("cv_power")
            + req.weights.get("cv_current", 1.0) * _agg_metric("cv_current")
            + req.weights.get("ripple_power", 0.5) * _agg_metric("ripple_power")
            + req.weights.get("ripple_current", 0.5) * _agg_metric("ripple_current")
            + req.weights.get("vacuum_cv", 0.5) * float(vacuum_cv or 0.0)
            + req.weights.get("uniformity_cv_power", 0.7) * uniformity_cv_power
            + req.weights.get("uniformity_cv_current", 0.7) * uniformity_cv_current
        )

        summary = {
            "overall_stability_score": float(score),
            "vacuum_cv": float(vacuum_cv) if vacuum_cv is not None else None,
            "uniformity_cv_current": float(uniformity_cv_current),
            "uniformity_cv_power": float(uniformity_cv_power),
            "active_cathodes_count": float(sum(1 for r in per_cathode if r["active_rate"] > 0)),
        }
        return PlasmaComputationResult(summary=summary, per_cathode=per_cathode, timeseries=ts_out, mode_used="timeseries")

    def compute(self, req: PlasmaStabilityRequest, loaded_df: pd.DataFrame) -> PlasmaComputationResult:
        df = self._load_external_if_requested(req, loaded_df)
        filtered = self._filter_by_date_time(df, req)

        key = self._cache_key(req, filtered.shape)
        if key in self.cache:
            self.last_result = self.cache[key]
            return self.cache[key]

        mode = req.mode
        if mode == "auto":
            has_long = any(c in filtered.columns for c in ["cathode", "compartment", "cathode_id"]) and self._resolve_time_column(filtered)
            mode = "timeseries" if has_long else "wide_auto"

        if mode == "timeseries":
            result = self._timeseries_metrics(filtered, req)
        else:
            result = self._wide_metrics(filtered, req)

        self.cache[key] = result
        self.last_result = result
        return result

    def export_last(self, fmt: str) -> tuple[str, str]:
        if self.last_result is None:
            raise ValueError("No plasma stability result available. Run analysis first.")

        if fmt == "json":
            return "application/json", json.dumps(sanitize_jsonable([self.last_result.summary, *self.last_result.per_cathode]), indent=2)

        if fmt == "csv":
            df = pd.DataFrame(self.last_result.per_cathode)
            buf = StringIO()
            df.to_csv(buf, index=False)
            return "text/csv", buf.getvalue()

        raise ValueError("Unsupported export format. Use json or csv.")
