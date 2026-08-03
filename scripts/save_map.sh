#!/usr/bin/env bash
# TERMINAL 4 — save the map once the world is fully covered.
#
#   scripts/save_map.sh [name]        default: custom_map_v2
#
# Writes maps/<name>.pgm and maps/<name>.yaml, then rebuilds so the launch files
# can see it. Drive every room and close the loop back to the start before
# saving: an unclosed perimeter is what let the planner route the robot out of
# the surveyed area last time.
set -eu
source "$(dirname "$0")/env.sh"
NAME="${1:-custom_map_v2}"
cd "$REPO/maps"
ros2 run nav2_map_server map_saver_cli -f "$NAME" --ros-args -p use_sim_time:=true
echo
echo "saved maps/$NAME.pgm and maps/$NAME.yaml"
cd ~/turtlebot3_ws && colcon build --symlink-install --packages-select multimodal_robot_autonomy >/dev/null
echo "rebuilt. use it with:  ros2 launch multimodal_robot_autonomy nav2_romr.launch.py map:=$NAME.yaml"
