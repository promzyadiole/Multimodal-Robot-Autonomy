#!/usr/bin/env bash
# Reject "--" inside an XML comment before it reaches xacro.
#
# XML forbids a double hyphen inside a comment. This has broken the build three
# times here, always from an em-dash written as "--" in a explanatory comment,
# and the error xacro reports ("not well-formed (invalid token)") points at the
# line but never says why.
set -eu
cd "$(dirname "$0")/.."
bad=0
for f in urdf/*.xacro gazebo/*.gazebo worlds/*.world; do
  [ -e "$f" ] || continue
  if python3 - "$f" <<'PY'
import re, sys
s = open(sys.argv[1]).read()
hits = [m.start() for m in re.finditer(r"<!--(.*?)-->", s, re.S) if "--" in m.group(1)]
sys.exit(1 if hits else 0)
PY
  then :; else echo "  $f contains '--' inside a comment"; bad=1; fi
done
[ "$bad" = 0 ] && echo "  all XML comments clean"
exit $bad
