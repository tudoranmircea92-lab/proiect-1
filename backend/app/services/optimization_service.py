from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from app.models.schemas import DeviceTarget, OptimizeRequest
from app.services.data_repository import DataRepository
from app.services.training_service import TrainingService


class OptimizationService:
    def __init__(self, trainer: TrainingService, repo: DataRepository) -> None:
        self.trainer = trainer
        self.repo = repo

    def _device_target(self, req: OptimizeRequest) -> DeviceTarget:
        if isinstance(req.targets, DeviceTarget):
            return req.targets
        dev = getattr(req.targets, req.device)
        if dev is None:
            raise ValueError(f"Missing target for device {req.device}")
        return dev

    def _col(self, ch: str, dev: str) -> str:
        return f"{ch}_{dev}_mean"

    def _delta_e(self, pred: dict[str, float], target: DeviceTarget, dev: str) -> float | None:
        vals = []
        for ch in ["L", "a", "b"]:
            t = getattr(target, ch)
            if t is None:
                return None
            col = self._col(ch, dev)
            vals.append((float(pred[col]) - float(t)) ** 2)
        return float(math.sqrt(sum(vals)))

    def _loss(self, pred: dict[str, float], req: OptimizeRequest, target: DeviceTarget, tol: DeviceTarget) -> float:
        if req.metric_group == "b_only":
            col = self._col("b", req.device)
            tol_b = tol.b if tol.b is not None else 0.0
            return float(max(0.0, abs(float(pred[col]) - float(target.b or 0.0)) - tol_b))

        if req.tol_deltaE is not None:
            de = self._delta_e(pred, target, req.device)
            if de is None:
                raise ValueError("deltaE tolerance requires L/a/b targets")
            return float(max(0.0, de - req.tol_deltaE))

        total = 0.0
        for ch in ["L", "a", "b"]:
            t = getattr(target, ch)
            if t is None:
                continue
            col = self._col(ch, req.device)
            tc = getattr(tol, ch)
            total += max(0.0, abs(float(pred[col]) - float(t)) - float(tc or 0.0))
        return float(total)

    def _smoothness_penalty(self, knobs: dict[str, float]) -> float:
        seg_by_cathode: dict[str, list[tuple[int, float]]] = {}
        for k, v in knobs.items():
            lk = k.lower().replace("_", ".")
            if ".s" in lk and lk.endswith("g"):
                left, right = lk.split(".s", 1)
                idx = ""
                for ch in right:
                    if ch.isdigit():
                        idx += ch
                    else:
                        break
                if not idx:
                    continue
                seg_by_cathode.setdefault(left, []).append((int(idx), float(v)))
        total = 0.0
        for vals in seg_by_cathode.values():
            vals = sorted(vals, key=lambda x: x[0])
            for i in range(1, len(vals)):
                total += abs(vals[i][1] - vals[i - 1][1])
        return float(total)

    def _knob_ranges(self, df: pd.DataFrame, cols: list[str]) -> dict[str, tuple[float, float]]:
        out: dict[str, tuple[float, float]] = {}
        for c in cols:
            s = pd.to_numeric(df[c], errors="coerce").dropna()
            if s.empty:
                out[c] = (0.0, 0.0)
            else:
                out[c] = (float(s.quantile(0.05)), float(s.quantile(0.95)))
        return out

    def _pick_baseline(self, df: pd.DataFrame, req: OptimizeRequest, control_cols: list[str], context_cols: list[str], target: DeviceTarget) -> tuple[dict[str, float], dict[str, Any], dict[str, Any]]:
        plate_col = self.repo.plate_col(df)
        prod_col = self.repo.product_col(df)
        row = df.iloc[0]
        if req.plate_id and plate_col:
            m = df[df[plate_col].astype(str) == str(req.plate_id)]
            if not m.empty:
                row = m.iloc[0]

        if req.baseline_source == "median_product" and prod_col:
            pval = row.get(prod_col)
            sub = df[df[prod_col] == pval] if pval is not None else df
            if not sub.empty:
                num = sub[control_cols].apply(pd.to_numeric, errors="coerce")
                med = num.median(axis=0, skipna=True).fillna(0.0)
                control = {c: float(med.get(c, 0.0)) for c in control_cols}
                context = {c: row.get(c, None) for c in context_cols}
                return control, context, row.to_dict()

        if req.baseline_source == "nearest_neighbor":
            bcol = self._col("b", req.device)
            if bcol in df.columns and target.b is not None:
                d = (pd.to_numeric(df[bcol], errors="coerce") - float(target.b)).abs()
                idx = d.idxmin()
                row = df.loc[idx]

        control = {c: float(pd.to_numeric(row.get(c), errors="coerce") if pd.notna(pd.to_numeric(row.get(c), errors="coerce")) else 0.0) for c in control_cols}
        context = {c: row.get(c, None) for c in context_cols}
        return control, context, row.to_dict()


    def _apply_logical_knobs(
        self,
        req: OptimizeRequest,
        knob_schema: dict[str, Any],
        active_prefixes: set[str],
        baseline_control: dict[str, float],
        ranges: dict[str, tuple[float, float]],
    ) -> list[str]:
        warnings: list[str] = []
        knobs = req.knobs or {}

        def _to_float(v):
            try:
                return float(v)
            except Exception:
                return None

        gases_main = knobs.get('gases_main', {}) if isinstance(knobs, dict) else {}
        main_cols = ((knob_schema or {}).get('gases_main') or {}).get('cols') or {}
        for main_key, spec in gases_main.items():
            col = main_cols.get(main_key)
            if not col or col not in ranges:
                continue
            if isinstance(spec, dict):
                cur = _to_float(spec.get('current'))
                mn = _to_float(spec.get('min'))
                mx = _to_float(spec.get('max'))
            else:
                cur = _to_float(spec)
                mn = mx = None
            if cur is not None:
                baseline_control[col] = cur
            lo, hi = ranges[col]
            if mn is not None:
                lo = mn
            if mx is not None:
                hi = mx
            if hi < lo:
                hi = lo
            ranges[col] = (lo, hi)

        seg = knobs.get('gases_segmented', {}) if isinstance(knobs, dict) else {}
        seg_schema = (knob_schema or {}).get('gases_segmented') or {}
        mode = seg_schema.get('mode', 'none')
        cols_map = seg_schema.get('cols') or {}
        for entity_id, entity_spec in (seg.items() if isinstance(seg, dict) else []):
            entity_cols = cols_map.get(entity_id) or {}
            if mode == 'by_cathode' and entity_id not in active_prefixes:
                warnings.append(f'Ignored OFF cathode request for {entity_id}')
                continue
            if not isinstance(entity_spec, dict):
                continue
            for main_key, spec in entity_spec.items():
                col = entity_cols.get(main_key)
                if not col or col not in ranges:
                    continue
                if isinstance(spec, dict):
                    cur = _to_float(spec.get('current'))
                    mn = _to_float(spec.get('min'))
                    mx = _to_float(spec.get('max'))
                else:
                    cur = _to_float(spec)
                    mn = mx = None
                if cur is not None:
                    baseline_control[col] = cur
                lo, hi = ranges[col]
                if mn is not None:
                    lo = mn
                if mx is not None:
                    hi = mx
                if hi < lo:
                    hi = lo
                ranges[col] = (lo, hi)

        return warnings

    def optimize(self, df_raw: pd.DataFrame, req: OptimizeRequest) -> dict:
        if not self.trainer.feature_schema:
            raise ValueError("Train a model before running optimizer.")

        df = self.repo.apply_filter(df_raw, req.filter)
        if df.empty:
            raise ValueError("No rows after filter.")

        control_cols_all = [c for c in self.trainer.feature_schema["control_knobs"] if c in df.columns]
        context_cols = [c for c in (self.trainer.feature_schema["context_numeric"] + self.trainer.feature_schema["context_categorical"]) if c in df.columns]

        use_power = req.knob_groups.get("power", True)
        use_main = req.knob_groups.get("main_gas", True)
        use_seg = req.knob_groups.get("segment_gas", True)

        def allow(col: str) -> bool:
            lc = col.lower().replace("_", ".")
            if ".pwr" in lc:
                return use_power
            if ".s" in lc and lc.endswith("g"):
                return use_seg
            if "maingas" in lc or ".m1g" in lc or ".m2g" in lc or ".m3g" in lc:
                return use_main
            return False

        target = self._device_target(req)
        tol = req.tolerances or DeviceTarget(L=0.0, a=0.0, b=0.0)

        baseline_control, fixed_context, baseline_row = self._pick_baseline(df, req, control_cols_all, context_cols, target)
        knob_schema = self.repo.discover_knob_schema(df, row=pd.Series(baseline_row))

        # active cathodes from pwr threshold
        active_prefixes = set()
        for c, v in baseline_control.items():
            lc = c.lower().replace("_", ".")
            if ".pwr" in lc and float(v) > req.active_threshold:
                active_prefixes.add(lc.split(".pwr")[0])

        control_cols = []
        for c in control_cols_all:
            lc = c.lower().replace("_", ".")
            prefix = lc.split(".")[0] if lc.startswith("c") else ""
            if allow(c) and (".pwr" in lc or prefix in active_prefixes):
                control_cols.append(c)

        bounds_df = df
        product_col = self.repo.product_col(df)
        if product_col and req.filter and req.filter.products:
            pset = {str(x) for x in req.filter.products}
            bdf = df[df[product_col].astype(str).isin(pset)]
            if not bdf.empty:
                bounds_df = bdf
        ranges = self._knob_ranges(bounds_df, control_cols)
        warnings = self._apply_logical_knobs(req, knob_schema, active_prefixes, baseline_control, ranges)

        baseline_pred = self.trainer.predict(baseline_control, fixed_context)

        best_loss = float("inf")
        best_knobs = dict(baseline_control)
        best_pred = dict(baseline_pred)

        for _ in range(req.params.n_iterations):
            cand = dict(baseline_control)
            for k in control_cols:
                lo, hi = ranges[k]
                if hi <= lo:
                    continue
                center = baseline_control.get(k, lo)
                width = (hi - lo) * (req.bounds.gas_pct if "g" in k.lower() else req.bounds.pwr_pct) / 100.0
                value = np.random.uniform(center - width, center + width)
                cand[k] = float(np.clip(value, lo, hi))

            pred = self.trainer.predict(cand, fixed_context)
            primary = self._loss(pred, req, target, tol)
            knob_pen = 0.0
            for k in control_cols:
                lo, hi = ranges[k]
                rng = max(hi - lo, 1e-6)
                knob_pen += abs(cand[k] - baseline_control.get(k, 0.0)) / rng
            smooth_pen = self._smoothness_penalty(cand)
            total = primary + req.lambda_knob_change * knob_pen + req.lambda_smoothness * smooth_pen

            if total < best_loss:
                best_loss = float(total)
                best_knobs = cand
                best_pred = pred

        # actual baseline from row means
        baseline_actual = {
            "L": baseline_row.get(self._col("L", req.device)),
            "a": baseline_row.get(self._col("a", req.device)),
            "b": baseline_row.get(self._col("b", req.device)),
        }

        changes: dict[str, list[dict[str, float]]] = {}
        for k in control_cols:
            dv = float(best_knobs.get(k, 0.0) - baseline_control.get(k, 0.0))
            if abs(dv) < 1e-10:
                continue
            lk = k.lower().replace("_", ".")
            cathode = lk.split(".")[0] if lk.startswith("c") else "other"
            changes.setdefault(cathode, []).append({
                "knob": k,
                "baseline": float(baseline_control.get(k, 0.0)),
                "optimized": float(best_knobs.get(k, 0.0)),
                "delta": dv,
                "bound_min": ranges[k][0],
                "bound_max": ranges[k][1],
            })

        return {
            "baseline_actual": baseline_actual,
            "baseline_pred": {
                "L": baseline_pred.get(self._col("L", req.device)),
                "a": baseline_pred.get(self._col("a", req.device)),
                "b": baseline_pred.get(self._col("b", req.device)),
            },
            "optimized_pred": {
                "L": best_pred.get(self._col("L", req.device)),
                "a": best_pred.get(self._col("a", req.device)),
                "b": best_pred.get(self._col("b", req.device)),
            },
            "knob_changes": changes,
            "bounds": {k: {"min": v[0], "max": v[1]} for k, v in ranges.items()},
            "diagnostics": {"iterations": req.params.n_iterations, "best_loss": best_loss, "warnings": warnings},
            "device": req.device,
            "plate_id": req.plate_id,
            "knob_schema": knob_schema,
        }
