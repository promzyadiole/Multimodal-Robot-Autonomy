from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import (
    get_action_mapper,
    get_intent_parser,
    get_ros_bridge_dep,
    get_state_store_dep,
    get_vision_service,
)
from app.models.schemas import BasicActionResponse, ChatCommandRequest
from app.services.action_mapper import ActionMapper
from app.services.intent_parser import IntentParser
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # rclpy is absent on hosts without ROS
    from app.services.ros2_bridge import ROS2Bridge
from app.services.state_store import StateStore
from app.services.command_graph import get_command_graph
from app.services.vision_service import VisionService

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/graph-command", response_model=BasicActionResponse)
def graph_command(
    payload: ChatCommandRequest,
    parser: IntentParser = Depends(get_intent_parser),
    mapper: ActionMapper = Depends(get_action_mapper),
    bridge: "ROS2Bridge" = Depends(get_ros_bridge_dep),
    store: StateStore = Depends(get_state_store_dep),
    vision: VisionService = Depends(get_vision_service),
):
    """Same command surface as /command, routed through the LangGraph graph.

    The difference that matters: this one waits for the goal's real outcome and,
    on an abort, clears the costmaps and retries once before answering. Each node
    is a LangSmith span when LANGSMITH_TRACING=true.
    """
    user_text = (
        getattr(payload, "message", None) or getattr(payload, "command", None) or ""
    ).strip()
    if not user_text:
        raise HTTPException(status_code=400, detail="Command text is required.")

    graph = get_command_graph(parser, mapper, bridge, store, vision)
    result = graph.run(user_text)
    return BasicActionResponse(
        success=result["success"],
        message=result["answer"],
        data=result,
    )


@router.get("/graph")
def graph_shape():
    """The command graph itself, for the command center to render."""
    from app.services.command_graph import CommandGraph

    return {
        "success": True,
        "message": "Command graph.",
        "data": {
            "mermaid": CommandGraph.mermaid(),
            "nodes": [
                {"id": "understand", "does": "classify intent, extract the place"},
                {"id": "navigate", "does": "resolve the place to a pose and dispatch to nav2"},
                {"id": "verify", "does": "wait for the goal's real outcome"},
                {"id": "recover", "does": "clear both costmaps, then retry once"},
                {"id": "move", "does": "bounded velocity primitive"},
                {"id": "answer", "does": "reply, with the reason when it failed"},
            ],
            "tracing_enabled": __import__("os").getenv("LANGSMITH_TRACING", "").lower() == "true",
            "langsmith_project": __import__("os").getenv("LANGSMITH_PROJECT"),
        },
    }


@router.post("/command", response_model=BasicActionResponse)
def chat_command(
    payload: ChatCommandRequest,
    parser: IntentParser = Depends(get_intent_parser),
    mapper: ActionMapper = Depends(get_action_mapper),
    bridge: "ROS2Bridge" = Depends(get_ros_bridge_dep),
    store: StateStore = Depends(get_state_store_dep),
    vision: VisionService = Depends(get_vision_service),
):
    user_text = (
        getattr(payload, "message", None)
        or getattr(payload, "command", None)
        or ""
    ).strip()

    if not user_text:
        raise HTTPException(status_code=400, detail="Command text is required.")

    parsed = parser.parse(user_text)

    if parsed.intent in {
        "GET_STATUS",
        "GET_POSE",
        "GET_PREVIOUS_POSE",
        "GET_LAST_COMMAND",
        "GET_SCAN_SUMMARY",
        "LIST_VISIBLE_OBJECTS",
        "SCENE_SUMMARY",
        "CAPTURE_FRAME",
        "UNKNOWN",
    }:
        return _handle_query(parsed.intent, parsed.response_text, bridge, store, vision)

    try:
        mapped = mapper.map_intent(parsed)
    except ValueError as exc:
        return BasicActionResponse(
            success=False,
            message=str(exc),
            data={
                "query_type": "UNKNOWN",
                "answer": str(exc),
            },
        )

    store.set_last_command(parsed.intent, "chat")

    if mapped["type"] == "nav_goal":
        pose = mapped["pose"]
        result = bridge.navigate_to_pose(pose["x"], pose["y"], pose["yaw"])
        store.set_last_result(result)
        return BasicActionResponse(
            success=True,
            message=parsed.response_text,
            data={
                "execution_type": "nav_goal",
                "target_place": mapped.get("place_key"),
                "pose": pose,
                "result": result,
                "answer": parsed.response_text,
            },
        )

    if mapped["type"] == "waypoint_route":
        result = bridge.follow_waypoints(mapped["points"])
        store.set_last_result(result)
        return BasicActionResponse(
            success=True,
            message=parsed.response_text,
            data={
                "execution_type": "waypoint_route",
                "route_name": mapped["route_name"],
                "num_points": len(mapped["points"]),
                "result": result,
                "answer": parsed.response_text,
            },
        )

    if mapped["type"] == "motion":
        cmd = mapped["cmd_vel"]
        if parsed.intent == "STOP":
            result = bridge.emergency_stop()
        else:
            result = bridge.publish_motion(
                linear_x=cmd["linear_x"],
                angular_z=cmd["angular_z"],
                duration_sec=cmd["duration_sec"],
            )
        store.set_last_result(result)
        return BasicActionResponse(
            success=True,
            message=parsed.response_text,
            data={
                "execution_type": "motion",
                "motion_key": mapped["motion_key"],
                "cmd_vel": cmd,
                "result": result,
                "answer": parsed.response_text,
            },
        )

    raise HTTPException(status_code=400, detail="Unsupported command")


def _handle_query(
    intent: str,
    response_text: str,
    bridge: ROS2Bridge,
    store: StateStore,
    vision: VisionService,
) -> BasicActionResponse:
    if intent == "GET_STATUS":
        summary = store.get_summary()
        nav2_ready = bridge.nav2_is_ready()
        is_navigating = bool(store.get("is_navigating", False))
        last_command = summary.get("last_command") or "none"

        answer = (
            f"Nav2 ready: {nav2_ready}. "
            f"Currently navigating: {is_navigating}. "
            f"Last command: {last_command}."
        )

        return BasicActionResponse(
            success=True,
            message=response_text,
            data={
                "query_type": "GET_STATUS",
                "answer": answer,
                "summary": summary,
                "nav2_ready": nav2_ready,
                "is_navigating": is_navigating,
            },
        )

    if intent == "GET_POSE":
        pose_raw = bridge.get_current_pose()
        if pose_raw:
            store.update_pose(
                x=pose_raw["x"],
                y=pose_raw["y"],
                yaw=pose_raw["yaw"],
                frame_id=pose_raw.get("frame_id", "map"),
            )

        current_pose = store.get_current_pose()

        if not current_pose:
            return BasicActionResponse(
                success=True,
                message=response_text,
                data={
                    "query_type": "GET_POSE",
                    "answer": "I do not yet have a stored current pose.",
                    "current_pose": None,
                },
            )

        answer = (
            f"My current position is x={current_pose['x']:.3f}, "
            f"y={current_pose['y']:.3f}, yaw={current_pose['yaw']:.3f} "
            f"in frame {current_pose['frame_id']}."
        )

        return BasicActionResponse(
            success=True,
            message=response_text,
            data={
                "query_type": "GET_POSE",
                "answer": answer,
                "current_pose": current_pose,
            },
        )

    if intent == "GET_PREVIOUS_POSE":
        pose_raw = bridge.get_current_pose()
        if pose_raw:
            store.update_pose(
                x=pose_raw["x"],
                y=pose_raw["y"],
                yaw=pose_raw["yaw"],
                frame_id=pose_raw.get("frame_id", "map"),
            )

        previous_pose = store.get_previous_pose()
        current_pose = store.get_current_pose()

        if not previous_pose:
            return BasicActionResponse(
                success=True,
                message=response_text,
                data={
                    "query_type": "GET_PREVIOUS_POSE",
                    "answer": "I do not yet have a stored previous pose.",
                    "previous_pose": None,
                    "current_pose": current_pose,
                },
            )

        answer = (
            f"My previous stored position was x={previous_pose['x']:.3f}, "
            f"y={previous_pose['y']:.3f}, yaw={previous_pose['yaw']:.3f} "
            f"in frame {previous_pose['frame_id']}."
        )

        return BasicActionResponse(
            success=True,
            message=response_text,
            data={
                "query_type": "GET_PREVIOUS_POSE",
                "answer": answer,
                "previous_pose": previous_pose,
                "current_pose": current_pose,
            },
        )

    if intent == "GET_LAST_COMMAND":
        last_command = store.get_last_command()
        last_result = store.get_last_result()

        if not last_command:
            return BasicActionResponse(
                success=True,
                message=response_text,
                data={
                    "query_type": "GET_LAST_COMMAND",
                    "answer": "I do not yet have a stored last command.",
                    "last_command": None,
                    "last_result": last_result,
                },
            )

        answer = (
            f"Your last command was '{last_command['command']}' "
            f"of type '{last_command['command_type']}'."
        )

        return BasicActionResponse(
            success=True,
            message=response_text,
            data={
                "query_type": "GET_LAST_COMMAND",
                "answer": answer,
                "last_command": last_command,
                "last_result": last_result,
            },
        )

    if intent == "GET_SCAN_SUMMARY":
        scan = bridge.get_scan_summary()
        return BasicActionResponse(
            success=True,
            message=response_text,
            data={
                "query_type": "GET_SCAN_SUMMARY",
                "answer": "I am checking nearby obstacles and scan readings.",
                **scan,
            },
        )

    if intent == "LIST_VISIBLE_OBJECTS":
        objects_result = vision.detect_objects_fast()
        return BasicActionResponse(
            success=True,
            message=response_text,
            data={
                "query_type": "LIST_VISIBLE_OBJECTS",
                "answer": "I am listing the visible objects I can currently detect.",
                **objects_result,
            },
        )

    if intent == "SCENE_SUMMARY":
        summary_result = vision.scene_summary_fast()
        return BasicActionResponse(
            success=True,
            message=response_text,
            data={
                "query_type": "SCENE_SUMMARY",
                "answer": summary_result.get(
                    "summary", "I am summarizing the current scene."
                ),
                **summary_result,
            },
        )

    if intent == "CAPTURE_FRAME":
        capture_result = bridge.trigger_capture("chat_capture")
        return BasicActionResponse(
            success=True,
            message=response_text,
            data={
                "query_type": "CAPTURE_FRAME",
                "answer": "I triggered a frame capture.",
                "result": capture_result,
            },
        )

    if intent == "UNKNOWN":
        return BasicActionResponse(
            success=False,
            message="Sorry, I could not confidently understand that command.",
            data={
                "query_type": "UNKNOWN",
                "answer": "Sorry, I could not confidently understand that command.",
            },
        )

    return BasicActionResponse(
        success=False,
        message="Unsupported query intent.",
        data={
            "query_type": intent,
            "answer": "Unsupported query intent.",
        },
    )