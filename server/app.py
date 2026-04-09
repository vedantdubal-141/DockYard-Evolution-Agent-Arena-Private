import sys
import os
import uuid
import asyncio
import logging
from typing import Optional, Dict

from fastapi import FastAPI, HTTPException, Request
from env.engine import DockForgeEnv
from env.state import Action

# Configure logging to show in HF logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

app = FastAPI(title="DockForge OpenEnv", version="1.1.0")

# ── per-session environment instances ──
_sessions: Dict[str, DockForgeEnv] = {}
_lock = asyncio.Lock()

# A single read-only env used only for metadata queries
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
async def reset(request: Request, task_id: Optional[int] = None, session_id: Optional[str] = None):
    """
    Reset the environment to a task.
    Supports task_id in JSON body or query params.
    """
    body_data = {}
    try:
        # Try to parse JSON body if possible
        if request.headers.get("content-type") == "application/json":
            body_data = await request.json()
    except Exception:
        pass

    # Priority: URL Param > Body JSON
    t_id = task_id if task_id is not None else body_data.get("task_id")
    s_id = session_id if session_id is not None else body_data.get("session_id")

    logger.info(f"RESET called: task_id={t_id}, session_id={s_id}")

    async with _lock:
        if s_id:
            _sessions[s_id] = DockForgeEnv()
            env = _sessions[s_id]
        else:
            if "__default__" not in _sessions:
                _sessions["__default__"] = DockForgeEnv()
            env = _sessions["__default__"]
        
        try:
            target_task = int(t_id) if t_id is not None else None
            obs = env.reset(target_task)
        except Exception as e:
            logger.error(f"Reset error: {e}")
            obs = env.reset(0)
    
    return obs.model_dump()


@app.post("/step")
async def step(action: Action, request: Request, session_id: Optional[str] = None):
    """Apply an action and return the next observation, reward, done, and info."""
    s_id = session_id
    if s_id is None:
        try:
            if request.headers.get("content-type") == "application/json":
                body = await request.json()
                s_id = body.get("session_id")
        except Exception:
            pass

    async with _lock:
        if s_id:
            env = _get_session(s_id)
        else:
            if "__default__" not in _sessions:
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
async def state(request: Request, session_id: Optional[str] = None):
    """Return the current observation without advancing the environment."""
    s_id = session_id
    if s_id is None:
        try:
            # Note: technically GET shouldn't have bodies, but checking just in case
            if request.headers.get("content-type") == "application/json":
                body = await request.json()
                s_id = body.get("session_id")
        except Exception:
            pass

    async with _lock:
        if s_id:
            env = _get_session(s_id)
        else:
            if "__default__" not in _sessions:
                 _sessions["__default__"] = DockForgeEnv()
            env = _sessions["__default__"]
        return env.state().model_dump()


@app.get("/tasks")
def list_tasks():
    """Enumerate all available tasks/scenarios."""
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

def main():
    import uvicorn
    uvicorn.run("server.app:app", host="0.0.0.0", port=7860, reload=False)

if __name__ == "__main__":
    main()
