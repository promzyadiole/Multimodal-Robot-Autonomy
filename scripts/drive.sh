#!/usr/bin/env bash
# Drive with the arrow keys — layout independent, one axis per key.
set -eu
source "$(dirname "$0")/env.sh"
exec python3 "$(dirname "$0")/drive.py"
