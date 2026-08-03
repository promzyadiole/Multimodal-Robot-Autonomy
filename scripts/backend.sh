#!/usr/bin/env bash
# TERMINAL 3 — the reasoning backend (FastAPI on :8000).
#
# start_backend.sh handles the awkward parts: it unsets SAM_MODEL_TYPE and
# SAM_CHECKPOINT so the vision service reads them from .env, redirects the three
# HuggingFace cache variables to a writable directory, and parses .env line by
# line rather than sourcing it, because several values contain spaces.
set -eu
cd "$(dirname "$0")/../backend"
exec bash app/scripts/start_backend.sh
