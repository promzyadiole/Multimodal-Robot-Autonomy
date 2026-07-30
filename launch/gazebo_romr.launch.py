import os

from launch import LaunchDescription
from launch.actions import ExecuteProcess, IncludeLaunchDescription, SetEnvironmentVariable, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare(package="multimodal_robot_autonomy").find("multimodal_robot_autonomy")
    pkg_share_parent = os.path.dirname(pkg_share)

    small_house_repo = os.path.expanduser(
        "~/turtlebot3_ws/src/aws-robomaker-small-house-world"
    )

    house_models = os.path.join(small_house_repo, "models")
    turtlebot3_models = os.path.join(pkg_share, "models")

    small_house_world = os.path.join(
        pkg_share,
        "worlds",
        "small_house.world",
    )

    state_publisher_launch = os.path.join(
        pkg_share,
        "launch",
        "state_publisher.launch.py",
    )

    spawn_romr_launch = os.path.join(
        pkg_share,
        "launch",
        "spawn_romr.launch.py",
    )

    gazebo_model_path = SetEnvironmentVariable(
        name="GAZEBO_MODEL_PATH",
        value=f"{pkg_share_parent}:{house_models}:{turtlebot3_models}",
    )

    gazebo = ExecuteProcess(
        cmd=[
            "gazebo",
            "--verbose",
            small_house_world,
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

    spawn_romr = TimerAction(
        period=5.0,
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(spawn_romr_launch)
            )
        ],
    )

    return LaunchDescription([
        gazebo_model_path,
        gazebo,
        state_publisher,
        spawn_romr,
    ])
