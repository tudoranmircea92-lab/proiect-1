from __future__ import annotations

from datetime import datetime, timedelta


def choose_best_process_candidate(candidates: list[dict], color_time: datetime) -> dict | None:
    if not candidates:
        return None
    return min(candidates, key=lambda c: abs((c["event_time"] - color_time).total_seconds()))


def resolve_pair_status(has_process: bool, has_color: bool, awaiting_color_until: datetime | None, now: datetime) -> str:
    if has_process and has_color:
        return "paired"
    if has_process and not has_color:
        if awaiting_color_until and now > awaiting_color_until:
            return "expired_unmatched"
        return "process_only"
    if has_color and not has_process:
        return "color_only"
    return "unknown"


def compute_awaiting_color_until(event_time: datetime, window: timedelta) -> datetime:
    return event_time + window
