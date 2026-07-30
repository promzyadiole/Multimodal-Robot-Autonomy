#!/usr/bin/env bash
# Default small-house stack: the ROMR custom robot.
# For the TurtleBot3 reference configuration, use start_small_house_turtlebot3.sh.
set -e

source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash

# This host has no multicast route, and ROS_DOMAIN_ID=0 on a shared subnet
# picks up other machines' ROS graphs. Both drop traffic between Gazebo and
# nav2, which surfaces as goals aborting for no visible reason. Keep the whole
# stack on loopback in its own domain. See config/cyclonedds.xml.
export CYCLONEDDS_URI=file://$(ros2 pkg prefix multimodal_robot_autonomy)/share/multimodal_robot_autonomy/config/cyclonedds.xml
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-42}

# The small house world still pulls its furniture models from the AWS checkout.
export HOUSE_MODELS=~/turtlebot3_ws/src/aws-robomaker-small-house-world/models
export PKG_SHARE="$(ros2 pkg prefix multimodal_robot_autonomy)/share/multimodal_robot_autonomy"
export GAZEBO_MODEL_PATH=$HOUSE_MODELS:$PKG_SHARE/models

pkill -9 -f gazebo || true
pkill -9 -f gzserver || true
pkill -9 -f gzclient || true
pkill -9 -f cartographer || true
pkill -9 -f robot_state_publisher || true
pkill -9 -f nav2 || true

# gazebo_romr.launch.py brings up Gazebo, robot_state_publisher and the spawn.
gnome-terminal -- bash -lc "source /opt/ros/humble/setup.bash; source ~/turtlebot3_ws/install/setup.bash; export CYCLONEDDS_URI=$CYCLONEDDS_URI; export ROS_DOMAIN_ID=$ROS_DOMAIN_ID; export GAZEBO_MODEL_PATH=$GAZEBO_MODEL_PATH; ros2 launch multimodal_robot_autonomy gazebo_romr.launch.py; exec bash"

gnome-terminal -- bash -lc "sleep 10; source /opt/ros/humble/setup.bash; source ~/turtlebot3_ws/install/setup.bash; ros2 launch multimodal_robot_autonomy nav2_romr.launch.py; exec bash"
