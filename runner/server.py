import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uuid
import asyncio
from typing import Optional

from fastapi import FastAPI, HTTPException
from env.engine import DockForgeEnv
from env.state import Action

app = FastAPI(title="DockForge OpenEnv", version="1.1.0")

# ── FIX: per-session environment instances to prevent shared-state corruption ──
# Each caller gets a unique session_id; their env lives in this dict.
_sessions: dict[str, DockForgeEnv] = {}
_lock = asyncio.Lock()

# A single read-only env used only for metadata queries (task list, etc.)
_meta_env = DockForgeEnv()


def _get_session(session_id: str) -> DockForgeEnv:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found. Call /new_session first.")
    return _sessions[session_id]


@app.get("/")
def read_root():
    return {
        "status": "ok",
        "app": "DockForge OpenEnv Server",
        "version": "1.1.0",
        "endpoints": ["/new_session", "/reset", "/step", "/state", "/tasks"],
    }


@app.post("/new_session")
async def new_session():
    """Create a new isolated environment session. Returns a session_id."""
    async with _lock:
        session_id = str(uuid.uuid4())
        _sessions[session_id] = DockForgeEnv()
    return {"session_id": session_id}


@app.post("/reset")
async def reset(payload: Optional[dict] = None, task_id: Optional[int] = None, session_id: Optional[str] = None):
    """
    Reset the environment to a task.
    Supports task_id as query param or in JSON body (payload).
    """
    # Extract task_id from payload if not provided in URL
    if task_id is None and payload and "task_id" in payload:
        try:
            task_id = int(payload["task_id"])
        except (ValueError, TypeError):
            task_id = None

    # Extract session_id from payload if not provided in URL
    if session_id is None and payload and "session_id" in payload:
        session_id = payload["session_id"]

    async with _lock:
        if session_id:
            # If session_id provided, always create/recreate it for a clean state
            _sessions[session_id] = DockForgeEnv()
            env = _sessions[session_id]
        else:
            # Fallback for single-client/grader: use default session
            if "__default__" not in _sessions:
                _sessions["__default__"] = DockForgeEnv()
            env = _sessions["__default__"]
        
        obs = env.reset(task_id)
    
    # Return Observation as top-level JSON
    return obs.model_dump()


@app.post("/step")
async def step(action: Action, payload: Optional[dict] = None, session_id: Optional[str] = None):
    """Apply an action and return the next observation, reward, done, and info."""
    if session_id is None and payload and "session_id" in payload:
        session_id = payload["session_id"]

    async with _lock:
        if session_id:
            env = _get_session(session_id)
        else:
            if "__default__" not in _sessions:
                # If no session yet, auto-create it (resets to task 0)
                _sessions["__default__"] = DockForgeEnv()
            env = _sessions["__default__"]
        
        obs, reward, done, info = env.step(action)
    
    return {
        "observation": obs.model_dump(),
        "reward": reward.model_dump(),
        "done": done,
        "info": info,
    }


@app.get("/state")
async def state(payload: Optional[dict] = None, session_id: Optional[str] = None):
    """Return the current observation without advancing the environment."""
    if session_id is None and payload and "session_id" in payload:
        session_id = payload["session_id"]

    async with _lock:
        if session_id:
            env = _get_session(session_id)
        else:
            if "__default__" not in _sessions:
                 _sessions["__default__"] = DockForgeEnv()
            env = _sessions["__default__"]
        return env.state().model_dump()


@app.get("/tasks")
def list_tasks():
    """Enumerate all available tasks/scenarios — useful for judges and agents."""
    return {
        "total": len(_meta_env.scenario_files),
        "tasks": [
            {
                "task_id": i,
                "path": os.path.relpath(p, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "domain": "java" if "java" in p else "rust" if "rust" in p else "unknown",
                "difficulty": (
                    "easy" if "easy" in p else
                    "medium" if "medium" in p else
                    "hard" if "hard" in p else "unknown"
                ),
            }
            for i, p in enumerate(_meta_env.scenario_files)
        ],
    }
