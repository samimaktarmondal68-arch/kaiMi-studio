"""Project template definitions with sensible defaults for each template type."""

from dataclasses import dataclass, field


@dataclass
class TemplateConfig:
    template_name: str
    platform: str
    video_type: str
    script_mode: str
    script_min: int
    script_max: int
    duration_preset: str
    description: str


TEMPLATES: list[TemplateConfig] = [
    TemplateConfig(
        template_name="YouTube Long Form",
        platform="YouTube",
        video_type="Educational",
        script_mode="characters",
        script_min=4500,
        script_max=5000,
        duration_preset="10-15 minutes",
        description="Standard YouTube educational content with detailed script.",
    ),
    TemplateConfig(
        template_name="YouTube Shorts",
        platform="YouTube",
        video_type="Educational",
        script_mode="characters",
        script_min=500,
        script_max=1000,
        duration_preset="30-60 seconds",
        description="Short-form YouTube content with concise script.",
    ),
    TemplateConfig(
        template_name="Instagram Reel",
        platform="Instagram",
        video_type="Educational",
        script_mode="characters",
        script_min=300,
        script_max=800,
        duration_preset="15-60 seconds",
        description="Vertical short-form educational content.",
    ),
    TemplateConfig(
        template_name="Educational",
        platform="YouTube",
        video_type="Educational",
        script_mode="characters",
        script_min=3000,
        script_max=6000,
        duration_preset="8-12 minutes",
        description="In-depth educational content with thorough explanations.",
    ),
    TemplateConfig(
        template_name="Documentary",
        platform="YouTube",
        video_type="Documentary",
        script_mode="characters",
        script_min=6000,
        script_max=10000,
        duration_preset="15-30 minutes",
        description="Long-form documentary-style content with narrative arcs.",
    ),
    TemplateConfig(
        template_name="Storytelling",
        platform="YouTube",
        video_type="Entertainment",
        script_mode="characters",
        script_min=2000,
        script_max=4000,
        duration_preset="5-10 minutes",
        description="Narrative-driven content with emotional engagement.",
    ),
    TemplateConfig(
        template_name="Podcast",
        platform="YouTube",
        video_type="Entertainment",
        script_mode="characters",
        script_min=5000,
        script_max=8000,
        duration_preset="20-40 minutes",
        description="Conversational format with discussion-style script.",
    ),
    TemplateConfig(
        template_name="Custom",
        platform="YouTube",
        video_type="Educational",
        script_mode="characters",
        script_min=4500,
        script_max=5000,
        duration_preset="",
        description="Fully customizable project settings.",
    ),
]


def get_template(name: str) -> TemplateConfig | None:
    for t in TEMPLATES:
        if t.template_name == name:
            return t
    return None


def get_template_names() -> list[str]:
    return [t.template_name for t in TEMPLATES]