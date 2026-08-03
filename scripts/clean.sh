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
# One pattern per pkill. "pkill -x a b c" does not kill a, b and c -- it takes
# a single pattern and rejects the rest, which is how 22 robot_state_publishers
# accumulated here, each publishing its own /robot_description and TF, and how a
# stale robot model kept being spawned after the URDF had changed.
for proc in gzserver gzclient robot_state_publisher; do
  pkill -x "$proc" 2>/dev/null || true
done
pkill -f "[c]omponent_container_isolated" 2>/dev/null
# slam_toolbox outlives its launch file and keeps publishing map->odom,
# which silently fights AMCL the next time nav2 comes up.
pkill -f "[a]sync_slam_toolbox_node" 2>/dev/null
sleep 3
for proc in gzserver gzclient robot_state_publisher; do
  pkill -9 -x "$proc" 2>/dev/null || true
done
pkill -9 -f "[c]omponent_container_isolated" 2>/dev/null
sleep 1

# The web services are only cleared on --all, because the usual reason to run
# this script is to restart the simulator while leaving the interface open.
# When they are cleared it is done by port rather than by process name: what
# actually blocks a restart is whoever holds the socket, and "[Errno 98]
# address already in use" name the port, not the process.
if [ "${1:-}" = "--all" ]; then
  for port in 8000 3000; do
    pids=$(lsof -t -i :"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "$pids" ]; then
      echo "clean: freeing port $port (pid $(echo "$pids" | tr '\n' ' '))"
      # shellcheck disable=SC2086
      kill $pids 2>/dev/null || true
      sleep 2
      # shellcheck disable=SC2086
      kill -9 $pids 2>/dev/null || true
    fi
  done
fi

left=$(pgrep -x gzserver; pgrep -x gzclient; pgrep -x robot_state_publisher; pgrep -f "[c]omponent_container_isolated"; pgrep -f "[a]sync_slam_toolbox_node")
if [ -z "$left" ]; then echo "clean: nothing left running"; else echo "still up: $left"; fi
