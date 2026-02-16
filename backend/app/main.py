import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router


def configure_logging() -> None:
    debug = os.getenv("APP_DEBUG", "0") == "1"
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING if not debug else logging.INFO)


configure_logging()
app = FastAPI(title="Glass Coater ML Platform", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
