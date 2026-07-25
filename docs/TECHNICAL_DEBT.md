# TECHNICAL_DEBT.md

# KaiMi Studio Technical Debt Inventory

Version: 0.1

Purpose: Catalogue every known debt item so development sessions can address them in priority order.

---

# Legend

Priority levels:

- **High** — Blocks v0.1 completion or causes incorrect behavior.
- **Medium** — Causes code fragility, confusion, or maintenance burden.
- **Low** — Cosmetic or aspirational. Safe to ignore until later.

Status indicators:

- **Open** — Not started.
- **Planned** — Acknowledged, fix designed, awaiting execution.
- **Partial** — Fix in progress or partially applied.

---

# Category 1: Duplicate Code

## 1.1 Duplicate constant definitions in `core/constants.py`

**File:** `core/constants.py` lines 1–15

`WINDOW_WIDTH`, `WINDOW_HEIGHT`, and `SIDEBAR_WIDTH` are each defined twice with different values. The second definition silently overwrites the first.

```
WINDOW_WIDTH = 1400   # line 1
WINDOW_WIDTH = 1400   # line 12 (same value, redundant)
WINDOW_HEIGHT = 820   # line 2
WINDOW_HEIGHT = 850   # line 13 (overwrites line 2)
SIDEBAR_WIDTH = 250   # line 4
SIDEBAR_WIDTH = 240   # line 15 (overwrites line 4)
```

**Impact:** Only the second values are used at runtime. The first values are dead. Anyone reading the file sees conflicting numbers and cannot tell which are intentional.

**Priority:** Medium

**Fix:** Remove lines 1–4 (the first definitions). Keep lines 12–15 as the single source of truth.

---

## 1.2 Duplicate constant definitions in `core/version.py`

**File:** `core/version.py` lines 3–14

`VERSION` is defined twice (both `"0.3.0"`). `CODENAME` is defined twice (`"Genesis"` then `"Iron Core"`).

**Impact:** Same as 1.1 — second values overwrite first. The `"Genesis"` codename is dead.

**Priority:** Medium

**Fix:** Remove lines 3 and 5. Keep the later definitions.

---

## 1.3 Two `BaseProvider` abstract classes

**Files:**
- `core/ai/base_provider.py` — 1 abstract method (`generate`)
- `providers/base_provider.py` — 4 abstract methods (`generate`, `validate_configuration`, `get_provider_name`, `get_supported_features`)

These are completely separate class hierarchies that happen to share a name. The legacy system (`AIEngine` + `core.ai.gemini_provider`) uses the minimal one. The new system (`ResearchOperator` + `ProviderManager`) uses the full one.

**Impact:** Any new provider must implement both interfaces to work with both systems. `_GeminiProviderAdapter` in `providers/provider_manager.py` exists solely to bridge this gap — it implements the full interface while delegating to the minimal `GeminiProvider`.

**Priority:** High

**Fix:** When migrating script, storyboard, and image prompt operators, route them through `ProviderManager` and `providers.base_provider.BaseProvider`. Then delete `core/ai/base_provider.py` and refactor `AIEngine` to use `ProviderManager`.

---

## 1.4 Two `ResearchPromptBuilder` implementations

**Files:**
- `core/research_prompt_builder.py` — `build(topic, keywords, goal, sources) -> str`
- `operators/research/prompt_builder.py` — `build(request: ResearchRequest) -> str`

**Impact:** Two classes with the same name producing different prompt formats. The core version is only used by `core/research_service.py`. The operators version is only used by `operators/research/operator.py`.

**Priority:** High

**Fix:** Delete `core/research_prompt_builder.py` when migrating workspace away from `ResearchService`.

---

## 1.5 Two `Theme`/`constants` systems for UI values

**Files:**
- `core/constants.py` — `SIDEBAR_WIDTH`, `BUTTON_HEIGHT`, `CARD_RADIUS`, `RADIUS`
- `core/theme.py` `Theme` class — `SIDEBAR_WIDTH`, `BUTTON_HEIGHT`, `CARD_RADIUS`, `BUTTON_RADIUS`, `ENTRY_RADIUS`, `PADDING`

Both define overlapping UI dimension constants with different values (`SIDEBAR_WIDTH`: 240 vs 280, `BUTTON_HEIGHT`: 42 vs 48).

**Impact:** No code references `Theme` at all. The workspace hardcodes its own values (e.g., `corner_radius=18`). Three potential sources of truth, none used consistently.

**Priority:** Low

**Fix:** Decide on one source. Delete the other. For v0.1, delete `core/theme.py` entirely since nothing imports it.

---

## 1.6 Duplicated `show_*` frame-hiding logic in workspace

**File:** `ui/workspace.py` lines 720–796

Six methods (`show_placeholder`, `show_research`, `show_script`, `show_storyboard`, `show_image_prompts`, `show_export`) each individually hide 5 other frames. Every method contains the same 5 `if ... pack_forget()` blocks in slightly different permutations.

**Impact:** ~120 lines of near-identical code. Adding a new stage requires editing all 6 methods.

**Priority:** Medium

**Fix:** Replace with a single `_show_frame(target)` method that hides all frames, then shows the target. Store all stage frames in a list or dict.

---

# Category 2: Dead Code

## 2.1 `core/theme.py` — `Theme` class

**File:** `core/theme.py`

63-line class defining colors, fonts, and sizes. Never imported by any file in the project.

**Priority:** Low

**Fix:** Delete the file.

---

## 2.2 `core/models/project.py` — `Project` dataclass

**File:** `core/models/project.py`

Defines a `Project` dataclass with fields `name`, `topic`, `language`, `style`, `created`, `status`. Never imported by any file. All code uses raw `dict` objects for project data.

**Priority:** Medium

**Fix:** Either integrate this dataclass into `ProjectManager` (replacing dict usage) or delete the file. The dataclass is correct and would improve type safety.

---

## 2.3 `ui/widgets.py` — `KButton`, `KLabel`, `KFrame`

**File:** `ui/widgets.py`

Three custom widget classes wrapping CTkinter defaults. Never imported or used anywhere.

**Priority:** Low

**Fix:** Delete the file.

---

## 2.4 `ui/components/section_header.py` — `SectionHeader`

**File:** `ui/components/section_header.py`

A reusable section header widget. Never imported or used anywhere.

**Priority:** Low

**Fix:** Delete the file, or keep it for future use if a consistent header style is planned.

---

## 2.5 `core/settings.py` — `initialize()` function

**File:** `core/settings.py`

Defines `initialize()` which sets CTkinter appearance mode and theme. This function is never called. `HomeWindow.__init__` in `ui/home.py` performs the same initialization directly (lines 16–17).

**Impact:** The `initialize()` function, `AUTO_SAVE`, `PROJECT_DIRECTORY`, and `EXPORT_DIRECTORY` constants are all dead.

**Priority:** Low

**Fix:** Either call `initialize()` from `main.py` and use its constants, or delete `core/settings.py`.

---

## 2.6 `ui/workspace.py` — `save()` method

**File:** `ui/workspace.py` lines 1511–1514

```python
def save(self) -> None:
    if self.selected_name:
        path = self.manager.PROJECTS_DIR / self.selected_name / "script.md"
        path.write_text("", encoding="utf-8")
```

Writes an empty string to `script.md`. Never called from anywhere in the codebase. Appears to be a stub that was never completed.

**Priority:** Low

**Fix:** Delete the method.

---

## 2.7 Unused constants in `core/constants.py`

**File:** `core/constants.py`

`APP_NAME` and `VERSION` are defined here but `core/version.py` also defines `APP_NAME` and `VERSION` with the same values. The codebase imports from `core/version.py` (e.g., `ui/dashboard.py` line 5). The copies in `constants.py` are dead.

**Priority:** Low

**Fix:** Remove `APP_NAME` and `VERSION` from `constants.py`. Import from `version.py`.

---

# Category 3: Legacy Architecture

## 3.1 `AIEngine` + `core.ai.*` provider system

**Files:**
- `core/ai/ai_engine.py`
- `core/ai/base_provider.py`
- `core/ai/gemini_provider.py`
- `core/ai/mock_provider.py`

This is the original provider system. It resolves providers by string name, checks environment variables, and has no configuration persistence, no validation API, and no feature flags.

The new system (`providers/provider_manager.py` + `providers/base_provider.py`) supersedes it with configuration persistence, validation, multi-provider support, and feature detection.

**Impact:** Four services still depend on the legacy system (`ScriptService`, `StoryboardService`, `ImagePromptService` use `AIEngine`; `ResearchService` also uses it but is being migrated). The two systems coexist in the same application.

**Priority:** High

**Fix:** Migrate all services to `ProviderManager`. Delete `core/ai/ai_engine.py`, `core/ai/base_provider.py`, `core/ai/mock_provider.py`. Keep `core/ai/gemini_provider.py` as the underlying implementation that `_GeminiProviderAdapter` delegates to (or move Gemini logic into `providers/gemini_provider.py`).

---

## 3.2 `ResearchService` + `core/research_prompt_builder.py`

**Files:**
- `core/research_service.py`
- `core/research_prompt_builder.py`

The legacy research pipeline. `ResearchService.generate()` builds a hardcoded prompt template and sends it to `AIEngine`. It does not use its own `ResearchPromptBuilder` for generation (only for preview). The prompt template differs from the one in `operators/research/prompt_builder.py`.

The new pipeline (`ResearchOperator` + `ResearchCritic` + `providers/`) supersedes this.

**Impact:** `ui/workspace.py` imports and uses `ResearchService` directly. Until the migration is complete, two parallel research pipelines exist.

**Priority:** High

**Fix:** Complete the workspace migration from `ResearchService` to `ResearchOperator`. Delete both legacy files.

---

## 3.3 Hardcoded prompt templates in all services

**Files:**
- `core/research_service.py` lines 31–65
- `core/script_service.py` lines 31–40
- `core/storyboard_service.py` lines 14–17
- `core/image_prompt_service.py` lines 17–25

All four services construct their AI prompts as inline f-string templates. There is no prompt management, no versioning, and no separation between prompt logic and service logic.

The `prompts/` directory contains markdown files (`research_prompt.md`, `script_prompt.md`, `storyboard_prompt.md`, `image_prompt.md`) that appear to be prompt documentation or templates, but no code reads them.

**Impact:** Changing a prompt requires editing service code. The markdown files in `prompts/` are disconnected from the actual prompts sent to the AI.

**Priority:** Medium

**Fix:** When migrating each service to the operator architecture, move prompt construction into dedicated prompt builder classes (following the pattern established by `operators/research/prompt_builder.py`).

---

# Category 4: Placeholder Modules (Empty Files)

## 4.1 Empty provider implementations

**Files:**
- `providers/gemini_provider.py`
- `providers/openai_provider.py`
- `providers/claude_provider.py`
- `providers/deepseek_provider.py`
- `providers/ollama_provider.py`
- `providers/openrouter_provider.py`

All six files are empty. The Gemini adapter already exists inside `providers/provider_manager.py`. The other five are stubs for future providers.

**Priority:** Low

**Fix:** Implement when needed. For now, the `_PlaceholderProvider` in `provider_manager.py` handles these gracefully.

---

## 4.2 Empty service integrations

**Files:**
- `core/services/openai.py`
- `core/services/gemini.py`
- `core/services/elevenlabs.py`
- `core/services/leonardo.py`
- `core/services/flow.py`

All empty. These appear to be planned service wrappers that were never implemented.

**Priority:** Low

**Fix:** Delete if the provider pattern in `providers/` is the chosen architecture. These overlap with the `providers/` package.

---

## 4.3 Empty model files

**Files:**
- `core/models/research.py`
- `core/models/script.py`
- `core/models/assets.py`

All empty. `core/models/project.py` has content but is unused (see 2.2).

**Priority:** Low

**Fix:** Either implement data models for each stage (following the `ResearchRequest` pattern from the operator architecture) or delete the empty files.

---

## 4.4 Empty operator stubs

**Files:**
- `operators/script/operator.py`
- `operators/script/critic.py`
- `operators/storyboard/operator.py`
- `operators/image_prompt/operator.py`

All empty. These are placeholders for future operator implementations following the pattern established by `operators/research/operator.py`.

**Priority:** Low

**Fix:** Implement when migrating each stage from the legacy service architecture to the operator architecture.

---

## 4.5 Empty AI module files

**Files:**
- `core/ai/critic.py`
- `core/ai/export.py`
- `core/ai/image.py`
- `core/ai/prompts.py`
- `core/ai/research.py`
- `core/ai/script.py`
- `core/ai/voice.py`

All empty. These appear to be planned AI-related modules that were never implemented.

**Priority:** Low

**Fix:** Delete. The operator architecture (`operators/`) has replaced this planned structure.

---

## 4.6 Empty UI component files

**Files:**
- `ui/components/button.py`
- `ui/components/card.py`
- `ui/components/dialog.py`
- `ui/components/header.py`
- `ui/components/input.py`

All empty. `ui/components/section_header.py` and `ui/components/stat_card.py` have content.

**Priority:** Low

**Fix:** Implement or delete. The workspace currently builds all UI inline without using components.

---

## 4.7 Empty core module files

**Files:**
- `core/navigation.py`
- `core/provider_manager.py`
- `core/file_manager.py`

All empty. These are stubs for planned modules.

**Priority:** Low

**Fix:** Delete. Navigation is handled by `ui/home.py` and `ui/sidebar.py`. Provider management is handled by `providers/provider_manager.py`. File management is handled by `core/project_manager.py`.

---

## 4.8 Empty asset directories

**Directories:**
- `assets/fonts/`
- `assets/icons/`
- `assets/images/`
- `assets/themes/`

All empty. No code references these directories.

**Priority:** Low

**Fix:** Populate when custom assets are needed, or remove if the app uses system defaults.

---

# Category 5: Potential Bugs

## 5.1 `StoryboardService.generate()` discards AI result

**File:** `core/storyboard_service.py` line 18

```python
self.ai_engine.generate(prompt)
```

The return value of `ai_engine.generate()` is discarded. The method then builds a hardcoded scene list regardless of what the AI returned. The AI call is purely cosmetic — it costs an API token but contributes nothing to the output.

**Impact:** Users pay for an API call that has no effect. Storyboard content is always the same template regardless of the script.

**Priority:** High

**Fix:** Either parse the AI response and use it to build scenes, or remove the AI call and use the template directly.

---

## 5.2 `WorkspacePage.save()` writes empty file

**File:** `ui/workspace.py` lines 1511–1514

Writes an empty string to `script.md`. This overwrites any existing script data if called. It is never called from anywhere, so no data is currently lost.

**Priority:** Low

**Fix:** Delete the method.

---

## 5.3 `build_script_prompt()` monkey-patches `ai_engine.generate`

**File:** `ui/workspace.py` lines 993–1019

To preview the script prompt without actually generating, the code temporarily replaces `ai_engine.generate` with a capture function, calls `script_service.generate()`, then restores the original. This is a thread-safety hazard — if two operations occur simultaneously, the generate method could be swapped mid-call.

**Impact:** In practice the app is single-threaded for UI operations, so this works. But it is fragile and violates the principle of least surprise.

**Priority:** Medium

**Fix:** Add a `get_prompt_preview()` method to `ScriptService` (following the `ResearchOperator` pattern) instead of monkey-patching.

---

## 5.4 `GeminiProvider.__init__` raises on missing key; `_GeminiProviderAdapter` does not

**Files:**
- `core/ai/gemini_provider.py` line 12: `raise RuntimeError("GEMINI_API_KEY environment variable is not set.")`
- `providers/provider_manager.py` line 16: `self._api_key = ... or os.getenv("GEMINI_API_KEY")` — no error on missing key

The legacy `GeminiProvider` crashes immediately if no API key is set. The adapter defers the error to `generate()` time. This means `AIEngine(provider="gemini")` raises at instantiation, while `ProviderManager().get_active_provider()` does not.

**Impact:** The workspace creates services eagerly in `__init__`. If `GEMINI_API_KEY` is unset, the legacy path crashes on startup. The new path would crash later during generation, which is actually better UX.

**Priority:** Medium

**Fix:** This is actually an improvement in the new path. Keep as-is. Document the behavioral difference.

---

## 5.5 `core/settings.py` — `THEME` variable is local, not module-level

**File:** `core/settings.py` line 9

```python
def initialize():
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    THEME = "iron"
```

`THEME` is assigned inside the function but never returned or stored as a module attribute. It is lost immediately. Even if `initialize()` were called, `THEME` would not be accessible outside the function.

**Priority:** Low

**Fix:** Delete `core/settings.py`. The initialization is handled by `HomeWindow.__init__`.

---

# Category 6: Architectural Inconsistencies

## 6.1 Missing `__init__.py` files

**Directories without `__init__.py`:**
- `operators/`
- `operators/research/`
- `operators/script/`
- `operators/storyboard/`
- `operators/image_prompt/`
- `providers/`
- `ui/components/`
- `core/models/`

Python 3 supports namespace packages (no `__init__.py` needed), but their absence means:
- Some tools (IDE autocompletion, type checkers, test runners) may not discover these packages.
- `from operators.research.operator import ResearchOperator` works only because of implicit namespace packages, which can break in certain packaging scenarios.

**Priority:** Medium

**Fix:** Add empty `__init__.py` files to all package directories.

---

## 6.2 Workspace is a 1514-line god class

**File:** `ui/workspace.py`

`WorkspacePage` has approximately 70 instance attributes and 55 methods. It handles:
- Research UI, generation, saving
- Script UI, generation, saving
- Storyboard UI, generation, editing, saving
- Image prompt UI, generation, saving
- Export UI and execution
- Task management
- Workflow state management
- Project loading and overview

**Impact:** Any change to one stage risks breaking another. The class is impossible to test in isolation. The constructor initializes every attribute eagerly, even for stages the user may never visit.

**Priority:** High

**Fix:** Split into stage-specific subframes (e.g., `ResearchFrame`, `ScriptFrame`, `StoryboardFrame`). Each subframe owns its own UI, service calls, and save logic. `WorkspacePage` becomes a thin coordinator.

---

## 6.3 No `__init__.py` in `providers/` but it works via namespace packages

**File:** `providers/provider_manager.py` line 8: `from providers.base_provider import BaseProvider`

This import works in Python 3.3+ without `__init__.py` due to namespace packages. However, if the project ever uses setuptools, pyinstaller, or certain packaging tools, this may break.

**Priority:** Low

**Fix:** Add `providers/__init__.py`.

---

## 6.4 Services create `AIEngine` eagerly with hardcoded provider name

**Files:**
- `core/research_service.py` line 8: `AIEngine(provider="gemini")`
- `core/script_service.py` line 8: `AIEngine(provider="gemini")`
- `core/storyboard_service.py` line 6: `AIEngine(provider="gemini")`
- `core/image_prompt_service.py` line 6: `AIEngine(provider="gemini")`

Every service hardcodes `"gemini"` as the provider. There is no way to switch providers without modifying source code. The `ProviderManager` exists to solve this but is only used by the new `ResearchOperator`.

**Priority:** Medium

**Fix:** When migrating each service to the operator pattern, inject `ProviderManager` instead of creating `AIEngine` directly.

---

## 6.5 Workspace imports all storage classes at module level

**File:** `ui/workspace.py` lines 8–16

```python
from core.research_storage import ResearchStorage
from core.script_storage import ScriptStorage
from core.storyboard_storage import StoryboardStorage
from core.image_prompt_storage import ImagePromptStorage
from core.export_service import ExportService
```

All five storage/service classes are imported and instantiated eagerly in `__init__` (lines 65–73), even though the user may only interact with one stage.

**Impact:** Startup time includes instantiating all five services. If any service has side effects at instantiation (e.g., `ProviderManager` reads config from disk), those side effects occur regardless of which stage is used.

**Priority:** Low

**Fix:** Lazy-instantiate services when their stage is first accessed. Or accept the cost if startup time is acceptable.

---

## 6.6 `ENGINE_STATUS.md` is entirely unchecked

**File:** `ENGINE_STATUS.md`

Every single item is marked `[ ]` (unchecked), including items that are demonstrably implemented (project creation, project loading, research generation, save/load all work).

**Impact:** The status tracker is not being maintained. It provides no useful signal about actual progress.

**Priority:** Medium

**Fix:** Update `ENGINE_STATUS.md` to reflect actual implementation status. Mark completed items as `[x]`.

---

# Category 7: Performance Issues

## 7.1 `ProviderManager` reads config from disk on every instantiation

**File:** `providers/provider_manager.py` line 67–71

Every time `ProviderManager()` is constructed, it reads `config/providers.json` from disk, parses JSON, and registers six provider factories. If `ResearchOperator` is constructed per workspace load, this disk read occurs every time the workspace is opened.

**Impact:** Negligible for a desktop app (single small JSON read). But architecturally, `ProviderManager` manages global state and should be a singleton or be created once at the application level.

**Priority:** Low

**Fix:** Create `ProviderManager` once in `main.py` or `HomeWindow` and inject it into operators via constructor.

---

## 7.2 Workspace creates all services eagerly

**File:** `ui/workspace.py` lines 65–73

Nine service/storage objects are instantiated in `WorkspacePage.__init__` regardless of which stage the user needs.

**Impact:** Minor. Each instantiation is lightweight (no network calls, just object creation). `ProviderManager` disk I/O is the only real cost.

**Priority:** Low

**Fix:** Accept for v0.1. Optimize if startup time becomes an issue.

---

## 7.3 No caching of AI responses

**Files:** All service `generate()` methods.

Every call to `generate()` sends a new request to the AI provider. There is no caching, no deduplication, and no memoization. If the user regenerates research with the same inputs, they pay for a new API call.

**Impact:** Cost and latency for the user. Not a bug, but a UX improvement opportunity.

**Priority:** Low

**Fix:** Implement response caching keyed on prompt hash. Defer to post-v0.1.

---

# Category 8: Missing Infrastructure

## 8.1 No automated tests

The project contains zero test files. No `tests/` directory. No test framework in `requirements.txt`. All verification is manual.

**Impact:** Every code change risks regression. The migration from legacy to operator architecture is particularly risky without tests.

**Priority:** High

**Fix:** Add at minimum:
- Unit tests for `ResearchCritic.evaluate()` (deterministic, easy to test)
- Unit tests for `ResearchPromptBuilder.build()` (pure function)
- Unit tests for `ResearchOperator` (with mock provider)
- Unit tests for `ProjectManager` (file I/O tests)

---

## 8.2 No linting or type checking configuration

No `pyproject.toml`, `setup.cfg`, `.flake8`, `mypy.ini`, or `ruff.toml` exists. No lint or typecheck commands are defined.

**Impact:** Code style inconsistencies and type errors are caught only at runtime.

**Priority:** Medium

**Fix:** Add `ruff` for linting and `mypy` for type checking. Add a `pyproject.toml` with basic configuration.

---

## 8.3 `requirements.txt` may be incomplete

**File:** `requirements.txt` (not read, but noted)

The project uses `customtkinter`, `google-genai`, and stdlib modules. Dependencies should be verified against all imports.

**Priority:** Low

**Fix:** Audit all imports against `requirements.txt`. Add any missing dependencies.

---

# Recommended Fix Order

This order follows the project's own priority: Engine > Stability > Usability.

---

## Phase 1: Stabilize the core (High priority, do first)

| # | Item | Why first |
|---|---|---|
| 1 | Fix duplicate constants (1.1, 1.2) | Silent bugs waiting to happen. Trivial fix. |
| 2 | Fix `StoryboardService` discarding AI result (5.1) | Users are paying for an API call that does nothing. |
| 3 | Complete research operator migration (3.2) | Unblocks deletion of legacy research pipeline. |
| 4 | Add `__init__.py` to all packages (6.1) | Prevents silent import failures in edge cases. |
| 5 | Update `ENGINE_STATUS.md` (6.6) | Restores the status tracker as a useful tool. |

## Phase 2: Reduce duplication (Medium priority)

| # | Item | Why here |
|---|---|---|
| 6 | Consolidate `BaseProvider` hierarchies (1.3) | Required before migrating other services. |
| 7 | Extract stage frames from workspace (6.2) | Reduces risk of every future change. |
| 8 | Replace `show_*` duplication (1.6) | ~120 lines of near-identical code. |
| 9 | Fix monkey-patching in `build_script_prompt` (5.3) | Fragile pattern, easy to fix properly. |
| 10 | Delete dead files (2.1–2.7) | Reduces confusion for anyone reading the codebase. |
| 11 | Delete empty placeholder files (4.1–4.8) | Reduces noise. Keep only intentional stubs. |

## Phase 3: Build infrastructure (High priority, parallel with Phase 2)

| # | Item | Why here |
|---|---|---|
| 12 | Add basic test suite (8.1) | Enables safe refactoring for everything else. |
| 13 | Add linting/type checking (8.2) | Catches issues before they become debt. |

## Phase 4: Migrate remaining services (High priority, after Phase 1–2)

| # | Item | Why here |
|---|---|---|
| 14 | Migrate `ScriptService` → `ScriptOperator` | Requires consolidated `BaseProvider` (6.1). |
| 15 | Migrate `StoryboardService` → `StoryboardOperator` | Same dependency. |
| 16 | Migrate `ImagePromptService` → `ImagePromptOperator` | Same dependency. |
| 17 | Delete `core/ai/ai_engine.py` and related legacy files | After all services are migrated. |

## Phase 5: Polish (Low priority, after v0.1)

| # | Item | Why last |
|---|---|---|
| 18 | Implement missing providers (4.1) | Only when users need non-Gemini providers. |
| 19 | Implement service integrations (4.2) | ElevenLabs, Leonardo, etc. are post-v0.1 features. |
| 20 | Add response caching (7.3) | Optimization, not correctness. |
| 21 | Delete `core/theme.py` (1.5) | Cosmetic. |
| 22 | Populate asset directories (4.8) | When custom assets are designed. |

---

# Debt Summary by Count

| Category | Count | High | Medium | Low |
|---|---|---|---|---|
| Duplicate Code | 6 | 2 | 4 | 0 |
| Dead Code | 7 | 0 | 2 | 5 |
| Legacy Architecture | 3 | 2 | 1 | 0 |
| Placeholder Modules | 8 | 0 | 0 | 8 |
| Potential Bugs | 5 | 1 | 2 | 2 |
| Architectural Inconsistencies | 6 | 1 | 3 | 2 |
| Performance Issues | 3 | 0 | 0 | 3 |
| Missing Infrastructure | 3 | 1 | 1 | 1 |
| **Total** | **41** | **7** | **13** | **21** |

The 7 High-priority items should be resolved before v0.1 is considered complete.
