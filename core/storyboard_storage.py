import json
from pathlib import Path


_PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"


class StoryboardStorage:
    def load(self, project_name: str) -> dict:
        storyboard_file = _PROJECTS_DIR / project_name / "storyboard.json"

        if not storyboard_file.exists():
            return {"scenes": []}

        try:
            with open(storyboard_file, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {"scenes": []}

    def save(self, project_name: str, scenes: list[dict]) -> None:
        project_path = _PROJECTS_DIR / project_name
        project_path.mkdir(exist_ok=True)

        storyboard_file = project_path / "storyboard.json"
        payload = {"scenes": scenes}

        try:
            with open(storyboard_file, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=4)
        except OSError:
            pass
