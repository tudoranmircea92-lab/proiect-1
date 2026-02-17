from __future__ import annotations

import os

PLASMA_SCORE_THRESHOLDS = {
    "normal_max": float(os.getenv("PLASMA_SCORE_NORMAL_MAX", "0.02")),
    "medium_max": float(os.getenv("PLASMA_SCORE_MEDIUM_MAX", "0.04")),
}

PLASMA_STATUS_MAPPING = {
    "Normal": "score <= normal_max",
    "Medium": "normal_max < score <= medium_max",
    "Critical": "score > medium_max",
    "OFF": "cathode active_rate == 0",
    "No data": "score unavailable",
}
