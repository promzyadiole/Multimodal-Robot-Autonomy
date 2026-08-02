# from functools import lru_cache

# from app.core.config import get_settings
# from app.services.action_mapper import ActionMapper
# from app.services.intent_parser import IntentParser
# from app.services.ros2_bridge import get_ros2_bridge
# from app.services.sam_clip_perceptor import SamClipPerceptor
# from app.services.state_store import StateStore, get_state_store
# from app.services.vision_service import VisionService
# from app.services.yaml_registry import YAMLRegistry


# @lru_cache
# def get_registry() -> YAMLRegistry:
#     settings = get_settings()
#     return YAMLRegistry(settings.actions_yaml_path)


# @lru_cache
# def get_intent_parser() -> IntentParser:
#     return IntentParser()


# @lru_cache
# def get_action_mapper() -> ActionMapper:
#     return ActionMapper(get_registry())


# @lru_cache
# def get_perceptor() -> SamClipPerceptor:
#     return SamClipPerceptor(get_registry())


# @lru_cache
# def get_vision_service() -> VisionService:
#     return VisionService(get_perceptor())


# def get_ros_bridge_dep():
#     return get_ros2_bridge()


# def get_state_store_dep() -> StateStore:
#     return get_state_store()


from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.services.action_mapper import ActionMapper, get_action_mapper
from app.services.environment_service import EnvironmentService, get_environment_service
from app.services.intent_parser import IntentParser, get_intent_parser
from app.services.state_store import StateStore, get_state_store
from app.services.vision_service import VisionService, get_vision_service

if TYPE_CHECKING:  # pragma: no cover
    from app.services.ros2_bridge import ROS2Bridge


# The ROS bridge is imported lazily so the service can start on a host with no
# ROS installation. That is not a hypothetical: Gazebo, ROS 2 and the perception
# models need a persistent machine, while the language and retrieval half is
# ordinary Python that deploys anywhere. Importing rclpy at module scope
# coupled the two, so a cloud deployment of the reasoning half was impossible.
#
# Routes that genuinely need the robot raise a clear 503 instead of failing at
# import time with a stack trace about a missing shared library.

ROS_AVAILABLE: bool | None = None


def ros_is_available() -> bool:
    global ROS_AVAILABLE
    if ROS_AVAILABLE is None:
        try:
            import rclpy  # noqa: F401
            ROS_AVAILABLE = True
        except Exception:  # noqa: BLE001
            ROS_AVAILABLE = False
    return ROS_AVAILABLE


def get_ros_bridge_dep() -> "ROS2Bridge":
    if not ros_is_available():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail=(
                "No ROS 2 runtime on this host, so the robot is not reachable. "
                "The language, retrieval and graph endpoints work; navigation, "
                "teleoperation and vision need the simulator, which runs on a "
                "persistent machine rather than here."
            ),
        )
    from app.services.ros2_bridge import get_ros2_bridge

    return get_ros2_bridge()


def get_state_store_dep() -> StateStore:
    return get_state_store()


def get_intent_parser_dep() -> IntentParser:
    return get_intent_parser()


def get_action_mapper_dep() -> ActionMapper:
    return get_action_mapper()


def get_vision_service_dep() -> VisionService:
    return get_vision_service()


def get_environment_service_dep() -> EnvironmentService:
    return get_environment_service()