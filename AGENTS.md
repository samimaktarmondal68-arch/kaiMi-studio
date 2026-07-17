# AGENTS.md

## Project overview
- KaiMi Studio is a desktop application built with Python and CustomTkinter.
- Keep the modular structure described in [README.md](README.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Working rules
- Only change files explicitly requested by the user.
- Read existing code before editing.
- Keep naming and style consistent with the repository.
- Preserve the current architecture and avoid unnecessary refactors.
- Prefer production-quality Python with full type hints.
- Do not add placeholder code, TODO comments, dead code, or duplicated logic.

## Architecture boundaries
- Put UI code in [ui/](ui/). UI modules should not perform filesystem or AI logic.
- Put core logic in [core/](core/). The project manager owns project folder lifecycle operations.
- Keep reusable widgets in [ui/components/](ui/components/).
- Keep page-specific logic in the corresponding page module under [ui/](ui/).

## CustomTkinter conventions
- Use CTk widgets only.
- Do not use absolute positioning.
- Use pack() unless the existing file already uses another layout.
- Avoid recreating widgets unnecessarily; update existing widgets when possible.

## Validation
- After editing Python files, run:
  - python -m py_compile <modified_file>

## Reference files
- [main.py](main.py)
- [core/project_manager.py](core/project_manager.py)
- [ui/home.py](ui/home.py)
- [ui/dashboard.py](ui/dashboard.py)
