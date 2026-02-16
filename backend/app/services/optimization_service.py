from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.constants import TARGET_COLUMNS
from app.models.schemas import OptimizeRequest
from app.services.training_service import TrainingService


class OptimizationService:
    def __init__(self, trainer: TrainingService) -> None:
        self.trainer = trainer

    @staticmethod
    def _means_targets_from_request(req: OptimizeRequest) -> dict[str, float]:
        out: dict[str, float] = {}
        for dev in ["RG", "RF", "T"]:
            device = getattr(req.targets, dev)
            if not device:
                continue
            out[f"L_{dev}_mean"] = device.L
            out[f"a_{dev}_mean"] = device.a
            out[f"b_{dev}_mean"] = device.b
        return out

    def _compute_loss(self, pred: dict[str, float], req: OptimizeRequest) -> float:
        means = self._means_targets_from_request(req)
        loss = 0.0
        for col, val in means.items():
            dev = col.split("_")[1]
            w = req.params.device_weights.get(dev, 1.0)
            loss += w * abs(pred[col] - val)

        if req.constraints:
            for dev in ["RG", "RF", "T"]:
                c = getattr(req.constraints, dev)
                if not c:
                    continue
                for channel in ["L", "a", "b"]:
                    max_std = getattr(c, channel)
                    if max_std is None:
                        continue
                    std_col = f"{channel}_{dev}_std"
                    over = max(0.0, pred[std_col] - max_std)
                    loss += 5.0 * over
        return float(loss)

    def _seed_from_df(self, df: pd.DataFrame, req: OptimizeRequest, control_cols: list[str], context_cols: list[str]) -> tuple[dict, dict]:
        seed_row = df.iloc[0]
        if req.seed_plate and "plate" in df.columns:
            matched = df[df["plate"].astype(str) == req.seed_plate]
            if not matched.empty:
                seed_row = matched.iloc[0]

        seed_control = {c: float(seed_row.get(c, 0.0)) for c in control_cols}
        seed_context = {c: seed_row.get(c, None) for c in context_cols}
        return seed_control, seed_context

    def optimize(self, df: pd.DataFrame, req: OptimizeRequest) -> list[dict]:
        if not self.trainer.feature_schema:
            raise ValueError("Train a model before running optimizer.")

        control_cols = self.trainer.feature_schema["control_knobs"]
        context_cols = self.trainer.feature_schema["context_numeric"] + self.trainer.feature_schema["context_categorical"]
        clean = df.dropna(subset=TARGET_COLUMNS)
        if clean.empty:
            raise ValueError("No rows with full target data available for optimization.")

        seed_control_df, seed_context_df = self._seed_from_df(clean, req, control_cols, context_cols)
        seed_control = req.seed_control_knobs or seed_control_df
        fixed_context = req.seed_context or seed_context_df

        if req.method == "nn":
            target_means = self._means_targets_from_request(req)
            if not target_means:
                raise ValueError("At least one mean target must be provided.")

            keys = list(target_means.keys())
            y_mat = clean[keys].to_numpy(dtype=float)
            desired = np.array([target_means[k] for k in keys], dtype=float)
            dists = np.linalg.norm(y_mat - desired, axis=1)
            idxs = np.argsort(dists)[: req.params.k_neighbors]
            candidates = clean.iloc[idxs]

            out = []
            for rank, (_, row) in enumerate(candidates.iterrows(), start=1):
                knobs = {c: float(row.get(c, 0.0)) for c in control_cols}
                pred = self.trainer.predict(knobs, fixed_context)
                out.append(
                    {
                        "rank": rank,
                        "loss": self._compute_loss(pred, req),
                        "control_knobs": knobs,
                        "predicted": pred,
                        "deltas_vs_seed": {k: float(knobs[k] - float(seed_control.get(k, 0.0))) for k in control_cols},
                    }
                )
            return out[: req.params.n_solutions]

        best: list[dict] = []
        for _ in range(req.params.n_iterations):
            cand = dict(seed_control)
            for k, v in list(cand.items()):
                pct = req.bounds.gas_pct if ("Gas" in k or k.endswith("g")) else req.bounds.pwr_pct
                cand[k] = float(v * (1 + np.random.uniform(-pct, pct) / 100.0))

            pred = self.trainer.predict(cand, fixed_context)
            best.append(
                {
                    "loss": self._compute_loss(pred, req),
                    "control_knobs": cand,
                    "predicted": pred,
                    "deltas_vs_seed": {k: float(cand[k] - float(seed_control.get(k, 0.0))) for k in control_cols},
                }
            )

        best_sorted = sorted(best, key=lambda x: x["loss"])[: req.params.n_solutions]
        for i, item in enumerate(best_sorted, start=1):
            item["rank"] = i
        return best_sorted
