#!/bin/bash
# Compatibility entry point; use the main launcher from the repository root.
set -euo pipefail
exec "$(dirname "$0")/../Start NextRole.command" "$@"
