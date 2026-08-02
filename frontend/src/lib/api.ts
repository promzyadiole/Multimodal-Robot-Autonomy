const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

export type PlacePose = {
  x: number;
  y: number;
  z?: number;
  qz: number;
  qw: number;
};

export type EnvironmentConfig = {
  name: string;
  description?: string;
  simulation?: {
    world_name?: string;
    world_path?: string;
    house_models_path?: string;
    turtlebot3_models_path?: string;
  };
  robot?: {
    model?: string;
    entity_name?: string;
    sdf_path?: string;
    urdf_path?: string;
    spawn_pose?: {
      x: number;
      y: number;
      z: number;
      yaw: number;
    };
  };
  navigation?: {
    use_sim_time?: boolean;
    map_yaml_path?: string;
    initial_pose?: {
      x: number;
      y: number;
      yaw: number;
      covariance?: {
        x?: number;
        y?: number;
        yaw?: number;
      };
    };
  };
  places_file?: string;
};

export type ApiResponse<T = unknown> = {
  success?: boolean;
  message?: string;
  data?: T;
  [key: string]: unknown;
};

export type EnvironmentResponseData = EnvironmentConfig;

export type PlacesResponseData = {
  environment: string;
  places: Record<string, PlacePose>;
};

export type LocalizationResponseData = {
  environment: string;
  result: {
    success: boolean;
    message: string;
    pose: {
      x: number;
      y: number;
      yaw: number;
    };
  };
};

export type NavigationResponseData = {
  environment: string;
  target_place: string;
  target_pose: PlacePose;
  result: {
    success?: boolean;
    [key: string]: unknown;
  };
};

export type ChatCommandResponseData = {
  answer?: string;
  response?: unknown;
  intent?: string;
  action?: string;
  [key: string]: unknown;
};

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed with status ${res.status}`);
  }
  return (await res.json()) as T;
}

/* existing project exports */

export async function getHealth(): Promise<ApiResponse> {
  const res = await fetch(`${API_BASE}/health`, {
    cache: "no-store",
  });
  return handleResponse<ApiResponse>(res);
}

export async function getRobotStatus(): Promise<ApiResponse> {
  const res = await fetch(`${API_BASE}/api/robot/status`, {
    cache: "no-store",
  });
  return handleResponse<ApiResponse>(res);
}

export async function stopRobot(): Promise<ApiResponse> {
  const res = await fetch(`${API_BASE}/api/robot/stop`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });
  return handleResponse<ApiResponse>(res);
}

export async function getVisionSummaryFast(): Promise<ApiResponse> {
  const res = await fetch(`${API_BASE}/api/vision/scene-summary-fast`, {
    cache: "no-store",
  });
  return handleResponse<ApiResponse>(res);
}

export async function getVisionObjectsFastAnnotated(): Promise<ApiResponse> {
  const res = await fetch(`${API_BASE}/api/vision/objects-fast-annotated`, {
    cache: "no-store",
  });
  return handleResponse<ApiResponse>(res);
}

export async function sendChatCommand(
  command: string
): Promise<ApiResponse<ChatCommandResponseData>> {
  const res = await fetch(`${API_BASE}/api/chat/command`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ command }),
  });
  return handleResponse<ApiResponse<ChatCommandResponseData>>(res);
}

/* new small-house exports */

export async function getEnvironment(): Promise<ApiResponse<EnvironmentResponseData>> {
  const res = await fetch(`${API_BASE}/api/system/environment`, {
    cache: "no-store",
  });
  return handleResponse<ApiResponse<EnvironmentResponseData>>(res);
}

export async function getNavigationPlaces(): Promise<ApiResponse<PlacesResponseData>> {
  const res = await fetch(`${API_BASE}/api/navigation/places`, {
    cache: "no-store",
  });
  return handleResponse<ApiResponse<PlacesResponseData>>(res);
}

export async function initializeLocalization(): Promise<ApiResponse<LocalizationResponseData>> {
  const res = await fetch(`${API_BASE}/api/localization/initialize`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  });
  return handleResponse<ApiResponse<LocalizationResponseData>>(res);
}

export async function goToPlace(placeName: string): Promise<ApiResponse<NavigationResponseData>> {
  const res = await fetch(
    `${API_BASE}/api/navigation/go-to/${encodeURIComponent(placeName)}`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    }
  );
  return handleResponse<ApiResponse<NavigationResponseData>>(res);
}

/* the LangGraph command graph */

export type CommandGraphNode = {
  id: string;
  does: string;
};

export type CommandGraphData = {
  mermaid?: string;
  nodes?: CommandGraphNode[];
  tracing_enabled?: boolean;
  langsmith_project?: string | null;
};

export type GraphRunData = {
  answer?: string;
  intent?: string;
  route?: string;
  place?: string;
  outcome?: string;
  attempts?: number;
  recovery?: string;
  /** the nodes the run actually passed through, in order, with repeats */
  path?: string[];
  tracing?: boolean;
  project?: string | null;
  pose?: Record<string, unknown>;
  [key: string]: unknown;
};

export async function getCommandGraph(): Promise<ApiResponse<CommandGraphData>> {
  const res = await fetch(`${API_BASE}/api/chat/graph`, { cache: "no-store" });
  return handleResponse<ApiResponse<CommandGraphData>>(res);
}

/**
 * Runs a command through the graph. This waits for nav2's real outcome —
 * including one recovery retry — so it can legitimately take minutes.
 */
export async function sendGraphCommand(
  command: string,
): Promise<ApiResponse<GraphRunData>> {
  const res = await fetch(`${API_BASE}/api/chat/graph-command`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ command }),
  });
  return handleResponse<ApiResponse<GraphRunData>>(res);
}