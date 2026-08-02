import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    pkg_share = FindPackageShare(package="multimodal_robot_autonomy").find("multimodal_robot_autonomy")
    nav2_bringup_dir = get_package_share_directory("nav2_bringup")

    # Defaults to custom_map.yaml, which pairs with worlds/new_world.world.
    # Pass map:=<name>.yaml for another, e.g. promzy_small_house_map.yaml or the
    # geometry-generated small_house_map.yaml (both for the AWS house world).
    map_file = PathJoinSubstitution([pkg_share, "maps", LaunchConfiguration("map")])

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
        DeclareLaunchArgument(
            "map",
            # custom_map_sealed.yaml is custom_map with its outer boundary closed.
            # SLAM left the perimeter open, so free space ran off the edge of the
            # grid and nav2 would plan a route out of the surveyed area; outside
            # it the scan matches nothing and AMCL diverged (measured 13.7 m)
            # while still reporting the goal succeeded. Interior geometry is
            # identical, and all seven destinations remain reachable.
            default_value="custom_map_sealed.yaml",
            description="Map file under the package's maps/ directory",
        ),
        nav2_launch,
    ])
