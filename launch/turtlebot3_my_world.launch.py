#!/usr/bin/env python3
#
# Copyright 2019 ROBOTIS CO., LTD.
#
# Licensed under the Apache License, Version 2.0 (the "License");
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#
# Authors: Joep Tool



import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription, TimerAction, OpaqueFunction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
import launch_ros.actions
import rclpy
from rclpy.task import Future
from rclpy.node import Node

def wait_for_spawn_service(context, *args, **kwargs):
    """Wait until the /spawn_entity service is available in Gazebo."""
    from rclpy.executors import SingleThreadedExecutor
    from gazebo_msgs.srv import SpawnEntity

    rclpy.init(args=None)
    node = Node("wait_for_spawn_service_node")
    client = node.create_client(SpawnEntity, '/spawn_entity')

    while not client.wait_for_service(timeout_sec=1.0):
        node.get_logger().info('Waiting for /spawn_entity service...')

    node.get_logger().info('/spawn_entity service is now available.')
    rclpy.shutdown()
    return []

def generate_launch_description():
    launch_file_dir = os.path.join(get_package_share_directory('multimodal_robot_autonomy'), 'launch')
    pkg_gazebo_ros = get_package_share_directory('gazebo_ros')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    x_pose = LaunchConfiguration('x_pose', default='-2.0')
    y_pose = LaunchConfiguration('y_pose', default='-0.5')

    world = os.path.join(
        get_package_share_directory('multimodal_robot_autonomy'),
        'worlds',
        'my_world.world'
    )

    # Launch Gazebo server and client
    gzserver_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzserver.launch.py')
        ),
        launch_arguments={'world': world}.items()
    )

    gzclient_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo_ros, 'launch', 'gzclient.launch.py')
        )
    )

    robot_state_publisher_cmd = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(launch_file_dir, 'robot_state_publisher.launch.py')
        ),
        launch_arguments={'use_sim_time': use_sim_time}.items()
    )

    # Spawn robot **after Gazebo is ready**
    spawn_turtlebot_cmd = TimerAction(
        period=0.1,  # small initial delay
        actions=[
            OpaqueFunction(function=wait_for_spawn_service),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(launch_file_dir, 'spawn_turtlebot3.launch.py')
                ),
                launch_arguments={
                    'x_pose': x_pose,
                    'y_pose': y_pose
                }.items()
            )
        ]
    )

    ld = LaunchDescription()
    ld.add_action(gzserver_cmd)
    ld.add_action(gzclient_cmd)
    ld.add_action(robot_state_publisher_cmd)
    ld.add_action(spawn_turtlebot_cmd)

    return ld
