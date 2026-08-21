#!/usr/bin/env bash
# Snapshot the live AMCL particle set as a figure.
set -eu
source "$(dirname "$0")/env.sh"
exec python3 "$(dirname "$0")/particle_figure.py" "$@"
