# ARCHITECTURE.md

# KaiMi Studio Architecture

Version: 0.1

---

# Architecture Philosophy

KaiMi Studio follows a modular architecture.

Every module has ONE responsibility.

No module should own responsibilities that belong to another module.

---

# Core Workflow

Project

↓

Workspace

↓

Research

↓

Script

↓

Storyboard

↓

Image Prompt Generator

↓

Export

---

# Module Responsibilities

## Project Manager

Responsible for:

- Create Project
- Open Project
- Delete Project
- Save Metadata
- Load Metadata

Must NOT contain UI logic.

---

## Workspace

Responsible for:

- Active Project
- Current Session
- Workflow State

Must NOT generate content.

---

## Dashboard

Responsible for:

- Display information
- Launch projects
- Show recent projects

Must NOT contain business logic.

---

## Sidebar

Responsible for:

- Navigation

Nothing else.

---

## Research

Responsible for:

- Research data
- Saving research
- Loading research

---

## Script

Responsible for:

- Script editing
- Script saving
- Script loading

---

## Storyboard

Responsible for:

- Storyboard data
- Storyboard editing
- Storyboard saving

---

## Image Prompt Generator

Responsible for:

- Prompt generation
- Prompt editing
- Prompt saving

---

## Export

Responsible for:

- TXT export
- JSON export
- Future export formats

Must NEVER modify project data.

---

## AI Engine

Responsible for:

- AI Providers
- Prompt execution
- AI communication

Must NEVER contain UI.

---

## Settings

Responsible for:

- User preferences
- Application configuration
- API Keys

---

## Logger

Responsible for:

- Logging
- Debugging
- Error reports

---

## Workflow Engine

Responsible for:

- Workflow progression
- Module coordination
- Navigation state

---

# Layer Rules

UI

↓

Services

↓

Core Logic

↓

Data

Never reverse this direction.

---

# Communication Rules

Modules communicate through their public interfaces.

Avoid direct dependencies whenever possible.

Avoid circular imports.

---

# Data Ownership

Project Manager

owns

Project Files

Research Module

owns

Research Data

Script Module

owns

Script Data

Storyboard Module

owns

Storyboard Data

Prompt Generator

owns

Prompt Data

Export Module

reads data

It does NOT own data.

---

# Design Rules

Keep modules independent.

Keep files small.

Avoid duplicate logic.

Prefer composition over duplication.

Business logic belongs outside UI.

---

# Future Rule

New features should extend existing modules before creating new ones.

Only create new modules when a completely new responsibility exists.

---

# Golden Rule

Every file should answer one question:

"What is my responsibility?"

If the answer contains multiple unrelated responsibilities,

the design should be reconsidered.