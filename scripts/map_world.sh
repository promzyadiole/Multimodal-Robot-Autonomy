#!/usr/bin/env bash
# TERMINAL 1 — simulator + SLAM. Builds the map as you drive.
#
#   scripts/map_world.sh [world]
#
# Leave this running. Drive with scripts/teleop.sh in another terminal, watch it
# build in scripts/rviz_map.sh in a third, and save with scripts/save_map.sh.
set -eu
source "$(dirname "$0")/env.sh"
WORLD="${1:-new_world.world}"
echo "SLAM mapping in $WORLD — drive with scripts/teleop.sh, save with scripts/save_map.sh"
exec ros2 launch multimodal_robot_autonomy slam_romr.launch.py world:="$WORLD"
