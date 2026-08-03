#!/usr/bin/env bash
# Wrapper so the tuner runs with the ROS environment.
#   scripts/tune.sh --show
#   scripts/tune.sh --test
#   scripts/tune.sh --set maxVel=0.0 minDepth=0.001 --test
set -eu
source "$(dirname "$0")/env.sh"
exec python3 "$(dirname "$0")/tune_physics.py" "$@"
