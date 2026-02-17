from __future__ import annotations

from datetime import datetime, timedelta, timezone
import csv
import io
from pathlib import Path
from typing import Any

import pandas as pd

from app.models.schemas import PlasmaStabilityRequest as AppPlasmaStabilityRequest
from app.services.plasma_stability_service import PlasmaStabilityService
from config.plasma_thresholds import PLASMA_SCORE_THRESHOLDS, PLASMA_STATUS_MAPPING
from schemas.plasma import (
    PlasmaColumnsResponse,
    PlasmaSeriesPoint,
    PlasmaStabilityRequest,
    PlasmaStabilityResponse,
    PlasmaStabilityV2Request,
    PlasmaStabilityV2Response,
)


class PlasmaService:
    VERSION = "2.0.0"

    @staticmethod
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "plasma",
            "version": PlasmaService.VERSION,
            "time": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _cached_dataset_path() -> Path:
        return Path("backend/app/artifacts_cache/cached_dataset.parquet")

    @staticmethod
    def _fallback_dataframe() -> pd.DataFrame:
        ts0 = datetime(2026, 2, 9, 12, 0, 0)
        rows = []
        for i in range(24):
            t = ts0 + timedelta(minutes=5 * i)
            rows.append(
                {
                    "file_ts": t.isoformat(),
                    "c1.pwr": 10.0,
                    "c1.current": 1.2,
                    "c1.voltage": 520.0,
                    "c1.s1g": 0.2,
                    "c2.pwr": 8.0,
                    "c2.current": 1.0,
                    "c2.voltage": 510.0,
                    "c2.s1g": 0.22,
                    "c3.pwr": 0.0,
                    "c3.current": 0.0,
                    "c3.voltage": 0.0,
                    "actVacuumPressure": 0.05,
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _load_df() -> pd.DataFrame:
        path = PlasmaService._cached_dataset_path()
        if path.exists():
            try:
                return pd.read_parquet(path)
            except Exception:
                return PlasmaService._fallback_dataframe()
        return PlasmaService._fallback_dataframe()

    @staticmethod
    def columns() -> PlasmaColumnsResponse:
        df = PlasmaService._load_df()
        time_column = "file_ts" if "file_ts" in df.columns else "ts" if "ts" in df.columns else "file_ts"
        defaults = {
            "active_threshold": 0.0,
            "aggregation": "mean",
            "group_by": ["device", "plate"],
            "thresholds": PLASMA_SCORE_THRESHOLDS,
        }
        return PlasmaColumnsResponse(
            time_column=time_column,
            available_columns=[str(c) for c in df.columns],
            defaults=defaults,
        )

    @staticmethod
    def _to_app_req(payload: PlasmaStabilityRequest) -> AppPlasmaStabilityRequest:
        return AppPlasmaStabilityRequest(
            from_ts=payload.from_ts.isoformat(),
            to_ts=payload.to_ts.isoformat(),
            active_threshold=payload.active_threshold,
            agg=payload.aggregation,
            filter={
                "products": payload.filters.product,
                "thicknesses": [str(x) for x in payload.filters.thickness_mm],
                "date_from": payload.from_ts.isoformat(),
                "date_to": payload.to_ts.isoformat(),
            },
        )

    @staticmethod
    def _status_for_score(score: float | None, active_rate: float | None) -> str:
        if active_rate is not None and active_rate <= 0:
            return "OFF"
        if score is None:
            return "No data"
        if score <= PLASMA_SCORE_THRESHOLDS["normal_max"]:
            return "Normal"
        if score <= PLASMA_SCORE_THRESHOLDS["medium_max"]:
            return "Medium"
        return "Critical"

    @staticmethod
    def _apply_window_preset(v2: PlasmaStabilityV2Request) -> PlasmaStabilityV2Request:
        if not v2.window_preset:
            return v2
        hours = {"1h": 1, "6h": 6, "24h": 24, "7d": 24 * 7}[v2.window_preset]
        end = v2.to_ts
        start = end - timedelta(hours=hours)
        data = v2.model_dump(mode="python")
        data["from_ts"] = start
        data["to_ts"] = end
        return PlasmaStabilityV2Request(**data)

    @staticmethod
    def _series_by_cathode(df: pd.DataFrame, svc: PlasmaStabilityService, app_req: AppPlasmaStabilityRequest) -> dict[str, list[PlasmaSeriesPoint]]:
        work, ts_col = svc._filter_interval(df, app_req)
        detected = svc._detect_cathode_signals(work)
        if ts_col is None:
            ts_now = datetime.utcnow()
            points: dict[str, list[PlasmaSeriesPoint]] = {}
            per = svc._compute_per_cathode(work, detected, app_req)
            by_c = {x.get("cathode"): x for x in per}
            for cath in detected.keys():
                score = by_c.get(cath, {}).get("score")
                ar = by_c.get(cath, {}).get("active_rate", 0.0)
                points[cath] = [
                    PlasmaSeriesPoint(ts=ts_now, value=float(score or 0.0), is_active=bool(ar and ar > 0), meta={"status": PlasmaService._status_for_score(score, ar)})
                ]
            return points

        work = work.sort_values(ts_col).copy()
        n_bins = min(24, max(6, int(len(work) ** 0.5)))
        work["_bin"] = pd.cut(work[ts_col].astype("int64"), bins=n_bins, labels=False, duplicates="drop")

        out: dict[str, list[PlasmaSeriesPoint]] = {c: [] for c in svc._detect_cathode_signals(work).keys()}
        for _, sub in work.groupby("_bin"):
            if sub.empty:
                continue
            t = pd.to_datetime(sub[ts_col].max(), errors="coerce")
            per = svc._compute_per_cathode(sub, svc._detect_cathode_signals(sub), app_req)
            per_map = {x.get("cathode"): x for x in per}
            for cath in out.keys():
                item = per_map.get(cath, {})
                score = item.get("score")
                ar = item.get("active_rate", 0.0)
                out[cath].append(
                    PlasmaSeriesPoint(
                        ts=t.to_pydatetime() if pd.notna(t) else datetime.utcnow(),
                        value=float(score or 0.0),
                        is_active=bool(ar and ar > 0),
                        meta={"status": PlasmaService._status_for_score(score, ar), "active_rate": ar},
                    )
                )
        return out

    @staticmethod
    def stability(payload: PlasmaStabilityRequest) -> PlasmaStabilityResponse:
        df = PlasmaService._load_df()
        svc = PlasmaStabilityService()
        app_req = PlasmaService._to_app_req(payload)
        warnings = []
        try:
            result = svc.compute(app_req, df)
            series = PlasmaService._series_by_cathode(df, svc, app_req)
            score = float(result.kpis.get("overall_score") or 0.0)
            score_details = result.kpis
            rows_used = int(result.interval.get("rows_used") or 0)
        except Exception as exc:
            warnings.append(str(exc))
            series = {}
            score = 0.0
            score_details = {"overall_score": 0.0}
            rows_used = 0
        first_cath = next(iter(series.keys()), None)
        selected = series.get(first_cath, []) if first_cath else []

        return PlasmaStabilityResponse(
            window={"from_ts": payload.from_ts, "to_ts": payload.to_ts},
            params={
                "from_ts": payload.from_ts.isoformat(),
                "to_ts": payload.to_ts.isoformat(),
                "active_threshold": payload.active_threshold,
                "aggregation": payload.aggregation,
                "group_by": payload.group_by,
                "features": payload.features,
                "filters": payload.filters.model_dump(),
            },
            score=score,
            score_details=score_details,
            series=selected,
            warnings=warnings,
            row_count=rows_used,
        )

    @staticmethod
    def stability_v2(payload: PlasmaStabilityV2Request) -> PlasmaStabilityV2Response:
        payload = PlasmaService._apply_window_preset(payload)
        df = PlasmaService._load_df()
        svc = PlasmaStabilityService()
        app_req = PlasmaService._to_app_req(payload)
        warnings = []
        try:
            result = svc.compute(app_req, df)
            series_all = PlasmaService._series_by_cathode(df, svc, app_req)
            base_per = result.per_cathode
            rows_used = int(result.interval.get("rows_used") or 0)
        except Exception as exc:
            warnings.append(str(exc))
            result = None
            series_all = {}
            base_per = []
            rows_used = 0

        scores = []
        for item in base_per:
            cath = str(item.get("cathode"))
            score = item.get("score")
            active_rate = item.get("active_rate")
            scores.append(
                {
                    "cathode": cath,
                    "score": float(score) if score is not None else None,
                    "status": PlasmaService._status_for_score(float(score) if score is not None else None, float(active_rate) if active_rate is not None else None),
                    "score_details": {
                        "psi": item.get("psi"),
                        "gas_cv": item.get("gas_cv"),
                        "cv_pwr": item.get("cv_pwr"),
                        "cv_current": item.get("cv_current"),
                        "cv_voltage": item.get("cv_voltage"),
                        "active_rate": item.get("active_rate"),
                    },
                }
            )

        # include OFF/no-data cathodes from series map
        known = {s["cathode"] for s in scores}
        for cath, points in series_all.items():
            if cath in known:
                continue
            status = "OFF" if points and all(not p.is_active for p in points) else "No data"
            scores.append({"cathode": cath, "score": None, "status": status, "score_details": {}})

        scores = sorted(scores, key=lambda x: (x["score"] is None, x["score"] if x["score"] is not None else 10**9))

        selected_cath = payload.cathode if payload.cathode and payload.cathode != "all" else "all"
        selected_series = series_all.get(selected_cath, []) if selected_cath != "all" else []

        if selected_cath != "all":
            series_out = {selected_cath: series_all.get(selected_cath, [])}
        else:
            series_out = series_all

        return PlasmaStabilityV2Response(
            window={"from_ts": payload.from_ts, "to_ts": payload.to_ts, "rows_used": rows_used},
            params={
                "active_threshold": payload.active_threshold,
                "aggregation": payload.aggregation,
                "cathode": payload.cathode,
                "window_preset": payload.window_preset,
            },
            thresholds=PLASMA_SCORE_THRESHOLDS,
            status_mapping=PLASMA_STATUS_MAPPING,
            scores=scores,
            series_by_cathode=series_out,
            selected={"cathode": selected_cath, "series": selected_series},
            warnings=warnings,
        )

    @staticmethod
    def export_csv(payload: PlasmaStabilityRequest) -> str:
        data = PlasmaService.stability(payload)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["from_ts", "to_ts", "score", "row_count", "aggregation", "active_threshold"])
        writer.writerow(
            [
                data.window["from_ts"].isoformat(),
                data.window["to_ts"].isoformat(),
                data.score,
                data.row_count,
                payload.aggregation,
                payload.active_threshold,
            ]
        )
        return out.getvalue()
