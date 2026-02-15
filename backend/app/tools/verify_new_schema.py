from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from backend.app.train.data_adapter import build_training_table, detect_schema_metadata, load_color, load_process


def main() -> None:
    parser = argparse.ArgumentParser(description='Verify new parquet schema migration')
    parser.add_argument('--process', required=True, help='Path to process parquet')
    parser.add_argument('--color', required=True, help='Path to color parquet')
    parser.add_argument('--key-strategy', default='auto', choices=['auto', 'plate+file_ts', 'plate+date+time'])
    args = parser.parse_args()

    process_df = load_process(args.process, mode='auto')
    color_df = load_color(args.color, mode='auto')

    process_meta = detect_schema_metadata(process_df, 'process')
    color_meta = detect_schema_metadata(color_df, 'color')
    merged_df, merge_stats = build_training_table(process_df, color_df, key_strategy=args.key_strategy)

    print('=== PROCESS META ===')
    print(process_meta)
    print('\n=== COLOR META ===')
    print(color_meta)
    print('\n=== MERGE STATS ===')
    print(merge_stats)
    print('\nMerged shape:', merged_df.shape)

    out_path = Path('backend/app/data/_debug_merged.parquet')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged_df.head(1000).to_parquet(out_path, index=False)
    print(f'Wrote debug merged sample to: {out_path}')


if __name__ == '__main__':
    main()
