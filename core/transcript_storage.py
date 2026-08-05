# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
import json
from pathlib import Path


_PROJECTS_DIR = Path(__file__).resolve().parent.parent / "projects"


def _validated_project_path(project_name: str) -> Path:
    """Return the validated project path or raise ValueError on traversal."""
    from core.project_manager import resolve_project_dir
    return resolve_project_dir(_PROJECTS_DIR, project_name)


class TranscriptStorage:
    """Persist the transcript produced by the Voice stage for downstream stages."""

    def load(self, project_name: str) -> dict:
        """Load transcript text and timestamp segments, falling back across
        transcript.json and voice.json."""
        try:
            project_path = _validated_project_path(project_name)
        except ValueError:
            return {"text": "", "segments": []}
        transcript_file = project_path / "transcript.json"
        voice_file = project_path / "voice.json"

        text = ""
        segments = []

        if transcript_file.exists():
            try:
                with open(transcript_file, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
                text = data.get("text", "")
            except (OSError, json.JSONDecodeError):
                text = ""

        if voice_file.exists():
            try:
                with open(voice_file, "r", encoding="utf-8") as handle:
                    vdata = json.load(handle)
                if not text:
                    text = vdata.get("transcript", "")
                segments = vdata.get("segments", [])
            except (OSError, json.JSONDecodeError):
                pass

        return {"text": text, "segments": segments}

    def save(self, project_name: str, text: str) -> None:
        """Write transcript text in the format the Voice stage uses."""
        try:
            project_path = _validated_project_path(project_name)
        except ValueError:
            return
        project_path.mkdir(exist_ok=True)

        transcript_file = project_path / "transcript.json"
        data = {"text": text}

        try:
            with open(transcript_file, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=4)
        except OSError:
            pass
