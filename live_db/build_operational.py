from __future__ import annotations

from collections import defaultdict
from statistics import mean


def _safe_mean(values: list[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    return mean(nums) if nums else None


def _material_class(material_raw: str, material_map: dict[str, str]) -> str:
    token = material_raw.strip().lower()
    for key, val in material_map.items():
        if key in token:
            return val
    return "other"


def build_compartment_state(rows: list[dict], zone_map: dict[str, list[int]], material_map: dict[str, str], gas_map: dict[str, str]) -> list[dict]:
    zone_by_loc = {}
    for zone_name, locs in zone_map.items():
        for loc in locs:
            zone_by_loc[loc] = zone_name

    out = []
    for r in rows:
        item = {
            "plate": r["plate"],
            "event_time": r["event_time"],
            "Location": r["Location"],
            "row_idx": r.get("row_idx"),
            "zone_id": f"z{list(zone_map.keys()).index(zone_by_loc.get(r['Location'], list(zone_map.keys())[-1])) + 1}" if zone_map else "z?",
            "zone_name": zone_by_loc.get(r["Location"], "unmapped"),
            "material_raw": r.get("material_raw"),
            "material_class": _material_class(r.get("material_raw", ""), material_map),
            "actVacuumPressure": r.get("actVacuumPressure"),
            "nomGasSegment": r.get("nomGasSegment"),
            "nomSegGasType": r.get("nomSegGasType"),
            "seg_sum": r.get("seg_sum"),
            "seg_mean": r.get("seg_mean"),
            "seg_max": r.get("seg_max"),
            "seg_range": r.get("seg_range"),
            "seg_active_count": r.get("seg_active_count"),
        }
        for m in ["Power", "Current", "Voltage"]:
            for k in ["nom", "act", "delta"]:
                item[f"{k}{m}"] = r.get(f"{k}{m}")
        for i in range(1, 4):
            for k in ["nom", "act", "delta"]:
                item[f"{k}MainGas{i}"] = r.get(f"{k}MainGas{i}")
                item[f"{k}RampGas{i}"] = r.get(f"{k}RampGas{i}")

        o2 = item.get("actMainGas1") or 0.0
        n2 = item.get("actMainGas2") or 0.0
        inert = item.get("actMainGas3") or 0.0
        denom = inert if inert > 0 else None
        item["oxidation_ratio_local"] = (o2 / (o2 + inert)) if (o2 + inert) > 0 else None
        item["nitridation_ratio_local"] = (n2 / (n2 + inert)) if (n2 + inert) > 0 else None
        item["reactive_inert_ratio_local"] = ((o2 + n2) / denom) if denom else None
        ro = (item.get("actRampGas1") or 0) + (item.get("actRampGas2") or 0)
        ri = item.get("actRampGas3") or 0
        item["ramp_reactive_inert_ratio"] = (ro / ri) if ri > 0 else None
        seg_type = (item.get("nomSegGasType") or "").lower()
        fam = gas_map.get(seg_type, "unknown")
        item["seg_gas_family"] = fam
        item["seg_is_reactive"] = fam.startswith("reactive")
        out.append(item)
    return out


def build_zone_summary(compartment_rows: list[dict]) -> list[dict]:
    by_key = defaultdict(list)
    for r in compartment_rows:
        by_key[(r["plate"], r["event_time"], r["zone_name"])].append(r)

    by_plate = defaultdict(dict)
    for (plate, event_time, zone_name), rows in by_key.items():
        by_plate[(plate, event_time)][f"{zone_name}_oxidation_mean"] = _safe_mean([x.get("oxidation_ratio_local") for x in rows])
        by_plate[(plate, event_time)][f"{zone_name}_nitridation_mean"] = _safe_mean([x.get("nitridation_ratio_local") for x in rows])
        by_plate[(plate, event_time)][f"{zone_name}_reactive_inert_mean"] = _safe_mean([x.get("reactive_inert_ratio_local") for x in rows])
        by_plate[(plate, event_time)][f"{zone_name}_power_delta_mean"] = _safe_mean([x.get("deltaPower") for x in rows])
        by_plate[(plate, event_time)][f"{zone_name}_voltage_delta_mean"] = _safe_mean([x.get("deltaVoltage") for x in rows])
        by_plate[(plate, event_time)][f"{zone_name}_vacuum_mean"] = _safe_mean([x.get("actVacuumPressure") for x in rows])

    return [{"plate": k[0], "event_time": k[1], **vals} for k, vals in by_plate.items()]


def build_risk_summary(compartment_rows: list[dict], thresholds: dict) -> list[dict]:
    by_plate = defaultdict(list)
    for r in compartment_rows:
        by_plate[(r["plate"], r["event_time"])].append(r)
    out = []
    for (plate, event_time), rows in by_plate.items():
        pre = [r for r in rows if str(r.get("zone_name", "")).startswith("z1_")]
        o2 = _safe_mean([r.get("actMainGas1") for r in pre])
        n2 = _safe_mean([r.get("actMainGas2") for r in pre])
        p = [r.get("actVacuumPressure") for r in pre if r.get("actVacuumPressure") is not None]
        grad = (max(p) - min(p)) if len(p) > 1 else 0.0
        rir = _safe_mean([r.get("reactive_inert_ratio_local") for r in pre])
        silver_risk_raw = (o2 or 0) * 0.4 + (n2 or 0) * 0.2 + grad * 10
        silver_risk_score = max(0.0, min(1.0, silver_risk_raw / (thresholds.get("silver_risk_pressure", 0.008) * 100)))
        plasma_stability_score = max(0.0, min(1.0, 1.0 - (_safe_mean([abs(r.get("deltaPower") or 0) for r in rows]) or 0) / 50))
        target_health_score = max(0.0, min(1.0, 1.0 - (_safe_mean([abs(r.get("deltaVoltage") or 0) for r in rows]) or 0) / 50))
        out.append(
            {
                "plate": plate,
                "event_time": event_time,
                "pre_ag_o2_mean": o2,
                "pre_ag_n2_mean": n2,
                "pre_ag_pressure_gradient": grad,
                "pre_ag_reactive_inert_ratio": rir,
                "silver_risk_raw": silver_risk_raw,
                "silver_risk_score": silver_risk_score,
                "plasma_stability_score": plasma_stability_score,
                "target_health_score": target_health_score,
            }
        )
    return out


def build_optics_summary(rows: list[dict], event_time) -> list[dict]:
    by_device = defaultdict(list)
    for r in rows:
        by_device[r["device_norm"]].append(r)

    out = {"event_time": event_time, "plate": rows[0]["plate"] if rows else None}
    for d, vals in by_device.items():
        l = [x.get("L") for x in vals if x.get("L") is not None]
        a = [x.get("a") for x in vals if x.get("a") is not None]
        b = [x.get("b") for x in vals if x.get("b") is not None]
        rt = [x.get("RT") for x in vals if x.get("RT") is not None]
        out[f"{d}_L_mean"] = _safe_mean(l)
        out[f"{d}_a_mean"] = _safe_mean(a)
        out[f"{d}_b_mean"] = _safe_mean(b)
        out[f"{d}_RT_mean"] = _safe_mean(rt)
        if b:
            bm = mean(b)
            out[f"{d}_b_std"] = (sum((x - bm) ** 2 for x in b) / len(b)) ** 0.5

    t_vals = sorted([r for r in rows if r["device_norm"] == "T"], key=lambda x: x["position"])
    if t_vals:
        n = len(t_vals)
        edge_count = max(1, n // 5)
        left = t_vals[:edge_count]
        right = t_vals[-edge_count:]
        center = t_vals[edge_count : n - edge_count] or t_vals
        edge = left + right
        b_edge = _safe_mean([x.get("b") for x in edge])
        b_center = _safe_mean([x.get("b") for x in center])
        l_edge = _safe_mean([x.get("L") for x in edge])
        l_center = _safe_mean([x.get("L") for x in center])
        out["T_b_edge_mean"] = b_edge
        out["T_b_center_mean"] = b_center
        out["T_b_edge_center_delta"] = (b_edge - b_center) if (b_edge is not None and b_center is not None) else None
        out["T_b_left_right_delta"] = (_safe_mean([x.get("b") for x in left]) - _safe_mean([x.get("b") for x in right]))
        out["T_L_edge_center_delta"] = (l_edge - l_center) if (l_edge is not None and l_center is not None) else None
        b_all = [x.get("b") for x in t_vals if x.get("b") is not None]
        out["T_uniformity_score"] = max(0.0, 1.0 - ((max(b_all) - min(b_all)) / 10 if b_all else 0.0))

    nagy = by_device.get("NAGY", [])
    res = [x.get("Resistance") for x in nagy if x.get("Resistance") is not None]
    out["NAGY_resistance_mean"] = _safe_mean(res)
    if res:
        rm = mean(res)
        out["NAGY_resistance_std"] = (sum((x - rm) ** 2 for x in res) / len(res)) ** 0.5

    return [out]
