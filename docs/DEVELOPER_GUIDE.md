# KaiMi Studio Developer Guide

The official handbook for every developer working on KaiMi Studio v1.0 "Aurora".

---

## Project Philosophy

KaiMi Studio is built on these core beliefs:

- **KaiMi Studio is not an AI chatbot.** It is a professional creator workspace.
- **AI is an implementation detail.** Creators should think about videos — not models.
- **The workflow must remain linear.** Each stage feeds the next. No branching complexity.
- **The interface must remain minimal.** Every feature should reduce effort, not add it.
- **Professional polish is mandatory.** This is a premium desktop tool, not a prototype.

## Development Philosophy

1. **Engine first, stability second, UI third.** Never reverse this order.
2. **Make it work. Make it stable. Make it beautiful.** In that exact order.
3. **Progress > Perfection.** A working feature is worth more than a perfect design.
4. **One task at a time.** Each commit solves exactly one problem.
5. **Bugs have higher priority than polish.** A broken feature must be fixed before it can be improved.

## UI Philosophy

- The UI is a thin presentation layer. Zero business logic lives in widgets.
- Pages import controllers and widgets — never providers directly.
- Every UI element gets its colors from `ThemeManager.instance().colors()`.
- Reusable widgets live in `ui/widgets/__init__.py`. Do not duplicate UI patterns.
- Pages should stay under 200 lines. Extract reusable components when they grow.

## Workflow Philosophy

- The 5-stage workflow (Project → Script → Voice → Image Prompts → Export) is the backbone.
- Each stage produces a file (`script.json`, `voice.json`, `image_prompts.json`).
- Stages unlock sequentially. Users can only work on one stage at a time.
- Resume logic picks up exactly where the user left off.
- Research is an internal implementation detail — hidden from users.

## Backend Philosophy

- `core/` contains all business logic. It never imports from `ui/`.
- `providers/` is an abstraction layer. Operators never know which provider is active.
- `operators/` bridge core services and providers. They validate inputs and coordinate.
- `ProjectManager` is the single source of truth for project data.
- Services are stateless where possible. State lives in JSON files on disk.

## Theme System

- Centralized in `core/theme.py` with `Dark` and `Light` color classes.
- Applied at runtime by `ui/theme_pyside.py` `ThemeManager` singleton.
- Every component reads colors via `ThemeManager.instance().colors()`.
- Never hardcode a color value. Never.
- Theme switching calls `_apply()` which rebuilds the Qt palette and stylesheet.

## Provider System

- `BaseProvider` is the abstract interface for all AI providers.
- `ProviderManager` is the single gateway. Operators call `ProviderManager.generate()`.
- Providers are registered via `ProviderRegistry`. Adding a provider = new class + one `register()` call.
- Auto-failover: if the active provider fails, the system tries the next in `FAILOVER_SEQUENCE`.
- Providers are configured through `config/providers.json`.

## Resume Logic

Defined in `core/workflow.py`:

- `WORKFLOW_STAGES = ["Script", "Voice", "Image Prompts", "Export"]`
- Each stage has a state: `LOCKED`, `AVAILABLE`, or `COMPLETED`.
- `advance_workflow_state()` marks the completed stage, unlocks the next, locks the rest.
- `get_resume_page_class()` returns the first incomplete stage's page class.
- Project cards on Dashboard and Projects page use this to navigate to the right stage.

## Project Storage

- Each project lives in `projects/<name>/` with subdirectories: `audio/`, `exports/`, `history/`.
- `project.json` stores metadata (name, topic, platform, workflow_state, timestamps, favorites).
- Stage data is stored in separate JSON files: `script.json`, `voice.json`, `transcript.json`, `image_prompts.json`.
- All file operations validate paths to prevent directory traversal.
- History snapshots are saved in `history/<stage>/<timestamp>.json`.

## Design Principles

1. **Consistency over cleverness.** Use existing patterns, widgets, and conventions.
2. **Readability over brevity.** Descriptive names beat short ones.
3. **Single responsibility.** One class, one file, one purpose.
4. **Fail gracefully.** Expected errors are caught. The app never crashes on bad input.
5. **Defense in depth.** Validate at every boundary (UI input → operator → file system).

## Future Development Rules

1. Never redesign the workflow without updating `WORKFLOW.md`.
2. Never change UI components without updating `DESIGN_SYSTEM.md`.
3. Never make architectural decisions without recording them in `DECISIONS.md`.
4. Never add providers without updating `ARCHITECTURE.md`.
5. Keep documentation synchronized with code.