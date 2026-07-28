"""Enhanced version history manager with action tracking and lightweight snapshots."""

import json
import re
from pathlib import Path
from datetime import datetime
from core.logger import get_logger


_VALID_STAGES = {"Script", "Voice", "Image Prompts"}
_SNAPSHOT_PATTERN = re.compile(r'^[\d_\-]+\.json$')


def _validate_snapshot_name(filename: str) -> bool:
    if not filename or "/" in filename or "\\" in filename:
        return False
    if ".." in filename:
        return False
    return bool(_SNAPSHOT_PATTERN.match(filename))


class HistoryManager:

    def __init__(self):
        from core.project_manager import ProjectManager
        self.pm = ProjectManager()
        self._log = get_logger()

    def _history_dir(self, project_name: str, stage: str = "") -> Path:
        d = self.pm.PROJECTS_DIR / project_name / "history"
        if stage:
            d = d / stage
        d.mkdir(parents=True, exist_ok=True)
        return d

    def record_action(self, project_name: str, action: str, description: str = "") -> str:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        d = self._history_dir(project_name)
        filename = f"action_{ts}.json"
        record = {
            "timestamp": ts,
            "action": action,
            "description": description,
            "datetime": datetime.now().strftime("%d-%m-%Y %H:%M"),
        }
        try:
            with open(d / filename, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=4)
            self._log.info("History", f"Action recorded: {project_name} - {action}")

            proj_data = self.pm.load_project(project_name)
            if proj_data:
                proj_data["total_versions"] = proj_data.get("total_versions", 0) + 1
                proj_data["current_version"] = proj_data["total_versions"]
                self.pm.update_project(project_name, proj_data)

            return filename
        except OSError as e:
            self._log.error("History", f"Failed to record action: {project_name}", exc=e)
            return ""

    def get_action_history(self, project_name: str) -> list[dict]:
        d = self._history_dir(project_name)
        actions = []
        for f in sorted(d.glob("action_*.json"), reverse=True):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                data["filename"] = f.name
                actions.append(data)
            except (OSError, json.JSONDecodeError):
                continue
        return actions

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
        if not _validate_snapshot_name(filename):
            return {}
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
        if not _validate_snapshot_name(filename):
            return False
        d = self._history_dir(project_name, stage)
        f = d / filename
        if f.exists():
            f.unlink()
            return True
        return False

    def restore_snapshot(self, project_name: str, stage: str, filename: str) -> dict:
        if not _validate_snapshot_name(filename):
            return {}
        data = self.load_snapshot(project_name, stage, filename)
        if not data:
            return {}
        self._apply_restored_data(project_name, stage, data)
        self.record_action(project_name, "Restore", f"Restored {stage} from snapshot {filename}")
        self._log.info("History", f"Snapshot restored: {project_name}/{stage}/{filename}")
        return data

    def _apply_restored_data(self, project_name: str, stage: str, data: dict):
        from core.script_storage import ScriptStorage
        from core.image_prompt_storage import ImagePromptStorage

        if stage == "Script":
            ScriptStorage().save(
                project_name=project_name,
                script_output=data.get("script_output", ""),
                script_mode=data.get("script_mode", "characters"),
                script_min=data.get("script_min", 4500),
                script_max=data.get("script_max", 5000),
                duration_preset=data.get("duration_preset", ""),
                research_data=data.get("research_data", ""),
            )
        elif stage == "Image Prompts":
            ImagePromptStorage().save(project_name, data.get("prompts", []))

    def compare_snapshots(self, project_name: str, stage: str, file1: str, file2: str) -> dict:
        if not _validate_snapshot_name(file1) or not _validate_snapshot_name(file2):
            return {}
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
        from core.script_storage import ScriptStorage
        from core.image_prompt_storage import ImagePromptStorage

        data = {}
        if stage == "Script":
            data = ScriptStorage().load(project_name)
        elif stage == "Image Prompts":
            data = ImagePromptStorage().load(project_name)

        if not data:
            return None

        has_content = any(v for v in data.values() if v and v != [] and v != {})
        if not has_content:
            return None

        return self.save_snapshot(project_name, stage, data)