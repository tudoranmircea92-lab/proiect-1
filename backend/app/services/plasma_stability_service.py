from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from io import StringIO
from typing import Any

import numpy as np
import pandas as pd

from app.models.schemas import PlasmaStabilityRequest
from app.services.json_sanitize import sanitize_jsonable

EPS = 1e-12


@dataclass
class PlasmaComputationResult:
    interval: dict[str, Any]
    kpis: dict[str, float | None]
    per_cathode: list[dict[str, Any]]
    trends: dict[str, list[Any]]


class PlasmaStabilityService:
    def __init__(self) -> None:
        self.last_result: PlasmaComputationResult | None = None

    @staticmethod
    def _safe_cv(vals: pd.Series | np.ndarray | list[float]) -> float | None:
        arr = pd.to_numeric(pd.Series(vals), errors="coerce").to_numpy(dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size == 0:
            return None
        mean = float(np.nanmean(arr))
        std = float(np.nanstd(arr, ddof=0))
        if not np.isfinite(mean) or not np.isfinite(std):
            return None
        return float(std / max(abs(mean), EPS))

    @staticmethod
    def _agg(values: list[float], method: str) -> float | None:
        if not values:
            return None
        return float(np.median(values) if method == "median" else np.mean(values))

    @staticmethod
    def _detect_cathode_signals(df: pd.DataFrame) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for c in df.columns:
            m = re.match(r"^(c\d+)\.(pwr|current|voltage)$", str(c))
            if m:
                cath, sig = m.group(1), m.group(2)
                out.setdefault(cath, {"pwr": False, "current": False, "voltage": False, "segments": []})
                out[cath][sig] = True
            mseg = re.match(r"^(c\d+)\.s(\d+)g$", str(c))
            if mseg:
                cath, seg = mseg.group(1), int(mseg.group(2))
                out.setdefault(cath, {"pwr": False, "current": False, "voltage": False, "segments": []})
                out[cath]["segments"] = sorted(list(set(out[cath]["segments"] + [seg])))
        return dict(sorted(out.items(), key=lambda x: int(x[0][1:])))

    def columns(self, df: pd.DataFrame) -> dict[str, Any]:
        detected = self._detect_cathode_signals(df)
        return {
            "cathodes": [
                {
                    "cathode": cath,
                    "signals": {
                        "pwr": info["pwr"],
                        "current": info["current"],
                        "voltage": info["voltage"],
                        "segments": info["segments"],
                    },
                }
                for cath, info in detected.items()
            ],
            "count": len(detected),
        }

    def _resolve_ts_col(self, df: pd.DataFrame, req: PlasmaStabilityRequest) -> str | None:
        if req.timestamp_col != "auto":
            return req.timestamp_col if req.timestamp_col in df.columns else None
        return "ts" if "ts" in df.columns else "file_ts" if "file_ts" in df.columns else None

    def _filter_interval(self, df: pd.DataFrame, req: PlasmaStabilityRequest) -> tuple[pd.DataFrame, str | None]:
        work = df.copy()
        ts_col = self._resolve_ts_col(work, req)
        if ts_col:
            work[ts_col] = pd.to_datetime(work[ts_col], errors="coerce")
            t_from = pd.to_datetime(req.from_ts, errors="coerce")
            t_to = pd.to_datetime(req.to_ts, errors="coerce")
            if pd.isna(t_from) or pd.isna(t_to):
                raise ValueError("Invalid from/to timestamp")
            work = work[(work[ts_col] >= t_from) & (work[ts_col] <= t_to)]
        work.replace([np.inf, -np.inf], np.nan, inplace=True)
        if work.empty:
            raise ValueError("No rows for selected interval")
        return work, ts_col

    def _uniformity_series(self, df: pd.DataFrame, detected: dict[str, dict[str, Any]], active_threshold: float, signal: str) -> list[float]:
        out: list[float] = []
        for _, row in df.iterrows():
            vals = []
            for cath, info in detected.items():
                pwr_col = f"{cath}.pwr"
                s_col = f"{cath}.{signal}"
                if not info.get("pwr") or s_col not in df.columns:
                    continue
                p = pd.to_numeric(row.get(pwr_col), errors="coerce")
                if pd.isna(p) or float(p) <= active_threshold:
                    continue
                v = pd.to_numeric(row.get(s_col), errors="coerce")
                if pd.notna(v):
                    vals.append(float(v))
            if len(vals) >= 2:
                cv = self._safe_cv(vals)
                if cv is not None:
                    out.append(float(cv))
        return out

    def _compute_per_cathode(self, df: pd.DataFrame, detected: dict[str, dict[str, Any]], req: PlasmaStabilityRequest) -> list[dict[str, Any]]:
        rows = []
        for cath, info in detected.items():
            p_col = f"{cath}.pwr"
            c_col = f"{cath}.current"
            v_col = f"{cath}.voltage"
            if p_col not in df.columns:
                continue

            pwr = pd.to_numeric(df[p_col], errors="coerce")
            active_mask = pwr > req.active_threshold
            active_rate = float(active_mask.mean()) if len(df) else 0.0
            active_df = df[active_mask]
            n_active = int(len(active_df))

            if n_active == 0 and not req.show_inactive:
                continue

            p_vals = pd.to_numeric(active_df[p_col], errors="coerce") if n_active else pd.Series(dtype=float)
            c_vals = pd.to_numeric(active_df[c_col], errors="coerce") if (n_active and c_col in active_df.columns) else pd.Series(dtype=float)
            v_vals = pd.to_numeric(active_df[v_col], errors="coerce") if (n_active and v_col in active_df.columns) else pd.Series(dtype=float)

            mean_p = float(np.nanmean(p_vals)) if p_vals.notna().any() else None
            std_p = float(np.nanstd(p_vals, ddof=0)) if p_vals.notna().any() else None
            cv_p = self._safe_cv(p_vals) if p_vals.notna().any() else None

            mean_c = float(np.nanmean(c_vals)) if c_vals.notna().any() else None
            std_c = float(np.nanstd(c_vals, ddof=0)) if c_vals.notna().any() else None
            cv_c = self._safe_cv(c_vals) if c_vals.notna().any() else None

            mean_v = float(np.nanmean(v_vals)) if v_vals.notna().any() else None
            std_v = float(np.nanstd(v_vals, ddof=0)) if v_vals.notna().any() else None
            cv_v = self._safe_cv(v_vals) if v_vals.notna().any() else None

            seg_cvs: list[float] = []
            for seg in info.get("segments", []):
                s_col = f"{cath}.s{seg}g"
                if s_col not in active_df.columns:
                    continue
                s_vals = pd.to_numeric(active_df[s_col], errors="coerce")
                scv = self._safe_cv(s_vals)
                if scv is not None:
                    seg_cvs.append(float(scv))
            gas_cv = float(np.mean(seg_cvs)) if seg_cvs else None

            psi = 0.5 * float(cv_p or 0.0) + 0.3 * float(cv_c or 0.0) + 0.2 * float(cv_v or 0.0)
            score = 0.6 * psi + 0.4 * gas_cv if gas_cv is not None else psi

            rows.append({
                "cathode": cath,
                "active_rate": active_rate,
                "n_active_samples": n_active,
                "mean_pwr": mean_p,
                "std_pwr": std_p,
                "cv_pwr": cv_p,
                "mean_current": mean_c,
                "std_current": std_c,
                "cv_current": cv_c,
                "mean_voltage": mean_v,
                "std_voltage": std_v,
                "cv_voltage": cv_v,
                "gas_cv": gas_cv,
                "psi": float(psi),
                "score": float(score),
            })
        return rows

    def _compute_kpis(self, df: pd.DataFrame, per_cathode: list[dict[str, Any]], req: PlasmaStabilityRequest, detected: dict[str, dict[str, Any]]) -> dict[str, float | None]:
        vac_col = "actVacuumPressure" if "actVacuumPressure" in df.columns else None
        vacuum_cv = self._safe_cv(df[vac_col]) if vac_col else None

        uniform_cur_series = self._uniformity_series(df, detected, req.active_threshold, "current")
        uniform_pwr_series = self._uniformity_series(df, detected, req.active_threshold, "pwr")

        uniform_cur = self._agg(uniform_cur_series, req.agg)
        uniform_pwr = self._agg(uniform_pwr_series, req.agg)

        score_vals = [float(r["score"]) for r in per_cathode if r.get("active_rate", 0) > 0 and r.get("score") is not None]
        cathode_median = float(np.median(score_vals)) if score_vals else None

        avg_active_counts = []
        for _, row in df.iterrows():
            n_active = 0
            for cath in detected.keys():
                p = pd.to_numeric(row.get(f"{cath}.pwr"), errors="coerce")
                if pd.notna(p) and float(p) > req.active_threshold:
                    n_active += 1
            avg_active_counts.append(n_active)
        avg_active = float(np.mean(avg_active_counts)) if avg_active_counts else 0.0

        overall = (
            req.weights.vacuum * float(vacuum_cv or 0.0)
            + req.weights.uniform_cur * float(uniform_cur or 0.0)
            + req.weights.uniform_pwr * float(uniform_pwr or 0.0)
            + float(cathode_median or 0.0)
        )

        return {
            "overall_score": float(overall),
            "vacuum_cv": vacuum_cv,
            "uniformity_cv_current": uniform_cur,
            "uniformity_cv_power": uniform_pwr,
            "avg_active_cathodes": avg_active,
        }

    def _compute_trends(self, df: pd.DataFrame, ts_col: str | None, req: PlasmaStabilityRequest, detected: dict[str, dict[str, Any]]) -> dict[str, list[Any]]:
        if ts_col is None:
            per = self._compute_per_cathode(df, detected, req)
            kpis = self._compute_kpis(df, per, req, detected)
            return {
                "time_bins": ["all"],
                "overall_score": [kpis["overall_score"]],
                "vacuum_cv": [kpis["vacuum_cv"]],
                "uniformity_cv_current": [kpis["uniformity_cv_current"]],
                "uniformity_cv_power": [kpis["uniformity_cv_power"]],
            }

        n = len(df)
        if isinstance(req.bins, int):
            n_bins = max(2, req.bins)
        else:
            n_bins = min(24, max(6, int(math.sqrt(max(n, 1)))))

        work = df.sort_values(ts_col).copy()
        work["_bin"] = pd.cut(work[ts_col].astype("int64"), bins=n_bins, labels=False, duplicates="drop")

        time_bins: list[str] = []
        overall, vac, ucur, upwr = [], [], [], []
        for b, sub in work.groupby("_bin"):
            if sub.empty:
                continue
            tmin = pd.to_datetime(sub[ts_col].min(), errors="coerce")
            tmax = pd.to_datetime(sub[ts_col].max(), errors="coerce")
            time_bins.append(f"{tmin.isoformat()} → {tmax.isoformat()}")
            per = self._compute_per_cathode(sub, detected, req)
            k = self._compute_kpis(sub, per, req, detected)
            overall.append(k["overall_score"])
            vac.append(k["vacuum_cv"])
            ucur.append(k["uniformity_cv_current"])
            upwr.append(k["uniformity_cv_power"])

        return {
            "time_bins": time_bins,
            "overall_score": overall,
            "vacuum_cv": vac,
            "uniformity_cv_current": ucur,
            "uniformity_cv_power": upwr,
        }

    def compute(self, req: PlasmaStabilityRequest, loaded_df: pd.DataFrame) -> PlasmaComputationResult:
        df, ts_col = self._filter_interval(loaded_df, req)
        detected = self._detect_cathode_signals(df)

        per_cathode = self._compute_per_cathode(df, detected, req)
        kpis = self._compute_kpis(df, per_cathode, req, detected)
        trends = self._compute_trends(df, ts_col, req, detected)

        interval = {
            "from": req.from_ts,
            "to": req.to_ts,
            "rows_used": int(len(df)),
        }

        result = PlasmaComputationResult(interval=interval, kpis=kpis, per_cathode=per_cathode, trends=trends)
        self.last_result = result
        return result

    def export_last(self, fmt: str) -> tuple[str, str]:
        if self.last_result is None:
            raise ValueError("No plasma stability result available. Run analysis first.")

        if fmt == "json":
            return "application/json", json.dumps(
                sanitize_jsonable(
                    {
                        "interval": self.last_result.interval,
                        "kpis": self.last_result.kpis,
                        "per_cathode": self.last_result.per_cathode,
                        "trends": self.last_result.trends,
                    }
                ),
                indent=2,
            )

        if fmt == "csv":
            pc = pd.DataFrame(self.last_result.per_cathode)
            pc.insert(0, "interval_from", self.last_result.interval.get("from"))
            pc.insert(1, "interval_to", self.last_result.interval.get("to"))
            for k, v in self.last_result.kpis.items():
                pc[k] = v
            buf = StringIO()
            pc.to_csv(buf, index=False)
            return "text/csv", buf.getvalue()

        raise ValueError("Unsupported export format. Use json or csv.")
