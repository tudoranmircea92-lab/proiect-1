from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.app.core import scan_files
from backend.app.services.io_utils import SUPPORTED_EXTENSIONS

router = APIRouter(prefix='/api', tags=['scan'])

UPLOAD_DIR = Path('backend/app/data/uploads')


@router.post('/scan')
async def api_scan(files: list[UploadFile] = File(default_factory=list)):
    try:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        paths = []
        for f in files:
            if not f.filename:
                continue
            ext = Path(f.filename).suffix.lower()
            if ext not in SUPPORTED_EXTENSIONS:
                raise ValueError("Invalid file type selected. Please upload a .csv, .xlsx, or .parquet file.")
            p = UPLOAD_DIR / f.filename
            p.write_bytes(f.file.read())
            paths.append(str(p))
        return scan_files(paths)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
