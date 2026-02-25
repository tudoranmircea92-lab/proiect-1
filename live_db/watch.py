from __future__ import annotations

import time
from pathlib import Path


def list_candidate_files(folder: Path, pattern: str) -> list[Path]:
    return sorted(p for p in folder.glob(pattern) if p.is_file())


def is_file_complete(path: Path, wait_seconds: float = 0.2) -> bool:
    if not path.exists():
        return False
    s1 = path.stat().st_size
    time.sleep(wait_seconds)
    s2 = path.stat().st_size
    time.sleep(wait_seconds)
    s3 = path.stat().st_size
    return s1 == s2 == s3


def acquire_lock(lock_path: Path) -> bool:
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        fd = lock_path.open("x")
        fd.write(str(time.time()))
        fd.close()
        return True
    except FileExistsError:
        return False


def release_lock(lock_path: Path) -> None:
    if lock_path.exists():
        lock_path.unlink()
