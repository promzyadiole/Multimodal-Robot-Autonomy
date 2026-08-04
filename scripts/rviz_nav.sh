#!/usr/bin/env bash
# Open the navigation view in RViz, against a nav2 that is already running.
#
#   scripts/rviz_nav.sh
#
# nav2_rviz.sh starts nav2 and RViz together. This opens RViz on its own, for
# when nav2 is healthy and only the window needs restarting -- reloading a
# changed layout, or recovering from a closed window -- without tearing down
# localisation and waiting for the lifecycle nodes to come back up.
set -eu
source "$(dirname "$0")/env.sh"
CONFIG="$(ros2 pkg prefix multimodal_robot_autonomy)/share/multimodal_robot_autonomy/rviz/navigation.rviz"
# RViz falls back to its factory layout when -d names a file that is not there,
# and still shows the missing path in the title bar, so the failure reads as a
# config that loaded and did nothing. Say so instead.
if [ ! -e "$CONFIG" ]; then
  echo "Not installed: $CONFIG"
  echo "Run scripts/build.sh first -- new files only appear in the workspace at build time."
  exit 1
fi
exec rviz2 -d "$CONFIG" --ros-args -p use_sim_time:=true
