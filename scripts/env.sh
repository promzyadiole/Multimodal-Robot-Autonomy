#!/usr/bin/env bash
# Shared environment for every script here. Source it, do not run it.
#
# Two settings are not optional on this machine:
#   CYCLONEDDS_URI  -- the host has no multicast route and domain 0 collides
#                      with another machine, so discovery is pinned to unicast
#                      loopback. Without it, topics exist but never deliver.
#   ROS_DOMAIN_ID   -- keeps this stack off the default domain.
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export REPO

# VS Code's snap injects library paths that break rviz2 and gz with
# "undefined symbol: __libc_pthread_init".
for v in $(env | grep -oE '^SNAP[A-Z_]*' || true); do unset "$v"; done
unset GTK_PATH LD_LIBRARY_PATH GIO_MODULE_DIR 2>/dev/null || true

source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash
source /usr/share/gazebo/setup.sh 2>/dev/null || true

export CYCLONEDDS_URI="file://$REPO/config/cyclonedds.xml"
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-42}"
# Detect the X display rather than assuming :0 -- this machine runs on :1, and
# a wrong DISPLAY makes every GUI fail with a misleading "cannot open display".
if [ -z "${DISPLAY:-}" ]; then
  for sock in /tmp/.X11-unix/X*; do
    [ -e "$sock" ] && export DISPLAY=":${sock##*/X}" && break
  done
fi
export DISPLAY="${DISPLAY:-:0}"
