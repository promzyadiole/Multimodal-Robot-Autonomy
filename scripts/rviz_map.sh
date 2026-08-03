#!/usr/bin/env bash
# TERMINAL 3 — watch the map build.
#
# Loads rviz/mapping.rviz, so Map, LaserScan and RobotModel are already set up
# and the fixed frame is 'map'. Nothing to click.
#
# Fixed frame matters: watching in 'odom' hides the loop-closure corrections you
# are driving to produce, because odom never jumps. TF is off by default -- nine
# frames of axes bury the map -- tick it on only to check a transform.
set -eu
source "$(dirname "$0")/env.sh"
exec ros2 run rviz2 rviz2 -d "$REPO/rviz/mapping.rviz" --ros-args -p use_sim_time:=true
