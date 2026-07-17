from __future__ import annotations

import json
from pathlib import Path
from shutil import copy2

from core.project_manager import ProjectManager
from core.research_storage import ResearchStorage
from core.script_storage import ScriptStorage
from core.storyboard_storage import StoryboardStorage
from core.image_prompt_storage import ImagePromptStorage


class ExportService:
    def __init__(self, project_manager: ProjectManager | None = None):
        self.project_manager = project_manager or ProjectManager()

    def export_project(self, project: dict) -> Path:
        project_name = project.get("name") or "project"
        project_path = self.project_manager.PROJECTS_DIR / project_name
        export_root = self.project_manager.PROJECTS_DIR / project_name / "exports" / project_name
        export_root.mkdir(parents=True, exist_ok=True)

        folders = [
            "research",
            "script",
            "storyboard",
            "image_prompts",
            "assets",
            "assets/images",
            "voice",
            "video",
        ]
        for folder in folders:
            (export_root / folder).mkdir(parents=True, exist_ok=True)

        research_storage = ResearchStorage()
        script_storage = ScriptStorage()
        storyboard_storage = StoryboardStorage()
        image_prompt_storage = ImagePromptStorage()

        research_data = research_storage.load(project_name)
        script_data = script_storage.load(project_name)
        storyboard_data = storyboard_storage.load(project_name)
        image_prompt_data = image_prompt_storage.load(project_name)

        project_json_path = project_path / "project.json"
        if project_json_path.exists():
            copy2(project_json_path, export_root / "project.json")

        research_markdown_path = project_path / "research.md"
        if research_markdown_path.exists():
            copy2(research_markdown_path, export_root / "research.md")

        script_markdown_path = project_path / "script.md"
        if script_markdown_path.exists():
            copy2(script_markdown_path, export_root / "script.md")

        prompts_markdown_path = project_path / "prompts.md"
        if prompts_markdown_path.exists():
            copy2(prompts_markdown_path, export_root / "prompts.md")

        critic_markdown_path = project_path / "critic.md"
        if critic_markdown_path.exists():
            copy2(critic_markdown_path, export_root / "critic.md")

        with open(export_root / "research" / "research.json", "w", encoding="utf-8") as handle:
            json.dump(research_data, handle, indent=4)

        with open(export_root / "script" / "script.json", "w", encoding="utf-8") as handle:
            json.dump(script_data, handle, indent=4)

        with open(export_root / "storyboard" / "storyboard.json", "w", encoding="utf-8") as handle:
            json.dump(storyboard_data, handle, indent=4)

        with open(export_root / "image_prompts" / "image_prompts.json", "w", encoding="utf-8") as handle:
            json.dump(image_prompt_data, handle, indent=4)

        prompt_lines = []
        for prompt in image_prompt_data.get("prompts", []):
            prompt_lines.append(f"Scene {prompt.get('scene_number', 1)}: {prompt.get('full_image_prompt', '')}")
        (export_root / "image_prompts" / "image_prompts.txt").write_text("\n\n".join(prompt_lines), encoding="utf-8")

        completed_stages = [
            stage
            for stage in ["Research", "Script", "Storyboard", "Image Prompts", "Images", "Voice Over", "Video Editing", "Thumbnail", "Export"]
            if project.get("workflow_state", {}).get(stage) == "COMPLETED"
        ]
        progress_text = f"{len(completed_stages)} / 9 stages completed"

        readme_lines = [
            f"Project Name: {project_name}",
            f"Creation Date: {project.get('created', '-')}",
            f"Progress: {progress_text}",
            f"Completed Stages: {', '.join(completed_stages) if completed_stages else 'None'}",
        ]
        (export_root / "README.txt").write_text("\n".join(readme_lines), encoding="utf-8")

        return export_root
