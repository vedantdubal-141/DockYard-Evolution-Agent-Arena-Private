from typing import Dict, Tuple
from env.state import Action


def apply_action(
    action: Action,
    state_files: Dict[str, str]
) -> Tuple[str, float]:
    """
    Applies the modification action to the file state in-memory.
    
    Returns:
        Tuple of (feedback_message, penalty).
        penalty is 0.0 for valid actions, -0.1 for out-of-sandbox writes.
    """
    if not action.file_to_edit or action.replacement_content is None:
        return "No file modified.", 0.0

    # Sandbox enforcement: only files in the scenario's initial_files are writable
    if action.file_to_edit not in state_files:
        return (
            f"SANDBOX VIOLATION: '{action.file_to_edit}' is not in the editable file set. "
            f"Allowed files: {list(state_files.keys())}. "
            f"Penalty applied: -0.1",
            -0.1
        )

    state_files[action.file_to_edit] = action.replacement_content
    return f"Updated {action.file_to_edit}.", 0.0
