#!/usr/bin/env bash
# Attach the Gazebo GUI to the running simulation.
#
#   scripts/gazebo_gui.sh
#
# The GUI is a separate process (gzclient) from the physics server (gzserver).
# It can be opened and closed at will without disturbing the simulation, which
# is useful because the GUI is the expensive half.
#
# It must NOT be started from VS Code's integrated terminal. That shell inherits
# the editor's snap sandbox -- SNAP_*, GTK_PATH and LD_LIBRARY_PATH pointing
# into /snap/code/ -- and the GUI dies on a mismatched GTK or a
# "undefined symbol: __libc_pthread_init" from the snap's libc. env.sh strips
# those, which is why this wrapper exists rather than plain `gzclient`.
set -eu
source "$(dirname "$0")/env.sh"

if ! pgrep -x gzserver >/dev/null; then
  echo "No gzserver running. Start the simulation first:"
  echo "  scripts/map_world.sh          (mapping)"
  echo "  ros2 launch multimodal_robot_autonomy gazebo_romr.launch.py   (normal)"
  exit 1
fi
echo "attaching GUI to gzserver (pid $(pgrep -x gzserver | head -1)) on DISPLAY=$DISPLAY"
exec gzclient --verbose
