from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="gazebo_ros",
            executable="spawn_entity.py",
            name="spawn_romr",
            arguments=[
                "-entity", "romr",
                "-topic", "robot_description",

                # Safe free-space spawn pose for AWS small house world
                "-x", "-3.5",
                "-y", "1.0",
                "-z", "0.20",
                "-Y", "0.02",
            ],
            output="screen",
        )
    ])
