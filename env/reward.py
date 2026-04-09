from typing import Dict, Any, List


def calculate_reward(
    state_files: Dict[str, str],
    criteria: Dict[str, Any],
    step_count: int = 0,
    previous_files: Dict[str, str] = None,
    action_file: str = None,
) -> float:
    """
    Calculates partial completion reward [0.0 - 1.0] with:
    - Partial progress from check passes
    - Step efficiency penalty (-0.02 per step)
    - Destructive action penalty (-0.15 if a previously-passing check now fails)
    - Order-dependent gating (check only awards if its 'requires' prerequisite is met)
    """
    checks = criteria.get("checks", [])
    if not checks:
        return 1.0

    # --- Base reward from checks ---
    base_score = 0.0
    for check in checks:
        file_path = check.get("file")
        required_snippet = check.get("contains")
        points = check.get("points", 0.0)

        content = state_files.get(file_path, "")
        if content is None:
            content = ""
        if required_snippet is None or required_snippet not in content:
            continue

        # Order-dependent gating: does this check have a prerequisite?
        prereq = check.get("requires")
        if prereq:
            prereq_file = prereq.get("file", "")
            prereq_snippet = prereq.get("contains", "")
            prereq_content = state_files.get(prereq_file, "")
            if prereq_content is None or prereq_snippet not in prereq_content:
                # Prerequisite not met — no points even though content matches
                continue

        base_score += points

    # --- Step efficiency penalty ---
    solution_files = {check.get("file") for check in checks if check.get("file")}
    if action_file and action_file in solution_files:
        step_penalty = 0.005 * step_count
    else:
        step_penalty = 0.02 * step_count

    score = max(0.0, base_score - step_penalty)

    # --- Destructive action penalty ---
    if previous_files is not None:
        for check in checks:
            file_path = check.get("file")
            required_snippet = check.get("contains")

            old_content = previous_files.get(file_path, "")
            new_content = state_files.get(file_path, "")

            if old_content is None:
                old_content = ""
            if new_content is None:
                new_content = ""

            was_passing = required_snippet in old_content
            now_failing = required_snippet not in new_content

            if was_passing and now_failing:
                score = max(0.0, score - 0.15)

    score = max(0.001, min(0.999, score))
    return score
