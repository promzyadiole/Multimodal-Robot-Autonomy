# from fastapi import FastAPI
# from fastapi.middleware.cors import CORSMiddleware

# from app.api.routes import chat, memory, navigation, robot, system, vision
# from app.core.config import get_settings
# from app.services.ros2_bridge import get_ros2_bridge




# settings = get_settings()

# app = FastAPI(title=settings.app_name)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:3000"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# app.include_router(system.router)
# app.include_router(robot.router)
# app.include_router(navigation.router)
# app.include_router(vision.router)
# app.include_router(chat.router)
# app.include_router(memory.router)


# @app.on_event("startup")
# def startup_event():
#     get_ros2_bridge()


# @app.get("/")
# def root():
#     return {"message": f"{settings.app_name} is running."}


import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import chat, localization, navigation, robot, system, vision
from app.core.security import guard, limits_status

app = FastAPI(title="Robot Command Center API")

# Origins allowed to call this service. Localhost for development; the deployed
# interface is added through ALLOWED_ORIGINS so the host, not the source, decides.
_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_extra = os.getenv("ALLOWED_ORIGINS", "").strip()
if _extra:
    _origins += [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def apply_limits(request: Request, call_next):
    """API key, per-client rate limit and daily budget on the paid endpoints.

    Middleware rather than a per-route dependency so that a route added later
    is protected by default: forgetting to attach a dependency is a silent
    hole, whereas forgetting to add a prefix to COSTLY_PREFIXES fails safe in
    the other direction only for genuinely new surface area.
    """
    try:
        await guard(request)
    except HTTPException as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                            headers=exc.headers or {})
    return await call_next(request)

app.include_router(system.router)
app.include_router(robot.router)
app.include_router(navigation.router)
app.include_router(localization.router)
app.include_router(chat.router)
app.include_router(vision.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/system/limits")
def limits():
    """What the public deployment enforces, so a caller can see it up front."""
    return limits_status()