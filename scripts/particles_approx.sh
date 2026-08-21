#!/usr/bin/env bash
set -eu
source "$(dirname "$0")/env.sh"
exec python3 "$(dirname "$0")/particle_approx_figure.py" "$@"
