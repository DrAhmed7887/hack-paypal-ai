#!/bin/zsh
# serve.sh: run BillCheck locally with keys read from the macOS Keychain (never from files).
# Usage: scripts/serve.sh [port]   (default 8000)
set -euo pipefail
cd "$(dirname "$0")/.."
export PAYPAL_CLIENT_ID=$(security find-generic-password -s PAYPAL_CLIENT_ID -w)
export PAYPAL_CLIENT_SECRET=$(security find-generic-password -s PAYPAL_CLIENT_SECRET -w)
export FIREWORKS_API_KEY=$(security find-generic-password -s FIREWORKS_API_KEY -w)
exec .venv/bin/uvicorn billcheck.web.app:app --host 127.0.0.1 --port "${1:-8000}" --no-proxy-headers
