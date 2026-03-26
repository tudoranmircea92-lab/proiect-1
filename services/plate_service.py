from __future__ import annotations

"""Plate linking and aggregation service used by Streamlit pages."""

from datetime import timedelta


def link_process_optoplex(process_rows: list[dict], optoplex_rows: list[dict], fallback_minutes: int = 45) -> list[dict]:
    out: list[dict] = []
    by_plate_proc: dict[str, list[dict]] = {}
    by_plate_opt: dict[str, list[dict]] = {}
    for p in process_rows:
        by_plate_proc.setdefault(str(p.get("plate_id") or ""), []).append(p)
    for o in optoplex_rows:
        by_plate_opt.setdefault(str(o.get("plate_id") or ""), []).append(o)

    all_plates = sorted(set(by_plate_proc) | set(by_plate_opt))
    for plate in all_plates:
        proc = by_plate_proc.get(plate, [])
        opt = by_plate_opt.get(plate, [])
        if proc and opt:
            out.append({"plate_id": plate, "process": proc[0], "optoplex": opt[0], "match_type": "plate_id"})
            continue
        best = None
        for p in proc:
            for o in opt:
                pt, ot = p.get("file_time"), o.get("file_time")
                if pt and ot and abs(pt - ot) <= timedelta(minutes=fallback_minutes):
                    best = {"plate_id": plate or str(p.get("plate_id") or o.get("plate_id") or ""), "process": p, "optoplex": o, "match_type": "time_window"}
        if best:
            out.append(best)
        elif proc or opt:
            out.append({"plate_id": plate, "process": proc[0] if proc else None, "optoplex": opt[0] if opt else None, "match_type": "partial"})
    return out
