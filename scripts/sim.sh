#!/usr/bin/env bash
# TERMINAL 1 -- Gazebo, the world, and the robot.
#
# Wrapped rather than run as a bare `ros2 launch` because env.sh strips the
# snap sandbox variables VS Code's terminal injects (SNAP_*, GTK_PATH,
# LD_LIBRARY_PATH into /snap/code/), which otherwise kill gzclient on a
# mismatched GTK, and because the DDS setup here needs unicast loopback.
#
# Pass through any launch argument, e.g.
#   scripts/sim.sh world:=new_world.world
#   scripts/sim.sh x_pose:=0.0 y_pose:=0.0
set -eu
source "$(dirname "$0")/env.sh"
exec ros2 launch multimodal_robot_autonomy gazebo_romr.launch.py "$@"
