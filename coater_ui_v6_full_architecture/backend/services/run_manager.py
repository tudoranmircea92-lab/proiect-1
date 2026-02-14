from __future__ import annotations

import csv
import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .data_loader import DataRepository
from .optimizer import KnobBound, OptimizerEngine
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class RunState:
    run_id: str
    state: str = "queued"
    progress: int = 0
    stage: str = "created"
    logs: List[str] = field(default_factory=list)
    results: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class RunManager:
    def __init__(self, repo: DataRepository):
        self.repo = repo
        self._states: Dict[str, RunState] = {}
        self._cancel_flags: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def start(self, payload: Dict[str, Any]) -> str:
        run_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._states[run_id] = RunState(run_id=run_id)
            self._cancel_flags[run_id] = threading.Event()
        threading.Thread(target=self._execute, args=(run_id, payload), daemon=True).start()
        return run_id

    def status(self, run_id: str) -> Dict[str, Any]:
        with self._lock:
            st = self._states.get(run_id)
        return asdict(st) if st else {"error": "run_id not found"}

    def cancel(self, run_id: str) -> Dict[str, Any]:
        flag = self._cancel_flags.get(run_id)
        if not flag:
            return {"error": "run_id not found"}
        flag.set()
        return {"status": "cancel_requested", "run_id": run_id}

    def results(self, run_id: str) -> Dict[str, Any]:
        with self._lock:
            st = self._states.get(run_id)
        if not st:
            return {"error": "run_id not found"}
        return st.results if st.results else {"state": st.state, "error": st.error}

    def _log(self, run_id: str, message: str) -> None:
        logger.info("run=%s %s", run_id, message)
        with self._lock:
            if run_id in self._states:
                self._states[run_id].logs.append(message)

    def _update(self, run_id: str, **kwargs: Any) -> None:
        with self._lock:
            st = self._states[run_id]
            for k, v in kwargs.items():
                setattr(st, k, v)

    def _execute(self, run_id: str, payload: Dict[str, Any]) -> None:
        cancel_flag = self._cancel_flags[run_id]
        self._update(run_id, state="running", stage="loading_dataset", progress=5)
        self._log(run_id, "Run started")

        rows = self.repo.load()
        if not rows:
            self._update(run_id, state="failed", error="Dataset unavailable or empty", progress=100)
            return
        if cancel_flag.is_set():
            self._update(run_id, state="cancelled", stage="cancelled", progress=100)
            return

        self._update(run_id, stage="filtering_context", progress=20)
        subset = self.repo.filter_for_run(
            rows,
            payload.get("date", ""),
            str(payload.get("plate", "")),
            payload.get("device"),
            payload.get("compartments", []),
        )
        if not subset:
            self._update(run_id, state="failed", error="No data for selected context", progress=100)
            return

        self._update(run_id, stage="optimizing", progress=55)
        bounds: Dict[str, KnobBound] = {}
        for knob, b in payload.get("knob_bounds", {}).items():
            bounds[knob] = KnobBound(
                minimum=float(b.get("min", -1e9)),
                maximum=float(b.get("max", 1e9)),
                step=float(b.get("step", 0.1)),
                locked=bool(b.get("locked", False)),
            )
        if not bounds:
            for col in subset[0].keys():
                if "." in col and col.startswith("c"):
                    bounds[col] = KnobBound(-1e9, 1e9, 0.1, False)

        engine = OptimizerEngine()
        recs = engine.build_recommendations(
            subset=subset,
            target_a=float(payload.get("target", {}).get("a", 0.0)),
            target_b=float(payload.get("target", {}).get("b", 0.0)),
            tolerance_de=float(payload.get("tolerances", {}).get("deltaE", 1.0)),
            knob_bounds=bounds,
            top_k=3,
        )

        if cancel_flag.is_set():
            self._update(run_id, state="cancelled", stage="cancelled", progress=100)
            return

        self._update(run_id, stage="writing_artifacts", progress=80)
        artifacts = self._write_artifacts(run_id, payload, recs)

        result_payload = {
            "run_id": run_id,
            "state": "completed",
            "recommendations": [asdict(r) for r in recs],
            "artifacts": artifacts,
        }
        self._update(run_id, state="completed", stage="done", progress=100, results=result_payload)
        self._log(run_id, "Run completed")

    def _write_artifacts(self, run_id: str, payload: Dict[str, Any], recs: List[Any]) -> Dict[str, str]:
        date_dir = datetime.utcnow().strftime("%Y-%m-%d")
        base = Path("artifacts") / date_dir / run_id
        base.mkdir(parents=True, exist_ok=True)

        summary = {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "input": payload,
            "dataset_path": str(self.repo.dataset_path) if self.repo.dataset_path else None,
        }
        (base / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

        rec_list = [asdict(r) for r in recs]
        (base / "recommendations.json").write_text(json.dumps(rec_list, indent=2), encoding="utf-8")

        with (base / "recommendations.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["rank", "delta_a", "delta_b", "delta_e", "tolerance_pass"])
            for r in recs:
                writer.writerow([r.rank, r.predicted_delta_a, r.predicted_delta_b, r.predicted_delta_e, r.tolerance_pass])

        # Minimal XLSX fallback artifact (CSV content with .xlsx extension for environments without excel libs).
        with (base / "recommendations.xlsx").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["rank", "delta_a", "delta_b", "delta_e", "tolerance_pass"])
            for r in recs:
                writer.writerow([r.rank, r.predicted_delta_a, r.predicted_delta_b, r.predicted_delta_e, r.tolerance_pass])

        changes = []
        for r in recs:
            for c in r.changes:
                changes.append({"rank": r.rank, **c})
        (base / "knob_changes.json").write_text(json.dumps(changes, indent=2), encoding="utf-8")

        with (base / "run_log.txt").open("w", encoding="utf-8") as f:
            for line in self._states[run_id].logs:
                f.write(line + "\n")

        return {
            "base": str(base),
            "summary": str(base / "run_summary.json"),
            "json": str(base / "recommendations.json"),
            "csv": str(base / "recommendations.csv"),
            "xlsx": str(base / "recommendations.xlsx"),
            "knob_changes": str(base / "knob_changes.json"),
            "log": str(base / "run_log.txt"),
        }
