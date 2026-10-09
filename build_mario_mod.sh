#!/bin/sh
# Mario 64 for Sonic 3 A.I.R. - mod builder (Linux / macOS)
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 was not found, please install it first."
    exit 1
fi
echo "Installing / checking required Python packages..."
python3 -m pip install --quiet --disable-pip-version-check --user numpy pillow soundfile 2>/dev/null \
    || python3 -m pip install --quiet --disable-pip-version-check --break-system-packages --user numpy pillow soundfile
python3 build_mario_mod.py "$@"
