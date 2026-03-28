"""
heuristic_agent.py — Rule-based baseline.
Uses simple string matching on logs to choose actions.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.env import DockForgeEnv
from env.state import Action

def run_heuristic_agent(task_idx: int = 0):
    env = DockForgeEnv()
    obs = env.reset(task_idx)
    
    print(f"--- Running Heuristic Agent on Task {task_idx} ---")
    
    for step in range(1, 10):
        log = obs.last_build_log.lower()
        action = None
        
        # Simple heuristic rules
        if "rust:nightly" in log:
            # RUST_001 fix
            action = Action(
                file_to_edit="rust_dashboard_app.Dockerfile",
                replacement_content="FROM rust:1.75-slim-bookworm AS builder\nRUN rustup default nightly\nWORKDIR /app\nCOPY . .\nRUN cargo build --release",
                run_build=True
            )
        elif "unknownhostexception: database" in log:
            # JAVA_002 fix
            action = Action(
                file_to_edit="Dockerfile",
                replacement_content=obs.files_content["Dockerfile"].replace("postgres", "local"),
                run_build=True
            )
        else:
            # Fallback: just try to build
            action = Action(run_build=True)
            
        obs, reward, done, info = env.step(action)
        print(f"Step {step}: Reward={reward.score:.3f} | Done={done}")
        
        if done:
            print("Successfully solved task via heuristics!")
            break
            
if __name__ == "__main__":
    run_heuristic_agent(0)
