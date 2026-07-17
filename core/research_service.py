from core.ai.ai_engine import AIEngine
from core.research_prompt_builder import ResearchPromptBuilder


class ResearchService:
    def __init__(self, prompt_builder: ResearchPromptBuilder | None = None, ai_engine: AIEngine | None = None):
        self.prompt_builder = prompt_builder or ResearchPromptBuilder()
        self.ai_engine = ai_engine or AIEngine(provider="gemini")

    def preview(
        self,
        topic: str,
        keywords: str,
        goal: str,
        sources: str,
    ) -> str:
        return self.prompt_builder.build(
            topic=topic,
            keywords=keywords,
            goal=goal,
            sources=sources,
        )

    def generate(
        self,
        topic: str,
        keywords: str,
        goal: str,
        sources: str,
    ) -> str:
        title = f"Research: {topic or 'Untitled Topic'}"
        summary = (
            f"This simulated research summary covers the core themes around '{topic or 'the selected topic'}' "
            f"with a focus on {goal or 'the stated goal'}."
        )
        key_facts = "\n".join(
            [
                f"- {item}"
                for item in [
                    "The topic is relevant to the requested production brief.",
                    "Keywords provide a strong thematic direction for planning.",
                    "The provided sources anchor the overview in clear reference points.",
                ]
            ]
        )
        timeline = "\n".join(
            [
                "- Phase 1: Gather core context and audience expectations.",
                "- Phase 2: Organize narrative and visual direction.",
                "- Phase 3: Prepare a production-ready brief for the next stage.",
            ]
        )
        references = "\n".join(
            [
                f"- {source}" for source in [sources or "No sources provided."] if source
            ]
        ) or "- No sources provided."

        prompt = (
            f"Title\n{title}\n\n"
            f"Summary\n{summary}\n\n"
            f"Key Facts\n{key_facts}\n\n"
            f"Timeline\n{timeline}\n\n"
            f"References\n{references}"
        )
        return self.ai_engine.generate(prompt)
