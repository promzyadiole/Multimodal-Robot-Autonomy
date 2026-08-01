#!/usr/bin/env bash
# Start the FastAPI command-center backend against the running simulation.
#
# The dependency situation here needs care. ~/.local holds the vision stack
# (torch, open_clip, segment_anything, cv2) AND numpy 2.2.6, but ROS Humble's
# cv_bridge and transforms3d are built against numpy 1.x and crash on numpy 2
# ("_ARRAY_API not found", "np.maximum_sctype was removed"). backend/.venv
# resolves this: it is created with --system-site-packages so ROS and the
# vision stack stay visible, and it holds numpy 1.26.4 (the version pyproject
# pins) plus a modern transforms3d, which shadow the broken ones. The old
# system transforms3d cannot be used either -- it calls np.float, removed in
# numpy 1.24.
#
# Recreate that venv with:
#   python3 -m venv --system-site-packages backend/.venv
#   backend/.venv/bin/pip install --ignore-installed \
#       numpy==1.26.4 "transforms3d>=0.4.2" fastapi "uvicorn[standard]" \
#       pydantic-settings python-dotenv pyyaml openai
set -e

cd "$(dirname "$0")/../.."   # backend/

# Same DDS domain as the sim; without this the bridge cannot see nav2 at all.
export CYCLONEDDS_URI=file:///home/promise/Multimodal-Robot-Autonomy/config/cyclonedds.xml
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-42}
export GAZEBO_MASTER_URI=${GAZEBO_MASTER_URI:-http://127.0.0.1:11345}

source /opt/ros/humble/setup.bash
source ~/turtlebot3_ws/install/setup.bash

# The default HF cache points at an unwritable /mnt/windows path on this host.
export HF_HOME=${HF_HOME:-$HOME/.cache/huggingface}
export TRANSFORMERS_CACHE=$HF_HOME
mkdir -p "$HF_HOME"

# Which environment the command center serves: new_world (default) or small_house.
export MRA_ENVIRONMENT=${MRA_ENVIRONMENT:-new_world}

exec ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 "$@"
