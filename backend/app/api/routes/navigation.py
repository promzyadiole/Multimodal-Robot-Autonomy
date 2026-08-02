from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import get_environment_service_dep, get_ros_bridge_dep
from app.models.schemas import BasicActionResponse
from app.services.environment_service import EnvironmentService
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # rclpy is absent on hosts without ROS
    from app.services.ros2_bridge import ROS2Bridge

router = APIRouter(prefix="/api/navigation", tags=["navigation"])


@router.get("/places", response_model=BasicActionResponse)
def list_places(
    env_service: EnvironmentService = Depends(get_environment_service_dep),
) -> BasicActionResponse:
    places = env_service.list_places()
    return BasicActionResponse(
        success=True,
        message="Available places loaded successfully.",
        data={
            "environment": env_service.environment.get("name"),
            "places": places,
        },
    )


@router.post("/go-to/{place_name}", response_model=BasicActionResponse)
def go_to_place(
    place_name: str,
    bridge: "ROS2Bridge" = Depends(get_ros_bridge_dep),
    env_service: EnvironmentService = Depends(get_environment_service_dep),
) -> BasicActionResponse:
    try:
        place = env_service.get_place(place_name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    result = bridge.navigate_to_pose_quaternion(
        x=float(place["x"]),
        y=float(place["y"]),
        qz=float(place["qz"]),
        qw=float(place["qw"]),
    )

    return BasicActionResponse(
        success=result.get("success", False),
        message=f"Navigation command sent to '{place_name}'.",
        data={
            "environment": env_service.environment.get("name"),
            "target_place": place_name,
            "target_pose": place,
            "result": result,
        },
    )