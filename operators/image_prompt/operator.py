from __future__ import annotations

import time

from core.logger import get_logger
from core.task_manager import TaskCancelledError
from operators.image_prompt.models import (
    ImagePromptGenerationError,
    ImagePromptParseError,
    ImagePromptRequest,
    ImagePromptValidationError,
)
from operators.image_prompt.parser import ImagePromptParser
from operators.image_prompt.prompt_builder import ImagePromptBuilder
from providers.exceptions import ProviderError, ProviderNotConfiguredError
from providers.models import GenerationRequest
from providers.provider_manager import ProviderManager, get_provider_manager


class ProviderConfigurationError(RuntimeError):
    pass


#: Human-readable labels for the RC-7 pipeline stages. Stage keys are stable
#: identifiers used by the UI's progress display and failure diagnostics.
STAGE_MESSAGES = {
    "validating_source": "Validating source data",
    "selecting_provider": "Selecting AI provider",
    "generating": "Generating image prompts",
    "parsing": "Parsing AI response",
    "validating": "Validating scenes",
    "retrying": "Retrying generation",
}


class ImagePromptOperator:

    def __init__(
        self,
        prompt_builder: ImagePromptBuilder | None = None,
        provider_manager: ProviderManager | None = None,
        parser: ImagePromptParser | None = None,
    ) -> None:
        self._prompt_builder = prompt_builder or ImagePromptBuilder()
        # Store an injected manager (used in tests); None means create fresh per call.
        self._provider_manager = provider_manager
        self._parser = parser or ImagePromptParser()
        self._log = get_logger()

    def _get_provider_manager(self) -> ProviderManager:
        """Return the injected ProviderManager or a fresh one.

        A fresh instance is created on every generation call so that any
        provider change saved via Settings takes effect immediately without
        requiring an application restart.
        """
        return self._provider_manager or get_provider_manager()

    def generate_prompts(
        self,
        request: ImagePromptRequest,
        progress_callback=None,
        cancel_event=None,
        max_retries: int = 1,
    ) -> list[dict]:
        """Run the complete production pipeline: build → generate → parse → validate.

        Every stage is reported through ``progress_callback(stage, message,
        fraction)`` so the UI can show honest stage-based progress (never a
        fabricated percentage). Cooperative cancellation is checked between
        stages via ``cancel_event`` (a ``threading.Event``); an in-flight
        provider request itself is blocking and finishes first.

        Malformed AI output triggers a *bounded* retry (at most ``max_retries``
        attempts, default 1) with a format reminder. If the retry also fails,
        an ``ImagePromptGenerationError`` is raised with diagnostics — malformed
        output is never silently displayed.

        Returns:
            The validated list of prompt dicts, ready for persistence.
        """
        t0 = time.perf_counter()
        self._report(progress_callback, "validating_source", 0.05)
        self._validate_request(request)
        self._check_cancel(cancel_event)

        system_prompt, user_prompt = self._prompt_builder.build(request)
        self._report(progress_callback, "selecting_provider", 0.15)

        reminder_appended = False
        attempts = 0
        while True:
            attempts += 1
            self._check_cancel(cancel_event)
            self._report(progress_callback, "generating", 0.4)
            raw = self._generate(system_prompt, user_prompt)
            self._check_cancel(cancel_event)

            self._report(progress_callback, "parsing", 0.7)
            try:
                prompts = self._parser.parse(raw)
            except ImagePromptParseError as exc:
                if attempts <= max_retries:
                    if not reminder_appended:
                        # Restate the output contract once; repeated appends
                        # would bloat the prompt and waste tokens.
                        user_prompt = (
                            user_prompt
                            + "\n\n"
                            + ImagePromptBuilder.retry_format_reminder()
                        )
                        reminder_appended = True
                    self._report(progress_callback, "retrying", 0.4)
                    continue
                raise ImagePromptGenerationError(
                    "Generation completed but the provider returned invalid "
                    f"prompt data. Details: {exc}"
                ) from exc

            self._report(progress_callback, "validating", 0.9)
            self._validate_prompt_count(request, prompts)
            self._log.info(
                "ImagePromptOperator",
                f"Image prompts generated in {time.perf_counter() - t0:.2f}s "
                f"({len(prompts)} prompts, {attempts} attempt(s))",
            )
            return prompts

    def execute(self, request: ImagePromptRequest) -> str:
        """Return the raw provider text (backward-compatible low-level API)."""
        self._log.info("ImagePromptOperator", f"Starting image prompt generation")
        t0 = time.perf_counter()
        self._validate_request(request)

        system_prompt, user_prompt = self._prompt_builder.build(request)

        result = self._generate(system_prompt, user_prompt)
        elapsed = time.perf_counter() - t0
        self._log.info("ImagePromptOperator", f"Image prompts generated in {elapsed:.2f}s ({len(result)} chars)")
        return result

    def get_prompt_preview(self, request: ImagePromptRequest) -> str:
        self._validate_request(request)
        _, user_prompt = self._prompt_builder.build(request)
        return user_prompt

    def _validate_request(self, request: ImagePromptRequest) -> None:
        if not isinstance(request, ImagePromptRequest):
            raise ImagePromptValidationError("Expected an ImagePromptRequest instance.")
        script_text = (request.script_text or "").strip()
        if not script_text:
            raise ImagePromptValidationError("Script text must not be empty.")

    @staticmethod
    def _check_cancel(cancel_event) -> None:
        """Raise TaskCancelledError when a cooperative cancel was requested."""
        if cancel_event is not None and cancel_event.is_set():
            raise TaskCancelledError("Image prompt generation cancelled.")

    @staticmethod
    def _report(progress_callback, stage: str, fraction: float) -> None:
        """Forward a stage update when the caller supplied a callback."""
        if progress_callback is not None:
            progress_callback(stage, STAGE_MESSAGES.get(stage, stage), fraction)

    @staticmethod
    def _validate_prompt_count(request: ImagePromptRequest, prompts: list[dict]) -> None:
        """Sanity-check the prompt count against the transcript scene count.

        The generation contract is one prompt per transcript scene. A wild
        mismatch (duplicated scenes or skipped transcript sections) is a
        validation failure, never silently accepted (RC-7). Projects without
        timestamp data skip the count check.
        """
        timestamps = request.timestamps
        if not timestamps:
            return
        n_scenes = len(timestamps)
        n_prompts = len(prompts)
        if n_prompts == 0:
            raise ImagePromptGenerationError(
                "The provider returned no prompts for the transcript scenes."
            )
        if n_prompts > n_scenes * 2:
            raise ImagePromptGenerationError(
                f"The provider returned {n_prompts} prompts for {n_scenes} "
                "transcript scenes — scenes appear to be duplicated."
            )
        if n_prompts < max(1, n_scenes // 2):
            raise ImagePromptGenerationError(
                f"The provider returned only {n_prompts} prompts for {n_scenes} "
                "transcript scenes — transcript coverage is incomplete."
            )

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
            raise ImagePromptGenerationError(str(exc)) from exc
        except Exception as exc:
            raise ImagePromptGenerationError(f"Image prompt generation failed: {exc}") from exc

        if not response.text or not response.text.strip():
            raise ImagePromptGenerationError("Provider returned empty content.")

        return response.text.strip()