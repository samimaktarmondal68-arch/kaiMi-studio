# DEVELOPMENT_RULES.md

# KaiMi Studio Development Rules

Version: 0.1

---

# Goal

Every development session should produce measurable progress toward a working engine.

No coding session should end without completing a defined task.

---

# Workflow

1. Open ENGINE_STATUS.md
2. Choose the first unfinished item
3. Create a task from TASK_TEMPLATE.md
4. Implement only that task
5. Test the feature
6. Commit the changes
7. Mark the task complete
8. Repeat

---

# One Task Rule

Each task should solve ONE problem.

Avoid combining unrelated features into a single implementation.

---

# Commit Rules

Each commit should represent one logical improvement.

Examples:

✔ Add project creation

✔ Fix project loading

✔ Implement research saving

Avoid commits like:

"Updated everything"

---

# Testing Rule

Before marking a task complete:

- Feature works
- No crashes
- Existing functionality still works
- No syntax errors

---

# Refactoring Rule

Do not refactor code unless:

- It blocks the current task
- It fixes a bug
- It improves maintainability without changing behavior

---

# Feature Rule

Every new feature must answer:

Does this improve the creator workflow?

If not, move it to the backlog.

---

# Bug Rule

Bugs have higher priority than polish.

Working software beats beautiful software.

---

# Version 0.1 Scope

Focus only on:

- Project Management
- Research
- Script
- Storyboard
- Image Prompt Generation
- Export
- Save / Load

Everything else is postponed.

---

# Done Criteria

A task is complete only if:

- Implementation finished
- Tested
- Stable
- Documented (if necessary)
- ENGINE_STATUS updated

---

# Golden Rule

Progress > Perfection

A small completed feature is always better than a large unfinished one.