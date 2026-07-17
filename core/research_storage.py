import json
from pathlib import Path


class ResearchStorage:
    def load(self, project_name: str) -> dict:
        project_path = Path(__file__).resolve().parent.parent / "projects" / project_name
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
        project_path = Path(__file__).resolve().parent.parent / "projects" / project_name
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

        with open(research_file, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=4)
