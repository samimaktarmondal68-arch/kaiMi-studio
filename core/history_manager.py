"""Version history manager for all stage outputs.

Creates timestamped snapshots in <project>/history/<stage>/.
Allows restore, compare, and delete operations.
"""

import json
from pathlib import Path
from datetime import datetime
from core.logger import get_logger


class HistoryManager:

    def __init__(self):
        from core.project_manager import ProjectManager
        self.pm = ProjectManager()
        self._log = get_logger()

    def _history_dir(self, project_name: str, stage: str) -> Path:
        d = self.pm.PROJECTS_DIR / project_name / "history" / stage
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_snapshot(self, project_name: str, stage: str, data: dict) -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        d = self._history_dir(project_name, stage)
        filename = f"{ts}.json"
        try:
            with open(d / filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            self._log.info("History", f"Snapshot saved: {project_name}/{stage}/{filename}")
        except OSError as e:
            self._log.error("History", f"Failed to save snapshot: {project_name}/{stage}", exc=e)
            filename = ""
        return filename

    def list_snapshots(self, project_name: str, stage: str) -> list[dict]:
        d = self._history_dir(project_name, stage)
        snapshots = []
        for f in sorted(d.glob("*.json"), reverse=True):
            try:
                stat = f.stat()
                snapshots.append({
                    "filename": f.name,
                    "timestamp": f.stem,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_ctime).strftime("%d-%m-%Y %H:%M"),
                })
            except OSError:
                continue
        return snapshots

    def load_snapshot(self, project_name: str, stage: str, filename: str) -> dict:
        d = self._history_dir(project_name, stage)
        f = d / filename
        if not f.exists():
            return {}
        try:
            with open(f, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}

    def delete_snapshot(self, project_name: str, stage: str, filename: str) -> bool:
        d = self._history_dir(project_name, stage)
        f = d / filename
        if f.exists():
            f.unlink()
            return True
        return False

    def restore_snapshot(self, project_name: str, stage: str, filename: str) -> dict:
        data = self.load_snapshot(project_name, stage, filename)
        if not data:
            return {}
        self._apply_restored_data(project_name, stage, data)
        self._log.info("History", f"Snapshot restored: {project_name}/{stage}/{filename}")
        return data

    def _apply_restored_data(self, project_name: str, stage: str, data: dict):
        from core.research_storage import ResearchStorage
        from core.script_storage import ScriptStorage
        from core.storyboard_storage import StoryboardStorage
        from core.image_prompt_storage import ImagePromptStorage

        if stage == "Research":
            ResearchStorage().save(
                project_name=project_name,
                topic=data.get("topic", ""),
                keywords=data.get("keywords", ""),
                goal=data.get("goal", ""),
                sources=data.get("sources", ""),
                prompt_preview=data.get("prompt_preview", ""),
                generated_research=data.get("generated_research", ""),
            )
        elif stage == "Script":
            ScriptStorage().save(
                project_name=project_name,
                style=data.get("style", "Educational"),
                length=data.get("length", "Medium"),
                tone=data.get("tone", "Friendly"),
                script_output=data.get("script_output", ""),
            )
        elif stage == "Storyboard":
            StoryboardStorage().save(project_name, data.get("scenes", []))
        elif stage == "Image Prompts":
            ImagePromptStorage().save(project_name, data.get("prompts", []))

    def compare_snapshots(self, project_name: str, stage: str, file1: str, file2: str) -> dict:
        data1 = self.load_snapshot(project_name, stage, file1)
        data2 = self.load_snapshot(project_name, stage, file2)

        diffs = {}
        all_keys = set(list(data1.keys()) + list(data2.keys()))
        for key in sorted(all_keys):
            v1 = data1.get(key)
            v2 = data2.get(key)
            if v1 != v2:
                diffs[key] = {"version_1": v1, "version_2": v2}
        return diffs

    def auto_snapshot(self, project_name: str, stage: str) -> str | None:
        from core.research_storage import ResearchStorage
        from core.script_storage import ScriptStorage
        from core.storyboard_storage import StoryboardStorage
        from core.image_prompt_storage import ImagePromptStorage

        data = {}
        if stage == "Research":
            data = ResearchStorage().load(project_name)
        elif stage == "Script":
            data = ScriptStorage().load(project_name)
        elif stage == "Storyboard":
            data = StoryboardStorage().load(project_name)
        elif stage == "Image Prompts":
            data = ImagePromptStorage().load(project_name)

        if not data:
            return None

        has_content = any(v for v in data.values() if v and v != [] and v != {})
        if not has_content:
            return None

        return self.save_snapshot(project_name, stage, data)
