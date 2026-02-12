from __future__ import annotations

import re
from datetime import date, datetime
from typing import List, Optional

_RE_WS = re.compile(r"\s+")
_RE_COMP = re.compile(r"compartment\s*-\s*(\d+)", re.IGNORECASE)
_RE_COMPACT = re.compile(r"^\d{8}(\d{6})?$")


def norm_col(c: str) -> str:
    return _RE_WS.sub(" ", (c or "").strip())


def sniff_delim_from_line(line: str) -> str:
    if line.count(";") >= 3 and line.count(";") > line.count(","):
        return ";"
    if line.count(",") >= 3:
        return ","
    if "\t" in line:
        return "\t"
    return ";"


def find_col_idx(header: List[str], name: str) -> Optional[int]:
    name_l = norm_col(name).lower()
    h_low = [norm_col(x).lower() for x in header]
    try:
        return h_low.index(name_l)
    except ValueError:
        return None


def safe_get(row: List[str], idx: Optional[int]) -> str:
    if idx is None or idx < 0 or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def _try_parse_multiple_formats(s: str) -> Optional[datetime]:
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%d.%m.%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d",
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def to_date_ymd(ts_raw: str) -> str:
    """
    Normalize optoplexGTime to YYYY-MM-DD.

    Supports:
    - 'YYYY-DD-MM' (glass export)  -> swap to ISO
    - 'YYYY-MM-DD' (ISO)           -> keep
    - 'YYYY-MM-DD ...' / ISO T...  -> keep first 10 chars logic
    - 'DD.MM.YYYY'                 -> convert
    - 'YYYYMMDD'                   -> convert
    - 'YYYYMMDDHHMMSS'             -> convert (first 8 digits)
    """
    s = (ts_raw or "").strip()
    if not s:
        return ""

    # Case A: compact numeric formats only when the whole string is compact
    if _RE_COMPACT.match(s):
        digits = s[:8]
        yyyy, mm, dd = digits[0:4], digits[4:6], digits[6:8]
        y, m, d = int(yyyy), int(mm), int(dd)
        if 1 <= m <= 12 and 1 <= d <= 31:
            return f"{y:04d}-{m:02d}-{d:02d}"

    # Case B: YYYY-??-?? (possibly followed by time)
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        yyyy = s[0:4]
        part1 = s[5:7]
        part2 = s[8:10]

        if yyyy.isdigit() and part1.isdigit() and part2.isdigit():
            p1 = int(part1)
            p2 = int(part2)

            # glass format = YYYY-DD-MM → swap to YYYY-MM-DD
            if p1 > 12 and p2 <= 12:
                dd, mm = p1, p2
                return f"{int(yyyy):04d}-{mm:02d}-{dd:02d}"

            # already ISO = YYYY-MM-DD
            if p2 > 12 and p1 <= 12:
                mm, dd = p1, p2
                return f"{int(yyyy):04d}-{mm:02d}-{dd:02d}"

            # ambiguous (01..12 both) -> domain rule: glass export uses YYYY-DD-MM
            dd, mm = p1, p2
            return f"{int(yyyy):04d}-{mm:02d}-{dd:02d}"

    # Case C: DD.MM.YYYY
    if len(s) >= 10 and s[2] == "." and s[5] == ".":
        dd, mm, yyyy = s[0:2], s[3:5], s[6:10]
        if dd.isdigit() and mm.isdigit() and yyyy.isdigit():
            d, m, y = int(dd), int(mm), int(yyyy)
            return f"{y:04d}-{m:02d}-{d:02d}"

    # Case D: fallback with explicit stdlib formats only
    dt = _try_parse_multiple_formats(s)
    if dt is None:
        return ""
    return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"


def parse_comp_to_int(loc: str) -> Optional[int]:
    s = (loc or "").strip()
    if not s:
        return None
    m = _RE_COMP.search(s.replace("_", "-"))
    if not m:
        return None
    try:
        return int(m.group(1))
    except Exception:
        return None


def round2_str(val: str) -> str:
    s = (val or "").strip()
    if not s:
        return ""
    s = s.replace(" ", "")
    if any(ch.isalpha() for ch in s):
        return s
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        x = float(s)
        return f"{x:.2f}"
    except Exception:
        return (val or "").strip()


def parse_ymd(s: str) -> date:
    s = (s or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    if len(s) >= 10 and s[2] == "." and s[5] == ".":
        return datetime.strptime(s[:10], "%d.%m.%Y").date()
    raise ValueError(f"Bad date format: {s!r} (use YYYY-MM-DD or DD.MM.YYYY)")
