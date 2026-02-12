from __future__ import annotations

import argparse
from pathlib import Path

from glass_processor_constants import (
    END_DEFAULT,
    INPUT_DEFAULT,
    OUTPUT_DEFAULT,
    PATTERN_DEFAULT,
    START_DEFAULT,
    TMP_CSV_DEFAULT,
)
from glass_processor_parsing import parse_ymd
from glass_processor_pipeline import stream_to_tmp_csv, tmp_csv_to_excel


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Clean glassFile process CSVs -> one Excel (one sheet), includes nomGasSegment, scans UNC root by day range, no sorting within day."
    )
    ap.add_argument("--input-root", default=INPUT_DEFAULT, help="UNC root like \\\\server\\share\\...\\process")
    ap.add_argument("--start", default=START_DEFAULT, help="Start date (YYYY-MM-DD or DD.MM.YYYY)")
    ap.add_argument("--end", default=END_DEFAULT, help="End date (YYYY-MM-DD or DD.MM.YYYY)")
    ap.add_argument("--pattern", default=PATTERN_DEFAULT)
    ap.add_argument("--output-xlsx", default=OUTPUT_DEFAULT)
    ap.add_argument("--tmp-csv", default=TMP_CSV_DEFAULT)
    ap.add_argument("--buffer-rows", type=int, default=200_000)
    ap.add_argument("--keep-tmp", action="store_true")
    args = ap.parse_args()

    input_root = Path(args.input_root)
    start_d = parse_ymd(args.start)
    end_d = parse_ymd(args.end)
    if end_d < start_d:
        raise SystemExit("end date must be >= start date")

    tmp_csv = Path(args.tmp_csv)
    out_xlsx = Path(args.output_xlsx)

    stream_to_tmp_csv(input_root, start_d, end_d, str(args.pattern), tmp_csv, flush_rows=int(args.buffer_rows))
    tmp_csv_to_excel(tmp_csv, out_xlsx)

    if not args.keep_tmp:
        try:
            tmp_csv.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
