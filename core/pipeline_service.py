from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from core.pipeline_events import get_pipeline_events
from core.project_manager import ProjectManager
from core.workflow import (
    WORKFLOW_STAGES,
    advance_workflow_state,
    build_initial_workflow_state,
    get_next_pending_stage,
    normalize_workflow_state,
)


class StageStatus(Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


STAGE_DISPLAY_NAMES = {
    "Script": "Script",
    "Voice": "Voice / Transcript",
    "Image Prompts": "Image Prompts",
    "Export": "Export",
}


@dataclass
class NextAction:
    stage: str
    label: str
    description: str
    can_execute: bool
    reason: str = ""


AVAILABLE_ACTIONS: dict[str, str] = {
    "Script": "Generate Script",
    "Voice": "Generate Voice / Upload Audio",
    "Image Prompts": "Generate Image Prompts",
    "Export": "Export Project",
}

COMPLETED_ACTIONS: dict[str, str] = {
    "Script": "Review Script",
    "Voice": "Review Transcript",
    "Image Prompts": "Review Prompts",
    "Export": "Project Exported",
}


@dataclass
class ValidationMessage:
    stage: str
    passed: bool
    messages: list[str] = field(default_factory=list)


@dataclass
class HealthItem:
    category: str
    status: str
    message: str


@dataclass
class HealthReport:
    project_name: str
    items: list[HealthItem] = field(default_factory=list)
    overall: str = "unknown"

    @property
    def score(self) -> float:
        if not self.items:
            return 0.0
        passed = sum(1 for i in self.items if i.status == "ok")
        return passed / len(self.items)


class PipelineService:

    def __init__(self):
        self._pm = ProjectManager()
        self._events = get_pipeline_events()
        self._active_stages: dict[str, str] = {}

    @property
    def events(self):
        return self._events

    def get_pipeline_state(self, project_name: str) -> dict[str, StageStatus]:
        data = self._pm.load_project(project_name)
        if data is None:
            return {s: StageStatus.BLOCKED for s in WORKFLOW_STAGES}
        workflow = normalize_workflow_state(data.get("workflow_state", {}))
        result = {}
        for stage in WORKFLOW_STAGES:
            legacy = workflow.get(stage, "LOCKED")
            active = self._active_stages.get(f"{project_name}:{stage}")
            if active == "failed":
                result[stage] = StageStatus.FAILED
            elif active == "in_progress":
                result[stage] = StageStatus.IN_PROGRESS
            elif legacy == "COMPLETED":
                result[stage] = StageStatus.COMPLETED
            elif legacy == "AVAILABLE":
                result[stage] = StageStatus.NOT_STARTED
            else:
                result[stage] = StageStatus.BLOCKED
        return result

    def get_next_action(self, project_name: str) -> NextAction:
        data = self._pm.load_project(project_name)
        if data is None:
            return NextAction("", "", "", False, "Project not found.")

        workflow = normalize_workflow_state(data.get("workflow_state", {}))
        pipeline = self.get_pipeline_state(project_name)

        for stage in WORKFLOW_STAGES:
            status = pipeline[stage]
            if status == StageStatus.IN_PROGRESS:
                return NextAction(
                    stage=stage,
                    label="Continue " + AVAILABLE_ACTIONS.get(stage, stage),
                    description=f"Resume work on {STAGE_DISPLAY_NAMES.get(stage, stage)}.",
                    can_execute=True,
                )
            if status == StageStatus.FAILED:
                return NextAction(
                    stage=stage,
                    label="Retry " + AVAILABLE_ACTIONS.get(stage, stage),
                    description=f"Previous attempt on {STAGE_DISPLAY_NAMES.get(stage, stage)} failed.",
                    can_execute=True,
                )
            if status == StageStatus.COMPLETED:
                continue
            if status == StageStatus.NOT_STARTED:
                stage_name = STAGE_DISPLAY_NAMES.get(stage, stage)
                return NextAction(
                    stage=stage,
                    label=AVAILABLE_ACTIONS.get(stage, f"Start {stage}"),
                    description=f"{stage_name} is ready to begin.",
                    can_execute=True,
                )
            if status == StageStatus.BLOCKED:
                prereq = self._get_blocking_stage(project_name, stage)
                return NextAction(
                    stage=stage,
                    label=AVAILABLE_ACTIONS.get(stage, stage),
                    description=f"Complete {STAGE_DISPLAY_NAMES.get(prereq, prereq)} first.",
                    can_execute=False,
                    reason=f"Requires: {prereq}",
                )

        completed_count = sum(
            1 for s in WORKFLOW_STAGES if pipeline.get(s) == StageStatus.COMPLETED
        )
        if completed_count == len(WORKFLOW_STAGES):
            return NextAction(
                stage="Export",
                label="Export Project",
                description="All stages complete. Ready to export.",
                can_execute=True,
            )

        return NextAction("", "", "", False, "No action available.")

    def _get_blocking_stage(self, project_name: str, stage: str) -> str:
        try:
            idx = WORKFLOW_STAGES.index(stage)
        except ValueError:
            return WORKFLOW_STAGES[-1]
        for i in range(idx - 1, -1, -1):
            prev = WORKFLOW_STAGES[i]
            state = self.get_pipeline_state(project_name).get(prev)
            if state != StageStatus.COMPLETED:
                return prev
        return WORKFLOW_STAGES[0]

    def validate_stage(self, project_name: str, stage: str) -> ValidationMessage:
        data = self._pm.load_project(project_name)
        if data is None:
            return ValidationMessage(stage, False, ["Project not found."])

        pipeline = self.get_pipeline_state(project_name)
        status = pipeline.get(stage, StageStatus.BLOCKED)

        if status == StageStatus.BLOCKED:
            blocker = self._get_blocking_stage(project_name, stage)
            return ValidationMessage(
                stage, False,
                [f"Cannot start {STAGE_DISPLAY_NAMES.get(stage, stage)}.",
                 f"Complete {STAGE_DISPLAY_NAMES.get(blocker, blocker)} first."],
            )

        if status == StageStatus.COMPLETED:
            return ValidationMessage(
                stage, True,
                [f"{STAGE_DISPLAY_NAMES.get(stage, stage)} is already complete."],
            )

        messages = []
        passed = True

        if stage == "Script":
            if not data.get("topic"):
                messages.append("No topic defined for the project.")
                passed = False
            if not data.get("platform"):
                # Legacy projects may lack a platform; default keeps them working.
                data["platform"] = "Long Form"
                self._pm.update_project(project_name, data)

        elif stage == "Voice":
            script_data = self._load_storage("script", project_name)
            if not script_data or not script_data.get("script_output", "").strip():
                messages.append("No script exists. Generate a script first.")
                passed = False

        elif stage == "Image Prompts":
            script_data = self._load_storage("script", project_name)
            if not script_data or not script_data.get("script_output", "").strip():
                messages.append("No script exists. Generate a script first.")
                passed = False

        elif stage == "Export":
            stages_needed = ["Script", "Voice", "Image Prompts"]
            missing = []
            for s in stages_needed:
                s_data = self._load_storage(s.lower().replace(" ", "_"), project_name)
                if not s_data:
                    missing.append(s)
            if missing:
                messages.append(f"Missing data from: {', '.join(missing)}.")
                passed = False

        if passed and not messages:
            messages.append(f"{STAGE_DISPLAY_NAMES.get(stage, stage)} prerequisites met.")

        return ValidationMessage(stage, passed, messages)

    def _load_storage(self, storage_name: str, project_name: str) -> dict | None:
        try:
            if storage_name == "script":
                from core.script_storage import ScriptStorage
                return ScriptStorage().load(project_name)
            elif storage_name == "voice":
                try:
                    import json
                    from pathlib import Path
                    voice_path = Path(__file__).resolve().parent.parent / "projects" / project_name / "voice.json"
                    if voice_path.exists():
                        with open(voice_path, "r", encoding="utf-8") as f:
                            return json.load(f)
                except Exception:
                    pass
                return None
            elif storage_name == "image_prompts":
                from core.image_prompt_storage import ImagePromptStorage
                return ImagePromptStorage().load(project_name)
            elif storage_name == "research":
                from core.research_storage import ResearchStorage
                return ResearchStorage().load(project_name)
        except Exception:
            return None
        return None

    def mark_stage_started(self, project_name: str, stage: str):
        key = f"{project_name}:{stage}"
        self._active_stages[key] = "in_progress"
        self._events.stage_started.emit(project_name, stage)

    def mark_stage_completed(self, project_name: str, stage: str):
        key = f"{project_name}:{stage}"
        self._active_stages.pop(key, None)
        data = self._pm.load_project(project_name)
        if data is not None:
            workflow = data.get("workflow_state", {})
            data["workflow_state"] = advance_workflow_state(workflow, stage)
            data["last_modified"] = datetime.now().strftime("%d-%m-%Y %H:%M")
            self._pm.update_project(project_name, data)
        self._events.stage_completed.emit(project_name, stage)
        self._events.project_updated.emit(project_name)
        self._events.health_changed.emit(project_name)

    def mark_stage_failed(self, project_name: str, stage: str, reason: str = ""):
        key = f"{project_name}:{stage}"
        self._active_stages[key] = "failed"
        self._events.stage_failed.emit(project_name, stage, reason)
        self._events.health_changed.emit(project_name)

    def mark_stage_reset(self, project_name: str, stage: str):
        key = f"{project_name}:{stage}"
        self._active_stages.pop(key, None)

    def get_project_health(self, project_name: str) -> HealthReport:
        data = self._pm.load_project(project_name)
        if data is None:
            return HealthReport(project_name, [HealthItem("project", "error", "Project not found.")], "error")

        items = []
        pipeline = self.get_pipeline_state(project_name)

        has_topic = bool(data.get("topic", "").strip())
        items.append(HealthItem(
            "topic", "ok" if has_topic else "warning",
            "Topic defined." if has_topic else "No topic set."
        ))

        for stage in WORKFLOW_STAGES:
            status = pipeline.get(stage, StageStatus.BLOCKED)
            if status == StageStatus.COMPLETED:
                items.append(HealthItem(stage.lower(), "ok", f"{stage} completed."))
            elif status == StageStatus.IN_PROGRESS:
                items.append(HealthItem(stage.lower(), "info", f"{stage} in progress."))
            elif status == StageStatus.FAILED:
                items.append(HealthItem(stage.lower(), "error", f"{stage} failed. Retry recommended."))
            elif status == StageStatus.NOT_STARTED:
                items.append(HealthItem(stage.lower(), "warning", f"{stage} not started."))
            else:
                items.append(HealthItem(stage.lower(), "info", f"{stage} blocked."))

        if has_topic:
            total_stages = len(WORKFLOW_STAGES)
            done = sum(1 for s in WORKFLOW_STAGES if pipeline.get(s) == StageStatus.COMPLETED)
            if done == total_stages:
                overall = "ready"
            elif done > 0:
                overall = "in_progress"
            else:
                overall = "new"
        else:
            overall = "incomplete"

        return HealthReport(project_name, items, overall)

    def get_completed_stage_names(self, project_name: str) -> list[str]:
        pipeline = self.get_pipeline_state(project_name)
        return [s for s in WORKFLOW_STAGES if pipeline.get(s) == StageStatus.COMPLETED]

    def export_project(self, project_name: str) -> str | None:
        """Export a project to TXT through the shared ExportService.

        Loads the project record and passes the full project data structure
        to ``ExportService.export_project``, which expects a dict (project
        metadata), not a name string (FIX B: previously the name was passed
        directly, raising an AttributeError that was silently swallowed, so
        this wrapper always returned None). Returns the written TXT path, or
        None when validation fails or the project cannot be found. Genuine
        export errors propagate to the caller instead of being swallowed.
        """
        validation = self.validate_stage(project_name, "Export")
        if not validation.passed:
            return None
        data = self._pm.load_project(project_name)
        if data is None:
            return None
        from core.export_service import ExportService
        service = ExportService(self._pm)
        result = service.export_project(data, fmt="txt")
        if result:
            self._events.export_completed.emit(project_name, str(result))
        return str(result) if result else None


_pipeline_service_instance = None


def get_pipeline_service() -> PipelineService:
    global _pipeline_service_instance
    if _pipeline_service_instance is None:
        _pipeline_service_instance = PipelineService()
    return _pipeline_service_instance
