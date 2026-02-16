from __future__ import annotations

import json
from pathlib import Path

from main import app


def _plasma_paths_snapshot() -> dict[str, list[str]]:
    schema = app.openapi()
    paths = schema.get("paths", {})
    filtered: dict[str, list[str]] = {}
    for path, methods in paths.items():
        if not path.startswith("/api/plasma"):
            continue
        filtered[path] = sorted([m for m in methods.keys() if m in {"get", "post", "put", "patch", "delete"}])
    return dict(sorted(filtered.items()))


def test_plasma_openapi_snapshot_matches_contract():
    snapshot_path = Path(__file__).resolve().parents[1] / "contracts" / "openapi_plasma.json"
    expected = json.loads(snapshot_path.read_text())
    actual = _plasma_paths_snapshot()
    assert actual == expected
