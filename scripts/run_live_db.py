#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import shutil
import time
from datetime import date, datetime
from pathlib import Path

from live_db.build_model import build_model_features, build_model_targets
from live_db.build_operational import build_compartment_state, build_optics_summary, build_risk_summary, build_zone_summary
from live_db.config import LiveDBConfig
from live_db.pairing import choose_best_process_candidate, compute_awaiting_color_until, resolve_pair_status
from live_db.parse_optoplex import parse_optoplex_file
from live_db.parse_process import parse_process_file
from live_db.store import DuckStore
from live_db.validators import validate_optoplex_rows, validate_process_rows
from live_db.watch import acquire_lock, is_file_complete, list_candidate_files, release_lock


UPSERT_KEYS = {
    "file_registry": ["full_path"],
    "ingested_files": ["file_path"],
    "pairing_log": ["plate", "event_time", "optoplex_file_time", "pair_status"],
    "raw_process_long": ["plate", "event_time", "Location"],
    "raw_optoplex_long": ["plate", "stamp", "device_norm", "position"],
    "plate_core": ["plate", "event_time"],
    "optics_summary": ["plate", "event_time"],
    "compartment_state_long": ["plate", "event_time", "Location"],
    "zone_summary": ["plate", "event_time"],
    "risk_summary": ["plate", "event_time"],
    "model_features_plate": ["plate", "event_time"],
    "model_targets_plate": ["plate", "event_time"],
}


def setup_logging(log_file: Path | None):
    handlers = [logging.StreamHandler()]
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)


def move_file(path: Path, archive_dir: Path | None, bucket: str):
    if not archive_dir:
        return
    dst = archive_dir / bucket
    dst.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dst / path.name))


def create_or_replace_training_view(store: DuckStore):
    has_features = store.conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='model_features_plate'").fetchone()[0] > 0
    has_targets = store.conn.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='model_targets_plate'").fetchone()[0] > 0
    if not (has_features and has_targets):
        return
    required_target_cols = {
        "plate",
        "event_time",
        "target_T_L_mean",
        "target_T_a_mean",
        "target_T_b_mean",
        "target_T_RT_mean",
        "target_T_b_std",
        "target_T_b_edge_center_delta",
        "target_T_b_left_right_delta",
        "target_T_uniformity_score",
        "target_NAGY_resistance_mean",
    }
    target_cols = {
        row[0]
        for row in store.conn.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name='model_targets_plate'"
        ).fetchall()
    }
    if not required_target_cols.issubset(target_cols):
        return
    store.conn.execute(
        """
        CREATE OR REPLACE VIEW model_training_color AS
        SELECT f.*, t.target_T_L_mean, t.target_T_a_mean, t.target_T_b_mean, t.target_T_RT_mean,
               t.target_T_b_std, t.target_T_b_edge_center_delta, t.target_T_b_left_right_delta,
               t.target_T_uniformity_score, t.target_NAGY_resistance_mean
        FROM model_features_plate f
        JOIN model_targets_plate t USING(plate, event_time)
        """
    )


def validate_db_path(db_path: Path):
    if db_path.exists() and db_path.is_dir():
        raise ValueError(f"Invalid --db-path '{db_path}': expected a DuckDB file path, got directory.")
    if db_path.suffix.lower() != ".duckdb":
        raise ValueError(f"Invalid --db-path '{db_path}': must end with .duckdb")
    db_path.parent.mkdir(parents=True, exist_ok=True)


def today_folder(base: Path, current_date: date) -> Path:
    return base / f"{current_date.year:04d}" / f"{current_date.month:02d}" / f"{current_date.day:02d}"


def should_process_file(store: DuckStore, path: Path) -> bool:
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    row = store.conn.execute("SELECT file_mtime FROM ingested_files WHERE file_path=?", [str(path)]).fetchone()
    if not row:
        return True
    return row[0] != mtime


def mark_ingested_file(store: DuckStore, path: Path):
    store.upsert_rows(
        "ingested_files",
        [{"file_path": str(path), "file_mtime": datetime.fromtimestamp(path.stat().st_mtime), "ingested_at": datetime.utcnow()}],
        UPSERT_KEYS["ingested_files"],
    )


def log_pairing(store: DuckStore, plate: str, event_time: datetime | None, optoplex_file_time: datetime | None, pair_status: str, note: str):
    store.upsert_rows(
        "pairing_log",
        [{
            "plate": plate,
            "event_time": event_time,
            "optoplex_file_time": optoplex_file_time,
            "pair_status": pair_status,
            "note": note,
            "updated_at": datetime.utcnow(),
        }],
        UPSERT_KEYS["pairing_log"],
    )


def process_process_file(store: DuckStore, cfg: LiveDBConfig, path: Path, metrics: dict):
    rows, core = parse_process_file(path)
    vr = validate_process_rows(rows, cfg.required_columns)
    if not vr.ok:
        raise ValueError("; ".join(vr.errors))

    zone_map = cfg.get_zone_mapping(core.get("product"))
    comp = build_compartment_state(rows, zone_map, cfg.material_map, cfg.gas_map)
    zone = build_zone_summary(comp)
    risk = build_risk_summary(comp, cfg.thresholds)

    existing_core = store.conn.execute("SELECT has_color, pair_status, optoplex_file_time, color_source_file, created_at FROM plate_core WHERE plate=? AND event_time=?", [core["plate"], core["event_time"]]).fetchone()
    already_has_color = bool(existing_core[0]) if existing_core else False
    core["has_process"] = True
    core["has_color"] = already_has_color
    core["awaiting_color_until"] = compute_awaiting_color_until(core["event_time"], cfg.match_window)
    core["pair_status"] = "paired" if already_has_color else resolve_pair_status(True, False, core["awaiting_color_until"], datetime.utcnow())
    core["color_missing_reason"] = None if already_has_color else "pending_color"
    core["process_source_file"] = str(path)
    core["color_source_file"] = existing_core[3] if existing_core else None
    core["created_at"] = existing_core[4] if existing_core else datetime.utcnow()
    core["updated_at"] = datetime.utcnow()

    feats = build_model_features(core, zone, risk, comp)

    store.upsert_rows("raw_process_long", rows, UPSERT_KEYS["raw_process_long"])
    store.upsert_rows("plate_core", [core], UPSERT_KEYS["plate_core"])
    store.upsert_rows("compartment_state_long", comp, UPSERT_KEYS["compartment_state_long"])
    store.upsert_rows("zone_summary", zone, UPSERT_KEYS["zone_summary"])
    store.upsert_rows("risk_summary", risk, UPSERT_KEYS["risk_summary"])
    store.upsert_rows("model_features_plate", feats, UPSERT_KEYS["model_features_plate"])

    if core["pair_status"] == "process_only":
        log_pairing(store, core["plate"], core["event_time"], None, "process_only", "process arrived; awaiting color")

    orphans = store.conn.execute("SELECT plate, optoplex_file_time FROM orphan_optoplex WHERE status='pending' AND plate=?", [core["plate"]]).fetchall()
    if orphans:
        color_candidates = [{"event_time": core["event_time"], "plate": core["plate"]}]
        best = choose_best_process_candidate(color_candidates, orphans[0][1])
        if best and abs((best["event_time"] - orphans[0][1]).total_seconds()) <= cfg.match_window.total_seconds():
            store.conn.execute("UPDATE orphan_optoplex SET status='matched', matched_event_time=? WHERE plate=? AND status='pending'", [core["event_time"], core["plate"]])
            store.conn.execute(
                "UPDATE plate_core SET has_color=true, pair_status='late_color_matched', color_missing_reason=NULL, updated_at=?, optoplex_file_time=?, color_source_file=coalesce(color_source_file, (SELECT full_path FROM orphan_optoplex WHERE plate=? AND status='matched' LIMIT 1)) WHERE plate=? AND event_time=?",
                [datetime.utcnow(), orphans[0][1], core["plate"], core["plate"], core["event_time"]],
            )
            log_pairing(store, core["plate"], core["event_time"], orphans[0][1], "late_color_matched", "matched pending orphan after process ingest")

    metrics["rows_written"] += len(rows) + len(comp) + len(zone) + len(risk) + len(feats) + 1


def process_optoplex_file(store: DuckStore, cfg: LiveDBConfig, path: Path, metrics: dict):
    rows, meta = parse_optoplex_file(path, cfg.device_map)
    vr = validate_optoplex_rows(rows)
    if not vr.ok:
        raise ValueError("; ".join(vr.errors))

    store.upsert_rows("raw_optoplex_long", rows, UPSERT_KEYS["raw_optoplex_long"])
    candidates = store.conn.execute("SELECT plate, event_time FROM plate_core WHERE plate=?", [meta["plate"]]).fetchall()
    event_time = meta["event_time"]
    if candidates:
        typed = [{"plate": c[0], "event_time": c[1]} for c in candidates]
        best = choose_best_process_candidate(typed, meta["event_time"])
        if best and abs((best["event_time"] - meta["event_time"]).total_seconds()) <= cfg.match_window.total_seconds():
            event_time = best["event_time"]
            store.conn.execute(
                "UPDATE plate_core SET has_color=true, optoplex_file_time=?, pair_status='paired', color_missing_reason=NULL, color_source_file=?, updated_at=? WHERE plate=? AND event_time=?",
                [meta["optoplex_file_time"], str(path), datetime.utcnow(), meta["plate"], event_time],
            )
            log_pairing(store, meta["plate"], event_time, meta["optoplex_file_time"], "paired", "color matched to nearest process event")
        else:
            store.upsert_rows(
                "orphan_optoplex",
                [{"plate": meta["plate"], "optoplex_file_time": meta["optoplex_file_time"], "full_path": str(path), "status": "pending", "created_at": datetime.utcnow(), "matched_event_time": None}],
                ["plate", "optoplex_file_time"],
            )
            log_pairing(store, meta["plate"], None, meta["optoplex_file_time"], "color_only", "color file pending process match")
    else:
        store.upsert_rows(
            "orphan_optoplex",
            [{"plate": meta["plate"], "optoplex_file_time": meta["optoplex_file_time"], "full_path": str(path), "status": "pending", "created_at": datetime.utcnow(), "matched_event_time": None}],
            ["plate", "optoplex_file_time"],
        )
        log_pairing(store, meta["plate"], None, meta["optoplex_file_time"], "color_only", "color file pending process match")

    summary = build_optics_summary(rows, event_time)
    targets = build_model_targets(summary)
    store.upsert_rows("optics_summary", summary, UPSERT_KEYS["optics_summary"])
    store.upsert_rows("model_targets_plate", targets, UPSERT_KEYS["model_targets_plate"])
    metrics["rows_written"] += len(rows) + len(summary) + len(targets)


def expire_unmatched(store: DuckStore):
    expired_rows = store.conn.execute(
        """
        SELECT plate, event_time FROM plate_core
        WHERE has_process=true AND has_color=false AND awaiting_color_until < now() AND pair_status <> 'expired_unmatched'
        """
    ).fetchall()
    store.conn.execute(
        """
        UPDATE plate_core SET pair_status='expired_unmatched', color_missing_reason='window_expired', updated_at=now()
        WHERE has_process=true AND has_color=false AND awaiting_color_until < now()
        """
    )
    for plate, event_time in expired_rows:
        log_pairing(store, plate, event_time, None, "expired_unmatched", "matching window expired")


def run_once(cfg: LiveDBConfig, current_date: date):
    store = DuckStore(cfg.db_path)
    create_or_replace_training_view(store)
    run_id = store.start_run()
    metrics = {"files_seen": 0, "files_processed": 0, "files_failed": 0, "rows_written": 0, "pending_unmatched_count": 0}
    try:
        with store.tx():
            process_folder = today_folder(cfg.process_dir, current_date)
            optoplex_folder = today_folder(cfg.optoplex_dir, current_date)

            proc = list_candidate_files(process_folder, "*_glassFile.csv") if process_folder.exists() else []
            opt = list_candidate_files(optoplex_folder, "*_Plate-*.csv") if optoplex_folder.exists() else []

            if not process_folder.exists():
                logging.info("No folder for today yet. %s", process_folder)
            if not optoplex_folder.exists():
                logging.info("No folder for today yet. %s", optoplex_folder)

            all_files = [("process", p) for p in proc] + [("optoplex", p) for p in opt]
            metrics["files_seen"] = len(all_files)

            for typ, path in all_files:
                if not is_file_complete(path):
                    continue
                if not should_process_file(store, path):
                    continue

                ok = False
                err = None
                for _ in range(cfg.max_retries):
                    try:
                        if typ == "process":
                            process_process_file(store, cfg, path, metrics)
                        else:
                            process_optoplex_file(store, cfg, path, metrics)
                        ok = True
                        break
                    except Exception as exc:
                        err = str(exc)
                        logging.exception("Failed parsing %s", path)
                        time.sleep(0.1)
                status = "processed" if ok else "failed"
                store.upsert_rows(
                    "file_registry",
                    [{
                        "full_path": str(path),
                        "file_type": typ,
                        "file_size": path.stat().st_size,
                        "file_mtime": datetime.fromtimestamp(path.stat().st_mtime),
                        "status": status,
                        "error_text": err,
                        "processed_at": datetime.utcnow(),
                    }],
                    UPSERT_KEYS["file_registry"],
                )
                mark_ingested_file(store, path)
                if ok:
                    metrics["files_processed"] += 1
                    move_file(path, cfg.archive_dir, "processed")
                else:
                    metrics["files_failed"] += 1
                    move_file(path, cfg.archive_dir, "failed")

            expire_unmatched(store)
            metrics["pending_unmatched_count"] = store.conn.execute("SELECT count(*) FROM plate_core WHERE pair_status IN ('process_only','color_only')").fetchone()[0]

        store.finish_run(run_id, "ok", metrics)
    except Exception as exc:
        store.finish_run(run_id, "failed", metrics, str(exc))
        raise
    finally:
        store.close()


def parse_args() -> LiveDBConfig:
    p = argparse.ArgumentParser()
    p.add_argument("--optoplex-dir", required=True)
    p.add_argument("--process-dir", required=True)
    p.add_argument("--db-path", required=True)
    p.add_argument("--poll-seconds", type=int, default=10)
    p.add_argument("--match-window-minutes", type=int, default=10)
    p.add_argument("--backfill", action="store_true")
    p.add_argument("--archive-dir")
    p.add_argument("--log-file")
    p.add_argument("--one-shot", action="store_true")
    a = p.parse_args()
    return LiveDBConfig(
        optoplex_dir=Path(a.optoplex_dir),
        process_dir=Path(a.process_dir),
        db_path=Path(a.db_path),
        poll_seconds=a.poll_seconds,
        match_window_minutes=a.match_window_minutes,
        backfill=a.backfill,
        archive_dir=Path(a.archive_dir) if a.archive_dir else None,
        log_file=Path(a.log_file) if a.log_file else None,
        one_shot=a.one_shot,
    )


def main():
    cfg = parse_args()
    validate_db_path(cfg.db_path)
    setup_logging(cfg.log_file)
    lock_file = cfg.db_path.with_suffix(".lock")
    if not acquire_lock(lock_file):
        raise SystemExit("Another instance is already running.")
    try:
        if cfg.one_shot:
            run_once(cfg, date.today())
            return
        active_date = date.today()
        while True:
            current = date.today()
            if current != active_date:
                active_date = current
                logging.info("Date rollover detected, switching to folder date: %s", active_date.isoformat())
            run_once(cfg, active_date)
            time.sleep(cfg.poll_seconds)
    finally:
        release_lock(lock_file)


if __name__ == "__main__":
    main()
