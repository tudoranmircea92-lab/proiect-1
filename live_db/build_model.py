from __future__ import annotations

from collections import Counter


def build_model_features(plate_core: dict, zone_summary: list[dict], risk_summary: list[dict], compartments: list[dict]) -> list[dict]:
    counts = Counter([r.get("material_class") for r in compartments])
    rec = {
        "plate": plate_core["plate"],
        "event_time": plate_core["event_time"],
        "feature_schema_version": "v1",
        "has_color": plate_core.get("has_color", False),
        "pair_status": plate_core.get("pair_status"),
        "active_compartment_count": len([r for r in compartments if r.get("actPower") is not None]),
        "oxide_compartment_count": counts.get("oxide", 0),
        "nitride_compartment_count": counts.get("nitride", 0),
        "silver_compartment_count": counts.get("silver", 0),
    }
    if zone_summary:
        rec.update({k: v for k, v in zone_summary[0].items() if k not in {"plate", "event_time"}})
    if risk_summary:
        rec.update({k: v for k, v in risk_summary[0].items() if k not in {"plate", "event_time"}})
    return [rec]


def build_model_targets(optics_summary: list[dict]) -> list[dict]:
    if not optics_summary:
        return []
    o = optics_summary[0]
    return [
        {
            "plate": o["plate"],
            "event_time": o["event_time"],
            "target_T_L_mean": o.get("T_L_mean"),
            "target_T_a_mean": o.get("T_a_mean"),
            "target_T_b_mean": o.get("T_b_mean"),
            "target_T_RT_mean": o.get("T_RT_mean"),
            "target_T_b_std": o.get("T_b_std"),
            "target_T_b_edge_center_delta": o.get("T_b_edge_center_delta"),
            "target_T_b_left_right_delta": o.get("T_b_left_right_delta"),
            "target_T_uniformity_score": o.get("T_uniformity_score"),
            "target_NAGY_resistance_mean": o.get("NAGY_resistance_mean"),
        }
    ]
