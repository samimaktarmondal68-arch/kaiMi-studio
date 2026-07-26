import json
from pathlib import Path


_PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"


class ScriptStorage:
    def load(self, project_name: str) -> dict:
        script_file = _PROJECTS_DIR / project_name / "script.json"

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
        style: str,
        length: str,
        tone: str,
        script_output: str,
    ) -> None:
        project_path = _PROJECTS_DIR / project_name
        project_path.mkdir(exist_ok=True)

        script_file = project_path / "script.json"
        data = {
            "style": style,
            "length": length,
            "tone": tone,
            "script_output": script_output,
        }

        try:
            with open(script_file, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=4)
        except OSError:
            pass
