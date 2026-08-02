from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


IntentType = Literal[
    "NAVIGATE_TO_PLACE",
    "FOLLOW_WAYPOINT_ROUTE",
    "MOVE_FORWARD",
    "MOVE_BACKWARD",
    "TURN_LEFT",
    "TURN_RIGHT",
    "ROTATE",
    "STOP",
    "GET_STATUS",
    "GET_POSE",
    "GET_SCAN_SUMMARY",
    "LIST_VISIBLE_OBJECTS",
    "SCENE_SUMMARY",
    "CAPTURE_FRAME",
    "UNKNOWN",
]


class ChatCommandRequest(BaseModel):
    message: str = Field(..., alias="command")

    model_config = {
        "populate_by_name": True,
    }


class ParsedIntent(BaseModel):
    intent: IntentType
    target_place: Optional[str] = None
    route_name: Optional[str] = None
    motion: Optional[str] = None
    query: Optional[str] = None
    response_text: str


class Pose2DResponse(BaseModel):
    x: float
    y: float
    yaw: float
    frame_id: str = "map"


class RobotStatusResponse(BaseModel):
    nav2_ready: bool
    current_pose: Optional[Pose2DResponse] = None
    last_command: Optional[str] = None
    is_navigating: bool = False
    linear_velocity: Optional[float] = None
    angular_velocity: Optional[float] = None
    # AMCL's own covariance, surfaced so the operator can see when the robot
    # does not trust its position. Absent until a pose estimate is published.
    localisation: Optional[dict] = None


class GoToPlaceRequest(BaseModel):
    place: str


class FollowRouteRequest(BaseModel):
    route_name: str


class BasicActionResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


class ScanSummaryResponse(BaseModel):
    min_distance: Optional[float] = None
    front_min_distance: Optional[float] = None
    left_min_distance: Optional[float] = None
    right_min_distance: Optional[float] = None
    obstacle_ahead: bool = False


class VisionObject(BaseModel):
    label: str
    confidence: float
    bbox: List[int]
    center_px: List[int]
    mask_id: Optional[int] = None
    direction: Optional[str] = None


class VisionObjectsResponse(BaseModel):
    timestamp: Optional[str] = None
    frame_id: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    objects: List[VisionObject] = []
    annotated_image: Optional[str] = None


class SceneSummaryResponse(BaseModel):
    summary: str
    objects: List[VisionObject] = []
    annotated_image: Optional[str] = None