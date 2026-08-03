#!/usr/bin/env bash
# TERMINAL 3 — watch the map build.
# Add displays: Map (/map), LaserScan (/scan), TF, RobotModel.
set -eu
source "$(dirname "$0")/env.sh"
exec ros2 run rviz2 rviz2 --ros-args -p use_sim_time:=true
