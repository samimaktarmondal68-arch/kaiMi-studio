# KaiMi Studio

**AI-powered creative intelligence suite for educational animation production.**

Version 1.0.0 "Aurora" | Python 3.10+ | Windows

---

## What is KaiMi Studio?

KaiMi Studio helps creators generate educational animation projects through a structured AI-powered pipeline:

```
Create Project → Research → Script → Storyboard → Image Prompts → Export
```

## Features

- **Multi-Provider AI** — Use Gemini, OpenAI-compatible, or custom AI providers
- **Full Pipeline** — Research, Script, Storyboard, and Image Prompt generation
- **Autosave** — Automatic saves every 30 seconds
- **Global Search** — Find any project with Ctrl+K
- **Multi-Format Export** — TXT, Markdown, JSON, ZIP, DOCX, PDF
- **Version History** — Compare and restore previous versions
- **Keyboard Shortcuts** — Ctrl+N, Ctrl+S, stage navigation with 1-5
- **Dark Theme** — Premium dark UI with consistent design system

## Quick Start

### From Source

```bash
# Clone the repository
git clone https://github.com/kaimi-studio/kaimi-studio.git
cd kaimi-studio

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Launch
python main.py
```

### From Build

1. Download the latest release
2. Extract `KaiMi Studio` folder
3. Run `KaiMi Studio.exe`

## Configuration

### AI Provider Setup

1. Launch the application
2. Go to **Provider Settings** in the sidebar
3. Select your provider (Gemini, OpenAI-compatible, or custom)
4. Enter your API key
5. Click **Test Connection** to verify

### Supported Providers

| Provider | Model | Notes |
|----------|-------|-------|
| Gemini | gemini-2.0-flash | Google AI, free tier available |
| OpenAI | gpt-4o | Requires OpenAI API key |
| Custom | Any | OpenAI-compatible endpoints |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New project |
| Ctrl+S | Save current page |
| Ctrl+Shift+S | Save as |
| Ctrl+K | Global search |
| 1-5 | Switch workflow stage |
| Esc | Close dialogs |

See [SHORTCUTS.md](SHORTCUTS.md) for the complete list.

## Project Structure

```
KaiMi Studio/
├── main.py              # Entry point
├── core/                # Business logic
│   ├── theme.py         # Design system
│   ├── version.py       # Version info
│   ├── settings.py      # App settings
│   ├── logger.py        # Logging system
│   ├── crash_handler.py # Error handling
│   ├── project_manager.py
│   ├── export_service.py
│   ├── history_manager.py
│   ├── notifications.py
│   ├── shortcuts.py
│   ├── task_manager.py
│   └── workflow.py
├── ui/                  # User interface
│   ├── home.py          # Main window
│   ├── sidebar.py       # Navigation
│   ├── dashboard.py     # Dashboard
│   ├── projects.py      # Project list
│   ├── workspace.py     # Stage editor
│   ├── export.py        # Export page
│   ├── settings_page.py # Settings
│   ├── about.py         # About page
│   └── dialogs.py       # Modals
├── providers/           # AI provider abstraction
├── operators/           # AI workflow operators
├── config/              # Configuration files
├── assets/              # Icons, fonts, images
├── projects/            # User projects
├── exports/             # Exported files
├── logs/                # Application logs
└── tests/               # Test suite
```

## Building from Source

```bash
# Install build dependencies
pip install pyinstaller

# Build executable
python build.py

# Output: dist/KaiMi Studio/KaiMi Studio.exe
```

## Requirements

- Python 3.10+
- Windows 10/11 (primary), macOS/Linux (experimental)
- 4 GB RAM minimum
- 100 MB disk space

## License

Copyright 2026 KaiMi. All rights reserved.

## Support

- **Issues**: https://github.com/kaimi-studio/kaimi-studio/issues
- **Documentation**: See `docs/` folder
