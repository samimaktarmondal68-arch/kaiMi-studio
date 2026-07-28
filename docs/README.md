# KaiMi Studio Documentation

> **AI-powered creative intelligence suite for educational animation production.**

KaiMi Studio is a professional creator workspace — not an AI chatbot. AI is an implementation detail. Creators should think about videos, not models.

## Project Vision

Help creators generate educational animation projects through a structured linear workflow:

```
Project → Script → Voice → Image Prompts → Export
```

## Technology Stack

| Layer | Technology |
|---|---|
| UI Framework | PySide6 (Qt for Python) |
| Window Management | QMainWindow + QStackedWidget |
| AI Providers | Gemini, OpenAI-compatible, Anthropic, Cohere, local models |
| Audio Transcription | OpenAI Whisper |
| Project Storage | JSON files in `projects/` |
| Settings | JSON files in `config/` |
| Logging | Rotating file logs in `logs/` |
| Build | PyInstaller |
| Auth/Config | `providers.json`, `settings.json` |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Launch the application
python main.py
```

## Where to Find Documentation

| Document | Purpose |
|---|---|
| [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | Official handbook — philosophy, workflow, all systems explained |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layered architecture with Mermaid diagrams, dependency rules |
| [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) | Color palette, typography, spacing, components, Light/Dark theme |
| [WORKFLOW.md](WORKFLOW.md) | Creator workflow — inputs, outputs, resume logic |
| [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) | Every folder and its responsibility |
| [CODING_STANDARDS.md](CODING_STANDARDS.md) | 17 coding rules with explanations |
| [CONTRIBUTING.md](CONTRIBUTING.md) | How to add pages, providers, stages — with checklists |
| [RELEASE_PROCESS.md](RELEASE_PROCESS.md) | Release lifecycle and checklists |
| [VERSIONING.md](VERSIONING.md) | Semantic versioning strategy |
| [CHANGELOG_GUIDE.md](CHANGELOG_GUIDE.md) | How to write changelog entries |
| [DECISIONS.md](DECISIONS.md) | Architecture Decision Records (ADRs) |

## Folder Structure Overview

```
kaiMi-studio/
├── core/           # Business logic, services, theme
├── ui/             # PySide6 pages, widgets, dialogs
├── providers/      # AI provider abstraction layer
├── operators/      # Business operators (Script, Image Prompt, etc.)
├── projects/       # User project data (JSON files)
├── config/         # Application configuration
├── logs/           # Rotating log files
├── tests/          # Integration and performance tests
├── assets/         # Icons, branding assets
└── docs/           # Developer documentation
```