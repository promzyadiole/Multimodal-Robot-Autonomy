"""Build a map of the small house with ROMR using slam_toolbox.

Spawned at yaw 0 on purpose: slam_toolbox anchors the map frame to the robot's
starting pose, so a zero heading keeps the resulting map axis-aligned with the
Gazebo world. That makes the saved map convertible to world coordinates by
adding the spawn translation to the yaml origin -- no rotation to reconcile.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    IncludeLaunchDescription,
    SetEnvironmentVariable,
    TimerAction,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('multimodal_robot_autonomy')

    # The world to map. This was hardcoded to the AWS small house, which meant
    # mapping the custom world silently produced a map of the wrong building.
    # Defaults to the custom world the place registry is georeferenced against.
    small_house_repo = os.path.expanduser('~/turtlebot3_ws/src/aws-robomaker-small-house-world')
    world = PathJoinSubstitution([
        pkg_share, 'worlds', LaunchConfiguration('world')
    ])

    gazebo_model_path = SetEnvironmentVariable(
        name='GAZEBO_MODEL_PATH',
        # Mirrors gazebo_romr.launch.py exactly. dirname(pkg_share) must come
        # first, or package:// mesh refs resolve for visuals but not collisions
        # and the robot falls through the floor.
        value=':'.join([
            os.path.dirname(pkg_share),
            os.path.expanduser('~/.gazebo/models'),
            os.path.join(small_house_repo, 'models'),
            os.path.join(pkg_share, 'models'),
        ]),
    )

    gazebo = ExecuteProcess(
        cmd=['gazebo', '--verbose', world,
             '-s', 'libgazebo_ros_init.so',
             '-s', 'libgazebo_ros_factory.so'],
        output='screen',
    )

    spawn = TimerAction(
        period=5.0,
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_share, 'launch', 'spawn_robot.launch.py')),
            launch_arguments={
                'robot': LaunchConfiguration('robot'),
                'x_pose': LaunchConfiguration('x_pose'),
                'y_pose': LaunchConfiguration('y_pose'),
                'z_pose': LaunchConfiguration('z_pose'),
                'yaw': '0.0',
            }.items(),
        )],
    )

    slam = TimerAction(
        period=9.0,
        actions=[Node(
            package='slam_toolbox',
            executable='async_slam_toolbox_node',
            name='slam_toolbox',
            output='screen',
            parameters=[
                os.path.join(pkg_share, 'config', 'mapper_params_online_async.yaml'),
                {'use_sim_time': True},
            ],
        )],
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'world', default_value='new_world.world',
            description='world file in this package to map, e.g. new_world.world'),
        DeclareLaunchArgument('robot', default_value='romr'),
        DeclareLaunchArgument('x_pose', default_value='-3.5'),
        DeclareLaunchArgument('y_pose', default_value='1.0'),
        DeclareLaunchArgument('z_pose', default_value='0.20'),
        gazebo_model_path,
        gazebo,
        spawn,
        slam,
    ])
