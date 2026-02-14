from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass
class RunInput:
    product: str | None
    day: str | None
    plate: str | None
    target: str
    tolerance: float
    mode: str
    train_new_model: bool
    use_existing_model: bool
    allowed_knobs: List[str]
    price_kwh: float
    price_gas: float


def _to_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def pick_context(rows: List[Dict[str, Any]], product: str | None, day: str | None, plate: str | None) -> List[Dict[str, Any]]:
    out = rows[:]
    if product:
        out = [r for r in out if str(r.get("product_name") or r.get("product") or "") == product]
    if day:
        out = [r for r in out if str(r.get("day") or "") == day]
    if plate:
        out = [r for r in out if str(r.get("plate_id") or "") == plate]
    return out


def detect_targets(rows: List[Dict[str, Any]]) -> List[str]:
    if not rows:
        return []
    cols = sorted(rows[0].keys())
    return [
        c
        for c in cols
        if c.endswith("_mean")
        or c.endswith("_std")
        or "_p" in c and (c.startswith("a_star") or c.startswith("b_star") or c.startswith("L_star"))
    ]


def detect_knobs(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, List[str]]]:
    if not rows:
        return {}
    cols = sorted(rows[0].keys())
    out: Dict[str, Dict[str, List[str]]] = {}
    for c in cols:
        if not (c.startswith("c") and "." in c):
            continue
        comp, knob = c.split(".", 1)
        if not comp[1:].isdigit():
            continue
        out.setdefault(comp, {"power": [], "main_gases": [], "segment_gases": []})
        if knob == "pwr":
            out[comp]["power"].append(c)
        elif knob in {"m1g", "m2g", "m3g"}:
            out[comp]["main_gases"].append(c)
        elif knob.startswith("s") and knob.endswith("g") and knob[1:-1].isdigit():
            out[comp]["segment_gases"].append(c)
    return out


def extract_profile(rows: List[Dict[str, Any]], target: str) -> Tuple[List[float], List[int]]:
    if not rows:
        return [], []
    row = rows[-1]
    if "_p" not in target:
        value = _to_float(row.get(target), 0.0)
        return [value], [1]

    prefix = target.split("_p", 1)[0] + "_p"
    candidates = []
    for k in row.keys():
        if k.startswith(prefix):
            suffix = k.split("_p", 1)[1]
            if suffix.isdigit():
                candidates.append((int(suffix), _to_float(row.get(k), 0.0)))
    candidates.sort(key=lambda x: x[0])
    return [v for _, v in candidates], [p for p, _ in candidates]


def run_optimizer(rows: List[Dict[str, Any]], params: RunInput) -> Dict[str, Any]:
    subset = pick_context(rows, params.product, params.day, params.plate)
    if not subset:
        raise ValueError("No rows for selected context")

    profile, positions = extract_profile(subset, params.target)
    if not profile:
        profile = [_to_float(subset[-1].get(params.target), 0.0)]
        positions = [1]

    knob_groups = detect_knobs(subset)
    all_knobs = [k for groups in knob_groups.values() for arr in groups.values() for k in arr]
    active_knobs = params.allowed_knobs if params.allowed_knobs else all_knobs

    step = 0.08 if params.mode.upper() == "SAFE" else 0.2
    top3 = []
    for rank in range(1, 4):
        factor = 1 - rank * step
        predicted = [round(v * factor, 4) for v in profile]
        changes = []
        for i, knob in enumerate(active_knobs[:10]):
            curr = _to_float(subset[-1].get(knob), 0.0)
            prop = curr + (rank * step * (1 if i % 2 == 0 else -1))
            delta = prop - curr
            changes.append(
                {
                    "compartment": knob.split(".", 1)[0],
                    "knob": knob,
                    "current": round(curr, 4),
                    "proposed": round(prop, 4),
                    "delta": round(delta, 4),
                    "pct_change": round((delta / curr * 100.0), 3) if curr else 0.0,
                }
            )
        cost_plate = round(sum(abs(c["delta"]) for c in changes) * (params.price_kwh + params.price_gas) * 0.1, 4)
        top3.append(
            {
                "rank": rank,
                "predicted_target_value": round(sum(predicted) / len(predicted), 4),
                "stability_score": round(max(0.0, 100 - rank * 7 - len(changes) * 0.6), 2),
                "cost_impact": {
                    "per_plate": cost_plate,
                    "per_day": round(cost_plate * 120, 2),
                    "per_month": round(cost_plate * 3600, 2),
                    "delta_cost": cost_plate,
                },
                "knob_changes": changes,
                "predicted_profile": predicted,
                "summary": f"{len(changes)} knob changes across {len(set(c['compartment'] for c in changes))} compartments",
            }
        )

    baseline_avg = round(sum(profile) / len(profile), 4)
    tol = round(params.tolerance, 1)

    return {
        "positions": positions,
        "current_profile": profile,
        "tolerance": tol,
        "optimized_profile": top3[0]["predicted_profile"],
        "cost_inputs": {"price_kwh": params.price_kwh, "price_gas": params.price_gas},
        "cost_summary": top3[0]["cost_impact"],
        "top_solutions": top3,
        "baseline_target_value": baseline_avg,
        "meta": {
            "mode": params.mode.upper(),
            "trained_new_model": params.train_new_model,
            "used_existing_model": params.use_existing_model,
            "selected_rows": len(subset),
        },
    }


def verify_application(rows: List[Dict[str, Any]], plate: str, target: str, predicted_profile: List[float]) -> Dict[str, Any]:
    subset = [r for r in rows if str(r.get("plate_id") or "") == str(plate)]
    if not subset:
        raise ValueError("Plate not found for verification")
    actual, positions = extract_profile(subset, target)
    n = min(len(actual), len(predicted_profile))
    if n == 0:
        raise ValueError("Insufficient data for verification")
    actual = actual[:n]
    pred = predicted_profile[:n]
    diffs = [abs(a - p) for a, p in zip(actual, pred)]
    mae = sum(diffs) / n
    rmse = (sum((a - p) ** 2 for a, p in zip(actual, pred)) / n) ** 0.5
    explanation = "Prediction close to actual" if mae < 0.5 else "Deviation indicates drift or partial application"
    return {
        "positions": positions[:n],
        "predicted_profile": pred,
        "actual_profile": actual,
        "metrics": {"mae": round(mae, 4), "rmse": round(rmse, 4), "max_abs_error": round(max(diffs), 4)},
        "explanation": explanation,
    }
