#!/bin/zsh
cd "$(dirname "$0")" || exit 1
# Launch the packaged app so Finder and the Dock use the EQD2 icon.
EMBRACE_APP="$(pwd)/../dist/EMBRACE EQD2.app"
if [[ -d "$EMBRACE_APP" ]]; then
    exec /usr/bin/open "$EMBRACE_APP"
fi
# Fall back to the source dashboard when the packaged app is unavailable.
EMBRACE_PYTHON="$HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3"
if [[ ! -x "$EMBRACE_PYTHON" ]]; then
    EMBRACE_PYTHON="$(command -v python3)"
fi
"$EMBRACE_PYTHON" EMBRACE2_EQD2_Excel_Autogenerator.py
