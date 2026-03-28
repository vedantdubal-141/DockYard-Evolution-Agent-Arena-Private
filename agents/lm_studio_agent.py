"""
lm_studio_agent.py — The real deal.
Uses a local LLM via LM Studio to interact with the environment.
Similar to inference.py but focused on local development and experimentation.
"""
import json
import os
import sys
from openai import OpenAI

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.env import DockForgeEnv
from env.state import Action

# Config
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:1234/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen3-4b-2507")

AGENT_PROMPT = """You are a senior DevOps engineer. You will receive a task description, current file contents, and build logs.
Analyze the errors and provide an action in JSON format:
{
  "file_to_edit": "filename",
  "replacement_content": "new_file_content",
  "run_build": true
}
"""

def run_lm_agent(task_idx: int = 0):
    client = OpenAI(base_url=API_BASE_URL, api_key="lm-studio")
    env = DockForgeEnv()
    obs = env.reset(task_idx)
    
    print(f"--- Running LM Studio Agent on Task {task_idx} ---")
    
    for step in range(1, 6):
        user_input = {
            "task": obs.task_description,
            "files": obs.files_content,
            "log": obs.last_build_log
        }
        
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": AGENT_PROMPT},
                    {"role": "user", "content": json.dumps(user_input)}
                ],
                response_format={"type": "json_object"}
            )
            
            action_data = json.loads(response.choices[0].message.content)
            action = Action(**action_data)
        except Exception as e:
            print(f"Error calling LLM: {e}")
            break
            
        obs, reward, done, info = env.step(action)
        print(f"Step {step}: Reward={reward.score:.3f} | Done={done}")
        
        if done:
            print("Task solved by LLM!")
            break

if __name__ == "__main__":
    run_lm_agent(0)
