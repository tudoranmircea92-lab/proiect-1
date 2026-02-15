from __future__ import annotations

CONTROLLABLE_SUFFIXES = [
    '.pwr', '.m1g', '.m2g', '.m3g',
    '.s1g', '.s2g', '.s3g', '.s4g', '.s5g',
    '.s6g', '.s7g', '.s8g', '.s9g', '.s10g', '.s11g',
]

MANDATORY_COLUMNS = ['date', 'plate', 'process_ts', 'color_ts']
LEAKAGE_COLUMNS = ['entryTime', 'exitTime', 'res_time_s']

# Backward-compatible aliases used elsewhere in the codebase
MANDATORY_COLUMN = 'product_name'
PLATE_COLUMN = 'plate'
TIMESTAMP_CANDIDATES = ['timestamp', 'process_ts', 'color_ts', 'datetime', 'date']


def is_controllable_column(col: str) -> bool:
    return any(col.endswith(s) for s in CONTROLLABLE_SUFFIXES)


def detect_compartments(columns: list[str]) -> list[str]:
    out = set()
    for c in columns:
        if c.startswith('c') and '.' in c:
            out.add(c.split('.', 1)[0])
    return sorted(out)
