from __future__ import annotations

import re
import time

from core.logger import get_logger
from operators.script.models import (
    ScriptGenerationError,
    ScriptRequest,
    ScriptValidationError,
)
from operators.script.prompt_builder import ScriptPromptBuilder
from providers.exceptions import ProviderError, ProviderNotConfiguredError
from providers.models import GenerationRequest
from providers.provider_manager import ProviderManager, get_provider_manager


class ProviderConfigurationError(RuntimeError):
    pass


SCRIPT_TARGET_MIN = 4500
SCRIPT_TARGET_MAX = 4999
MAX_CONTINUATION_ATTEMPTS = 4

_FORBIDDEN_LABELS = {
    "hook",
    "body",
    "ending",
    "pause",
    "intro",
    "introduction",
    "outro",
    "conclusion",
}


class ScriptOperator:

    def __init__(
        self,
        prompt_builder: ScriptPromptBuilder | None = None,
        provider_manager: ProviderManager | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder or ScriptPromptBuilder()
        # Store an injected manager (used in tests); None means create fresh per call.
        self._provider_manager = provider_manager
        self._log = get_logger()

    def _get_provider_manager(self) -> ProviderManager:
        """Return the injected ProviderManager or a fresh one.

        A fresh instance is created on every generation call so that any
        provider change saved via Settings takes effect immediately without
        requiring an application restart.
        """
        return self._provider_manager or get_provider_manager()

    def execute(self, request: ScriptRequest) -> str:
        self._log.info("ScriptOperator", f"Starting script generation: topic={request.topic}")
        t0 = time.perf_counter()
        self._validate_request(request)

        system_prompt, user_prompt = self._prompt_builder.build(request)

        result = self._generate(system_prompt, user_prompt)
        result = self._enforce_script_requirements(result, system_prompt)
        elapsed = time.perf_counter() - t0
        self._log.info("ScriptOperator", f"Script generated in {elapsed:.2f}s ({len(result)} chars)")
        return result

    def get_prompt_preview(self, request: ScriptRequest) -> str:
        self._validate_request(request)
        _, user_prompt = self._prompt_builder.build(request)
        return user_prompt

    def _validate_request(self, request: ScriptRequest) -> None:
        if not isinstance(request, ScriptRequest):
            raise ScriptValidationError("Expected a ScriptRequest instance.")
        topic = (request.topic or "").strip()
        if not topic:
            raise ScriptValidationError("Script topic must not be empty.")

    def _generate(self, system_prompt: str, user_prompt: str) -> str:
        try:
            generation_request = GenerationRequest(
                prompt=user_prompt,
                system_prompt=system_prompt,
            )
            response = self._get_provider_manager().generate(generation_request)
        except ProviderNotConfiguredError as exc:
            raise ProviderConfigurationError(str(exc)) from exc
        except ProviderError as exc:
            raise ScriptGenerationError(str(exc)) from exc
        except Exception as exc:
            raise ScriptGenerationError(f"Script generation failed: {exc}") from exc

        if not response.text or not response.text.strip():
            raise ScriptGenerationError("Provider returned empty content.")

        return self._format_script_text(response.text)

    def _enforce_script_requirements(self, script: str, system_prompt: str) -> str:
        """Return a formatted script within the required character range."""
        result = self._fit_to_maximum(self._format_script_text(script))

        attempts = 0
        while len(result) < SCRIPT_TARGET_MIN and attempts < MAX_CONTINUATION_ATTEMPTS:
            attempts += 1
            continuation = self._generate_continuation(result, system_prompt)
            result = self._merge_continuation(result, continuation)
            result = self._fit_to_maximum(result)

        if len(result) < SCRIPT_TARGET_MIN:
            raise ScriptGenerationError(
                "Generated script did not reach the 4500 character minimum."
            )

        if len(result) > SCRIPT_TARGET_MAX:
            result = self._fit_to_maximum(result)

        return result

    def _generate_continuation(self, script: str, system_prompt: str) -> str:
        remaining_min = SCRIPT_TARGET_MIN - len(script)
        remaining_max = SCRIPT_TARGET_MAX - len(script)
        prompt = (
            "Continue this YouTube documentary narration seamlessly from the exact point it stops.\n\n"
            "Rules:\n"
            f"- Add between {remaining_min} and {remaining_max} characters.\n"
            "- Continue the same thought naturally; do not restart the script.\n"
            "- Do not repeat previous paragraphs.\n"
            "- Do not add headings, labels, stage directions, SSML, pause markers, or markdown.\n"
            "- Use natural paragraphs with one blank line between paragraphs.\n"
            "- End with a strong closing line if the script feels complete.\n\n"
            "Existing script ending:\n"
            f"{script[-1200:]}\n\n"
            "Continuation only:"
        )
        return self._generate(system_prompt, prompt)

    def _merge_continuation(self, script: str, continuation: str) -> str:
        continuation = self._format_script_text(continuation)
        if not continuation:
            return script
        return self._format_script_text(f"{script}\n\n{continuation}")

    def _fit_to_maximum(self, script: str) -> str:
        script = self._format_script_text(script)
        if len(script) <= SCRIPT_TARGET_MAX:
            return script

        boundary = self._find_clean_cut(script)
        if boundary:
            return self._format_script_text(script[:boundary])

        return self._format_script_text(script[:SCRIPT_TARGET_MAX].rstrip())

    def _find_clean_cut(self, script: str) -> int:
        """Find a natural cut point that keeps the script inside the target range."""
        paragraph_cut = script.rfind("\n\n", SCRIPT_TARGET_MIN, SCRIPT_TARGET_MAX + 1)
        if paragraph_cut >= SCRIPT_TARGET_MIN:
            return paragraph_cut

        sentence_matches = list(re.finditer(r"[.!?][\"')\]]?(?=\s)", script[:SCRIPT_TARGET_MAX + 1]))
        for match in reversed(sentence_matches):
            cut = match.end()
            if cut >= SCRIPT_TARGET_MIN:
                return cut

        return 0

    def _format_script_text(self, text: str) -> str:
        """Normalize generated narration into clean voiceover paragraphs."""
        cleaned_lines = []
        for raw_line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                cleaned_lines.append("")
                continue
            if self._is_forbidden_line(line):
                continue
            line = re.sub(r"\((?:pause|breath|beat|silence)\)", "", line, flags=re.IGNORECASE)
            line = re.sub(r"\[(?:pause|breath|beat|silence)\]", "", line, flags=re.IGNORECASE)
            line = line.strip()
            if line:
                cleaned_lines.append(line)

        paragraphs = self._build_paragraphs(cleaned_lines)
        return "\n\n".join(paragraphs).strip()

    def _is_forbidden_line(self, line: str) -> bool:
        stripped = line.strip()
        if re.fullmatch(r"(?:\.{3,}|-|_|\*)+", stripped):
            return True
        normalized = stripped.strip("#:.-_* ").lower()
        if normalized in _FORBIDDEN_LABELS:
            return True
        return False

    def _build_paragraphs(self, lines: list[str]) -> list[str]:
        raw_paragraphs: list[str] = []
        current: list[str] = []

        for line in lines:
            if not line:
                if current:
                    raw_paragraphs.append(" ".join(current).strip())
                    current = []
                continue
            current.append(line)

        if current:
            raw_paragraphs.append(" ".join(current).strip())

        paragraphs: list[str] = []
        for paragraph in raw_paragraphs:
            sentences = self._split_sentences(paragraph)
            if len(sentences) <= 5:
                paragraphs.append(" ".join(sentences).strip())
                continue

            for index in range(0, len(sentences), 4):
                chunk = sentences[index:index + 4]
                if chunk:
                    paragraphs.append(" ".join(chunk).strip())

        return [paragraph for paragraph in paragraphs if paragraph]

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [part.strip() for part in parts if part.strip()]
