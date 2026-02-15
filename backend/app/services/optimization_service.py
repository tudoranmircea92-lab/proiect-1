from __future__ import annotations

import math

import joblib
import numpy as np

from backend.app.data.schema_contract import is_knob_column
from backend.app.services.config_service import load_machine_config
from backend.app.services.io_utils import read_json
from backend.app.services.registry_service import add_optimize_result, get_active_model, list_entries, stamp

MODE_WEIGHTS = {
    'match_color': {'delta_e': 1.0, 'change': 0.1, 'gas': 0.05, 'energy': 0.05},
    'balanced': {'delta_e': 0.8, 'change': 0.2, 'gas': 0.15, 'energy': 0.15},
    'minimize_gas': {'delta_e': 0.7, 'change': 0.2, 'gas': 0.4, 'energy': 0.1},
    'minimize_energy': {'delta_e': 0.7, 'change': 0.2, 'gas': 0.1, 'energy': 0.4},
}


def _delta_e(pred: np.ndarray, target: np.ndarray) -> float:
    return float(np.sqrt(((pred - target) ** 2).sum()))


def _model_bundle(product_name: str, model_id: str | None = None, model_type: str = 'process') -> tuple[dict, object, dict]:
    entry = None
    if model_id:
        entry = next((e for e in list_entries() if e.get('run_id') == model_id), None)
    if not entry:
        entry = get_active_model(product_name, model_type=model_type)
    if not entry:
        raise ValueError('No active model for product or GENERAL fallback')
    model = joblib.load(entry['artifacts']['model'])
    schema = read_json(entry['artifacts']['schema'])
    return entry, model, schema


def _allowed_knobs(config: dict, include_compartments: list[str] | None, exclude_compartments: list[str] | None) -> dict[str, dict]:
    include_set = set(include_compartments or [])
    exclude_set = set(exclude_compartments or [])

    allowed: dict[str, dict] = {}
    for comp, knobs in config.get('compartments', {}).items():
        if include_set and 'all' not in include_set and comp not in include_set:
            continue
        if comp in exclude_set:
            continue
        for key, lim in knobs.items():
            if is_knob_column(key):
                allowed[key] = lim
    return allowed


def _relevance_by_compartment(model, features: list[str], current_state: dict, target: np.ndarray, config: dict, allowed_knobs: set[str]) -> list[dict]:
    base = {f: float(current_state.get(f, 0.0)) for f in features}
    base_pred = model.predict([base])[0]
    baseline_de = _delta_e(base_pred, target)
    comp_scores = []
    for comp, knobs in config.get('compartments', {}).items():
        perturbed = dict(base)
        for key, lim in knobs.items():
            if key in perturbed and key in allowed_knobs:
                step = lim.get('step', 1.0)
                perturbed[key] = min(lim['max'], float(perturbed[key]) + step)
        de = _delta_e(model.predict([perturbed])[0], target)
        score = max(0.0, baseline_de - de)
        comp_scores.append({'compartment': comp, 'score': float(score)})
    comp_scores.sort(key=lambda x: x['score'], reverse=True)
    return comp_scores


def optimize(
    product_name: str,
    current_state: dict,
    target_color: dict[str, float],
    mode: str,
    top_k: int,
    coverage_threshold: float,
    include_compartments: list[str] | None = None,
    exclude_compartments: list[str] | None = None,
    model_id: str | None = None,
    objective: str = 'minimize_delta_e',
    constraints: dict[str, float] | None = None,
) -> dict:
    entry, model, schema = _model_bundle(product_name, model_id=model_id)
    features = schema['features']
    targets = schema['targets']
    config = load_machine_config()
    constraints = constraints or {}

    target = np.array([float(target_color[t]) for t in targets])
    allowed = _allowed_knobs(config, include_compartments, exclude_compartments)
    relevance = _relevance_by_compartment(model, features, current_state, target, config, set(allowed.keys()))

    include_set = set(include_compartments or [])
    exclude_set = set(exclude_compartments or [])
    if include_set and 'all' not in include_set:
        relevance = [r for r in relevance if r['compartment'] in include_set]
    relevance = [r for r in relevance if r['compartment'] not in exclude_set]

    selected = []
    cum = 0.0
    total = sum(r['score'] for r in relevance) or 1.0
    for r in relevance:
        if len(selected) < top_k or cum / total < coverage_threshold:
            selected.append(r)
            cum += r['score']

    candidate = {f: float(current_state.get(f, 0.0)) for f in features}
    deltas = {}
    changed = []
    weights = MODE_WEIGHTS.get(mode, MODE_WEIGHTS['balanced'])

    max_gas = float(constraints.get('max_gas', float('inf')))
    max_power = float(constraints.get('max_power', float('inf')))

    for item in selected:
        comp = item['compartment']
        knobs = config.get('compartments', {}).get(comp, {})
        for key, lim in knobs.items():
            if key not in candidate or key not in allowed or not is_knob_column(key):
                continue

            best_val = candidate[key]
            best_score = math.inf
            for direction in (-1, 1):
                trial = dict(candidate)
                step = float(lim.get('step', 1.0))
                trial_val = min(float(lim['max']), max(float(lim['min']), float(candidate[key]) + direction * step))
                trial[key] = trial_val

                gas_total = sum(v for k, v in trial.items() if k.endswith(('m1g', 'm2g', 'm3g')) and is_knob_column(k))
                pwr_total = sum(v for k, v in trial.items() if k.endswith('pwr') and is_knob_column(k))
                if gas_total > max_gas or pwr_total > max_power:
                    continue

                pred = model.predict([trial])[0]
                delta_e = _delta_e(pred, target)
                change_penalty = abs(trial_val - float(current_state.get(key, 0.0)))
                gas_penalty = trial_val if key.endswith(('m1g', 'm2g', 'm3g')) else 0.0
                energy_penalty = trial_val if key.endswith('pwr') else 0.0

                objective_score = delta_e
                if objective == 'target_lab':
                    objective_score = float(np.mean(np.abs(pred - target)))

                score = (
                    weights['delta_e'] * objective_score
                    + weights['change'] * change_penalty
                    + weights['gas'] * gas_penalty * 0.001
                    + weights['energy'] * energy_penalty * 0.001
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
    base_prediction = model.predict([{f: float(current_state.get(f, 0.0)) for f in features}])[0]
    before_color = {targets[i]: float(base_prediction[i]) for i in range(len(targets))}
    score = _delta_e(prediction, target)

    recommendation = {k: float(v) for k, v in candidate.items() if k in changed and is_knob_column(k)}
    payload = {
        'model_run_id': entry['run_id'],
        'product_name': product_name,
        'selected_compartments': selected,
        'recommendation': recommendation,
        'deltas': deltas,
        'predicted_color': result_color,
        'before_color': before_color,
        'score': score,
        'changed_keys': changed,
        'created_at': stamp(),
    }
    add_optimize_result(payload)
    return payload
