#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

fail() {
  printf '\n%s\n' "$1" >&2
  if [[ -t 0 ]]; then read -r -p 'Press Return to close.' || true; fi
  exit 1
}

python_bin=""
for candidate in "$PWD/.venv/bin/python" python3 python3.14 python3.13 python3.12; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert sys.version_info >= (3,12)' 2>/dev/null; then
    python_bin="$candidate"
    break
  fi
done
[[ -n "$python_bin" ]] || fail 'Install Python 3.12 or later from https://www.python.org/downloads/macos/, then reopen this launcher. Open START HERE.html for instructions.'
"$python_bin" launcher.py "$@" || fail 'Job Seeker stopped. Read the error above; START HERE.html has troubleshooting steps.'
