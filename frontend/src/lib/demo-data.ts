/**
 * Recorded data from real runs of this system.
 *
 * The public deployment has no robot behind it: Gazebo, ROS 2, and the SAM/CLIP
 * models cannot run on a serverless host, and a single navigation command takes
 * between 25 and 143 seconds, which is past any serverless timeout. Rather than
 * present a broken interface, the client falls back to these recordings when the
 * backend cannot be reached, and says so plainly in the header.
 *
 * Everything here is measured, not invented. The trace below is a genuine run
 * that aborted on its first attempt, recovered by clearing both costmaps, and
 * succeeded on the second -- which is why it is the one shown: it exercises the
 * recovery cycle that motivates expressing the policy as a graph.
 */

export const DEMO_PLACES = {
  parlour: { x: -5.9101, y: -3.3416, z: 0, qz: -0.7077, qw: 0.7065 },
  kitchen: { x: -8.9101, y: -4.3416, z: 0, qz: -0.7077, qw: 0.7065 },
  dining_room: { x: -8.9101, y: 7.6584, z: 0, qz: 1.0, qw: 0.0004 },
  master_bedroom: { x: -2.9101, y: 7.6584, z: 0, qz: 1.0, qw: 0.0004 },
  garage: { x: -0.4101, y: 2.8584, z: 0, qz: 0.000398, qw: 1.0 },
  store_area: { x: -0.4101, y: -3.3416, z: 0, qz: -0.7077, qw: 0.7065 },
  home: { x: -5.8533, y: -0.2812, z: 0, qz: 0.706895, qw: 0.707319 },
} as const;

export const DEMO_STATUS = {
  nav2_ready: true,
  current_pose: { x: -0.4101, y: 2.8584, yaw: 0.0008, frame_id: "map" },
  last_command: "NAVIGATE_TO_PLACE",
  is_navigating: false,
  linear_velocity: 0.0,
  angular_velocity: 0.0,
  localisation: {
    known: true,
    confident: true,
    reason: "particle spread within limits",
    sigma_x: 0.0412,
    sigma_y: 0.0388,
    sigma_yaw: 0.0231,
    position_sigma: 0.0412,
    age_sec: 0.3,
  },
};

export const DEMO_ENVIRONMENT = {
  name: "new_world",
  navigation: {
    map_yaml_path: "/maps/custom_map_sealed.yaml",
    world: "new_world.world",
  },
};

export const DEMO_GRAPH_SHAPE = {
  nodes: [
    { id: "understand", does: "classify intent, extract the place" },
    { id: "navigate", does: "resolve the place to a pose and dispatch to nav2" },
    { id: "verify", does: "wait for the goal's real outcome" },
    { id: "recover", does: "clear both costmaps, then retry once" },
    { id: "move", does: "bounded velocity primitive" },
    { id: "answer", does: "reply, with the reason when it failed" },
  ],
  tracing_enabled: true,
  langsmith_project: "multimodal-robot-autonomy",
};

/** A real run: aborted, recovered, then succeeded. */
export const DEMO_RUN = {
  answer: "Arrived at garage.",
  intent: "NAVIGATE_TO_PLACE",
  route: "nav_goal",
  place: "garage",
  outcome: "succeeded",
  attempts: 2,
  elapsed_ms: 60300,
  tracing: true,
  project: "multimodal-robot-autonomy",
  path: ["understand", "navigate", "verify", "recover", "navigate", "verify", "answer"],
  trace: [
    {
      node: "understand", at_ms: 1216, took_ms: 1216,
      detail: {
        heard: "go to the garage",
        intent: "NAVIGATE_TO_PLACE",
        target_place: "garage",
      },
    },
    {
      node: "navigate", at_ms: 1220, took_ms: 4,
      detail: {
        branch: "intent named a place",
        resolved_to: "garage",
        goal: "x -0.410  y 2.858  yaw 0.001",
        attempt: 1,
        accepted: true,
      },
    },
    {
      node: "verify", at_ms: 41767, took_ms: 40547,
      detail: { waited_for: "nav2 goal result", outcome: "aborted", budget_sec: 90 },
    },
    {
      node: "recover", at_ms: 43780, took_ms: 2002,
      detail: {
        branch: "outcome was 'aborted' on attempt 1 of 2",
        action: "cleared the global and local costmaps",
        cleared: "global,local",
        settle_sec: 2,
      },
    },
    {
      node: "navigate", at_ms: 43784, took_ms: 4,
      detail: {
        branch: "intent named a place",
        resolved_to: "garage",
        goal: "x -0.410  y 2.858  yaw 0.001",
        attempt: 2,
        accepted: true,
      },
    },
    {
      node: "verify", at_ms: 60299, took_ms: 16515,
      detail: { waited_for: "nav2 goal result", outcome: "succeeded", budget_sec: 90 },
    },
    {
      node: "answer", at_ms: 60300, took_ms: 1,
      detail: {
        branch: "nav2 outcome 'succeeded'",
        reported: "Arrived at garage.",
        attempts_used: 2,
        localisation: "confident",
      },
    },
  ],
};

/** Headline numbers from the 54-command ground-truth validation. */
export const DEMO_VALIDATION = {
  commands: 54,
  resolved: 54,
  claimed_success: 12,
  actually_arrived: 3,
  false_positives: 10,
  median_true_error_m: 6.041,
  max_true_error_m: 15.664,
};

/**
 * The channel inventory, mirroring backend/app/api/routes/system.py so the
 * deployed build can describe the system without a robot behind it. The ROS
 * legs are reported as unknown rather than live there -- see getChannels().
 */
export const DEMO_CHANNELS = {
  channels: [
    {"id": "chat.graph", "surface": "Chat", "label": "language command", "http": "POST /api/chat/graph-command", "service": "CommandGraph (LangGraph)", "ros": "navigate_to_pose (action)", "direction": "out", "note": "the full state machine: intent, dispatch, verify, recover"},
    {"id": "chat.command", "surface": "Chat", "label": "question", "http": "POST /api/chat/command", "service": "IntentService + RAG", "ros": "—", "direction": "out", "note": "answered from state and the retrieval corpus, no motion"},
    {"id": "nav.places", "surface": "Navigation", "label": "place registry", "http": "GET /api/navigation/places", "service": "YAMLRegistry", "ros": "—", "direction": "in", "note": "the recorded poses a goal can name"},
    {"id": "nav.goto", "surface": "Navigation", "label": "go to place", "http": "POST /api/navigation/go-to/{place}", "service": "ROS2Bridge", "ros": "navigate_to_pose (action)", "direction": "out", "note": "dispatches without waiting; the outcome arrives on the action"},
    {"id": "robot.status", "surface": "Dashboard", "label": "telemetry", "http": "GET /api/robot/status", "service": "StateStore", "ros": "/amcl_pose, /odom", "direction": "in", "note": "pose, velocity and the particle spread behind confidence"},
    {"id": "robot.scan", "surface": "Dashboard", "label": "laser summary", "http": "GET /api/robot/scan-summary", "service": "ROS2Bridge", "ros": "/scan", "direction": "in", "note": "nearest return and its bearing"},
    {"id": "robot.stop", "surface": "Control", "label": "stop", "http": "POST /api/robot/stop", "service": "ROS2Bridge", "ros": "/cmd_vel", "direction": "out", "note": "cancels the goal and publishes a zero twist"},
    {"id": "vision.objects", "surface": "Vision", "label": "detected objects", "http": "GET /api/vision/objects-fast-annotated", "service": "SAM + OpenCLIP", "ros": "/camera/romr_camera/image_raw", "direction": "in", "note": "segment the frame, label each mask, annotate"},
    {"id": "vision.scene", "surface": "Vision", "label": "scene summary", "http": "GET /api/vision/scene-summary-fast", "service": "VisionService", "ros": "/camera/romr_camera/image_raw", "direction": "in", "note": "the same detections phrased for the chat to speak"},
    {"id": "loc.init", "surface": "Control", "label": "seed localisation", "http": "POST /api/localization/initialize", "service": "ROS2Bridge", "ros": "/initialpose", "direction": "out", "note": "AMCL publishes no map->odom until it is given a pose"},
    {"id": "graph.shape", "surface": "Reasoning", "label": "graph shape", "http": "GET /api/chat/graph", "service": "CommandGraph", "ros": "—", "direction": "in", "note": "the node and edge inventory this page draws"},
    {"id": "sys.environment", "surface": "All", "label": "environment", "http": "GET /api/system/environment", "service": "EnvironmentService", "ros": "—", "direction": "in", "note": "which world and map the registry is bound to"},
  ],
  surfaces: ["All", "Chat", "Control", "Dashboard", "Navigation", "Reasoning", "Vision"],
  ros_available: false,
  nav2_ready: false,
};
