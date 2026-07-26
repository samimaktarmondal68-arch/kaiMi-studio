from pathlib import Path
from datetime import datetime
import json
import os
import shutil
import tempfile

from core.workflow import build_initial_workflow_state
from core.logger import get_logger


class ProjectManager:

    PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"

    def __init__(self):
        self.PROJECTS_DIR.mkdir(exist_ok=True)
        self._log = get_logger()

    # ==========================================================
    # CREATE PROJECT
    # ==========================================================

    def create_project(self, name, topic, language, style):
        name = name.strip()
        if not name:
            raise ValueError("Project name cannot be empty.")
        if Path(name).name != name or name in {".", ".."}:
            raise ValueError("Project name cannot contain folder separators.")

        project_path = self.PROJECTS_DIR / name
        if project_path.exists():
            raise FileExistsError(f'Project "{name}" already exists.')

        project_path.mkdir()
        for folder in ["images", "audio", "exports", "history"]:
            (project_path / folder).mkdir()
        for file in ["research.md", "critic.md", "script.md", "prompts.md"]:
            (project_path / file).touch()

        data = {
            "name": name,
            "topic": topic,
            "language": language,
            "style": style,
            "created": datetime.now().strftime("%d-%m-%Y %H:%M"),
            "last_modified": datetime.now().strftime("%d-%m-%Y %H:%M"),
            "status": "Research",
            "workflow_state": build_initial_workflow_state(),
            "favorite": False,
            "archived": False,
            "thumbnail_color": "",
        }

        with open(project_path / "project.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)

        self._log.info("ProjectManager", f"Created project: {name}")
        return project_path

    # ==========================================================
    # LOAD ALL PROJECTS
    # ==========================================================

    def get_projects(self, include_archived=False):
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
                if not include_archived and data.get("archived", False):
                    continue
                projects.append(data)
        return projects

    def get_all_projects(self):
        return self.get_projects(include_archived=True)

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
            key=lambda x: x.get("last_modified", x.get("created", "01-01-1970 00:00")),
            reverse=True,
        )
        return projects[:limit]

    # ==========================================================
    # SEARCH / SORT / FILTER
    # ==========================================================

    def search_projects(self, query: str):
        query = query.lower().strip()
        if not query:
            return self.get_projects()
        results = []
        for p in self.get_projects():
            searchable = " ".join([
                p.get("name", ""),
                p.get("topic", ""),
                p.get("status", ""),
                p.get("language", ""),
                p.get("style", ""),
            ]).lower()
            if query in searchable:
                results.append(p)
        return results

    def sort_projects(self, projects, sort_by="last_modified", reverse=True):
        key_map = {
            "last_modified": lambda x: x.get("last_modified", x.get("created", "")),
            "name": lambda x: x.get("name", "").lower(),
            "status": lambda x: x.get("status", ""),
            "created": lambda x: x.get("created", ""),
        }
        key_fn = key_map.get(sort_by, key_map["last_modified"])
        return sorted(projects, key=key_fn, reverse=reverse)

    def filter_projects(self, projects, status_filter=None):
        if not status_filter or status_filter == "All":
            return projects
        return [p for p in projects if p.get("status") == status_filter]

    # ==========================================================
    # DUPLICATE PROJECT
    # ==========================================================

    def duplicate_project(self, original_name: str, new_name: str):
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("New project name cannot be empty.")

        src = self.PROJECTS_DIR / original_name
        dst = self.PROJECTS_DIR / new_name

        if not src.exists():
            raise FileNotFoundError(f'Project "{original_name}" not found.')
        if dst.exists():
            raise FileExistsError(f'Project "{new_name}" already exists.')

        shutil.copytree(src, dst)

        json_file = dst / "project.json"
        if json_file.exists():
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["name"] = new_name
            data["created"] = datetime.now().strftime("%d-%m-%Y %H:%M")
            data["last_modified"] = datetime.now().strftime("%d-%m-%Y %H:%M")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

        return dst

    # ==========================================================
    # RENAME PROJECT
    # ==========================================================

    def rename_project(self, old_name: str, new_name: str):
        new_name = new_name.strip()
        if not new_name:
            raise ValueError("New project name cannot be empty.")

        src = self.PROJECTS_DIR / old_name
        dst = self.PROJECTS_DIR / new_name

        if not src.exists():
            raise FileNotFoundError(f'Project "{old_name}" not found.')
        if dst.exists():
            raise FileExistsError(f'Project "{new_name}" already exists.')

        src.rename(dst)

        json_file = dst / "project.json"
        if json_file.exists():
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["name"] = new_name
            data["last_modified"] = datetime.now().strftime("%d-%m-%Y %H:%M")
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)

        return dst

    # ==========================================================
    # ARCHIVE PROJECT
    # ==========================================================

    def archive_project(self, project_name: str):
        data = self.load_project(project_name)
        if data is None:
            return False
        data["archived"] = True
        data["last_modified"] = datetime.now().strftime("%d-%m-%Y %H:%M")
        return self.update_project(project_name, data)

    def unarchive_project(self, project_name: str):
        data = self.load_project(project_name)
        if data is None:
            return False
        data["archived"] = False
        data["last_modified"] = datetime.now().strftime("%d-%m-%Y %H:%M")
        return self.update_project(project_name, data)

    # ==========================================================
    # FAVORITE PROJECT
    # ==========================================================

    def toggle_favorite(self, project_name: str):
        data = self.load_project(project_name)
        if data is None:
            return False
        data["favorite"] = not data.get("favorite", False)
        data["last_modified"] = datetime.now().strftime("%d-%m-%Y %H:%M")
        return self.update_project(project_name, data)

    # ==========================================================
    # DELETE PROJECT
    # ==========================================================

    def delete_project(self, project_name):
        project_path = self.PROJECTS_DIR / project_name
        if project_path.exists():
            shutil.rmtree(project_path)
            self._log.info("ProjectManager", f"Deleted project: {project_name}")
            return True
        return False

    # ==========================================================
    # LOAD SINGLE PROJECT
    # ==========================================================

    def load_project(self, project_name):
        json_file = self.PROJECTS_DIR / project_name / "project.json"
        if not json_file.exists():
            return None
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    # ==========================================================
    # LAST MODIFIED
    # ==========================================================

    def get_last_modified(self, project_name: str) -> str:
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
    # TOUCH MODIFIED
    # ==========================================================

    def touch_modified(self, project_name: str):
        data = self.load_project(project_name)
        if data is None:
            return False
        data["last_modified"] = datetime.now().strftime("%d-%m-%Y %H:%M")
        return self.update_project(project_name, data)

    # ==========================================================
    # UPDATE PROJECT
    # ==========================================================

    def update_project(self, project_name, data):
        json_file = self.PROJECTS_DIR / project_name / "project.json"
        if not json_file.exists():
            return False

        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(
                dir=json_file.parent, prefix=".project_", suffix=".tmp",
            )
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(data, tmp_file, indent=4)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
            os.replace(str(tmp_path), str(json_file))
            tmp_path = None
            return True
        except (OSError, json.JSONDecodeError):
            return False
        finally:
            if tmp_path is not None:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
