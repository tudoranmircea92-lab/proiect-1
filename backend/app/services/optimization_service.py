from __future__ import annotations

import math

import joblib
import numpy as np

from app.core.constants import CONTROLLABLE_SUFFIXES, is_controllable_column
from app.services.config_service import load_machine_config
from app.services.io_utils import read_json
from app.services.registry_service import get_active_model


MODE_WEIGHTS = {
    "match_color": {"delta_e": 1.0, "change": 0.1, "gas": 0.05, "energy": 0.05},
    "balanced": {"delta_e": 0.8, "change": 0.2, "gas": 0.15, "energy": 0.15},
    "minimize_gas": {"delta_e": 0.7, "change": 0.2, "gas": 0.4, "energy": 0.1},
    "minimize_energy": {"delta_e": 0.7, "change": 0.2, "gas": 0.1, "energy": 0.4},
}


def _delta_e(pred: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(((pred - target) ** 2).sum()))


def _model_bundle(product_name: str, model_type: str = "process") -> tuple[dict, object, dict]:
    entry = get_active_model(product_name, model_type=model_type)
    if not entry:
        raise ValueError("No active model for product or GENERAL fallback")
    model = joblib.load(entry["artifacts"]["model"])
    schema = read_json(entry["artifacts"]["schema"])
    return entry, model, schema


def _collect_controllable(current_state: dict, config: dict) -> dict[str, float]:
    allowed = {}
    for comp, knobs in config.get("compartments", {}).items():
        for key in knobs.keys():
            if is_controllable_column(key) and key in current_state:
                allowed[key] = float(current_state[key])
    return allowed


def _relevance_by_compartment(model, features: list[str], current_state: dict, target: np.ndarray, config: dict) -> list[dict]:
    base = {f: current_state.get(f, 0.0) for f in features}
    base_pred = model.predict([base])[0]
    baseline_de = _delta_e(base_pred, target)
    comp_scores = []
    for comp, knobs in config.get("compartments", {}).items():
        perturbed = dict(base)
        for key, lim in knobs.items():
            if key in perturbed:
                step = lim.get("step", 1.0)
                perturbed[key] = min(lim["max"], float(perturbed[key]) + step)
        de = _delta_e(model.predict([perturbed])[0], target)
        score = max(0.0, baseline_de - de)
        comp_scores.append({"compartment": comp, "score": float(score)})
    comp_scores.sort(key=lambda x: x["score"], reverse=True)
    return comp_scores


def optimize(product_name: str, current_state: dict, target_color: dict[str, float], mode: str, top_k: int, coverage_threshold: float) -> dict:
    entry, model, schema = _model_bundle(product_name)
    features = schema["features"]
    targets = schema["targets"]
    config = load_machine_config()

    target = np.array([target_color[t] for t in targets])
    relevance = _relevance_by_compartment(model, features, current_state, target, config)
    selected = []
    cum = 0.0
    total = sum(r["score"] for r in relevance) or 1.0
    for r in relevance:
        if len(selected) < top_k or cum / total < coverage_threshold:
            selected.append(r)
            cum += r["score"]

    candidate = {f: current_state.get(f, 0.0) for f in features}
    deltas = {}
    changed = []
    weights = MODE_WEIGHTS[mode]

    for item in selected:
        comp = item["compartment"]
        knobs = config.get("compartments", {}).get(comp, {})
        for key, lim in knobs.items():
            if key not in candidate or not is_controllable_column(key):
                continue
            best_val = candidate[key]
            best_score = math.inf
            for direction in (-1, 1):
                trial = dict(candidate)
                step = lim.get("step", 1.0)
                trial_val = min(lim["max"], max(lim["min"], float(candidate[key]) + direction * step))
                trial[key] = trial_val
                pred = model.predict([trial])[0]
                delta_e = _delta_e(pred, target)
                change_penalty = abs(trial_val - float(current_state.get(key, 0.0)))
                gas_penalty = trial_val if key.endswith(("m1g", "m2g", "m3g")) else 0.0
                energy_penalty = trial_val if key.endswith("pwr") else 0.0
                score = (
                    weights["delta_e"] * delta_e
                    + weights["change"] * change_penalty
                    + weights["gas"] * gas_penalty * 0.001
                    + weights["energy"] * energy_penalty * 0.001
                )
                if score < best_score:
                    best_score = score
                    best_val = trial_val
            if best_val != candidate[key]:
                candidate[key] = best_val
                deltas[key] = float(best_val - float(current_state.get(key, 0.0)))
                changed.append(key)

    prediction = model.predict([candidate])[0]
    result_color = {targets[i]: float(prediction[i]) for i in range(len(targets))}
    score = _delta_e(prediction, target)

    recommendation = {k: float(v) for k, v in candidate.items() if is_controllable_column(k) and k in changed}
    return {
        "model_run_id": entry["run_id"],
        "product_name": product_name,
        "selected_compartments": selected,
        "recommendation": recommendation,
        "deltas": deltas,
        "predicted_color": result_color,
        "score": score,
        "changed_keys": changed,
    }
