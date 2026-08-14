#!/usr/bin/env bash
# Arranca los dos servidores del proyecto en segundo plano:
#   - CIA API (cia_api.py) en el puerto 8000   -> /confidentiality/* y /integrity/*
#   - Chat seguro (app.py) en el puerto 8001   -> consume la CIA API vía HTTP
set -e
cd "$(dirname "$0")"

pkill -f "uvicorn cia_api:app" 2>/dev/null || true
pkill -f "uvicorn app:app" 2>/dev/null || true
sleep 1

CIA_ROOT="$(cd .. && pwd)"

setsid nohup python3 -m uvicorn cia_api:app --host 127.0.0.1 --port 8000 \
    --app-dir "$CIA_ROOT" > /tmp/opencode/cia_api.log 2>&1 < /dev/null &

setsid nohup python3 -m uvicorn app:app --host 127.0.0.1 --port 8001 \
    > /tmp/opencode/chat.log 2>&1 < /dev/null &

sleep 2
echo "CIA API   -> http://127.0.0.1:8000/docs"
echo "Chat      -> http://127.0.0.1:8001"
