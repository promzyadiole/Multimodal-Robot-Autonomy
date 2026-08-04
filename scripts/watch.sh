#!/usr/bin/env bash
# Live truth-vs-belief scorer. Run beside the web interface.
set -eu
source "$(dirname "$0")/env.sh"
exec python3 "$(dirname "$0")/watch_robot.py" "$@"
