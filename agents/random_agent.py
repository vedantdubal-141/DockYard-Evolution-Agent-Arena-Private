"""
random_agent.py — A baseline baseline.
Indiscriminately edits files and triggers builds to see what happens.
Used to establish the absolute minimum score floor.
"""
import random
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.engine import DockForgeEnv
from env.state import Action

def run_random_agent(task_idx: int = 0):
    env = DockForgeEnv()
    obs = env.reset(task_idx)
    
    # ¯\_(ツ)_/¯
    print(f"--- Running Random Agent on Task {task_idx} ---")
    
    total_reward = 0.0
    for step in range(1, 6):  # Just 5 steps
        # Pick a random file from what's available
        filename = random.choice(list(obs.files_content.keys()))
        
        # 50/50 chance to edit or build
        if random.random() > 0.5:
            action = Action(
                file_to_edit=filename,
                replacement_content="Random noise for science...",
                run_build=True
            )
        else:
            action = Action(run_build=True)
            
        obs, reward, done, info = env.step(action)
        total_reward += reward.score
        
        print(f"Step {step}: Action={action.file_to_edit if action.file_to_edit else 'build'} "
              f"| Reward={reward.score:.3f} | Done={done}")
        
        if done:
            break
            
    print(f"--- Complete. Total Reward: {total_reward:.3f} ---")

if __name__ == "__main__":
    run_random_agent(0)
