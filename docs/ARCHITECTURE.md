# KaiMi Studio Architecture

Version: 1.0

---

## Overview

KaiMi Studio follows a modular architecture.

The application separates:

- UI
- Components
- Core logic
- Project management
- AI services
- Assets
- Export system

No business logic should exist inside reusable UI components.

---

# Folder Structure

kaiMi-studio/

assets/
core/
docs/
exports/
projects/
ui/

---

# Application Flow

main.py

↓

HomeWindow

↓

Sidebar

↓

Pages

↓

Components

↓

Core Services

↓

ProjectManager

---

# UI Layer

Responsible for:

- Window
- Navigation
- Pages
- Dialogs
- User interaction

No filesystem operations.

No AI logic.

---

# Components

Reusable widgets.

Examples:

Button

Card

Header

Input

Dialog

Stat Card

Scrollable Frame

Icon Button

Pages assemble components.

Components never know about pages.

---

# Core Layer

Responsible for:

ProjectManager

Settings

Theme

Navigation

Workflow

Version

AI Engine

File Management

No UI code.

---

# Project Manager

Only ProjectManager may:

Create projects

Delete projects

Rename projects

Load metadata

Read/write project files

UI never directly edits project folders.

---

# Navigation

Sidebar owns navigation.

Only one page visible.

Pages are dynamically loaded.

Navigation should remain modular.

---

# Future Modules

AI Workspace

Prompt Manager

Timeline

Render Queue

Export Queue

Plugin System

Updater

Analytics

---

End of Architecture.