from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / '.env')

from backend.app.main import app


if __name__ == '__main__':
    import uvicorn

    uvicorn.run('backend.main:app', host='127.0.0.1', port=8000, reload=True)
