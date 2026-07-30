import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare(package="multimodal_robot_autonomy").find("multimodal_robot_autonomy")
    nav2_bringup_dir = get_package_share_directory("nav2_bringup")

    map_file = os.path.join(
        pkg_share,
        "maps",
        "small_house_map.yaml",
    )

    params_file = os.path.join(
        pkg_share,
        "config",
        "nav2_params.yaml",
    )

    use_sim_time = LaunchConfiguration("use_sim_time", default="true")

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_dir, "launch", "bringup_launch.py")
        ),
        launch_arguments={
            "map": map_file,
            "use_sim_time": use_sim_time,
            "params_file": params_file,
        }.items(),
    )

    return LaunchDescription([
        nav2_launch,
    ])
