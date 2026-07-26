import json
from pathlib import Path


_PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"


class ImagePromptStorage:
    def load(self, project_name: str) -> dict:
        prompts_file = _PROJECTS_DIR / project_name / "image_prompts.json"

        if not prompts_file.exists():
            return {"prompts": []}

        try:
            with open(prompts_file, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {"prompts": []}

    def save(self, project_name: str, prompts: list[dict]) -> None:
        project_path = _PROJECTS_DIR / project_name
        project_path.mkdir(exist_ok=True)

        prompts_file = project_path / "image_prompts.json"
        payload = {"prompts": prompts}

        try:
            with open(prompts_file, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=4)
        except OSError:
            pass
