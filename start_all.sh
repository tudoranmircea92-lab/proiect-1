#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Starting backend on http://127.0.0.1:8000"
(
  cd "$ROOT_DIR"
  uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
) &
BACK_PID=$!

echo "Starting frontend on http://127.0.0.1:5173"
(
  cd "$ROOT_DIR/frontend"
  npm run dev -- --host 127.0.0.1 --port 5173
) &
FRONT_PID=$!

sleep 2
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "http://127.0.0.1:5173" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "http://127.0.0.1:5173" >/dev/null 2>&1 || true
fi

echo "Backend PID: $BACK_PID"
echo "Frontend PID: $FRONT_PID"
echo "Press Ctrl+C to stop both."

trap 'kill $BACK_PID $FRONT_PID 2>/dev/null || true' INT TERM
wait
