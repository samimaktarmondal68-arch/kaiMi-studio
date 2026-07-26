# Changelog

All notable changes to KaiMi Studio are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/).

---

## [1.0.0] — 2026-07-26

### Added
- **Application Branding** — Official .ico icon, window icon, professional about page
- **Production Logging** — Structured logging to application.log, errors.log, startup.log
- **Crash Handler** — Global exception handler with friendly error dialog
- **Session Restore** — Window geometry and theme preference persisted across sessions
- **First Run Experience** — Welcome dialog guiding new users through the workflow
- **DOCX Export** — Microsoft Word export via python-docx
- **PDF Export** — PDF export via reportlab
- **Version History** — Snapshot, compare, restore, and delete version history
- **Autosave** — 30-second automatic saves with visual indicator
- **Global Search** — Ctrl+K instant project search
- **Keyboard Shortcuts** — Ctrl+N, Ctrl+S, Ctrl+K, stage navigation 1-5
- **Multi-Provider Support** — Gemini, OpenAI-compatible, custom AI providers
- **Background Tasks** — Non-blocking AI generation with progress updates
- **78 Integration Tests** — Full coverage of core workflows
- **Performance Profiling** — Automated performance benchmarking

### Improved
- **Error Handling** — All storage classes now handle OSError gracefully
- **Code Quality** — Deduplicated storage paths, removed dead code
- **Configuration** — Centralized settings with persistent storage
- **Documentation** — README, CHANGELOG, USER_GUIDE, SHORTCUTS, LICENSE

---

## [0.4.0] — "Aurora" (Alpha)

### Added
- Workflow engine (Research → Script → Storyboard → Image Prompts)
- Project management (create, search, sort, filter, duplicate, rename, archive)
- Export system (TXT, Markdown, JSON, ZIP)
- Provider abstraction layer
- Notification system
- Dark theme design system

---

## [0.3.0] — Initial Development

### Added
- Basic project structure
- AI provider integration
- Core business logic
