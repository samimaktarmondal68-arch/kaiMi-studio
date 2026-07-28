# KaiMi Studio Project Structure

## Top-Level Directory

```
kaiMi-studio/
├── core/              Business logic, services, theme, workflow
├── ui/                PySide6 UI layer — pages, widgets, dialogs
├── providers/         AI provider abstraction layer
├── operators/         Business operators (Script, Image Prompt, etc.)
├── projects/          User projects (created at runtime)
├── config/            Application configuration
├── logs/              Rotating log files (created at runtime)
├── tests/             Integration and performance tests
├── assets/            Icons, branding assets
├── docs/              Developer documentation
├── build/             Build output (created by build.py)
├── dist/              Distribution packages (created by PyInstaller)
├── release/           Release artifacts
├── exports/           Export output directory
├── main.py            Application entry point
├── build.py           Build script
├── requirements.txt   Python dependencies
└── CHANGELOG.md       Release changelog
```

## `core/` — Business Logic Layer

```
core/
├── __init__.py
├── theme.py              Design tokens: Dark/Light colors, Fonts, Spacing, Radius
├── project_manager.py    Project CRUD: create, load, update, delete, search, sort, filter
├── workflow.py           Stage state machine: LOCKED/AVAILABLE/COMPLETED, resume logic
├── script_storage.py     Save/load script.json for projects
├── image_prompt_storage.py  Save/load image_prompts.json for projects
├── export_service.py     Gather all stage data and export as TXT
├── settings.py           AppSettings singleton — persistent app config
├── task_manager.py       Background task execution with queue, cancel, retry
├── history_manager.py    Version snapshot system with restore/compare/delete
├── notifications.py      Toast notification service (currently CustomTkinter)
├── logger.py             Production logger with rotating files and secret masking
├── crash_handler.py      Global sys.excepthook with crash log and error dialog
├── shortcuts.py          Keyboard shortcut bindings
├── version.py            Version string, codename, copyright metadata
├── prompts/              System prompts and rules for AI generation
│   ├── system_prompt.md
│   ├── script_rules.md
│   ├── image_prompt_rules.md
│   └── workflow_rules.md
└── research_storage.py   (reserved) Research data persistence
```

**Key rule:** `core/` never imports from `ui/`, `operators/`, or `providers/`.

## `ui/` — Presentation Layer

```
ui/
├── __init__.py
├── main_window.py        QMainWindow — central navigation hub
├── sidebar.py            Navigation sidebar with global + project items
├── theme_pyside.py       ThemeManager singleton — applies Dark/Light to QPalette
├── pages/                One QWidget per page
│   ├── __init__.py
│   ├── dashboard.py      Dashboard page — greeting, continue, recent, quick actions
│   ├── projects.py       Projects page — card grid, search, sort, filter
│   ├── script_page.py    Script generation and editing
│   ├── voice_page.py     Audio upload and Whisper transcription
│   ├── image_prompts_page.py  Image prompt generation and display
│   ├── export_page.py    Project export
│   └── settings_page.py  Appearance, language, AI provider config
├── widgets/              Reusable UI components
│   └── __init__.py       ModernButton, ModernCard, ProgressWidget, labels, SearchInput
└── dialogs/              Modal dialogs
    └── __init__.py       NewProjectDialog, FirstRunDialog
```

## `providers/` — AI Provider Abstraction

```
providers/
├── __init__.py
├── base_provider.py      ABC: generate(), validate_key(), list_models(), get_capabilities()
├── provider_manager.py   Gateway: selects provider, auto-failover, config management
├── registry.py           ProviderRegistry: maps names → provider classes
├── models.py             Dataclasses: ProviderConfig, GenerationRequest, GenerationResponse
├── exceptions.py         Error classes: ProviderError, RateLimitedError, QuotaExceededError
├── gemini_provider.py    Gemini SDK implementation
├── anthropic_provider.py Anthropic HTTP implementation
├── cohere_provider.py    Cohere HTTP implementation
└── opencode_provider.py  OpenAI-compatible provider (used by 12+ providers)
```

## `operators/` — Business Operators

```
operators/
├── __init__.py
├── script/              Script generation
│   ├── operator.py      ScriptOperator: validate → build prompts → generate
│   ├── models.py        ScriptRequest, ScriptGenerationError
│   └── prompt_builder.py  Prompt construction
├── image_prompt/        Image prompt generation
│   ├── operator.py      ImagePromptOperator
│   ├── models.py        ImagePromptRequest
│   ├── prompt_builder.py  Prompt construction
│   └── parser.py        Parse raw output into structured prompts
├── research/            (reserved) Research operator
│   ├── operator.py
│   ├── prompt_builder.py
│   └── critic.py
└── storyboard/          (reserved) Storyboard operator
    ├── operator.py
    ├── models.py
    ├── prompt_builder.py
    └── parser.py
```

## `projects/` — User Projects (Runtime)

```
projects/
└── <project_name>/
    ├── project.json          Metadata: name, topic, workflow_state, timestamps, favorites
    ├── script.json           Generated script output
    ├── voice.json            Transcript + timestamped segments
    ├── transcript.json       Clean transcript text
    ├── image_prompts.json    Structured image prompts per scene
    ├── audio/                Uploaded audio files
    ├── exports/              Exported TXT files
    └── history/              Version snapshots per stage
        ├── Script/
        ├── Voice/
        └── Image Prompts/
```

## `config/` — Application Configuration

```
config/
├── settings.json         App preferences: theme, window geometry, recent projects
└── providers.json        AI provider config: active provider, API keys, base URLs, models
```

## `logs/` — Runtime Logs

```
logs/
├── application.log       All INFO+ events (rotating, 1 MB × 10 backups)
├── errors.log            ERROR+ events with full tracebacks
├── startup.log           Startup/shutdown lifecycle
└── crash.log             Unhandled exception reports with sanitized secrets
```

## `tests/` — Automated Tests

```
tests/
├── test_integration.py   78 integration tests covering core workflows
└── perf_measure.py       Performance benchmarking
```

## `assets/` — Static Assets

```
assets/
└── icons/
    ├── kaimi.ico         Application icon (Windows)
    └── ...               Other asset files
```

## Folder Responsibility Summary

| Directory | Responsibility | Imports From |
|---|---|---|
| `core/` | Business logic, services | stdlib, PySide6 |
| `ui/` | Rendering, user input | core/, operators/ |
| `providers/` | AI provider abstraction | (nothing outside) |
| `operators/` | Business operations | providers/, core/ |
| `config/` | Configuration storage | (read by core/settings.py) |
| `projects/` | User data | (read/written by core/) |
| `logs/` | Log output | (written by core/logger.py) |
| `tests/` | Automated tests | all modules |