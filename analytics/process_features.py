from __future__ import annotations

"""Process feature engineering for plate-level RCA and monitoring."""

from typing import Any

CRITICAL_BLOCKS = {58, 60, 62, 63, 65}


def build_process_features(rows: list[dict[str, Any]]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    crit = [r for r in rows if int(r.get("Location") or -1) in CRITICAL_BLOCKS]

    def avg(col: str, source: list[dict[str, Any]]) -> float | None:
        vals = [float(r[col]) for r in source if r.get(col) is not None]
        return sum(vals) / len(vals) if vals else None

    for metric in ("deltaPower", "deltaCurrent", "deltaVoltage", "actVacuumPressure"):
        out[f"critical_{metric}_mean"] = avg(metric, crit)

    c62 = [r for r in rows if int(r.get("Location") or -1) == 62]
    c63 = [r for r in rows if int(r.get("Location") or -1) == 63]
    p62 = avg("actPower", c62)
    p63 = avg("actPower", c63)
    out["split_power_c62_c63"] = (p62 / p63) if p62 and p63 else None
    return out
