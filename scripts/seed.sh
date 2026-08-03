#!/usr/bin/env bash
# Seed AMCL from ground truth, then rotate so the filter converges.
set -eu
source "$(dirname "$0")/env.sh"
exec python3 "$(dirname "$0")/seed_localisation.py"
