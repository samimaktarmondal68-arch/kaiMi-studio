from __future__ import annotations

import json
from pathlib import Path

from core.project_manager import ProjectManager, _validate_project_path, _sanitize_project_name
from core.logger import get_logger


class ExportService:

    FORMATS = ["txt"]

    def __init__(self, project_manager: ProjectManager | None = None):
        self.project_manager = project_manager or ProjectManager()
        self._log = get_logger()

    def _load_stage_data(self, project_name, stage):
        project_path = self.project_manager.PROJECTS_DIR / project_name
        if stage == "Script":
            fp = project_path / "script.json"
        elif stage == "Voice":
            fp = project_path / "voice.json"
        elif stage == "Image Prompts":
            fp = project_path / "image_prompts.json"
        else:
            return {}
        if not fp.exists():
            return {}
        try:
            with open(fp, "r", encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def export_project(self, project: dict, fmt: str = "txt") -> Path:
        project_name = _sanitize_project_name(project.get("name") or "project")
        if not _validate_project_path(
            self.project_manager.PROJECTS_DIR / project_name,
            self.project_manager.PROJECTS_DIR,
        ):
            raise ValueError("Invalid project name for export.")
        self._log.info("Export", f"Exporting '{project_name}' as {fmt}")
        export_root = self.project_manager.PROJECTS_DIR / project_name / "exports" / project_name
        try:
            export_root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise OSError(f"Failed to create export directory: {e}")

        script_data = self._load_stage_data(project_name, "Script")
        voice_data = self._load_stage_data(project_name, "Voice")
        image_prompt_data = self._load_stage_data(project_name, "Image Prompts")

        all_data = {
            "project": {k: v for k, v in project.items() if k != "path"},
            "script": script_data,
            "voice": voice_data,
            "image_prompts": image_prompt_data,
        }

        if fmt == "txt":
            return self._export_txt(export_root, all_data, project_name)
        else:
            return self._export_txt(export_root, all_data, project_name)

    def _export_txt(self, export_root, data, name):
        lines = []
        proj = data.get("project", {})
        lines.append(f"Project: {proj.get('name', '')}")
        lines.append(f"Topic: {proj.get('topic', '')}")
        lines.append(f"Platform: {proj.get('platform', '')}")
        lines.append(f"Language: {proj.get('language', '')}")
        lines.append("")

        script = data.get("script", {})
        if script.get("script_output"):
            lines.append("=" * 60)
            lines.append("SCRIPT")
            lines.append("=" * 60)
            lines.append(script["script_output"])
            lines.append("")

        voice = data.get("voice", {})
        if voice.get("transcript"):
            lines.append("=" * 60)
            lines.append("TRANSCRIPT")
            lines.append("=" * 60)
            lines.append(voice["transcript"])
            lines.append("")

        prompts = data.get("image_prompts", {})
        prompt_list = prompts.get("prompts", [])
        if prompt_list:
            lines.append("")
            lines.append(self.build_image_prompts_txt(prompt_list))

        out = export_root / f"{name}.txt"
        try:
            out.write_text("\n".join(lines), encoding="utf-8")
        except OSError as e:
            raise OSError(f"Failed to write export file: {e}")
        return out

    @staticmethod
    def build_image_prompts_txt(prompts: list[dict]) -> str:
        """Render image prompts in the Google Flow TXT queue format (RC-7.1).

        Google Flow's "one prompt per line" queue treats every physical line
        as a separate prompt, so each scene occupies EXACTLY one physical
        line:

            [MM:SS] <full image prompt>

        The timestamp opens the same line, the full generated prompt follows
        verbatim, and no other metadata is serialized: no "Scene N" headers,
        no "Title:" lines, no separate timestamp lines, no blank lines, no
        numbering. Scene order and timestamps are preserved exactly and the
        prompt text is never shortened or rewritten.

        Any newline characters inside a prompt are collapsed into spaces so
        a single prompt can never wrap across physical lines (the prompt
        builder already forbids line breaks inside prompts). Both the Image
        Prompts page export (user-chosen destination) and ``export_stage``
        render through this single definition so the on-disk format can
        never drift between entry points (RC-7.1).
        """
        lines = []
        for prompt in prompts:
            ts = prompt.get("timestamp", "")
            full = (prompt.get("full_image_prompt") or "").strip()
            # One physical line per prompt: embedded line breaks would make
            # Google Flow read a single scene as several queue items.
            full = full.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
            if ts:
                lines.append(f"[{ts}] {full}")
            else:
                lines.append(full)
        return "\n".join(lines)

    def export_stage(self, project_name: str, stage: str, fmt: str = "txt") -> Path | None:
        project_name = _sanitize_project_name(project_name)
        if not project_name:
            return None
        if not _validate_project_path(
            self.project_manager.PROJECTS_DIR / project_name,
            self.project_manager.PROJECTS_DIR,
        ):
            return None
        data = self._load_stage_data(project_name, stage)
        if not data:
            return None

        export_root = self.project_manager.PROJECTS_DIR / project_name / "exports" / project_name
        try:
            export_root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._log.error("Export", f"Failed to create export directory: {e}")
            return None

        if stage == "Image Prompts":
            filename = "image_prompts.txt"
            out = export_root / filename
            text = self.build_image_prompts_txt(data.get("prompts", []))
            try:
                out.write_text(text, encoding="utf-8")
            except OSError as e:
                self._log.error("Export", f"Failed to write export file: {e}")
                return None
            return out
        else:
            return None