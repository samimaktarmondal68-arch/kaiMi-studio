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
        batch_size: int | None = None,
    ) -> list[dict]:
        """Run the complete production pipeline: build → generate → parse → validate.

        Every stage is reported through ``progress_callback(stage, message,
        fraction)`` so the UI can show honest stage-based progress (never a
        fabricated percentage). Cooperative cancellation is checked between
        stages via ``cancel_event`` (a ``threading.Event``); an in-flight
        provider request itself is blocking and finishes first.

        Long transcripts (more scenes than the resolved batch size) are split
        into ordered scene batches and generated through the same provider
        abstraction (RC-7.3). Each batch is validated for exact coverage — one
        prompt per scene with the absolute scene numbers and exact timestamps —
        and a failing batch is retried alone under the bounded retry policy;
        successful batches are never regenerated. Results recombine losslessly
        in transcript order, and the existing RC-7 coverage validation runs
        against the COMPLETE aggregate before anything is returned.

        Short transcripts keep the legacy single-request path unchanged.

        ``batch_size`` overrides the default derived from the provider's output
        token budget (tests and tuning); when ``None`` it is computed from
        ``GenerationRequest.max_tokens``.

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

        timestamps = request.timestamps or []
        n_scenes = len(timestamps)
        size = self._resolve_batch_size(batch_size, n_scenes)

        if n_scenes <= size:
            prompts, attempts = self._generate_single(
                request, progress_callback, cancel_event, max_retries
            )
        else:
            prompts, attempts = self._generate_batched(
                request, size, progress_callback, cancel_event, max_retries
            )

        self._log.info(
            "ImagePromptOperator",
            f"Image prompts generated in {time.perf_counter() - t0:.2f}s "
            f"({len(prompts)} prompts, {attempts} attempt(s), {n_scenes} scenes, "
            f"batch size {size})",
        )
        return prompts

    def _generate_single(self, request, progress_callback, cancel_event, max_retries):
        """Legacy single-request path: build once, run the bounded retry loop.

        Used when the transcript is short enough for one provider call. The
        behavior — including the stage sequence and the retry contract — is
        preserved exactly so existing callers and tests see no change.
        """
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
            return prompts, attempts

    def _generate_batched(
        self, request, batch_size, progress_callback, cancel_event, max_retries
    ):
        """Generate a long transcript in scene batches and combine the results.

        Splits the transcript scenes into ordered batches and generates each
        batch through the same provider abstraction (RC-7.3). Every batch must
        cover exactly its own scenes with the absolute scene numbers and exact
        timestamps before it is aggregated; a failing batch is retried alone
        (bounded) without regenerating completed batches. Only after the
        COMPLETE collection passes the existing RC-7 coverage validation is it
        returned for persistence — a partial generation is never presented as
        complete.
        """
        timestamps = request.timestamps or []
        n_scenes = len(timestamps)
        batches = [
            timestamps[i : i + batch_size] for i in range(0, n_scenes, batch_size)
        ]
        n_batches = len(batches)
        self._report(progress_callback, "selecting_provider", 0.15)

        aggregated: list[dict] = []
        total_attempts = 0
        #: Visual identity pins fed to later batches: the first generated
        #: prompt (project style lock) plus the previous batch's last prompt
        #: (continuity across the batch boundary).
        anchor: list[str] = []

        for index, batch_ts in enumerate(batches):
            self._check_cancel(cancel_event)
            start_scene = index * batch_size + 1
            end_scene = start_scene + len(batch_ts) - 1
            label = f"{index + 1}/{n_batches}"
            fraction = 0.2 + (index / n_batches) * 0.65

            batch_prompts, batch_attempts = self._generate_batch(
                request=request,
                batch_ts=batch_ts,
                start_scene=start_scene,
                end_scene=end_scene,
                label=label,
                total_scenes=n_scenes,
                anchor=anchor,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
                max_retries=max_retries,
                fraction=fraction,
            )
            aggregated.extend(batch_prompts)
            total_attempts += batch_attempts
            anchor = [
                aggregated[0]["full_image_prompt"],
                aggregated[-1]["full_image_prompt"],
            ]

        self._report(progress_callback, "validating", 0.92)
        # RC-7: run the existing coverage validation on the COMPLETE aggregate.
        self._validate_prompt_count(request, aggregated)
        self._validate_aggregate(request, aggregated)
        return aggregated, total_attempts

    def _generate_batch(
        self,
        request,
        batch_ts,
        start_scene,
        end_scene,
        label,
        total_scenes,
        anchor,
        progress_callback,
        cancel_event,
        max_retries,
        fraction,
    ):
        """Generate one scene batch under the bounded per-batch retry policy.

        The batch prompt reuses the full KaiMi style lock and output contract
        (``ImagePromptBuilder.build_batch``) scoped to the batch scenes, with
        absolute scene numbers so results recombine losslessly. A response that
        fails to parse, or that does not cover exactly the batch's scenes with
        the exact scene numbers and timestamps, is retried at most
        ``max_retries`` times with a format reminder; the batch is never
        accepted partially. Provider-level failures propagate immediately (the
        same policy as the single-shot path — retries cover malformed or
        incomplete output only).
        """
        system_prompt, user_prompt = self._prompt_builder.build_batch(
            request,
            batch_ts,
            start_scene,
            end_scene,
            previous_prompts=anchor,
        )
        reminder_appended = False
        attempts = 0
        while True:
            attempts += 1
            self._check_cancel(cancel_event)
            self._report(
                progress_callback,
                "generating",
                fraction,
                message=(
                    f"Generating image prompts — Batch {label} "
                    f"(scenes {start_scene}–{end_scene} of {total_scenes})"
                ),
            )
            raw = self._generate(system_prompt, user_prompt)
            self._check_cancel(cancel_event)

            self._report(
                progress_callback,
                "parsing",
                min(0.9, fraction + 0.03),
                message=f"Parsing AI response — Batch {label}",
            )
            try:
                prompts = self._parser.parse(raw)
                self._validate_batch(prompts, batch_ts, start_scene)
            except ImagePromptParseError as exc:
                if attempts <= max_retries:
                    if not reminder_appended:
                        user_prompt = (
                            user_prompt
                            + "\n\n"
                            + ImagePromptBuilder.retry_format_reminder()
                        )
                        reminder_appended = True
                    self._report(
                        progress_callback,
                        "retrying",
                        fraction,
                        message=f"Retrying batch {label} — {exc}",
                    )
                    continue
                raise ImagePromptGenerationError(
                    f"Batch {label} (scenes {start_scene}–{end_scene}) could not "
                    f"be generated after {attempts} attempt(s). Details: {exc}"
                ) from exc
            return prompts, attempts

    @staticmethod
    def _validate_batch(
        prompts: list[dict], batch_ts: list[dict], start_scene: int
    ) -> None:
        """Require a batch response to cover exactly its own scenes.

        Every batch must return exactly one prompt per supplied scene, with the
        absolute scene numbers and the exact timestamps of that batch. Anything
        less — truncation, invented timestamps, batch-local numbering — is a
        batch failure that triggers the bounded retry, never a partial accept
        (RC-7.3).
        """
        expected_count = len(batch_ts)
        if len(prompts) != expected_count:
            raise ImagePromptParseError(
                f"The batch returned {len(prompts)} prompts for "
                f"{expected_count} scenes."
            )
        expected_numbers = list(range(start_scene, start_scene + expected_count))
        actual_numbers = [prompt["scene_number"] for prompt in prompts]
        if actual_numbers != expected_numbers:
            raise ImagePromptParseError(
                f"The batch returned scene numbers {actual_numbers}; "
                f"expected {expected_numbers}."
            )
        expected_times = [
            ImagePromptBuilder.format_scene_time(segment) for segment in batch_ts
        ]
        actual_times = [prompt["timestamp"] for prompt in prompts]
        if actual_times != expected_times:
            raise ImagePromptParseError(
                f"The batch returned timestamps {actual_times}; "
                f"expected {expected_times}."
            )

    @staticmethod
    def _validate_aggregate(request: ImagePromptRequest, prompts: list[dict]) -> None:
        """Verify the recombined batch collection is complete and exact.

        After batching, the aggregate must contain exactly one prompt per
        source scene, with unique scene numbers 1..N and timestamps matching
        the transcript order — the same contract the parser enforces for a
        single-shot response (RC-7.3).
        """
        timestamps = request.timestamps or []
        expected_numbers = list(range(1, len(timestamps) + 1))
        actual_numbers = [prompt["scene_number"] for prompt in prompts]
        if actual_numbers != expected_numbers:
            raise ImagePromptGenerationError(
                "Aggregated prompts are missing or duplicate scene numbers."
            )
        expected_times = [
            ImagePromptBuilder.format_scene_time(segment) for segment in timestamps
        ]
        actual_times = [prompt["timestamp"] for prompt in prompts]
        if actual_times != expected_times:
            raise ImagePromptGenerationError(
                "Aggregated prompts do not preserve the transcript "
                "order/timestamps."
            )

    @staticmethod
    def _resolve_batch_size(requested: int | None, n_scenes: int) -> int:
        """Resolve the scene batch size for long transcripts.

        An explicit ``batch_size`` (tests, tuning) wins. Otherwise the size is
        derived from the provider's standard output-token budget: a complete
        scene prompt (JSON object, narration quote, style boilerplate) costs
        roughly 800 output tokens, so a batch sized ``max_tokens // 800`` stays
        comfortably within the response budget. With the default 8192-token
        budget this yields 10 scenes per batch (RC-7.3).
        """
        if requested is not None and requested > 0:
            return int(requested)
        budget = int(GenerationRequest.max_tokens)
        return max(1, budget // 800)


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
    def _report(
        progress_callback, stage: str, fraction: float, message: str | None = None
    ) -> None:
        """Forward a stage update when the caller supplied a callback.

        ``message`` overrides the default stage label — used by batched
        generation, where the default label would hide batch progress
        (RC-7.3).
        """
        if progress_callback is not None:
            progress_callback(
                stage, message or STAGE_MESSAGES.get(stage, stage), fraction
            )

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