from __future__ import annotations

"""Simple RCA heuristics that map anomalies to likely causes."""


def likely_root_causes(feature_map: dict[str, float | None]) -> list[str]:
    causes: list[str] = []
    if (feature_map.get("critical_actVacuumPressure_mean") or 0) > 0.01:
        causes.append("chamber_state_drift")
    split = feature_map.get("split_power_c62_c63")
    if split is not None and (split < 0.9 or split > 1.1):
        causes.append("stack_balance_drift")
    cdelta = feature_map.get("critical_deltaCurrent_mean")
    if cdelta is not None and abs(cdelta) > 0.5:
        causes.append("local_c62_instability")
    gdelta = feature_map.get("critical_deltaPower_mean")
    if gdelta is not None and abs(gdelta) > 1.0:
        causes.append("gas_delivery_drift")
    return causes
