#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WHL="$PROJECT_DIR/wheels/en_core_web_lg-3.8.0-py3-none-any.whl"

if [ ! -f "$WHL" ]; then
    echo "[ensure-models] Downloading en_core_web_lg-3.8.0..."
    mkdir -p "$(dirname "$WHL")"
    curl -L --retry 3 --retry-delay 10 \
        -o "$WHL" \
        "https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl"
    echo "[ensure-models] Download complete."
else
    echo "[ensure-models] en_core_web_lg wheel already present, skipping download."
fi
