from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class ResearchRequest:
    """Structured input for building a research prompt."""

    topic: str
    keywords: str | Iterable[str] = ""
    goal: str = ""
    sources: str | Iterable[str] = ""
    research_objectives: str | Iterable[str] = ""
    required_output_format: str = ""
    audience: str = ""
    language: str = "English"


class ResearchPromptBuilder:
    """Builds deterministic research prompts from structured request data."""

    def build(self, request: ResearchRequest) -> str:
        topic = self._normalize_text(request.topic)
        keywords = self._normalize_list(request.keywords)
        goal = self._normalize_text(request.goal)
        sources = self._normalize_list(request.sources)
        objectives = self._normalize_list(request.research_objectives)
        output_format = self._normalize_text(request.required_output_format)
        audience = self._normalize_text(request.audience)
        language = self._normalize_text(request.language) or "English"

        return (
            "Research Request\n\n"
            f"Topic:\n{topic}\n\n"
            f"Keywords:\n{keywords}\n\n"
            f"Goal:\n{goal}\n\n"
            f"Sources:\n{sources}\n\n"
            f"Research Objectives:\n{objectives}\n\n"
            f"Required Output Format:\n{output_format}\n\n"
            f"Audience:\n{audience}\n\n"
            f"Language:\n{language}"
        )

    @staticmethod
    def _normalize_text(value: object) -> str:
        if value is None:
            return "Not provided"
        text = str(value).strip()
        return text if text else "Not provided"

    @staticmethod
    def _normalize_list(value: str | Iterable[str]) -> str:
        if value is None:
            return "Not provided"

        if isinstance(value, str):
            normalized = value.strip()
            return normalized if normalized else "Not provided"

        items = [str(item).strip() for item in value if str(item).strip()]
        if not items:
            return "Not provided"
        return "\n".join(f"- {item}" for item in items)