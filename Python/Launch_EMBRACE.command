#!/bin/zsh
cd "$(dirname "$0")" || exit 1
# Prefer the modern runtime available in Codex on this Mac.
EMBRACE_PYTHON="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
if [[ ! -x "$EMBRACE_PYTHON" ]]; then
    EMBRACE_PYTHON="$(command -v python3)"
fi
"$EMBRACE_PYTHON" EMBRACE2_EQD2_Excel_Autogenerator.py
