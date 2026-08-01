"""RViz view of ROMR, styled to match the command centre.

Intended for capturing stills and screen recordings for the landing page, so
the background is the same near-black as the site and the default camera frames
the robot rather than the whole floor plan.

  ros2 launch multimodal_robot_autonomy rviz_romr.launch.py

The robot appears once something publishes /robot_description, which
gazebo_romr.launch.py does. Without nav2 running the map, plan and AMCL pose
displays stay empty; the robot model and laser scan still show.

Pass fixed_frame:=odom to view the robot without a map or localisation:

  ros2 launch multimodal_robot_autonomy rviz_romr.launch.py fixed_frame:=odom
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory("multimodal_robot_autonomy")
    default_config = os.path.join(pkg_share, "rviz", "romr_showcase.rviz")

    rviz = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        arguments=["-d", LaunchConfiguration("rviz_config")],
        parameters=[{"use_sim_time": LaunchConfiguration("use_sim_time")}],
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            "rviz_config",
            default_value=default_config,
            description="RViz config to load",
        ),
        DeclareLaunchArgument(
            "use_sim_time",
            default_value="true",
            description="Follow Gazebo's clock; leave true whenever the sim is running",
        ),
        DeclareLaunchArgument(
            "fixed_frame",
            default_value="map",
            description="Reference frame; use odom to view the robot without localisation",
        ),
        rviz,
    ])
