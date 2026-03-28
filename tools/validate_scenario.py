"""
validate_scenario.py — Pre-submission scenario validator.

Verifies every scenario JSON in scenarios/ is:
  - Parseable and well-formed
  - Solvable (a known-good solution exists that scores 1.0)
  - Reward points sum to exactly 1.0
  - All referenced files exist in initial_files
  - 'requires' chains don't create circular dependencies
  - Deterministic grading (running grader twice yields same result)

Usage:
    python tools/validate_scenario.py
"""
import json
import os
import sys
import copy

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from env.reward import calculate_reward
from env.logs import generate_logs

SCENARIOS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scenarios")


def validate_scenario(path: str) -> list:
    """Returns a list of error strings. Empty = valid."""
    errors = []
    
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        return [f"PARSE ERROR: {e}"]

    # --- Required keys ---
    for key in ["description", "initial_files", "initial_log", "solution_criteria"]:
        if key not in data:
            errors.append(f"MISSING KEY: '{key}'")

    if errors:
        return errors

    initial_files = data.get("initial_files", {})
    criteria = data.get("solution_criteria", {})
    checks = criteria.get("checks", [])

    if not checks:
        errors.append("NO CHECKS: solution_criteria.checks is empty")
        return errors

    # --- Points sum to 1.0 ---
    total_points = sum(c.get("points", 0.0) for c in checks)
    if abs(total_points - 1.0) > 0.001:
        errors.append(f"POINTS SUM: {total_points:.3f} != 1.0")

    # --- All referenced files exist in initial_files ---
    for i, check in enumerate(checks):
        file_ref = check.get("file", "")
        if file_ref not in initial_files:
            errors.append(f"CHECK[{i}]: references file '{file_ref}' not in initial_files")

    # --- Circular dependency check on 'requires' ---
    def trace_requires(idx, visited):
        if idx in visited:
            return True  # Circular!
        visited.add(idx)
        check = checks[idx]
        prereq = check.get("requires")
        if prereq:
            # Find the check that matches the prereq
            for j, other in enumerate(checks):
                if other.get("file") == prereq.get("file") and other.get("contains") == prereq.get("contains"):
                    if trace_requires(j, visited):
                        return True
        return False

    for i in range(len(checks)):
        if trace_requires(i, set()):
            errors.append(f"CHECK[{i}]: circular 'requires' dependency detected")

    # --- Solvability: build a "perfect solution" and verify it scores 1.0 ---
    perfect_files = copy.deepcopy(initial_files)
    for check in checks:
        file_path = check.get("file")
        snippet = check.get("contains")
        if file_path in perfect_files:
            if snippet not in perfect_files[file_path]:
                perfect_files[file_path] += f"\n{snippet}"

    score = calculate_reward(perfect_files, criteria, step_count=0)
    if score < 0.999:
        errors.append(f"SOLVABILITY: perfect solution scores {score:.3f}, expected 1.0")

    # --- Determinism: run grader twice ---
    score2 = calculate_reward(perfect_files, criteria, step_count=0)
    if abs(score - score2) > 0.001:
        errors.append(f"NON-DETERMINISTIC: score1={score:.3f} != score2={score2:.3f}")

    # --- Log generation doesn't crash ---
    try:
        domain = "unknown"
        if "java" in path:
            domain = "java"
        elif "rust" in path:
            domain = "rust"
        generate_logs(initial_files, criteria, domain=domain, noise_level=0.0)
    except Exception as e:
        errors.append(f"LOG GENERATION CRASH: {e}")

    return errors


def main():
    print("=" * 60)
    print("DockForge Scenario Validator")
    print("=" * 60)

    all_valid = True
    scenario_count = 0

    for root, _, files in os.walk(SCENARIOS_DIR):
        for f in sorted(files):
            if not f.endswith(".json"):
                continue
            scenario_count += 1
            path = os.path.join(root, f)
            rel = os.path.relpath(path, SCENARIOS_DIR)

            errors = validate_scenario(path)
            if errors:
                all_valid = False
                print(f"\n❌ {rel}")
                for err in errors:
                    print(f"   └── {err}")
            else:
                print(f"✅ {rel}")

    print(f"\n{'=' * 60}")
    print(f"Validated {scenario_count} scenarios.")
    if all_valid:
        print("ALL PASSED ✅")
    else:
        print("FAILURES DETECTED ❌")
        sys.exit(1)


if __name__ == "__main__":
    main()
