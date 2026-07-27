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


class ImagePromptStorage:
    def load(self, project_name: str) -> dict:
        try:
            project_path = _validated_project_path(project_name)
        except ValueError:
            return {"prompts": []}
        prompts_file = project_path / "image_prompts.json"

        if not prompts_file.exists():
            return {"prompts": []}

        try:
            with open(prompts_file, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {"prompts": []}

    def save(self, project_name: str, prompts: list[dict]) -> None:
        try:
            project_path = _validated_project_path(project_name)
        except ValueError:
            return
        project_path.mkdir(exist_ok=True)

        prompts_file = project_path / "image_prompts.json"
        payload = {"prompts": prompts}

        try:
            with open(prompts_file, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=4)
        except OSError:
            pass
