from __future__ import annotations

"""Comparison helpers for good vs bad plates."""


def compare_feature_maps(good: dict[str, float | None], bad: dict[str, float | None]) -> list[dict[str, float | None | str]]:
    rows: list[dict[str, float | None | str]] = []
    for key in sorted(set(good) | set(bad)):
        gv = good.get(key)
        bv = bad.get(key)
        diff = None
        if gv is not None and bv is not None:
            diff = bv - gv
        rows.append({"feature": key, "good": gv, "bad": bv, "delta": diff})
    return rows
