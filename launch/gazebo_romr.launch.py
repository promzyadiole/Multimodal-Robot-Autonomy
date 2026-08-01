"""Bring up Gazebo with ROMR in this project's custom world.

Defaults to worlds/new_world.world, the custom scene from
Language-Grounded-Robot-Autonomy, paired with maps/custom_map.yaml. Pass
world:=<name>.world to use another (e.g. promzy_small_house.world, the AWS
residential house).
"""

import os

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
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare(package="multimodal_robot_autonomy").find("multimodal_robot_autonomy")
    pkg_share_parent = os.path.dirname(pkg_share)

    # new_world.world builds its scene from stock Gazebo models (suv, cafe_table,
    # euro_pallet, wooden_case), which live in the user's local model database --
    # Gazebo's online database is unreachable here, so without ~/.gazebo/models
    # the world would load with pieces missing. The AWS house models stay on the
    # path so promzy_small_house.world still works via world:=.
    gazebo_models = os.path.expanduser("~/.gazebo/models")
    house_models = os.path.expanduser(
        "~/turtlebot3_ws/src/aws-robomaker-small-house-world/models"
    )
    robot_models = os.path.join(pkg_share, "models")

    world = PathJoinSubstitution([pkg_share, "worlds", LaunchConfiguration("world")])

    state_publisher_launch = os.path.join(pkg_share, "launch", "state_publisher.launch.py")
    spawn_launch = os.path.join(pkg_share, "launch", "spawn_robot.launch.py")

    gazebo_model_path = SetEnvironmentVariable(
        name="GAZEBO_MODEL_PATH",
        # pkg_share_parent first so package:// mesh refs resolve; without it the
        # robot loads with no collision geometry and falls through the floor.
        value=f"{pkg_share_parent}:{gazebo_models}:{house_models}:{robot_models}",
    )

    gazebo = ExecuteProcess(
        cmd=[
            "gazebo",
            "--verbose",
            world,
            "-s",
            "libgazebo_ros_init.so",
            "-s",
            "libgazebo_ros_factory.so",
        ],
        output="screen",
    )

    state_publisher = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(state_publisher_launch)
    )

    spawn = TimerAction(
        period=5.0,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(spawn_launch),
                launch_arguments={
                    "robot": LaunchConfiguration("robot"),
                    "x_pose": LaunchConfiguration("x_pose"),
                    "y_pose": LaunchConfiguration("y_pose"),
                    "z_pose": LaunchConfiguration("z_pose"),
                    "yaw": LaunchConfiguration("yaw"),
                }.items(),
            )
        ],
    )

    return LaunchDescription([
        DeclareLaunchArgument("world", default_value="new_world.world"),
        DeclareLaunchArgument("robot", default_value="romr"),
        # (-2.0, -1.0) is the spawn the original turtlebot3_new_world.launch.py
        # used; it sits in 1.71 m of clearance on custom_map.
        DeclareLaunchArgument("x_pose", default_value="-2.0"),
        DeclareLaunchArgument("y_pose", default_value="-1.0"),
        DeclareLaunchArgument("z_pose", default_value="0.20"),
        DeclareLaunchArgument("yaw", default_value="0.0"),
        gazebo_model_path,
        gazebo,
        state_publisher,
        spawn,
    ])
