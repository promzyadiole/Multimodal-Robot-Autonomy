#!/usr/bin/env bash
# Rebuild the explainer PDF.
#
# tectonic is used rather than the system TeX because it fetches whatever
# packages the document needs on first run and needs no local TeX Live.
# /usr/local/bin/tectonic on this host is linked against a newer glibc than
# the system provides; pass TECTONIC=/path/to/working/tectonic if it fails.
set -eu
cd "$(dirname "$0")"
exec "${TECTONIC:-tectonic}" -X compile how-this-robot-knows-where-it-is.tex --outdir .
