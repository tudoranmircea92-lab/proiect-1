@echo off
set ROOT=%~dp0

echo Starting Backend...
start "Backend" cmd /k "cd /d %ROOT% && uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload"

echo Starting Frontend...
start "Frontend" cmd /k "cd /d %ROOT%frontend && npm run dev -- --host 127.0.0.1 --port 5173"

timeout /t 2 >nul
start "" "http://127.0.0.1:5173"

echo Both backend and frontend are now running.
