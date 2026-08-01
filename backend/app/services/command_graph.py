"""LangGraph orchestration for natural-language robot commands.

The existing chat route is a straight line: parse, map, dispatch, reply. It
works, but it cannot answer the question that actually matters here — *did the
robot get there?* — because dispatch is fire-and-forget. Most failures in this
stack are not misunderstood language; the intent parse is nearly always right.
They are a correct pose nav2 cannot reach, usually because the obstacle layer
has accumulated readings of world furniture the SLAM map does not contain and
closed a doorway behind the robot.

So the graph earns its place in two nodes:

  verify   wait for the goal's real outcome rather than assuming success
  recover  on an abort, clear both costmaps and retry once, then explain

Every node is a traced span when LANGSMITH_TRACING=true, so a wrong turn is
inspectable instead of inferred from logs.

This wraps the existing services rather than replacing them — IntentParser,
ActionMapper, ROS2Bridge, VisionService and StateStore are unchanged, and the
original /api/chat/command route still works exactly as before.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

# Intents that are questions about state rather than instructions to act.
QUERY_INTENTS = {
    "GET_STATUS",
    "GET_POSE",
    "GET_PREVIOUS_POSE",
    "GET_LAST_COMMAND",
    "GET_SCAN_SUMMARY",
    "LIST_VISIBLE_OBJECTS",
    "SCENE_SUMMARY",
    "CAPTURE_FRAME",
    "UNKNOWN",
}

MAX_NAV_ATTEMPTS = 2          # one retry after a recovery
VERIFY_TIMEOUT_SEC = 90.0     # long enough to cross this building
VERIFY_POLL_SEC = 0.5


class CommandState(TypedDict, total=False):
    user_text: str
    parsed: Any          # ParsedIntent, carried so we never re-run the LLM
    mapped: Optional[Dict[str, Any]]
    intent: str
    response_text: str
    route: str
    place_key: Optional[str]
    pose: Optional[Dict[str, float]]
    dispatch: Optional[Dict[str, Any]]
    outcome: Optional[str]
    attempts: int
    recovery: Optional[Dict[str, Any]]
    answer: str
    success: bool
    data: Dict[str, Any]
    trail: List[str]


class CommandGraph:
    """Routes one natural-language command through understand → act → verify."""

    def __init__(self, parser, mapper, bridge, store, vision) -> None:
        self.parser = parser
        self.mapper = mapper
        self.bridge = bridge
        self.store = store
        self.vision = vision
        self._graph = self._build()

    # ---- nodes ---------------------------------------------------------
    def _understand(self, state: CommandState) -> CommandState:
        parsed = self.parser.parse(state["user_text"])
        return {
            "parsed": parsed,
            "intent": parsed.intent,
            "response_text": parsed.response_text,
            "trail": state.get("trail", []) + ["understand"],
        }

    def _classify(self, state: CommandState) -> str:
        """Conditional edge: which capability handles this intent.

        The ParsedIntent from `understand` is reused here and in the acting
        nodes -- re-parsing would mean a second LLM call for every command.
        map_intent runs again in the acting node because a conditional edge's
        state mutations are not persisted; that is a local YAML lookup, not an
        LLM call, so it is cheap.
        """
        if state.get("intent", "UNKNOWN") in QUERY_INTENTS:
            return "answer"
        try:
            mapped = self.mapper.map_intent(state["parsed"])
        except Exception:
            return "answer"
        kind = mapped.get("type")
        if kind in {"nav_goal", "waypoint_route"}:
            return "navigate"
        if kind == "motion":
            return "move"
        return "answer"

    def _navigate(self, state: CommandState) -> CommandState:
        mapped = state.get("mapped") or self.mapper.map_intent(state["parsed"])
        attempts = state.get("attempts", 0) + 1

        if mapped["type"] == "waypoint_route":
            dispatch = self.bridge.follow_waypoints(mapped["points"])
            return {
                "route": "waypoint_route",
                "dispatch": dispatch,
                "attempts": attempts,
                "place_key": mapped.get("route_name"),
                "trail": state.get("trail", []) + ["navigate"],
            }

        pose = mapped["pose"]
        dispatch = self.bridge.navigate_to_pose(pose["x"], pose["y"], pose["yaw"])
        self.store.set_last_command(state.get("intent", ""), "chat-graph")
        return {
            "route": "nav_goal",
            "place_key": mapped.get("place_key"),
            "pose": pose,
            "dispatch": dispatch,
            "attempts": attempts,
            "trail": state.get("trail", []) + ["navigate"],
        }

    def _verify(self, state: CommandState) -> CommandState:
        """Wait for the goal's real outcome instead of assuming it succeeded."""
        deadline = time.time() + VERIFY_TIMEOUT_SEC
        outcome = None
        while time.time() < deadline:
            outcome = self.store.get("nav_outcome")
            if outcome:
                break
            time.sleep(VERIFY_POLL_SEC)
        return {
            "outcome": outcome or "timeout",
            "trail": state.get("trail", []) + ["verify"],
        }

    def _after_verify(self, state: CommandState) -> str:
        if state.get("outcome") == "succeeded":
            return "answer"
        if state.get("attempts", 1) < MAX_NAV_ATTEMPTS:
            return "recover"
        return "answer"

    def _recover(self, state: CommandState) -> CommandState:
        """Clear the costmaps, which is what unsticks an accumulated obstacle layer."""
        result = self.bridge.clear_costmaps()
        time.sleep(2.0)  # let the layers repopulate from live scans
        return {
            "recovery": result,
            "trail": state.get("trail", []) + ["recover"],
        }

    def _move(self, state: CommandState) -> CommandState:
        mapped = state.get("mapped") or self.mapper.map_intent(state["parsed"])
        cmd = mapped["cmd_vel"]
        if state.get("intent") == "STOP":
            result = self.bridge.emergency_stop()
        else:
            result = self.bridge.publish_motion(
                linear_x=cmd["linear_x"],
                angular_z=cmd["angular_z"],
                duration_sec=cmd["duration_sec"],
            )
        self.store.set_last_command(state.get("intent", ""), "chat-graph")
        return {
            "route": "motion",
            "dispatch": result,
            "place_key": mapped.get("motion_key"),
            "trail": state.get("trail", []) + ["move"],
        }

    def _answer(self, state: CommandState) -> CommandState:
        intent = state.get("intent", "UNKNOWN")
        route = state.get("route")
        base = state.get("response_text") or ""

        if route == "nav_goal" or route == "waypoint_route":
            outcome = state.get("outcome")
            place = state.get("place_key") or "the destination"
            if outcome == "succeeded":
                answer = f"Arrived at {place}."
                success = True
            elif outcome == "timeout":
                answer = (
                    f"Still driving to {place} — it did not finish within "
                    f"{int(VERIFY_TIMEOUT_SEC)} seconds, so I stopped waiting."
                )
                success = True
            else:
                rec = state.get("recovery") or {}
                detail = (
                    " I cleared the costmaps and tried again."
                    if rec.get("cleared") else ""
                )
                answer = (
                    f"I could not reach {place}: nav2 reported '{outcome}'.{detail} "
                    "The planner usually reports this when the route is blocked by "
                    "obstacles that are not in the map."
                )
                success = False
            return {"answer": answer, "success": success,
                    "trail": state.get("trail", []) + ["answer"]}

        if route == "motion":
            return {"answer": base or "Motion command sent.", "success": True,
                    "trail": state.get("trail", []) + ["answer"]}

        # queries and everything unhandled fall back to the existing behaviour
        payload = self._query_payload(intent, base)
        return {
            "answer": payload["answer"],
            "success": payload["success"],
            "data": payload.get("data", {}),
            "route": "query",
            "trail": state.get("trail", []) + ["answer"],
        }

    def _query_payload(self, intent: str, response_text: str) -> Dict[str, Any]:
        if intent == "GET_POSE":
            pose = self.bridge.get_current_pose()
            if pose:
                self.store.update_pose(x=pose["x"], y=pose["y"], yaw=pose["yaw"],
                                       frame_id=pose.get("frame_id", "map"))
                return {"success": True,
                        "answer": (f"I am at x={pose['x']:.3f}, y={pose['y']:.3f}, "
                                   f"yaw={pose['yaw']:.3f} in {pose.get('frame_id','map')}."),
                        "data": {"current_pose": pose}}
            return {"success": True, "answer": "I do not have a current pose yet.", "data": {}}

        if intent == "GET_STATUS":
            summary = self.store.get_summary()
            return {"success": True,
                    "answer": (f"Nav2 ready: {bool(self.store.get('nav2_ready', False))}. "
                               f"Navigating: {bool(self.store.get('is_navigating', False))}."),
                    "data": {"summary": summary}}

        if intent == "GET_SCAN_SUMMARY":
            scan = self.bridge.get_scan_summary()
            return {"success": True, "answer": "Nearest obstacles from the last scan.",
                    "data": scan}

        if intent in {"LIST_VISIBLE_OBJECTS"}:
            return {"success": True, "answer": "Objects I can currently see.",
                    "data": self.vision.detect_objects_fast()}

        if intent == "SCENE_SUMMARY":
            res = self.vision.scene_summary_fast()
            return {"success": True, "answer": res.get("summary", "Scene summary."),
                    "data": res}

        if intent == "CAPTURE_FRAME":
            return {"success": True, "answer": "Frame captured.",
                    "data": self.bridge.trigger_capture("chat_graph_capture")}

        if intent == "UNKNOWN":
            return {"success": False,
                    "answer": "I could not confidently understand that command.",
                    "data": {}}

        return {"success": True, "answer": response_text or "Done.", "data": {}}

    # ---- wiring --------------------------------------------------------
    def _build(self):
        g = StateGraph(CommandState)
        g.add_node("understand", self._understand)
        g.add_node("navigate", self._navigate)
        g.add_node("verify", self._verify)
        g.add_node("recover", self._recover)
        g.add_node("move", self._move)
        g.add_node("answer", self._answer)

        g.set_entry_point("understand")
        g.add_conditional_edges("understand", self._classify,
                                {"navigate": "navigate", "move": "move", "answer": "answer"})
        g.add_edge("navigate", "verify")
        g.add_conditional_edges("verify", self._after_verify,
                                {"recover": "recover", "answer": "answer"})
        g.add_edge("recover", "navigate")   # retry once
        g.add_edge("move", "answer")
        g.add_edge("answer", END)
        return g.compile()

    # ---- entry point ---------------------------------------------------
    def run(self, user_text: str) -> Dict[str, Any]:
        final = self._graph.invoke({"user_text": user_text, "attempts": 0, "trail": []})
        return {
            "success": bool(final.get("success", True)),
            "answer": final.get("answer", ""),
            "intent": final.get("intent"),
            "route": final.get("route"),
            "place": final.get("place_key"),
            "pose": final.get("pose"),
            "outcome": final.get("outcome"),
            "attempts": final.get("attempts", 0),
            "recovery": final.get("recovery"),
            "path": final.get("trail", []),
            "tracing": os.getenv("LANGSMITH_TRACING", "").lower() == "true",
            "project": os.getenv("LANGSMITH_PROJECT"),
            "data": final.get("data", {}),
        }

    @staticmethod
    def mermaid() -> str:
        """The graph as mermaid, for the command center to render."""
        return (
            "flowchart TD\n"
            "  START([command]) --> understand[understand<br/>classify intent]\n"
            "  understand -->|place named| navigate[navigate<br/>resolve pose, dispatch]\n"
            "  understand -->|raw motion| move[move<br/>velocity primitive]\n"
            "  understand -->|question| answer[answer]\n"
            "  navigate --> verify[verify<br/>wait for real outcome]\n"
            "  verify -->|succeeded| answer\n"
            "  verify -->|aborted, attempt 1| recover[recover<br/>clear costmaps]\n"
            "  verify -->|aborted, attempt 2| answer\n"
            "  recover --> navigate\n"
            "  move --> answer\n"
            "  answer --> DONE([reply])\n"
        )


_command_graph: Optional[CommandGraph] = None


def get_command_graph(parser, mapper, bridge, store, vision) -> CommandGraph:
    global _command_graph
    if _command_graph is None:
        _command_graph = CommandGraph(parser, mapper, bridge, store, vision)
    return _command_graph
