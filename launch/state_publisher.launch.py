import os

from launch import LaunchDescription
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare(package='multimodal_robot_autonomy').find('multimodal_robot_autonomy')
    xacro_file = os.path.join(pkg_share, 'urdf', 'romr.urdf.xacro')

    robot_description_content = ParameterValue(
        Command(['xacro ', xacro_file]),
        value_type=str
    )

    robot_state_publisher_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[
            {
                'use_sim_time': True,
                'robot_description': robot_description_content,
            }
        ],
    )

    return LaunchDescription([
        robot_state_publisher_node,
    ])
