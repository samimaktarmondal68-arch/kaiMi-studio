# Changelog Guide

## Structure

Every changelog entry follows this structure:

```markdown
## [<version>] — <YYYY-MM-DD> — "<codename>"

### Added
- New features

### Changed
- Changes to existing functionality

### Fixed
- Bug fixes

### Removed
- Removed features

### Deprecated
- Features soon to be removed

### Security
- Security fixes
```

## Categories

### Added
New features that did not previously exist.

```
### Added
- **Application Branding** — Official .ico icon, window icon, professional about page
- **Production Logging** — Structured logging to application.log, errors.log, startup.log
```

### Changed
Changes to existing functionality that are not bug fixes and not new features.

```
### Changed
- **Error Handling** — All storage classes now handle OSError gracefully
- **Code Quality** — Deduplicated storage paths, removed dead code
```

### Fixed
Bug fixes that correct incorrect behavior.

```
### Fixed
- Export now handles special characters in project names
- Theme persistence across application restarts
```

### Removed
Features that are no longer available.

```
### Removed
- Deprecated CustomTkinter theme toggle (replaced by ThemeManager)
```

### Deprecated
Features that are still available but will be removed in a future version.

```
### Deprecated
- Legacy project format (v0.3)
```

### Security
Security fixes, vulnerability patches, hardening.

```
### Security
- **Proprietary License** — Replaced MIT license with full proprietary license
- **Secret Protection** — API keys masked in logs and crash reports
- **Path Traversal Protection** — All project file operations validate paths
```

## Style Rules

1. **Bold the feature area** — Makes scanning easier: `- **Export System** — New TXT export format`
2. **One line per change** — Each bullet describes one logical change
3. **User-focused language** — Describe what the user experiences, not the implementation
4. **Past tense for changes** — "Added", "Fixed", not "Adds", "Fixes"
5. **Group related changes** — All export changes in one section, all UI in another
6. **No implementation details** — Say "Export now supports PDF" not "Added reportlab dependency and PDF renderer"

## Full Example

```markdown
## [1.1.0] — 2026-08-15

### Added
- **Research Stage** — Automatic research before script generation
- **Storyboard Stage** — Visual scene planning before image prompts
- **PDF Export** — Export projects as formatted PDF documents
- **SRT Export** — Export transcripts as subtitle files

### Changed
- **Export Dialog** — Redesigned with format selection and preview

### Fixed
- **Script Regeneration** — No longer resets unsaved edits without warning
- **Voice Upload** — Handles filenames with special characters correctly

### Security
- **API Key Storage** — Keys now encrypted at rest in providers.json
```