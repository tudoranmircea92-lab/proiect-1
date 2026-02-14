from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class KnobBound:
    minimum: float
    maximum: float
    step: float
    locked: bool = False


@dataclass
class Recommendation:
    rank: int
    predicted_delta_a: float
    predicted_delta_b: float
    predicted_delta_e: float
    tolerance_pass: bool
    why: str
    changes: List[Dict[str, float | str | bool]]


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _mean(rows: List[dict], key: str) -> float:
    vals: List[float] = []
    for r in rows:
        try:
            vals.append(float(r.get(key, "")))
        except Exception:
            pass
    return sum(vals) / len(vals) if vals else 0.0


class OptimizerEngine:
    def build_recommendations(
        self,
        subset: List[dict],
        target_a: float,
        target_b: float,
        tolerance_de: float,
        knob_bounds: Dict[str, KnobBound],
        top_k: int = 3,
    ) -> List[Recommendation]:
        if not subset:
            return []

        current_a = _mean(subset, "a_star_RG_mean")
        current_b = _mean(subset, "b_star_RG_mean")

        recommendations: List[Recommendation] = []
        unlocked_knobs = [k for k, b in knob_bounds.items() if not b.locked]

        for rank in range(1, top_k + 1):
            changes: List[Dict[str, float | str | bool]] = []
            step_scale = 1.0 + (rank - 1) * 0.5

            for knob in unlocked_knobs[:12]:
                bound = knob_bounds[knob]
                old_value = _mean(subset, knob)
                proposed = old_value + bound.step * step_scale
                new_value = clamp(proposed, bound.minimum, bound.maximum)
                changes.append(
                    {
                        "knob": knob,
                        "old": round(old_value, 4),
                        "new": round(new_value, 4),
                        "delta": round(new_value - old_value, 4),
                        "locked": bound.locked,
                        "clamped": proposed != new_value,
                    }
                )

            predicted_a = current_a + (target_a - current_a) * (0.35 + 0.2 * rank)
            predicted_b = current_b + (target_b - current_b) * (0.35 + 0.2 * rank)
            delta_a = predicted_a - current_a
            delta_b = predicted_b - current_b
            delta_e = (delta_a**2 + delta_b**2) ** 0.5

            top_changes = sorted(changes, key=lambda x: abs(float(x["delta"])), reverse=True)[:3]
            why = "Top drivers: " + ", ".join(str(c["knob"]) for c in top_changes)

            recommendations.append(
                Recommendation(
                    rank=rank,
                    predicted_delta_a=round(delta_a, 4),
                    predicted_delta_b=round(delta_b, 4),
                    predicted_delta_e=round(delta_e, 4),
                    tolerance_pass=delta_e <= tolerance_de,
                    why=why,
                    changes=changes,
                )
            )

        return recommendations
