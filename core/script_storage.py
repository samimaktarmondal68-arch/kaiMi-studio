import json
from pathlib import Path


class ScriptStorage:
    def load(self, project_name: str) -> dict:
        project_path = Path(__file__).resolve().parent.parent / "projects" / project_name
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
        style: str,
        length: str,
        tone: str,
        script_output: str,
    ) -> None:
        project_path = Path(__file__).resolve().parent.parent / "projects" / project_name
        project_path.mkdir(exist_ok=True)

        script_file = project_path / "script.json"
        data = {
            "style": style,
            "length": length,
            "tone": tone,
            "script_output": script_output,
        }

        with open(script_file, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4)
