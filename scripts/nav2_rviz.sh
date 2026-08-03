#!/usr/bin/env bash
# TERMINAL 2 (alternative) -- nav2 with RViz, so you can set the pose yourself.
#
# Same stack as nav2.sh plus an RViz window. Use it when you want to place the
# initial pose by hand instead of seeding from ground truth, or when a goal is
# failing and you need to see the costmap the planner is searching.
#
#   "2D Pose Estimate"  click where the robot is, drag the way it faces
#   "Nav2 Goal"         click a destination, drag the final heading
set -eu
source "$(dirname "$0")/env.sh"
exec ros2 launch multimodal_robot_autonomy nav2_romr.launch.py rviz:=true "$@"
