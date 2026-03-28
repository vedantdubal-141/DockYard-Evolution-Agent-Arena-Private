from pydantic import BaseModel, Field, validator
from typing import Dict, Optional, List


class Observation(BaseModel):
    files_content: Dict[str, str] = Field(
        description="A dictionary mapping file paths to their current text content."
    )
    last_build_log: str = Field(
        description="The build log or error from the last attempted action, or from the initial broken state."
    )
    task_description: str = Field(
        description="Instructions for the current debugging task."
    )


class Action(BaseModel):
    file_to_edit: Optional[str] = Field(
        default=None,
        description="Path of the file to modify. Must be a file present in the current task's file set."
    )
    replacement_content: Optional[str] = Field(
        default=None,
        description="The entirely new content of the file (completely replaces existing file)."
    )
    run_build: bool = Field(
        default=False,
        description="Set to True to attempt running the automated build and testing process."
    )


class Reward(BaseModel):
    score: float = Field(
        description="Reward float between 0.0 and 1.0 reflecting task progress."
    )
    feedback: str = Field(
        description="Verbal feedback on the last action or overall environment state."
    )
