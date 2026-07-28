from __future__ import annotations

WORKFLOW_STAGES = [
    "Script",
    "Voice",
    "Image Prompts",
    "Export",
]


def build_initial_workflow_state() -> dict[str, str]:
    return {stage: "AVAILABLE" if stage == "Script" else "LOCKED" for stage in WORKFLOW_STAGES}


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


def get_next_pending_stage(workflow_state: dict | None) -> str:
    workflow = normalize_workflow_state(workflow_state)
    for stage in WORKFLOW_STAGES:
        if workflow.get(stage) != "COMPLETED":
            return stage
    return WORKFLOW_STAGES[-1]


PAGE_MAP = {}

def get_resume_page_class(workflow_state: dict | None):
    global PAGE_MAP
    if not PAGE_MAP:
        from ui.pages.script_page import ScriptPage
        from ui.pages.voice_page import VoicePage
        from ui.pages.image_prompts_page import ImagePromptsPage
        from ui.pages.export_page import ExportPage
        PAGE_MAP = {
            "Script": ScriptPage,
            "Voice": VoicePage,
            "Image Prompts": ImagePromptsPage,
            "Export": ExportPage,
        }
    stage = get_next_pending_stage(workflow_state)
    return PAGE_MAP.get(stage), stage
