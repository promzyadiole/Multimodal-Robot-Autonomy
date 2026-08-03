#!/usr/bin/env bash
# TERMINAL 2 — drive the robot by keyboard.
#
# Keys: i forward · , back · j turn left · l turn right · k stop
#       q/z raise/lower both speeds   w/x linear only   e/c angular only
#
# Start slow. This robot reaches ~90% of commanded speed and its casters are
# fixed skids, so hard turns scrub rather than roll.
set -eu
source "$(dirname "$0")/env.sh"
echo "drive slowly: press z a few times first, then i / j / l / , and k to stop"
exec ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args -p use_sim_time:=true -r /cmd_vel:=/cmd_vel
