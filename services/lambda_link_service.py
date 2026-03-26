from __future__ import annotations

"""Link Lambda950 measurements to plates, preferring XML ID then time fallback."""

from datetime import timedelta


def link_lambda(plate_id: str, plate_time, lambda_records: list[dict], max_minutes: int = 90) -> dict | None:
    same_id = [x for x in lambda_records if str(x.get("plate_id") or "") == str(plate_id)]
    if same_id:
        return min(same_id, key=lambda x: abs((x.get("measure_time") - plate_time).total_seconds()) if x.get("measure_time") and plate_time else 0)
    time_ok = []
    if plate_time:
        for x in lambda_records:
            t = x.get("measure_time")
            if t and abs(t - plate_time) <= timedelta(minutes=max_minutes):
                time_ok.append(x)
    return min(time_ok, key=lambda x: abs((x.get("measure_time") - plate_time).total_seconds())) if time_ok else None
