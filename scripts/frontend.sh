#!/usr/bin/env bash
# TERMINAL 4 — the command centre (Next.js on :3000).
#
# NEXT_PUBLIC_DEMO is deliberately not set here. It is set only on the Vercel
# deployment, where there is no robot; locally the interface talks to the
# backend on :8000 and drives the real simulation.
set -eu
cd "$(dirname "$0")/../frontend"
exec npx next dev
