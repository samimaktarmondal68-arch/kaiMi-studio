# User Guide

Complete guide to using KaiMi Studio for educational animation production.

---

## Getting Started

### First Launch

When you first open KaiMi Studio, you'll see a welcome dialog explaining the workflow. You can dismiss it and choose "Don't show again" if you're already familiar.

### Setting Up Your AI Provider

Before generating content, configure your AI provider:

1. Click **Settings** in the sidebar
2. Select your provider from the dropdown
3. Enter your API key
4. Click **Test Connection** to verify
5. Click **Save Configuration**

### Creating Your First Project

1. Click **Dashboard** in the sidebar
2. Click the **+ New Project** button
3. Enter:
   - **Project Name** — A unique name for your project
   - **Topic** — What your animation is about
   - **Language** — Output language (English, etc.)
   - **Style** — Educational, Entertainment, Documentary, etc.
4. Click **Create Project**

---

## The Workflow Pipeline

KaiMi Studio guides you through a structured pipeline:

### Stage 1: Research

The AI analyzes your topic and produces:
- Key concepts and facts
- Audience analysis
- Learning objectives
- Content structure

**How to use:**
1. Open your project from the Projects page
2. Click **Research** in the stage selector
3. Click **Generate Research** and wait for completion
4. Review and edit the generated content
5. Click **Save**

### Stage 2: Script

Based on the research, the AI creates a structured script:
- Scene-by-scene breakdown
- Narration text
- Visual cues
- Timing markers

**How to use:**
1. Click **Script** in the stage selector (or press `2`)
2. Click **Generate Script**
3. Review and edit the generated script
4. Click **Save**

### Stage 3: Storyboard

The AI generates visual descriptions for each scene:
- Scene descriptions
- Camera angles
- Character positions
- Background elements

**How to use:**
1. Click **Storyboard** (or press `3`)
2. Click **Generate Storyboard**
3. Review scene descriptions
4. Click **Save**

### Stage 4: Image Prompts

For each scene, the AI creates detailed image generation prompts:
- Art style specifications
- Character descriptions
- Environment details
- Lighting and mood

**How to use:**
1. Click **Image Prompts** (or press `4`)
2. Click **Generate Image Prompts**
3. Copy prompts to your preferred image generator
4. Click **Save**

---

## Project Management

### Viewing Projects

Click **Projects** in the sidebar to see all your projects with:
- Status indicators
- Last modified dates
- Favorite/archive status

### Search and Filter

- Use the search bar to filter projects by name
- Sort by name, date, or status
- Filter by status (Research, Script, etc.)

### Project Actions

Right-click or use the context menu to:
- **Open** — Open in workspace
- **Duplicate** — Create a copy
- **Rename** — Change project name
- **Archive** — Hide from main list
- **Delete** — Permanently remove

### Favorites

Star your important projects to pin them to the top.

---

## Exporting

### Export Options

| Format | Best For |
|--------|----------|
| TXT | Plain text, universal |
| Markdown | Documentation, editing |
| JSON | Data backup, integration |
| ZIP | Complete package |
| DOCX | Microsoft Word |
| PDF | Sharing, printing |

### How to Export

1. Click **Exports** in the sidebar
2. Select the project to export
3. Choose your format
4. Click **Export**
5. Find the exported file in the `exports/` folder

---

## Version History

Every time you save a stage, KaiMi Studio creates a version snapshot.

### Viewing History

1. Open a project in the workspace
2. Click **Version History** in the sidebar
3. Select a stage to view its history

### Comparing Versions

1. Select two snapshots to compare
2. Click **Compare** to see field-by-field differences
3. Review what changed

### Restoring a Version

1. Select the snapshot you want to restore
2. Click **Restore**
3. Confirm the restoration

---

## Settings

Access settings from the sidebar:

### Appearance
- **Theme** — Dark, Light, or System

### AI Provider
- **Provider** — Select your AI backend
- **API Key** — Your authentication key
- **Base URL** — Custom endpoint (for OpenAI-compatible providers)
- **Model** — Select or enter a model name

---

## Tips

- **Autosave** — Your work is saved automatically every 30 seconds
- **Keyboard shortcuts** — Press `Ctrl+K` to instantly search projects
- **Stage navigation** — Press `1-5` to quickly switch between stages
- **Version history** — Save early, save often — you can always go back
- **Export regularly** — Keep backups of your completed work

---

## Troubleshooting

### App won't start
- Check that Python 3.10+ is installed
- Verify all dependencies: `pip install -r requirements.txt`
- Check logs in the `logs/` folder

### AI generation fails
- Verify your API key in Settings
- Check your internet connection
- Ensure your API quota isn't exhausted

### Projects not saving
- Check disk space
- Verify the `projects/` folder exists and is writable
- Check `logs/errors.log` for details

### Export fails
- Ensure `python-docx` is installed for DOCX
- Ensure `reportlab` is installed for PDF
- Check available disk space
