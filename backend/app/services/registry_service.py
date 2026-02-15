from __future__ import annotations

from datetime import datetime
from pathlib import Path

from backend.app.services.io_utils import read_json, write_json

REGISTRY_ROOT = Path("backend/app/registry")
INDEX_FILE = REGISTRY_ROOT / "index.json"
RESULTS_FILE = REGISTRY_ROOT / "optimize_results.json"


def _load_index() -> dict:
    return read_json(INDEX_FILE, {"entries": [], "active": {}})


def _save_index(index: dict) -> None:
    write_json(INDEX_FILE, index)


def add_entry(entry: dict) -> None:
    index = _load_index()
    index["entries"].append(entry)
    _save_index(index)


def list_entries(product_name: str | None = None) -> list[dict]:
    index = _load_index()
    entries = index.get("entries", [])
    active = index.get("active", {})
    if product_name:
        entries = [e for e in entries if e.get("product_name") == product_name]
    enriched = []
    for e in entries:
        key = f"{e['product_name']}::{e['model_type']}"
        enriched.append({**e, "is_active": active.get(key) == e["run_id"]})
    return sorted(enriched, key=lambda x: x.get("created_at", ""), reverse=True)


def activate_model(run_id: str) -> dict:
    index = _load_index()
    match = next((e for e in index.get("entries", []) if e["run_id"] == run_id), None)
    if not match:
        raise ValueError("Run id not found")
    key = f"{match['product_name']}::{match['model_type']}"
    index.setdefault("active", {})[key] = run_id
    _save_index(index)
    return match


def get_active_model(product_name: str, model_type: str = "process") -> dict | None:
    index = _load_index()
    key = f"{product_name}::{model_type}"
    general_key = f"GENERAL::{model_type}"
    run_id = index.get("active", {}).get(key) or index.get("active", {}).get(general_key)
    if not run_id:
        return None
    return next((e for e in index.get("entries", []) if e["run_id"] == run_id), None)


def ensure_registry_dirs(run_id: str) -> Path:
    path = REGISTRY_ROOT / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def add_optimize_result(payload: dict) -> None:
    data = read_json(RESULTS_FILE, {"results": []})
    data["results"].append(payload)
    write_json(RESULTS_FILE, data)


def list_optimize_results(limit: int = 25) -> list[dict]:
    data = read_json(RESULTS_FILE, {"results": []})
    return list(reversed(data["results"][-limit:]))


def stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")
