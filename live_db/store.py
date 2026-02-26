from __future__ import annotations

import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import duckdb


def _sql_type(value):
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "BIGINT"
    if isinstance(value, float):
        return "DOUBLE"
    if isinstance(value, datetime):
        return "TIMESTAMP"
    return "VARCHAR"


class DuckStore:
    def __init__(self, db_path: Path):
        self.conn = duckdb.connect(str(db_path))
        self.init_schema()

    def close(self):
        self.conn.close()

    @contextmanager
    def tx(self):
        self.conn.execute("BEGIN")
        try:
            yield
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def init_schema(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS file_registry (
                full_path VARCHAR PRIMARY KEY,
                file_type VARCHAR,
                file_size BIGINT,
                file_mtime TIMESTAMP,
                status VARCHAR,
                error_text VARCHAR,
                processed_at TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS pairing_log (
                plate VARCHAR,
                event_time TIMESTAMP,
                optoplex_file_time TIMESTAMP,
                pair_status VARCHAR,
                note VARCHAR,
                updated_at TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS orphan_optoplex (
                plate VARCHAR,
                optoplex_file_time TIMESTAMP,
                full_path VARCHAR,
                status VARCHAR,
                created_at TIMESTAMP,
                matched_event_time TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS ingest_runs (
                run_id VARCHAR,
                run_started_at TIMESTAMP,
                run_finished_at TIMESTAMP,
                status VARCHAR,
                files_seen BIGINT,
                files_processed BIGINT,
                files_failed BIGINT,
                rows_written BIGINT,
                pending_unmatched_count BIGINT,
                error_text VARCHAR
            );
            CREATE TABLE IF NOT EXISTS ingested_files (
                file_path VARCHAR PRIMARY KEY,
                file_mtime TIMESTAMP,
                ingested_at TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS plate_core (
                plate VARCHAR,
                event_time TIMESTAMP,
                product VARCHAR,
                glassWidth DOUBLE,
                glassLength DOUBLE,
                glassThickness DOUBLE,
                glassState VARCHAR,
                nomProcessSpeed_mm DOUBLE,
                actProcessSpeed_mm DOUBLE,
                deltaProcessSpeed_mm DOUBLE,
                optoplex_file_time TIMESTAMP,
                process_file_time TIMESTAMP,
                has_process BOOLEAN,
                has_color BOOLEAN,
                pair_status VARCHAR,
                color_missing_reason VARCHAR,
                awaiting_color_until TIMESTAMP,
                PRIMARY KEY(plate, event_time)
            );
            CREATE TABLE IF NOT EXISTS raw_process_long (
                plate VARCHAR,
                event_time TIMESTAMP,
                Location BIGINT,
                PRIMARY KEY(plate, event_time, Location)
            );
            CREATE TABLE IF NOT EXISTS raw_optoplex_long (
                plate VARCHAR,
                stamp TIMESTAMP,
                device_norm VARCHAR,
                position BIGINT,
                PRIMARY KEY(plate, stamp, device_norm, position)
            );
            CREATE TABLE IF NOT EXISTS compartment_state_long (
                plate VARCHAR,
                event_time TIMESTAMP,
                Location BIGINT,
                PRIMARY KEY(plate, event_time, Location)
            );
            CREATE TABLE IF NOT EXISTS zone_summary (
                plate VARCHAR,
                event_time TIMESTAMP,
                PRIMARY KEY(plate, event_time)
            );
            CREATE TABLE IF NOT EXISTS risk_summary (
                plate VARCHAR,
                event_time TIMESTAMP,
                PRIMARY KEY(plate, event_time)
            );
            CREATE TABLE IF NOT EXISTS optics_summary (
                plate VARCHAR,
                event_time TIMESTAMP,
                PRIMARY KEY(plate, event_time)
            );
            CREATE TABLE IF NOT EXISTS model_features_plate (
                plate VARCHAR,
                event_time TIMESTAMP,
                PRIMARY KEY(plate, event_time)
            );
            CREATE TABLE IF NOT EXISTS model_targets_plate (
                plate VARCHAR,
                event_time TIMESTAMP,
                PRIMARY KEY(plate, event_time)
            );
            """
        )

    def ensure_table_for_rows(self, table: str, rows: list[dict]):
        if not rows:
            return
        cols = rows[0]
        col_defs = ", ".join(f'"{k}" {_sql_type(v)}' for k, v in cols.items())
        self.conn.execute(f'CREATE TABLE IF NOT EXISTS {table} ({col_defs});')
        existing = {r[1] for r in self.conn.execute(f"PRAGMA table_info('{table}')").fetchall()}
        for k, v in cols.items():
            if k not in existing:
                self.conn.execute(f'ALTER TABLE {table} ADD COLUMN "{k}" {_sql_type(v)}')

    def upsert_rows(self, table: str, rows: list[dict], key_cols: list[str]):
        if not rows:
            return
        self.ensure_table_for_rows(table, rows)
        temp = f"tmp_{table}_{uuid.uuid4().hex[:8]}"
        cols = list(rows[0].keys())
        self.conn.execute(f'CREATE TEMP TABLE {temp} AS SELECT * FROM {table} WHERE 1=0')
        placeholders = ",".join(["?"] * len(cols))
        col_list = ', '.join([f'"{c}"' for c in cols])
        self.conn.executemany(
            f'INSERT INTO {temp} ({col_list}) VALUES ({placeholders})',
            [[r.get(c) for c in cols] for r in rows],
        )
        on_clause = " AND ".join([f't."{k}" = s."{k}"' for k in key_cols])
        updates = ", ".join([f'"{c}" = s."{c}"' for c in cols if c not in key_cols])
        insert_cols = ", ".join([f'"{c}"' for c in cols])
        insert_vals = ", ".join([f's."{c}"' for c in cols])
        self.conn.execute(
            f'''
            MERGE INTO {table} t
            USING {temp} s
            ON {on_clause}
            WHEN MATCHED THEN UPDATE SET {updates}
            WHEN NOT MATCHED THEN INSERT ({insert_cols}) VALUES ({insert_vals})
            '''
        )
        self.conn.execute(f"DROP TABLE {temp}")

    def start_run(self) -> str:
        run_id = uuid.uuid4().hex
        self.conn.execute(
            "INSERT INTO ingest_runs(run_id, run_started_at, status, files_seen, files_processed, files_failed, rows_written, pending_unmatched_count) VALUES (?, now(), 'running', 0,0,0,0,0)",
            [run_id],
        )
        return run_id

    def finish_run(self, run_id: str, status: str, metrics: dict, error_text: str | None = None):
        self.conn.execute(
            """
            UPDATE ingest_runs
            SET run_finished_at = now(), status = ?, files_seen = ?, files_processed = ?, files_failed = ?, rows_written = ?, pending_unmatched_count = ?, error_text = ?
            WHERE run_id = ?
            """,
            [
                status,
                metrics.get("files_seen", 0),
                metrics.get("files_processed", 0),
                metrics.get("files_failed", 0),
                metrics.get("rows_written", 0),
                metrics.get("pending_unmatched_count", 0),
                error_text,
                run_id,
            ],
        )
