from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class JobState:
    job_id: str
    status: str = "queued"
    progress: int = 0
    stage: str = "Queued"
    result: Any = None
    error: str | None = None
    updated_at: float = field(default_factory=time.time)


class JobService:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        job_id = uuid.uuid4().hex[:12]
        with self._lock:
            self._jobs[job_id] = JobState(job_id=job_id)
        return job_id

    def update(self, job_id: str, *, status: str | None = None, progress: int | None = None, stage: str | None = None, result: Any = None, error: str | None = None) -> None:
        with self._lock:
            job = self._jobs[job_id]
            if status is not None:
                job.status = status
            if progress is not None:
                job.progress = progress
            if stage is not None:
                job.stage = stage
            if result is not None:
                job.result = result
            if error is not None:
                job.error = error
            job.updated_at = time.time()

    def get(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            j = self._jobs[job_id]
            return {
                "job_id": j.job_id,
                "status": j.status,
                "progress": j.progress,
                "stage": j.stage,
                "result": j.result,
                "error": j.error,
                "updated_at": j.updated_at,
            }

    def run_async(self, job_id: str, func: Callable[[], Any]) -> None:
        def _runner() -> None:
            try:
                self.update(job_id, status="running")
                result = func()
                self.update(job_id, status="done", progress=100, stage="Done", result=result)
            except Exception as exc:
                self.update(job_id, status="error", error=str(exc), stage="Failed")

        threading.Thread(target=_runner, daemon=True).start()
