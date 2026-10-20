#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

fail() {
  printf '\n%s\n' "$1" >&2
  if [[ -t 0 ]]; then read -r -p 'Press Return to close.' || true; fi
  exit 1
}

if [[ ! -x .venv/bin/python ]]; then
  python_bin="$(command -v python3 || true)"
  [[ -n "$python_bin" ]] || fail 'Install Python 3.12 or later, then reopen this launcher.'
  "$python_bin" -c 'import sys; assert sys.version_info >= (3, 12)' || fail 'Python 3.12 or later is required.'
  "$python_bin" -m venv .venv
fi

if ! .venv/bin/python -c 'import campus_agent, fastapi, reportlab, sqlmodel, mcp, playwright, google.genai' 2>/dev/null; then
  .venv/bin/python -m ensurepip --upgrade
  .venv/bin/python -m pip install -r requirements-lock.txt || fail 'Dependency installation failed. Check your connection and try again.'
  .venv/bin/python -m pip install --no-deps -e .
fi

.venv/bin/python -m campus_agent demo
if .venv/bin/python - <<'PY'
import json
from pathlib import Path
import urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8876/api/status', timeout=1) as response:
        state = json.load(response)
    raise SystemExit(0 if state.get('offline') is True and state.get('workspace') == str(Path('demo').resolve()) else 1)
except (OSError, ValueError):
    raise SystemExit(1)
PY
then
  open http://127.0.0.1:8876
  exit 0
fi
.venv/bin/python - <<'PY' || exit 1
import socket
with socket.socket() as probe:
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(('127.0.0.1', 8876))
    except OSError:
        raise SystemExit('Port 8876 is already in use. Open the existing dashboard or stop that server first.')
PY

printf '\nOpening http://127.0.0.1:8876\nKeep this window open. Press Ctrl+C to stop.\n'
.venv/bin/python -m campus_agent --config demo/config.json serve &
server_pid=$!
trap 'kill "$server_pid" 2>/dev/null || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
.venv/bin/python - <<'PY'
import json
import time
import urllib.request
import webbrowser
for _ in range(100):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8876/api/status', timeout=1) as response:
            state = json.load(response)
        if state.get('offline') is True:
            webbrowser.open('http://127.0.0.1:8876')
            break
    except OSError:
        pass
    time.sleep(0.1)
else:
    raise SystemExit('Dashboard did not start. Check the server error above.')
PY
wait "$server_pid"
