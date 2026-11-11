#!/bin/sh
# replay.sh: run BillCheck in replay mode: no API keys, no PayPal account, no network once installed.
# AI and PayPal responses are recorded or simulated for the five sample bills; the audit runs for real.
# The first run creates .venv and installs the dependencies (that step needs the network once).
# Usage: scripts/replay.sh [port]   (default 8000)  then open http://127.0.0.1:PORT
set -eu
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/uvicorn ]; then
  PY=""
  for c in python3.13 python3.12 python3.11 python3.14 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then PY=$c; break; fi
  done
  [ -n "$PY" ] || { echo "replay.sh: Python 3.11 or newer is required (python.org or 'brew install python')" >&2; exit 1; }
  rm -rf .venv
  "$PY" -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -e .
fi
echo "BillCheck REPLAY mode: http://127.0.0.1:${1:-8000}  (Ctrl+C to stop)"
exec env -u PAYPAL_CLIENT_ID -u PAYPAL_CLIENT_SECRET -u FIREWORKS_API_KEY \
  BILLCHECK_REPLAY=1 .venv/bin/uvicorn billcheck.web.app:app --host 127.0.0.1 --port "${1:-8000}" --no-proxy-headers
