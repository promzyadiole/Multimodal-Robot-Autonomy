#!/usr/bin/env bash
# Rebuild the package into the workspace that is actually sourced.
#
# This exists because of a trap that costs an hour every time. The package
# source lives here, but the colcon workspace is ~/turtlebot3_ws, which carries
# this directory as a symlink under src/ and is what env.sh sources. Running
# `colcon build` from the repository root succeeds, prints no warning, and
# creates a second install tree that nothing ever reads.
#
# Existing files survive that mistake, because --symlink-install links them
# back to source and edits go live without any build at all. NEW files do not:
# they are only linked at build time, so a newly added launch file, rviz config
# or map is simply absent, and the tool that wanted it falls back to a default
# instead of reporting the miss. A brand-new navigation.rviz was silently
# replaced by RViz's factory layout exactly this way.
set -eu
source "$(dirname "$0")/env.sh"
cd ~/turtlebot3_ws
exec colcon build --packages-select multimodal_robot_autonomy --symlink-install "$@"
