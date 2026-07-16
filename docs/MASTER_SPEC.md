# KaiMi Studio — Master Specification

Version: 1.0

---

# Mission

KaiMi Studio is an AI-powered desktop application designed to automate professional faceless YouTube production from idea to final export.

The software must feel like a premium creative application similar to Notion, Arc Browser, Figma, Adobe Creative Cloud, or Cursor.

This is NOT a prototype.

Every release must be production quality.

---

# Development Philosophy

Never create placeholder code.

Never remove existing functionality.

Never break imports.

Never rewrite unrelated files.

Keep the project modular.

Prefer reusable components.

Every release must compile successfully.

---

# UI Philosophy

Modern

Minimal

Premium

Professional

Fast

Consistent

The interface should feel handcrafted.

Never use default CustomTkinter styling unless explicitly required.

---

# Color System

Primary Background:
#1E1E1E

Secondary Background:
#252526

Cards:
#2D2D30

Accent:
#FF8C00

Hover:
#FFA733

Text:
White

Secondary Text:
#BBBBBB

Borders:
#3C3C3C

---

# Typography

Large headings

Comfortable spacing

Rounded corners

Minimal shadows

Professional desktop layout

---

# Architecture

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

Project Manager

↓

Exports

↓

Assets

---

# Component Rules

Every reusable UI element belongs in /components.

Examples:

Button

Card

Header

Dialog

Input

Stat Card

Scrollable Frame

Icon Button

Never duplicate component logic.

---

# Page Rules

Pages should never contain reusable UI code.

Pages assemble components.

Components provide functionality.

---

# Navigation

Sidebar controls navigation.

Only one page visible at a time.

Navigation must be dynamic.

---

# Project Rules

Projects are managed only through ProjectManager.

Never manually manipulate project folders from UI pages.

---

# Code Quality

PEP8

Clear method names

Type hints where useful

Short methods

Readable classes

Minimal duplication

---

# AI Rules

Before making any change:

Read this document.

Preserve architecture.

Modify only requested files.

Never reduce functionality.

Return working code.

Verify imports.

Verify compilation.

---

End of Specification.