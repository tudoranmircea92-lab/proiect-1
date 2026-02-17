@echo off
setlocal

echo [1/5] Preparing backend virtual environment...
if not exist backend\.venv (
  py -3 -m venv backend\.venv
)

call backend\.venv\Scripts\activate.bat
if errorlevel 1 (
  echo Failed to activate backend venv.
  exit /b 1
)

echo [2/5] Installing backend dependencies...
pip install -r backend\requirements.txt
if errorlevel 1 (
  echo Backend dependency install failed.
  exit /b 1
)

echo [3/5] Installing frontend dependencies...
cd frontend
call npm install
if errorlevel 1 (
  echo Frontend dependency install failed.
  exit /b 1
)
cd ..

echo [4/5] Starting backend server...
start cmd /k "cd /d %~dp0backend && call .venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8000"

echo [5/5] Starting frontend server...
start cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo Backend URL : http://localhost:8000
echo Frontend URL: http://localhost:5173
echo.

endlocal
