#!/usr/bin/env bash
set -e

source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash

export TURTLEBOT3_MODEL=waffle_pi
export HOUSE_MODELS=~/turtlebot3_ws/src/aws-robomaker-small-house-world/models
export TB3_MODELS="$(ros2 pkg prefix multimodal_robot_autonomy)/share/multimodal_robot_autonomy/models"
export GAZEBO_MODEL_PATH=$HOUSE_MODELS:$TB3_MODELS

pkill -9 -f gazebo || true
pkill -9 -f gzserver || true
pkill -9 -f gzclient || true
pkill -9 -f cartographer || true
pkill -9 -f robot_state_publisher || true
pkill -9 -f nav2 || true

gnome-terminal -- bash -lc "source /opt/ros/humble/setup.bash; source ~/turtlebot3_ws/install/setup.bash; export TURTLEBOT3_MODEL=waffle_pi; export HOUSE_MODELS=~/turtlebot3_ws/src/aws-robomaker-small-house-world/models; export TB3_MODELS=\$(ros2 pkg prefix multimodal_robot_autonomy)/share/multimodal_robot_autonomy/models; export GAZEBO_MODEL_PATH=\$HOUSE_MODELS:\$TB3_MODELS; gazebo --verbose ~/turtlebot3_ws/src/aws-robomaker-small-house-world/worlds/small_house.world -s libgazebo_ros_init.so -s libgazebo_ros_factory.so; exec bash"

gnome-terminal -- bash -lc "sleep 5; source /opt/ros/humble/setup.bash; source ~/turtlebot3_ws/install/setup.bash; export TURTLEBOT3_MODEL=waffle_pi; ros2 run gazebo_ros spawn_entity.py -entity turtlebot3 -file \$(ros2 pkg prefix multimodal_robot_autonomy)/share/multimodal_robot_autonomy/models/turtlebot3_waffle_pi/model.sdf -x -3.5 -y 1.0 -z 0.01; exec bash"

gnome-terminal -- bash -lc "source /opt/ros/humble/setup.bash; source ~/turtlebot3_ws/install/setup.bash; ros2 run robot_state_publisher robot_state_publisher --ros-args -p use_sim_time:=true -p robot_description:=\"\$(cat ~/Multimodal-Robot-Autonomy/urdf/turtlebot3_waffle_pi.urdf)\"; exec bash"

gnome-terminal -- bash -lc "source /opt/ros/humble/setup.bash; source ~/turtlebot3_ws/install/setup.bash; export TURTLEBOT3_MODEL=waffle_pi; ros2 launch turtlebot3_navigation2 navigation2.launch.py use_sim_time:=True map:=\$HOME/turtlebot3_ws/maps/small_house_map.yaml; exec bash"