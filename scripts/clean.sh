#!/usr/bin/env bash
# Kill every leftover from a previous session.
#
# This exists because the single most common failure in this project is not a
# bug but a stale process: a nav2 container left bound to a simulator that has
# since died still answers on its topics, and extra robot_state_publishers feed
# Gazebo an older robot description. Symptoms look like application faults.
set -u
pkill -f "[g]azebo_romr.launch.py"  2>/dev/null
pkill -f "[n]av2_romr.launch.py"    2>/dev/null
pkill -f "[s]lam_romr.launch.py"    2>/dev/null
# teleop_twist_keyboard republishes its last twist in a loop, so a session left
# open after a keypress drives the robot forever. Measured: a forgotten teleop
# crept the robot 588 mm in 60 s with nobody touching the keyboard, which reads
# exactly like a physics bug.
pkill -f "[t]eleop_twist_keyboard"  2>/dev/null
pkill -f "[s]cripts/drive.py"       2>/dev/null
sleep 3
pkill -x gzserver gzclient robot_state_publisher 2>/dev/null
pkill -f "[c]omponent_container_isolated" 2>/dev/null
sleep 3
pkill -9 -x gzserver 2>/dev/null
pkill -9 -f "[c]omponent_container_isolated" 2>/dev/null
sleep 1
left=$(pgrep -x gzserver; pgrep -x robot_state_publisher; pgrep -f "[c]omponent_container_isolated")
if [ -z "$left" ]; then echo "clean: nothing left running"; else echo "still up: $left"; fi
