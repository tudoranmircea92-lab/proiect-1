from __future__ import annotations

import logging
import os
from collections import Counter

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as app_router
from core.errors import register_error_handlers
from routes.plasma import router as plasma_router


def configure_logging() -> None:
    debug = os.getenv("APP_DEBUG", "0") == "1"
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")


configure_logging()
app = FastAPI(title="Glass Coater ML Platform", version="1.0.0", redirect_slashes=False)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)

# Plasma contract-first routes.
app.include_router(plasma_router)

# Remaining application routes.
app.include_router(app_router)


@app.on_event("startup")
def _startup_validate_routes() -> None:
    entries: list[tuple[str, str]] = []
    print("[startup] routes:")
    for route in app.routes:
        methods = sorted(getattr(route, "methods", set()) or set())
        path = getattr(route, "path", "")
        if not methods or not path:
            continue
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            entries.append((method, path))
        print(f" - {','.join(methods):10s} {path}")

    counts = Counter(entries)
    duplicates = [f"{m} {p}" for (m, p), c in counts.items() if c > 1]
    if duplicates:
        raise RuntimeError(f"Duplicate routes detected: {duplicates}")

    required = {
        ("GET", "/api/plasma/health"),
        ("GET", "/api/plasma/columns"),
        ("POST", "/api/plasma/stability"),
        ("GET", "/api/plasma/stability/export"),
    }
    missing = sorted([f"{m} {p}" for (m, p) in required if (m, p) not in counts])
    if missing:
        raise RuntimeError(f"Missing required plasma routes: {missing}")

    print("[startup] No duplicate routes")


@app.get("/health")
def health():
    return {"status": "ok"}
