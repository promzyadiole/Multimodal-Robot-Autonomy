from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_environment_service_dep
from app.models.schemas import BasicActionResponse
from app.services.environment_service import EnvironmentService

router = APIRouter(prefix="/api/localization", tags=["localization"])


@router.post("/initialize", response_model=BasicActionResponse)
def initialize_localization(
    env_service: EnvironmentService = Depends(get_environment_service_dep),
) -> BasicActionResponse:
    nav_cfg = env_service.environment.get("navigation", {})
    pose = nav_cfg.get("initial_pose", {})
    covariance = pose.get("covariance", {})

    # imported here, not at module scope: this pulls in rclpy, and the service
    # must start on hosts with no ROS runtime (see core.dependencies)
    from app.core.dependencies import ros_is_available

    if not ros_is_available():
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail="No ROS 2 runtime on this host, so localisation cannot be seeded.",
        )
    from app.services.initial_pose_service import get_initial_pose_publisher

    publisher = get_initial_pose_publisher()
    result = publisher.publish_initial_pose(
        x=float(pose["x"]),
        y=float(pose["y"]),
        yaw=float(pose["yaw"]),
        cov_x=float(covariance.get("x", 0.1)),
        cov_y=float(covariance.get("y", 0.1)),
        cov_yaw=float(covariance.get("yaw", 0.03)),
    )

    return BasicActionResponse(
        success=True,
        message="Localization initialized.",
        data={
            "environment": env_service.environment.get("name"),
            "result": result,
        },
    )