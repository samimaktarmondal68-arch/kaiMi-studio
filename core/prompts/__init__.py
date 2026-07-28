from pathlib import Path


_PROMPTS_DIR = Path(__file__).resolve().parent


def load_prompt(name: str) -> str:
    path = _PROMPTS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def load_all_system_prompts() -> str:
    parts = []
    for f in ["system_prompt.md", "script_rules.md", "image_prompt_rules.md", "workflow_rules.md"]:
        content = load_prompt(f)
        if content:
            parts.append(content)
    return "\n\n".join(parts)
