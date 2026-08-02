from fastapi import APIRouter, Depends

from app.core.dependencies import get_ros_bridge_dep, get_state_store_dep
from app.models.schemas import BasicActionResponse, RobotStatusResponse, ScanSummaryResponse
from app.services.ros2_bridge import ROS2Bridge
from app.services.state_store import StateStore

router = APIRouter(prefix="/api/robot", tags=["robot"])


@router.get("/status", response_model=RobotStatusResponse)
def get_status(
    bridge: ROS2Bridge = Depends(get_ros_bridge_dep),
    store: StateStore = Depends(get_state_store_dep),
):
    snapshot = store.get_summary()
    current_pose = snapshot.get("current_pose")
    odom = bridge.get_odom()

    return RobotStatusResponse(
        # live probe, not the cached flag -- see ROS2Bridge.nav2_is_ready
        nav2_ready=bridge.nav2_is_ready(),
        current_pose=current_pose,
        last_command=snapshot.get("last_command"),
        is_navigating=bool(store.get("is_navigating", False)),
        linear_velocity=odom.get("linear_x"),
        angular_velocity=odom.get("angular_z"),
        localisation=bridge.get_localisation_confidence(),
    )


@router.get("/scan-summary", response_model=ScanSummaryResponse)
def get_scan_summary(
    bridge: ROS2Bridge = Depends(get_ros_bridge_dep),
):
    scan = bridge.get_scan_summary()
    return ScanSummaryResponse(**scan)


@router.post("/stop", response_model=BasicActionResponse)
def stop_robot(
    bridge: ROS2Bridge = Depends(get_ros_bridge_dep),
    store: StateStore = Depends(get_state_store_dep),
):
    result = bridge.emergency_stop()
    store.set_last_command("STOP", "control")
    store.set_last_result(result)
    return BasicActionResponse(**result)


@router.post("/capture", response_model=BasicActionResponse)
def capture_frame(
    bridge: ROS2Bridge = Depends(get_ros_bridge_dep),
    store: StateStore = Depends(get_state_store_dep),
):
    result = bridge.trigger_capture("manual_capture")
    store.set_last_command("CAPTURE_FRAME", "vision")
    store.set_last_result(result)
    return BasicActionResponse(**result)