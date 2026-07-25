from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ResearchReview:
    """Structured evaluation of generated research content."""

    overall_score: int
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)
    factual_risk: str = "low"
    recommendation: str = "PASS"


class ResearchCritic:
    """Evaluates generated research text using deterministic heuristics.

    This critic never calls an AI provider, never modifies the research,
    and never accesses UI, storage, workflow, or project management.

    Responsibilities:
        - Accept research text
        - Evaluate usability via text analysis
        - Return a structured ResearchReview
    """

    MIN_WORDS = 150
    IDEAL_WORDS = 400
    MAX_SENTENCE_LENGTH = 40
    SECTION_KEYWORDS = [
        "introduction",
        "background",
        "overview",
        "summary",
        "conclusion",
        "findings",
        "analysis",
        "key points",
        "main points",
        "objectives",
        "results",
        "discussion",
    ]
    PLACEHOLDER_PATTERNS = [
        r"\b(todo|tbd|placeholder|lorem ipsum|insert here)\b",
        r"\.{3,}",
        r"\[.*?\]",
    ]
    ABSOLUTE_CLAIM_PATTERNS = [
        r"\b(always|never|impossible|guaranteed|100%|without exception)\b",
        r"\bproves? that\b",
        r"\bundeniably\b",
    ]

    def evaluate(self, research_text: str) -> ResearchReview:
        """Evaluate research text and return a structured review.

        Args:
            research_text: The generated research content to evaluate.

        Returns:
            A ResearchReview with score, strengths, weaknesses,
            missing information, factual risk, and recommendation.
        """
        text = (research_text or "").strip()

        if not text:
            return ResearchReview(
                overall_score=0,
                strengths=[],
                weaknesses=["Research text is empty."],
                missing_information=["Complete research content."],
                factual_risk="low",
                recommendation="REVISE",
            )

        words = text.split()
        word_count = len(words)
        sentences = self._split_sentences(text)
        sentence_count = len(sentences)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        paragraph_count = len(paragraphs)
        lower_text = text.lower()

        score = 50
        strengths: list[str] = []
        weaknesses: list[str] = []
        missing: list[str] = []

        # --- Word count evaluation ---
        if word_count >= self.IDEAL_WORDS:
            score += 15
            strengths.append(f"Good length ({word_count} words).")
        elif word_count >= self.MIN_WORDS:
            score += 5
            strengths.append(f"Adequate length ({word_count} words).")
        else:
            score -= 20
            weaknesses.append(
                f"Too short ({word_count} words, minimum {self.MIN_WORDS})."
            )
            missing.append("More detailed content.")

        # --- Structural sections ---
        found_sections = [
            kw for kw in self.SECTION_KEYWORDS if kw in lower_text
        ]
        if len(found_sections) >= 3:
            score += 15
            strengths.append(
                f"Well-structured with sections: {', '.join(found_sections[:3])}."
            )
        elif len(found_sections) >= 1:
            score += 5
            strengths.append("Has some structural sections.")
        else:
            score -= 15
            weaknesses.append("No recognizable section headings or structure.")
            missing.append("Organized sections (e.g., introduction, key points, conclusion).")

        # --- Paragraph quality ---
        if paragraph_count >= 3:
            score += 10
            strengths.append(f"Good paragraph organization ({paragraph_count} paragraphs).")
        elif paragraph_count >= 2:
            score += 0
        else:
            score -= 10
            weaknesses.append("Content is not broken into paragraphs.")

        # --- Sentence length (readability) ---
        if sentence_count > 0:
            avg_sentence_len = word_count / sentence_count
            if avg_sentence_len <= self.MAX_SENTENCE_LENGTH:
                score += 5
                strengths.append("Sentences are readable length.")
            else:
                score -= 5
                weaknesses.append(
                    f"Sentences are long on average ({avg_sentence_len:.0f} words)."
                )

        # --- Placeholder detection ---
        placeholder_count = 0
        for pattern in self.PLACEHOLDER_PATTERNS:
            placeholder_count += len(re.findall(pattern, lower_text))
        if placeholder_count > 0:
            score -= 15
            weaknesses.append(
                f"Contains {placeholder_count} placeholder(s) or incomplete markers."
            )
            missing.append("Replace all placeholders with real content.")

        # --- Factual risk (absolute claims) ---
        absolute_count = 0
        for pattern in self.ABSOLUTE_CLAIM_PATTERNS:
            absolute_count += len(re.findall(pattern, lower_text))

        if absolute_count >= 5:
            factual_risk = "high"
            score -= 15
            weaknesses.append(
                f"High factual risk: {absolute_count} absolute claims detected."
            )
        elif absolute_count >= 2:
            factual_risk = "medium"
            score -= 5
            weaknesses.append(
                f"Moderate factual risk: {absolute_count} absolute claims detected."
            )
        else:
            factual_risk = "low"

        # --- Empty or very short paragraphs ---
        thin_paragraphs = sum(1 for p in paragraphs if len(p.split()) < 10)
        if thin_paragraphs > 0 and paragraph_count > 1:
            score -= 5
            weaknesses.append(
                f"{thin_paragraphs} paragraph(s) are very thin (< 10 words)."
            )

        # --- Clamp score ---
        score = max(0, min(100, score))

        recommendation = "PASS" if score >= 50 else "REVISE"

        if not weaknesses:
            weaknesses.append("No significant weaknesses detected.")
        if not strengths:
            strengths.append("Content is present and readable.")
        if not missing:
            missing.append("None identified.")

        return ResearchReview(
            overall_score=score,
            strengths=strengths,
            weaknesses=weaknesses,
            missing_information=missing,
            factual_risk=factual_risk,
            recommendation=recommendation,
        )

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split text into sentences using basic punctuation rules."""
        return [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
