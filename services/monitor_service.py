from __future__ import annotations

"""Monitoring service for recent drift/anomaly overview."""


def top_anomalies(plates: list[dict], score_key: str = "anomaly_score", top_n: int = 20) -> list[dict]:
    ranked = sorted(plates, key=lambda x: x.get(score_key) or 0, reverse=True)
    return ranked[:top_n]
