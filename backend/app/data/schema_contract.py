from __future__ import annotations

import re
from dataclasses import dataclass

# Primary merge keys
PLATE_KEY_CANDIDATES = ['plate', 'Plate', 'PLATE']
FILE_TS_CANDIDATES = ['file_ts', 'timestamp', 'process_ts', 'color_ts', 'datetime', 'date_time']
DATE_CANDIDATES = ['date', 'process_date', 'color_date']
TIME_CANDIDATES = ['time', 'process_time', 'color_time']

# Target candidates (wide preferred)
TARGET_COLUMN_PATTERNS = [
    re.compile(r'.*L\*.*', re.IGNORECASE),
    re.compile(r'.*a\*.*', re.IGNORECASE),
    re.compile(r'.*b\*.*', re.IGNORECASE),
    re.compile(r'.*L_star.*', re.IGNORECASE),
    re.compile(r'.*a_star.*', re.IGNORECASE),
    re.compile(r'.*b_star.*', re.IGNORECASE),
]

# Strict knob contract:
# - c{comp}.pwr
# - c{comp}.m1g, c{comp}.m2g, c{comp}.m3g
# - c{comp}.s1g ... c{comp}.s11g
KNOB_REGEX = re.compile(r'^c\d+\.(?:pwr|m[123]g|s(?:[1-9]|10|11)g)$')


@dataclass(frozen=True)
class KeyStrategy:
    name: str
    required: tuple[str, ...]


KEY_STRATEGY_FILE_TS = KeyStrategy('plate+file_ts', ('plate', 'file_ts'))
KEY_STRATEGY_DATE_TIME = KeyStrategy('plate+date+time', ('plate', 'date', 'time'))

SUPPORTED_KEY_STRATEGIES = (
    KEY_STRATEGY_FILE_TS,
    KEY_STRATEGY_DATE_TIME,
)

# One training row = one unique plate-time entity (plate + file_ts preferred).
TRAINING_ROW_DEFINITION = 'one unique plate-time entity (plate + file_ts preferred; plate + date + time fallback)'


def is_knob_column(column: str) -> bool:
    return bool(KNOB_REGEX.match(str(column)))


def detect_target_columns(columns: list[str]) -> list[str]:
    out: list[str] = []
    for c in columns:
        if any(p.match(c) for p in TARGET_COLUMN_PATTERNS):
            out.append(c)
    return sorted(set(out))
