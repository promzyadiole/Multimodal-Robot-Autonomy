# # from fastapi import APIRouter

# # from app.services.state_store import state_store

# # router = APIRouter(prefix="/api/system", tags=["system"])


# # @router.get("/health")
# # def health():
# #     snapshot = state_store.snapshot()
# #     return {
# #         "status": "ok",
# #         "nav2_ready": snapshot.get("nav2_ready", False),
# #         "camera_available": snapshot.get("latest_image_meta") is not None,
# #     }


# from __future__ import annotations

# from fastapi import APIRouter, Depends

# from app.models.schemas import BasicActionResponse
# from app.services.environment_service import EnvironmentService, get_environment_service

# router = APIRouter(prefix="/api/system", tags=["system"])


# @router.get("/environment", response_model=BasicActionResponse)
# def get_environment(
#     env_service: EnvironmentService = Depends(get_environment_service),
# ) -> BasicActionResponse:
#     return BasicActionResponse(
#         success=True,
#         message="Environment loaded successfully.",
#         data=env_service.environment,
#     )


from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_environment_service_dep
from app.models.schemas import BasicActionResponse
from app.services.environment_service import EnvironmentService

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/environment", response_model=BasicActionResponse)
def get_environment(
    env_service: EnvironmentService = Depends(get_environment_service_dep),
) -> BasicActionResponse:
    return BasicActionResponse(
        success=True,
        message="Environment loaded successfully.",
        data=env_service.environment,
    )


# Every route the interface can take to the robot, declared once here rather
# than drawn in the frontend. A hand-drawn diagram of a system's connections
# starts accurate and quietly stops being so; this is generated from the
# running process, so a channel that is dead reports itself as dead. The
# camera spent this session subscribed to a topic nobody published on, and
# nothing in the interface could have shown that.
#
# `ros` names the topic, action or service the backend actually talks to.
# `live` is resolved at request time by asking the ROS graph whether anyone is
# on the other end -- None when there is no ROS at all, which is the case for
# the public deployment.
CHANNELS: list[dict] = [
    {
        "id": "chat.graph",
        "surface": "Chat",
        "label": "language command",
        "http": "POST /api/chat/graph-command",
        "service": "CommandGraph (LangGraph)",
        "ros": "navigate_to_pose (action)",
        "direction": "out",
        "note": "the full state machine: intent, dispatch, verify, recover",
    },
    {
        "id": "chat.command",
        "surface": "Chat",
        "label": "question",
        "http": "POST /api/chat/command",
        "service": "IntentService + RAG",
        "ros": "—",
        "direction": "out",
        "note": "answered from state and the retrieval corpus, no motion",
    },
    {
        "id": "nav.places",
        "surface": "Navigation",
        "label": "place registry",
        "http": "GET /api/navigation/places",
        "service": "YAMLRegistry",
        "ros": "—",
        "direction": "in",
        "note": "the recorded poses a goal can name",
    },
    {
        "id": "nav.goto",
        "surface": "Navigation",
        "label": "go to place",
        "http": "POST /api/navigation/go-to/{place}",
        "service": "ROS2Bridge",
        "ros": "navigate_to_pose (action)",
        "direction": "out",
        "note": "dispatches without waiting; the outcome arrives on the action",
    },
    {
        "id": "robot.status",
        "surface": "Dashboard",
        "label": "telemetry",
        "http": "GET /api/robot/status",
        "service": "StateStore",
        "ros": "/amcl_pose, /odom",
        "direction": "in",
        "note": "pose, velocity and the particle spread behind confidence",
    },
    {
        "id": "robot.scan",
        "surface": "Dashboard",
        "label": "laser summary",
        "http": "GET /api/robot/scan-summary",
        "service": "ROS2Bridge",
        "ros": "/scan",
        "direction": "in",
        "note": "nearest return and its bearing",
    },
    {
        "id": "robot.stop",
        "surface": "Control",
        "label": "stop",
        "http": "POST /api/robot/stop",
        "service": "ROS2Bridge",
        "ros": "/cmd_vel",
        "direction": "out",
        "note": "cancels the goal and publishes a zero twist",
    },
    {
        "id": "vision.objects",
        "surface": "Vision",
        "label": "detected objects",
        "http": "GET /api/vision/objects-fast-annotated",
        "service": "SAM + OpenCLIP",
        "ros": "/camera/romr_camera/image_raw",
        "direction": "in",
        "note": "segment the frame, label each mask, annotate",
    },
    {
        "id": "vision.scene",
        "surface": "Vision",
        "label": "scene summary",
        "http": "GET /api/vision/scene-summary-fast",
        "service": "VisionService",
        "ros": "/camera/romr_camera/image_raw",
        "direction": "in",
        "note": "the same detections phrased for the chat to speak",
    },
    {
        "id": "loc.init",
        "surface": "Control",
        "label": "seed localisation",
        "http": "POST /api/localization/initialize",
        "service": "ROS2Bridge",
        "ros": "/initialpose",
        "direction": "out",
        "note": "AMCL publishes no map->odom until it is given a pose",
    },
    {
        "id": "graph.shape",
        "surface": "Reasoning",
        "label": "graph shape",
        "http": "GET /api/chat/graph",
        "service": "CommandGraph",
        "ros": "—",
        "direction": "in",
        "note": "the node and edge inventory this page draws",
    },
    {
        "id": "sys.environment",
        "surface": "All",
        "label": "environment",
        "http": "GET /api/system/environment",
        "service": "EnvironmentService",
        "ros": "—",
        "direction": "in",
        "note": "which world and map the registry is bound to",
    },
]


@router.get("/channels")
def channels():
    """Live inventory of every path between the interface and the robot.

    Liveness is judged from data this process has actually received, not from
    the DDS graph. That is a lesson already paid for twice in this codebase:
    count_publishers() reported zero while nav2 was demonstrably serving goals,
    because a node's graph view is only current for topics it holds an endpoint
    on, and ActionClient.server_is_ready() stayed true 30 s after nav2 was
    killed. A channel is reported live here when something arrived on it.
    """
    from app.services.state_store import state_store

    snap = state_store.snapshot()
    ros_up = False
    nav2 = False
    try:
        from app.core.dependencies import ros_is_available

        ros_up = ros_is_available()
    except Exception:  # noqa: BLE001
        ros_up = False
    if ros_up:
        nav2 = bool(snap.get("nav2_ready"))

    # What counts as evidence that each channel carries traffic. Anything not
    # listed is a pure backend path with no ROS leg, and is live whenever the
    # process is answering at all -- which it is, or this would not return.
    evidence = {
        "/amcl_pose, /odom": snap.get("amcl_pose") is not None,
        "/scan": snap.get("scan") is not None,
        "/camera/romr_camera/image_raw": snap.get("latest_image_meta") is not None,
        "navigate_to_pose (action)": nav2,
        "/cmd_vel": nav2,
        "/initialpose": ros_up,
    }

    out = []
    for ch in CHANNELS:
        ros = ch["ros"]
        if ros == "—":
            live = True
        elif not ros_up:
            live = None
        else:
            live = bool(evidence.get(ros, False))
        out.append({**ch, "live": live})

    return {
        "success": True,
        "message": "Communication channels.",
        "data": {
            "channels": out,
            "surfaces": sorted({c["surface"] for c in CHANNELS}),
            "ros_available": ros_up,
            "nav2_ready": nav2,
        },
    }