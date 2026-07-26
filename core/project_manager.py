from pathlib import Path
from datetime import datetime
import json
import shutil

from core.workflow import build_initial_workflow_state


class ProjectManager:

    PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"

    def __init__(self):
        self.PROJECTS_DIR.mkdir(exist_ok=True)

    # ==========================================================
    # CREATE PROJECT
    # ==========================================================

    def create_project(
        self,
        name,
        topic,
        language,
        style
    ):

        name = name.strip()

        if not name:
            raise ValueError("Project name cannot be empty.")

        if Path(name).name != name or name in {".", ".."}:
            raise ValueError("Project name cannot contain folder separators.")

        project_path = self.PROJECTS_DIR / name

        if project_path.exists():
            raise FileExistsError(f'Project "{name}" already exists.')

        project_path.mkdir()

        # ------------------------------------------------------
        # Create folders
        # ------------------------------------------------------

        folders = [
            "images",
            "audio",
            "exports"
        ]

        for folder in folders:
            (project_path / folder).mkdir()

        # ------------------------------------------------------
        # Create workflow files
        # ------------------------------------------------------

        files = [
            "research.md",
            "critic.md",
            "script.md",
            "prompts.md"
        ]

        for file in files:
            (project_path / file).touch()

        # ------------------------------------------------------
        # Save metadata
        # ------------------------------------------------------

        data = {
            "name": name,
            "topic": topic,
            "language": language,
            "style": style,
            "created": datetime.now().strftime("%d-%m-%Y %H:%M"),
            "status": "Research",
            "workflow_state": build_initial_workflow_state(),
        }

        with open(project_path / "project.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        return project_path

    # ==========================================================
    # LOAD ALL PROJECTS
    # ==========================================================

    def get_projects(self):

        projects = []

        for folder in sorted(self.PROJECTS_DIR.iterdir()):

            if not folder.is_dir():
                continue

            json_file = folder / "project.json"

            if json_file.exists():

                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except (OSError, json.JSONDecodeError):
                    continue

                data["path"] = folder

                projects.append(data)

        return projects

    # ==========================================================
    # PROJECT COUNT
    # ==========================================================

    def get_project_count(self):

        return len(self.get_projects())

    # ==========================================================
    # RECENT PROJECTS
    # ==========================================================

    def get_recent_projects(self, limit=5):

        projects = self.get_projects()

        projects.sort(
            key=lambda x: datetime.strptime(x.get("created", "01-01-1970 00:00"), "%d-%m-%Y %H:%M"),
            reverse=True
        )

        return projects[:limit]

    # ==========================================================
    # DELETE PROJECT
    # ==========================================================

    def delete_project(self, project_name):

        project_path = self.PROJECTS_DIR / project_name

        if project_path.exists():
            shutil.rmtree(project_path)
            return True

        return False

    # ==========================================================
    # LOAD SINGLE PROJECT
    # ==========================================================

    def load_project(self, project_name):

        json_file = self.PROJECTS_DIR / project_name / "project.json"

        if not json_file.exists():
            return None

        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # ==========================================================
    # LAST MODIFIED
    # ==========================================================

    def get_last_modified(self, project_name: str) -> str:
        """Return a human-readable last-modified timestamp for a project folder."""
        project_path = self.PROJECTS_DIR / project_name
        if not project_path.exists():
            return "Unknown"
        try:
            latest = max(
                (f.stat().st_mtime for f in project_path.rglob("*") if f.is_file()),
                default=project_path.stat().st_mtime,
            )
            return datetime.fromtimestamp(latest).strftime("%d-%m-%Y %H:%M")
        except OSError:
            return "Unknown"

    # ==========================================================
    # UPDATE PROJECT
    # ==========================================================

    def update_project(self, project_name, data):

        json_file = self.PROJECTS_DIR / project_name / "project.json"

        if not json_file.exists():
            return False

        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        return True
