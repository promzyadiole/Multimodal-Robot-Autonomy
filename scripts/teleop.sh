#!/usr/bin/env bash
# TERMINAL 2 — drive by keyboard (teleop_twist_keyboard).
#
#   scripts/teleop.sh              slow, for mapping
#   scripts/teleop.sh 0.15 0.5     custom linear / angular
#
# Keys are a 3x3 grid whose CORNERS MIX linear and angular on purpose:
#
#     u  i  o        i  = straight forward      u / o = forward + turn
#     j  k  l        ,  = straight back         m / . = back + turn
#     m  ,  .        j / l = rotate in place    k = stop
#
# Use i and , for straight lines; anything else curves. Any unbound key also
# stops the robot, which is why pressing n looks like a stop key.
#
# Defaults are 0.08 m/s and 0.3 rad/s, not the upstream 0.5 and 1.0. Upstream
# commands more than this robot can deliver -- its configured maximum is
# 0.35 m/s -- so the controller saturates and the robot lurches. Slow, steady
# motion also gives slam_toolbox far better scan matches.
#
# scripts/drive.sh is the alternative: arrow keys, one axis per key, and it
# releases the velocity when you stop pressing.
set -eu
source "$(dirname "$0")/env.sh"
SPEED="${1:-0.08}"
TURN="${2:-0.3}"
echo "linear ${SPEED} m/s   angular ${TURN} rad/s   —  i forward · , back · j/l turn · k stop"
echo "q/z scale both · w/x linear only · e/c angular only"
exec ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -p use_sim_time:=true -p speed:="$SPEED" -p turn:="$TURN"
