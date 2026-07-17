from __future__ import annotations

WORKFLOW_STAGES = [
    "Research",
    "Script",
    "Storyboard",
    "Image Prompts",
    "Images",
    "Voice Over",
    "Video Editing",
    "Thumbnail",
    "Export",
]


def build_initial_workflow_state() -> dict[str, str]:
    return {stage: "AVAILABLE" if stage == "Research" else "LOCKED" for stage in WORKFLOW_STAGES}


def normalize_workflow_state(workflow_state: dict | None) -> dict[str, str]:
    normalized = build_initial_workflow_state()
    if not isinstance(workflow_state, dict):
        return normalized

    for stage in WORKFLOW_STAGES:
        state = workflow_state.get(stage)
        if state in {"LOCKED", "AVAILABLE", "COMPLETED"}:
            normalized[stage] = state

    return normalized


def advance_workflow_state(workflow_state: dict[str, str], completed_stage: str) -> dict[str, str]:
    normalized = normalize_workflow_state(workflow_state)
    normalized[completed_stage] = "COMPLETED"

    try:
        index = WORKFLOW_STAGES.index(completed_stage)
    except ValueError:
        return normalized

    if index + 1 < len(WORKFLOW_STAGES):
        normalized[WORKFLOW_STAGES[index + 1]] = "AVAILABLE"

    for stage in WORKFLOW_STAGES[index + 2:]:
        normalized[stage] = "LOCKED"

    return normalized
