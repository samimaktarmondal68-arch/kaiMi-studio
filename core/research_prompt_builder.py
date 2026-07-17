class ResearchPromptBuilder:
    def build(
        self,
        topic: str,
        keywords: str,
        goal: str,
        sources: str,
    ) -> str:
        return (
            f"Topic:\n{topic}\n\n"
            f"Keywords:\n{keywords or 'No keywords provided.'}\n\n"
            f"Goal:\n{goal or 'No goal provided.'}\n\n"
            f"Sources:\n{sources or 'No sources provided.'}"
        )
