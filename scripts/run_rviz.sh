#!/usr/bin/env bash
# Open the ROMR view in RViz, styled to match the command centre.
#
#   scripts/run_rviz.sh                    # map frame, needs nav2 for map/plan
#   scripts/run_rviz.sh odom               # no map or localisation needed
#
# Why the environment scrubbing: launched from VS Code's integrated terminal
# this inherits the editor's snap confinement, and rviz2 then resolves
# /snap/core20/.../libpthread.so.0 and dies with
#   "undefined symbol: __libc_pthread_init, version GLIBC_PRIVATE"
# Clearing the SNAP_* variables and the paths they inject makes it resolve the
# system libraries again. Running from a plain terminal, this is a no-op.
set -e

FIXED_FRAME="${1:-map}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

# drop every SNAP_* variable and the library/module paths snap injects
for v in $(env | grep -oE '^SNAP[A-Z_]*' || true); do unset "$v"; done
unset LD_LIBRARY_PATH GTK_PATH GIO_MODULE_DIR LOCPATH GSETTINGS_SCHEMA_DIR

source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash

# same DDS domain as the sim, or RViz sees nothing at all
export CYCLONEDDS_URI="file://$REPO/config/cyclonedds.xml"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
export DISPLAY="${DISPLAY:-:0}"

exec ros2 launch multimodal_robot_autonomy rviz_romr.launch.py \
  fixed_frame:="$FIXED_FRAME"
