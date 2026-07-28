# Architecture Decision Records (ADRs)

This document records every major architectural decision made during the development of KaiMi Studio.

New ADRs must be added when making architectural changes. Use the format below.

---

## ADR-001: Migrate from CustomTkinter to PySide6

**Status:** Accepted (2026)

**Context:**
The initial prototype was built with CustomTkinter due to rapid prototyping needs. As the application grew, limitations became apparent:
- No native Qt widget ecosystem (tables, trees, rich text, scroll areas)
- Inconsistent styling compared to premium desktop applications
- Limited theming capabilities
- Poor performance with complex layouts
- Small community and ecosystem

**Decision:**
Adopt PySide6 (Qt for Python) as the UI framework. This provides:
- Full Qt widget library (QStackedWidget, QScrollArea, QComboBox, QPlainTextEdit)
- QPalette-based theming with runtime switching
- Professional look and feel matching Notion, Cursor, Figma
- Mature ecosystem with extensive documentation
- Native performance and platform integration

**Consequences:**
- All existing CustomTkinter code was rewritten (new pages, widgets, dialogs)
- Theme system redesigned from legacy theme system to QPalette + QSS stylesheet
- All components migrated from CustomTkinter to PySide6

---

## ADR-002: Hide Research Stage from Users

**Status:** Accepted (2026)

**Context:**
The workflow originally included an explicit Research stage before Script generation. However, research is an internal implementation detail — users care about the script, not how it was researched.

**Decision:**
Research happens automatically during script generation. The Script operator internally calls research logic (via `ResearchOperator`) before generating. Users see a unified "Generate Script" flow with progress stages like "Researching..." and "Finding sources...".

**Consequences:**
- Simpler 5-stage workflow instead of 6
- Research operator exists in `operators/research/` but is called internally
- Research can be made visible later if users request it

---

## ADR-003: Sidebar Navigation with Global + Project Context

**Status:** Accepted (2026)

**Context:**
Navigation needed to be minimal but context-aware. Some pages are always available (Dashboard, Projects, Settings), while others depend on an open project (Script, Voice, Image Prompts, Export).

**Decision:**
- Global items (Dashboard, Projects, Settings) are always visible in the sidebar
- Project items appear only when a project is open, below a "Current Project" section
- Project items show workflow progress (✓ ● ○ indicators)
- Clicking a project item on Dashboard/Projects triggers resume logic

**Consequences:**
- `Sidebar.set_project_context()` shows/hides the project section
- `MainWindow.navigate_to()` calls `set_project()` on destination pages
- Resume logic determines which stage page to navigate to

---

## ADR-004: Centralized ThemeManager Singleton

**Status:** Accepted (2026)

**Context:**
Initial prototype had colors scattered across files. Theme switching was impossible without restarting.

**Decision:**
Create a centralized `ThemeManager` singleton that:
- Holds color tokens for Dark and Light themes in `core/theme.py`
- Provides `ThemeManager.instance().colors()` to all components
- Applies theme changes via QPalette + global QSS stylesheet rebuild
- Fires `on_change()` callbacks when theme switches

**Consequences:**
- Every component must read colors from `ThemeManager.instance().colors()`
- Theme switching is instant and affects all open windows
- New components automatically get correct theme colors

---

## ADR-005: JSON File Storage Instead of Database

**Status:** Accepted (2026)

**Context:**
A database (SQLite) was considered for project storage. However, the data model is simple — each project is a collection of related JSON documents.

**Decision:**
Use JSON files on the filesystem:
- `projects/<name>/project.json` for metadata
- `projects/<name>/script.json`, `voice.json`, `image_prompts.json` for stage data
- `projects/<name>/history/<stage>/<timestamp>.json` for version snapshots
- No database server or ORM dependency

**Consequences:**
- Simple backup: copy the `projects/` folder
- No database migration needed for schema changes
- Path traversal protection required for all file operations
- Performance is acceptable for single-user desktop usage

---

## ADR-006: ProviderManager as Single Gateway

**Status:** Accepted (2026)

**Context:**
Operators need to call AI providers. Without a gateway, every operator would need to know about provider configuration, API keys, failover logic, and error handling.

**Decision:**
`ProviderManager` is the single gateway for all AI generation:
- Operators call `ProviderManager.generate(GenerationRequest)` and receive `GenerationResponse`
- ProviderManager handles selection, configuration, initialization, failover
- No operator knows which concrete provider is active
- Adding a provider = one class + one `register()` call

**Consequences:**
- Zero operator changes when adding providers
- Auto-failover across providers when quota/rate limits are hit
- Simplified testing — mock ProviderManager instead of individual providers
- Providers are truly interchangeable

---

## ADR-007: Threaded Background Tasks with TaskManager

**Status:** Accepted (2026)

**Context:**
AI generation calls can take 30+ seconds. Running them on the UI thread freezes the application.

**Decision:**
Create `TaskManager` as a dedicated controller:
- Runs AI generation on daemon threads
- Provides queue, cancel, retry, and progress tracking
- Separates task execution from UI state
- Uses callbacks (`on_complete`, `on_error`) to update UI on the main thread

**Consequences:**
- UI remains responsive during long-running operations
- Tasks can be queued, cancelled, and retried
- Pages pass lambdas/callbacks to TaskManager instead of implementing threading themselves
- Thread safety is maintained by never touching UI objects from worker threads

---

## ADR-008: Linear Workflow with State Machine

**Status:** Accepted (2026)

**Context:**
Early prototypes allowed users to work on any stage in any order, causing data inconsistency (e.g., generating image prompts before a script existed).

**Decision:**
Enforce a linear workflow using a state machine:
- `WORKFLOW_STAGES = ["Script", "Voice", "Image Prompts", "Export"]`
- Each stage has a state: `LOCKED`, `AVAILABLE`, or `COMPLETED`
- Stages unlock sequentially — you cannot skip ahead
- Resume logic navigates to the first incomplete stage

**Consequences:**
- Data consistency is guaranteed (each stage depends on the previous)
- Users cannot generate image prompts without a script
- Simple state machine logic in `core/workflow.py`
- Future stages can be added by appending to `WORKFLOW_STAGES`

---

## ADR-009: Operator Pattern for Business Operations

**Status:** Accepted (2026)

**Context:**
AI generation involves multiple steps: validate input, build prompt, call provider, parse response. Without a pattern, this logic would be scattered across pages and core services.

**Decision:**
Create an `Operator` layer with a consistent pattern:
1. `Request` model (dataclass) — validated input
2. `PromptBuilder` — constructs system and user prompts
3. `Operator.execute(request)` — validates, builds prompts, generates, returns result
4. `Parser` (optional) — parses raw output into structured data

**Consequences:**
- Each operator is independently testable
- Consistent interface across all generation types
- Operators can be composed (e.g., Script operator calls Research operator)
- New generation types follow the same pattern

---

## ADR-010: PyInstaller for Distribution

**Status:** Accepted (2026)

**Context:**
Users need a standalone executable. Python source distribution requires Python installation and dependency management.

**Decision:**
Use PyInstaller to bundle the application:
- Single executable with all dependencies
- One-file mode for distribution
- Build configured in `KaiMi Studio.spec`
- Automated via `build.py`

**Consequences:**
- Build process is simple: `python build.py`
- Distribution is a single executable file
- Startup integrity verification ensures bundled assets are present
- PyInstaller-specific issues (hidden imports, data files) are documented in the build script