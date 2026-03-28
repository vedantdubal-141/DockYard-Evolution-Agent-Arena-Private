import random
from typing import Dict, Any
from env.domains import java as java_domain
from env.domains import rust as rust_domain


def generate_logs(
    state_files: Dict[str, str],
    criteria: Dict[str, Any],
    domain: str = "unknown",
    noise_level: float = 0.0
) -> str:
    """
    Generates mock build output based on check validation.
    Only shows errors for checks whose prerequisites are already satisfied.
    This mirrors reward.py's gating logic so the agent sees the correct next error.
    """
    checks = criteria.get("checks", [])
    if not checks:
        return "Build started...\n\nSUCCESS: Build completed successfully!\n"

    log = "Build started...\n"
    first_failing_gated = None  # First check the agent is expected to fix next
    all_pass = True

    for check in checks:
        file_path = check.get("file")
        required_snippet = check.get("contains")
        content = state_files.get(file_path, "") or ""

        snippet_ok = (required_snippet is None) or (required_snippet in content)

        # Check if prerequisite is satisfied
        prereq = check.get("requires")
        prereq_ok = True
        if prereq:
            p_file = prereq.get("file", "")
            p_snip = prereq.get("contains", "")
            p_content = state_files.get(p_file, "") or ""
            prereq_ok = p_snip in p_content

        if not snippet_ok:
            all_pass = False
            # Only surface this error if prerequisite is satisfied
            # (i.e. this is the stage the agent should be at)
            if prereq_ok and first_failing_gated is None:
                first_failing_gated = check

    if all_pass:
        log += "\nSUCCESS: Build completed successfully!\n"
        return log

    # If no gated check is ready (prerequisite not met), still show the first failing check
    # so the agent knows SOMEthing is wrong, but keep it vague
    if first_failing_gated is None:
        first_failing_gated = next(
            (c for c in checks if (c.get("contains") or "") not in (state_files.get(c.get("file"), "") or "")),
            checks[0]
        )

    primary_check = first_failing_gated
    if domain == "java":
        log += java_domain.generate_domain_logs(state_files, primary_check)
    elif domain == "rust":
        log += rust_domain.generate_domain_logs(state_files, primary_check)
    else:
        log += primary_check.get("error_msg", "Unknown build error.") + "\n"

    # Progressive log masking: occasionally leak secondary hints
    if noise_level > 0 and first_failing_gated != checks[-1] and random.random() < noise_level:
        # Find next still-failing check after the primary one
        found = False
        for check in checks:
            if found:
                c_content = state_files.get(check.get("file"), "") or ""
                c_snip = check.get("contains") or ""
                if c_snip not in c_content:
                    hint = check.get("error_msg", "")
                    if hint:
                        log += f"\nWARNING (secondary): {hint}\n"
                    break
            if check is primary_check:
                found = True

    return log
