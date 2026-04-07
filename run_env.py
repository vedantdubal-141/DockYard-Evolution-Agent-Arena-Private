"""
run_env.py — Human Debug Interface for DockForge OpenEnv

Run this script to interactively debug any scenario manually.
Lets you inspect files, write fixes, and trigger builds — same
API the LLM agent uses, but driven from your terminal.

Usage:
    python run_env.py                    # starts at scenario 0
    python run_env.py --task 3           # e.g. rust/easy
    python run_env.py --list             # print all available tasks
"""
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from env.engine import DockForgeEnv
from env.state import Action


def print_obs(obs, step: int):
    """Pretty-print the current observation."""
    print(f"\n{'─' * 60}")
    print(f"  STEP {step} — Observation")
    print(f"{'─' * 60}")
    print(f"\n📋 Task:\n  {obs.task_description}")
    print(f"\n🔴 Build Log:\n{obs.last_build_log.strip()}")
    print(f"\n📁 Editable Files:")
    for fname, content in obs.files_content.items():
        print(f"\n  ── {fname} ──")
        for line in content.splitlines():
            print(f"    {line}")


def interactive_loop(env: DockForgeEnv, task_idx: int):
    obs = env.reset(task_idx, deterministic=True)
    step = 0
    print_obs(obs, step)

    while True:
        print(f"\n{'─' * 60}")
        print("Commands:")
        print("  edit <filename>   — write new file content (multi-line, end with EOF on new line)")
        print("  build             — trigger build + reward calculation")
        print("  state             — re-print current observation")
        print("  quit              — exit")
        print(f"{'─' * 60}")
        cmd = input("\n> ").strip()

        if cmd == "quit":
            print("Exiting.")
            break

        elif cmd == "state":
            print_obs(obs, step)

        elif cmd == "build":
            action = Action(run_build=True)
            obs, reward, done, info = env.step(action)
            step += 1
            print_obs(obs, step)
            print(f"\n⭐ Reward: {reward.score:.3f}  |  {reward.feedback}")
            if done:
                print("\n✅ DONE — Task solved!")
                break

        elif cmd.startswith("edit "):
            filename = cmd[len("edit "):].strip()
            if filename not in obs.files_content:
                print(f"❌ '{filename}' is not in the editable file set.")
                print(f"   Allowed: {list(obs.files_content.keys())}")
                continue
            print(f"Enter new content for '{filename}' (type EOF on a blank line to finish):")
            lines = []
            while True:
                line = input()
                if line == "EOF":
                    break
                lines.append(line)
            new_content = "\n".join(lines)
            action = Action(file_to_edit=filename, replacement_content=new_content, run_build=False)
            obs, reward, done, info = env.step(action)
            step += 1
            print(f"✏️  {reward.feedback}")

        else:
            print("Unknown command. Use: edit <file>, build, state, quit")


def main():
    parser = argparse.ArgumentParser(description="DockForge Human Debug Interface")
    parser.add_argument("--task", type=int, default=0, help="Task index to load (default: 0)")
    parser.add_argument("--list", action="store_true", help="List all available tasks and exit")
    args = parser.parse_args()

    env = DockForgeEnv()

    if args.list:
        print(f"\n{'─' * 60}")
        print(f"  Available Tasks ({len(env.scenario_files)} total)")
        print(f"{'─' * 60}")
        for i, path in enumerate(env.scenario_files):
            rel = os.path.relpath(path, os.path.dirname(os.path.abspath(__file__)))
            domain = "java" if "java" in path else "rust" if "rust" in path else "?"
            diff   = "easy" if "easy" in path else "medium" if "medium" in path else "hard"
            print(f"  [{i}]  {rel:<45}  domain={domain}  difficulty={diff}")
        print()
        return

    if args.task < 0 or args.task >= len(env.scenario_files):
        print(f"❌ Invalid task index {args.task}. Use --list to see available tasks.")
        sys.exit(1)

    print(f"\n🐳 DockForge OpenEnv — Human Debug Interface")
    print(f"   Task {args.task}: {os.path.relpath(env.scenario_files[args.task])}")
    interactive_loop(env, args.task)


if __name__ == "__main__":
    main()
