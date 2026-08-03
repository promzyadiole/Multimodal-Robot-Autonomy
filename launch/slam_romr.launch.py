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
        # (-3.5, 1.0) was chosen for the AWS small house. In new_world the robot
        # spawns wedged against geometry there: it reaches ~6% of commanded speed
        # and yaws 10 deg on a straight command, which reads as a broken
        # drivetrain. Backed out by hand it does 93-108%. This is the pose
        # Inside the building, on open floor. Chosen by flooding outward from
        # the parlour through gaps wider than 0.45 m, which cannot escape the
        # 0.30 m leak in the map perimeter, then taking the most open cell:
        # 1.35 m to the nearest wall and 3.28 m to the nearest world object.
        #
        # (-2.0, -1.0) settled 0.69 m from wooden_case_1 against a 0.67 m
        # contact threshold, so the robot spawned touching the crate and every
        # forward command ground into it: 6-11% of commanded speed with 10-15
        # degrees of yaw error. (-4.27, 6.17) was open but OUTSIDE the house --
        # the map's free space leaks into the driveway, which is the same defect
        # that let the planner drive the robot out of the surveyed area.
        DeclareLaunchArgument('x_pose', default_value='-2.92'),
        DeclareLaunchArgument('y_pose', default_value='-3.43'),
        DeclareLaunchArgument('z_pose', default_value='0.20'),
        gazebo_model_path,
        gazebo,
        spawn,
        slam,
    ])
