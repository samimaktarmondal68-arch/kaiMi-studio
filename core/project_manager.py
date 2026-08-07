# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
import json
import os
import re
import shutil
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from core.workflow import build_initial_workflow_state
from core.logger import get_logger
from core.templates import get_template
from core.script_lengths import resolve_preset_bounds

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

_PROJECT_VERSION = 2


def _sanitize_project_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("Project name cannot be empty.")
    if _INVALID_CHARS.search(name):
        raise ValueError("Project name contains invalid characters.")
    if ".." in name:
        raise ValueError("Project name cannot contain '..'.")
    name = name.strip(". ")
    if not name:
        raise ValueError("Project name cannot be only dots or spaces.")
    if len(name) > 200:
        name = name[:200]
    return name


def _validate_project_path(project_path: Path, base_dir: Path) -> bool:
    try:
        resolved = project_path.resolve()
        base_resolved = base_dir.resolve()
        return str(resolved).startswith(str(base_resolved))
    except (OSError, ValueError):
        return False


def resolve_project_dir(base_dir: Path, project_name: str) -> Path:
    name = _sanitize_project_name(project_name)
    path = base_dir / name
    if not _validate_project_path(path, base_dir):
        raise ValueError("Invalid project path.")
    return path


def _build_smart_metadata(
    name: str, template_name: str, topic: str, platform: str, video_type: str,
    language: str, script_mode: str, script_min: int, script_max: int,
    duration_preset: str, research_sources: str, keywords: str,
) -> dict:
    preset_min, preset_max = resolve_preset_bounds(script_min, script_max)
    return {
        "name": name,
        "topic": topic,
        "template": template_name,
        "platform": platform,
        "video_type": video_type,
        "language": language,
        "script_mode": script_mode,
        "script_min": script_min,
        "script_max": script_max,
        "script_min_characters": preset_min,
        "script_max_characters": preset_max,
        "duration_preset": duration_preset,
        "research_sources": research_sources,
        "keywords": keywords,
        "project_version": _PROJECT_VERSION,
        "project_id": str(uuid.uuid4())[:8],
        "created": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "last_modified": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "last_opened": datetime.now().strftime("%d-%m-%Y %H:%M"),
        "status": "Script",
        "workflow_state": build_initial_workflow_state(),
        "current_version": 0,
        "total_versions": 0,
        "autosave_time": 7,
        "favorite": False,
        "archived": False,
        "thumbnail_color": "",
        "asset_count": 0,
        "storage_used": 0,
        "description": "",
    }


def _migrate_project_data(data: dict) -> dict:
    version = data.get("project_version", 1)
    if version >= _PROJECT_VERSION:
        return data

    if "project_id" not in data:
        data["project_id"] = str(uuid.uuid4())[:8]
    if "template" not in data:
        t = get_template("Custom")
        data["template"] = t.template_name if t else "Custom"
    if "last_opened" not in data:
        data["last_opened"] = data.get("last_modified", datetime.now().strftime("%d-%m-%Y %H:%M"))
    if "current_version" not in data:
        data["current_version"] = 0
    if "total_versions" not in data:
        data["total_versions"] = 0
    if "autosave_time" not in data:
        data["autosave_time"] = 7
    if "asset_count" not in data:
        data["asset_count"] = 0
    if "storage_used" not in data:
        data["storage_used"] = 0
    if "description" not in data:
        data["description"] = ""
    if "project_version" not in data:
        data["project_version"] = _PROJECT_VERSION

    data["project_version"] = _PROJECT_VERSION
    return data


class ProjectManager:

    PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"

    def __init__(self):
        self.PROJECTS_DIR.mkdir(exist_ok=True)
        self._log = get_logger()

    def create_project(self, name, topic, platform="Long Form", video_type="Educational",
                       language="English", script_mode="characters",
                       script_min=4500, script_max=5000,
                       research_sources="", keywords="",
                       duration_preset="", template_name="Custom",
                       description=""):
        name = _sanitize_project_name(name)
        if not name:
            raise ValueError("Project name cannot be empty.")
        if len(name) > 200:
            raise ValueError("Project name is too long (max 200 characters).")
        if name in _RESERVED_NAMES:
            raise ValueError(f'"{name}" is a reserved system name.')
        if name.startswith(".") or name.endswith("."):
            raise ValueError("Project name cannot start or end with a period.")

        project_path = self.PROJECTS_DIR / name
        if not _validate_project_path(project_path, self.PROJECTS_DIR):
            raise ValueError("Invalid project name (path traversal detected).")
        if project_path.exists():
            raise FileExistsError(f'Project "{name}" already exists.')

        try:
            project_path.mkdir()
            for folder in ["audio", "exports", "history", "images", "videos", "temp"]:
                (project_path / folder).mkdir()
        except OSError as e:
            raise OSError(f"Failed to create project directories: {e}")

        data = _build_smart_metadata(
            name=name, template_name=template_name, topic=topic,
            platform=platform, video_type=video_type, language=language,
            script_mode=script_mode, script_min=script_min,
            script_max=script_max, duration_preset=duration_preset,
            research_sources=research_sources, keywords=keywords,
        )
        data["description"] = description

        try:
            with open(project_path / "project.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except OSError as e:
            raise OSError(f"Failed to write project metadata: {e}")

        self._log.info("ProjectManager", f"Created project: {name} (template: {template_name})")
        return project_path

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
                data = _migrate_project_data(data)
                data["path"] = folder
                self._compute_asset_stats(data, folder)
                if not include_archived and data.get("archived", False):
                    continue
                projects.append(data)
        return projects

    def _compute_asset_stats(self, data: dict, project_path: Path) -> None:
        try:
            total_size = 0
            file_count = 0
            for entry in os.scandir(project_path):
                if entry.is_dir():
                    for root, _dirs, files in os.walk(entry.path):
                        for fname in files:
                            if fname != "project.json":
                                try:
                                    fpath = os.path.join(root, fname)
                                    total_size += os.path.getsize(fpath)
                                    file_count += 1
                                except OSError:
                                    pass
                elif entry.is_file() and entry.name != "project.json":
                    try:
                        total_size += entry.stat().st_size
                        file_count += 1
                    except OSError:
                        pass
            data["asset_count"] = file_count
            data["storage_used"] = total_size
        except OSError:
            pass

    def get_all_projects(self):
        return self.get_projects(include_archived=True)

    def get_project_count(self):
        return len(self.get_projects())

    def get_recent_projects(self, limit=5):
        projects = self.get_projects()
        projects.sort(
            key=lambda x: x.get("last_modified", x.get("created", "01-01-1970 00:00")),
            reverse=True,
        )
        return projects[:limit]

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
                p.get("template", ""),
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

    def duplicate_project(self, original_name: str, new_name: str):
        new_name = _sanitize_project_name(new_name)
        if not new_name:
            raise ValueError("New project name cannot be empty.")

        src = self.PROJECTS_DIR / original_name
        dst = self.PROJECTS_DIR / new_name

        if not _validate_project_path(src, self.PROJECTS_DIR):
            raise FileNotFoundError(f'Project "{original_name}" not found.')
        if not _validate_project_path(dst, self.PROJECTS_DIR):
            raise ValueError("Invalid project name (path traversal detected).")
        if not src.exists():
            raise FileNotFoundError(f'Project "{original_name}" not found.')
        if dst.exists():
            raise FileExistsError(f'Project "{new_name}" already exists.')

        try:
            shutil.copytree(src, dst)
        except OSError as e:
            raise OSError(f"Failed to copy project directory: {e}")

        json_file = dst / "project.json"
        if json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["name"] = new_name
                data["project_id"] = str(uuid.uuid4())[:8]
                data["created"] = datetime.now().strftime("%d-%m-%Y %H:%M")
                data["last_modified"] = datetime.now().strftime("%d-%m-%Y %H:%M")
                data["current_version"] = 0
                data["total_versions"] = 0
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
            except (OSError, json.JSONDecodeError) as e:
                raise OSError(f"Failed to update duplicated project metadata: {e}")

        return dst

    def rename_project(self, old_name: str, new_name: str):
        new_name = _sanitize_project_name(new_name)
        if not new_name:
            raise ValueError("New project name cannot be empty.")

        src = self.PROJECTS_DIR / old_name
        dst = self.PROJECTS_DIR / new_name

        if not _validate_project_path(src, self.PROJECTS_DIR):
            raise FileNotFoundError(f'Project "{old_name}" not found.')
        if not _validate_project_path(dst, self.PROJECTS_DIR):
            raise ValueError("Invalid project name (path traversal detected).")
        if not src.exists():
            raise FileNotFoundError(f'Project "{old_name}" not found.')
        if dst.exists():
            raise FileExistsError(f'Project "{new_name}" already exists.')

        try:
            src.rename(dst)
        except OSError as e:
            raise OSError(f"Failed to rename project directory: {e}")

        json_file = dst / "project.json"
        if json_file.exists():
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["name"] = new_name
                data["last_modified"] = datetime.now().strftime("%d-%m-%Y %H:%M")
                with open(json_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
            except (OSError, json.JSONDecodeError) as e:
                raise OSError(f"Failed to update renamed project metadata: {e}")

        return dst

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

    def toggle_favorite(self, project_name: str):
        data = self.load_project(project_name)
        if data is None:
            return False
        data["favorite"] = not data.get("favorite", False)
        data["last_modified"] = datetime.now().strftime("%d-%m-%Y %H:%M")
        return self.update_project(project_name, data)

    def delete_project(self, project_name):
        project_name = _sanitize_project_name(project_name)
        if not project_name:
            return False
        project_path = self.PROJECTS_DIR / project_name
        if not _validate_project_path(project_path, self.PROJECTS_DIR):
            return False
        if project_path.exists():
            try:
                shutil.rmtree(project_path)
            except OSError as e:
                self._log.error("ProjectManager", f"Failed to delete project: {e}")
                return False
            self._log.info("ProjectManager", f"Deleted project: {project_name}")
            return True
        return False

    def load_project(self, project_name):
        project_name = _sanitize_project_name(project_name)
        if not project_name:
            return None
        project_path = self.PROJECTS_DIR / project_name
        if not _validate_project_path(project_path, self.PROJECTS_DIR):
            return None
        json_file = project_path / "project.json"
        if not json_file.exists():
            return None
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data = _migrate_project_data(data)
            self._compute_asset_stats(data, project_path)
            return data
        except (OSError, json.JSONDecodeError):
            return None

    def mark_opened(self, project_name: str) -> None:
        data = self.load_project(project_name)
        if data is None:
            return
        data["last_opened"] = datetime.now().strftime("%d-%m-%Y %H:%M")
        self.update_project(project_name, data)

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

    def touch_modified(self, project_name: str):
        data = self.load_project(project_name)
        if data is None:
            return False
        data["last_modified"] = datetime.now().strftime("%d-%m-%Y %H:%M")
        return self.update_project(project_name, data)

    def update_project(self, project_name, data):
        project_name = _sanitize_project_name(project_name)
        if not project_name:
            return False
        project_path = self.PROJECTS_DIR / project_name
        if not _validate_project_path(project_path, self.PROJECTS_DIR):
            return False
        json_file = project_path / "project.json"
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

    def scan_assets(self, project_name: str) -> list[dict]:
        project_name = _sanitize_project_name(project_name)
        if not project_name:
            return []
        project_path = self.PROJECTS_DIR / project_name
        if not _validate_project_path(project_path, self.PROJECTS_DIR):
            return []
        if not project_path.exists():
            return []

        assets = []
        try:
            for f in sorted(project_path.rglob("*"), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True):
                if not f.is_file() or f.name == "project.json":
                    continue
                rel = f.relative_to(project_path)
                parent = rel.parent
                assets.append({
                    "name": f.name,
                    "path": str(f),
                    "relative_path": str(rel),
                    "folder": str(parent) if str(parent) != "." else "root",
                    "type": f.suffix.lower().lstrip(".") or "unknown",
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%d-%m-%Y %H:%M"),
                })
        except OSError:
            pass
        return assets