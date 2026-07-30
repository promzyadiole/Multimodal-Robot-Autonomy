import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch_ros.substitutions import FindPackageShare

# ROMR is the default robot; the TurtleBot3 variants are kept so the stack can
# be A/B'd against the configuration it was originally built on.
DESCRIPTIONS = {
    'romr': 'romr.urdf.xacro',
    'burger': 'turtlebot3_burger.urdf',
    'burger_cam': 'turtlebot3_burger_cam.urdf',
    'waffle': 'turtlebot3_waffle.urdf',
    'waffle_pi': 'turtlebot3_waffle_pi.urdf',
}


def launch_setup(context, *args, **kwargs):
    robot = LaunchConfiguration('robot').perform(context)
    if robot not in DESCRIPTIONS:
        raise RuntimeError(
            f"Unknown robot '{robot}'. Choose one of: {', '.join(sorted(DESCRIPTIONS))}"
        )

    pkg_share = FindPackageShare('multimodal_robot_autonomy').find('multimodal_robot_autonomy')
    description_file = os.path.join(pkg_share, 'urdf', DESCRIPTIONS[robot])

    robot_description = ParameterValue(
        Command(['xacro ', description_file]),
        value_type=str,
    )

    state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[
            {
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                'robot_description': robot_description,
            }
        ],
    )

    spawn = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        name='spawn_robot',
        output='screen',
        arguments=[
            '-entity', robot,
            '-topic', 'robot_description',
            '-x', LaunchConfiguration('x_pose'),
            '-y', LaunchConfiguration('y_pose'),
            '-z', LaunchConfiguration('z_pose'),
            '-Y', LaunchConfiguration('yaw'),
        ],
    )

    return [state_publisher, spawn]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'robot',
            default_value='romr',
            description=f"Robot to spawn: {', '.join(sorted(DESCRIPTIONS))}",
        ),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        # Free-space pose in the AWS small house world.
        DeclareLaunchArgument('x_pose', default_value='-3.5'),
        DeclareLaunchArgument('y_pose', default_value='1.0'),
        DeclareLaunchArgument('z_pose', default_value='0.20'),
        DeclareLaunchArgument('yaw', default_value='0.02'),
        OpaqueFunction(function=launch_setup),
    ])
