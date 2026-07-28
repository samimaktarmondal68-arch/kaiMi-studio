import json
from pathlib import Path


_PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"


def _validated_project_path(project_name: str) -> Path:
    from core.project_manager import resolve_project_dir
    return resolve_project_dir(_PROJECTS_DIR, project_name)


class ScriptStorage:
    def load(self, project_name: str) -> dict:
        try:
            project_path = _validated_project_path(project_name)
        except ValueError:
            return {}
        script_file = project_path / "script.json"

        if not script_file.exists():
            return {}

        try:
            with open(script_file, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}

    def save(
        self,
        project_name: str,
        script_output: str,
        script_mode: str = "characters",
        script_min: int = 4500,
        script_max: int = 5000,
        duration_preset: str = "",
        research_data: str = "",
    ) -> None:
        try:
            project_path = _validated_project_path(project_name)
        except ValueError:
            return
        project_path.mkdir(exist_ok=True)

        script_file = project_path / "script.json"
        data = {
            "script_output": script_output,
            "script_mode": script_mode,
            "script_min": script_min,
            "script_max": script_max,
            "duration_preset": duration_preset,
            "research_data": research_data,
        }

        try:
            with open(script_file, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=4)
        except OSError:
            pass