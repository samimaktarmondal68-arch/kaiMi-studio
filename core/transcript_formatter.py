# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Production transcript formatter for the KaiMi Studio Voice stage.

Converts raw Whisper segment dicts into the canonical block structure:

    [M:SS] narration line

    [M:SS] narration line

One blank line separates every block. Minutes are never zero-padded;
seconds are zero-padded to two digits. No scene numbers, no labels,
no markup of any kind — plain text only.

Each Whisper segment maps to exactly one transcript block. Scene
segmentation follows Whisper's own timing rather than silence-gap
paragraph grouping, which preserves the natural pacing and rhythm of
the narration without compression.
"""

from __future__ import annotations

import re

#: Matches consecutive duplicate words produced by Whisper (e.g. "the the").
_DUPLICATE_WORD = re.compile(r"\b(\w+)(\s+\1\b)+", re.IGNORECASE)

#: Capitalises a lowercase letter that immediately follows sentence-ending
#: punctuation and whitespace within a single segment's text.
_INTRA_SENTENCE_CAP = re.compile(r"([.!?]\s+)([a-z])")

#: Characters that end a sentence and trigger capitalisation on the next block.
_SENTENCE_END = frozenset(".!?")


class TranscriptFormatter:
    """Convert Whisper segment dicts to the canonical [M:SS] block transcript.

    Usage::

        formatter = TranscriptFormatter()
        text = formatter.format(segments)

    Each ``segments`` entry must be a dict with at least:
    - ``start``: float seconds from audio start
    - ``text``: raw segment text (whitespace already collapsed is preferred)
    """

    def format(self, segments: list[dict]) -> str:
        """Return the formatted transcript string.

        Args:
            segments: List of dicts with at minimum ``start`` (float) and
                ``text`` (str) keys, as returned by faster-whisper after an
                initial whitespace-collapse pass.

        Returns:
            Plain-text string where each segment is rendered as::

                [M:SS] narration text

            Blocks are separated by exactly one blank line. An empty segment
            list returns an empty string.
        """
        blocks: list[str] = []
        prev_text: str | None = None

        for seg in segments:
            text = self._clean_text(seg.get("text", ""), prev_text)
            if not text:
                continue
            try:
                start = float(seg.get("start") or 0.0)
            except (TypeError, ValueError):
                start = 0.0
            blocks.append(f"{self._format_timestamp(start)} {text}")
            prev_text = text

        return "\n\n".join(blocks).strip()

    @staticmethod
    def _format_timestamp(start_seconds: float) -> str:
        """Format seconds as [M:SS] — minutes are not zero-padded."""
        total = int(start_seconds)
        return f"[{total // 60}:{total % 60:02d}]"

    @staticmethod
    def _clean_text(text: str, prev_text: str | None) -> str:
        """Apply light cleanup to a single segment's text.

        Only corrects: collapsed whitespace, duplicate-word Whisper artifacts,
        and sentence-boundary capitalisation. The narration is never rewritten
        or shortened.

        Args:
            text: Raw segment text to clean.
            prev_text: The cleaned text of the immediately preceding block, or
                None for the first block. Used to decide whether this block
                opens a new sentence.
        """
        text = " ".join(str(text).split())
        if not text:
            return text

        # Remove consecutive duplicate words (common Whisper hallucination).
        text = _DUPLICATE_WORD.sub(r"\1", text)

        # Capitalise the first word when this block starts a new sentence.
        starts_new_sentence = (
            prev_text is None
            or (prev_text and prev_text[-1] in _SENTENCE_END)
        )
        if starts_new_sentence and text[0].islower():
            text = text[0].upper() + text[1:]

        # Capitalise after sentence-ending punctuation within this segment.
        text = _INTRA_SENTENCE_CAP.sub(
            lambda m: m.group(1) + m.group(2).upper(), text
        )

        return text.strip()
