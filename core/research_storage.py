# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
import json
from pathlib import Path


_PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"


def _validated_project_path(project_name: str) -> Path:
    """Return the validated project path or raise ValueError on traversal."""
    from core.project_manager import resolve_project_dir
    return resolve_project_dir(_PROJECTS_DIR, project_name)


class ResearchStorage:
    def load(self, project_name: str) -> dict:
        try:
            project_path = _validated_project_path(project_name)
        except ValueError:
            return {}
        research_file = project_path / "research.json"

        if not research_file.exists():
            return {}

        try:
            with open(research_file, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}

    def save(
        self,
        project_name: str,
        topic: str,
        keywords: str,
        goal: str,
        sources: str,
        prompt_preview: str,
        generated_research: str | None = None,
    ) -> None:
        try:
            project_path = _validated_project_path(project_name)
        except ValueError:
            return
        project_path.mkdir(exist_ok=True)

        research_file = project_path / "research.json"
        data = {
            "topic": topic,
            "keywords": keywords,
            "goal": goal,
            "sources": sources,
            "prompt_preview": prompt_preview,
            "generated_research": generated_research or "",
        }

        try:
            with open(research_file, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=4)
        except OSError:
            pass
