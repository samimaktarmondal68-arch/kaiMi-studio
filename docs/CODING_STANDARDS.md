# KaiMi Studio Coding Standards

## Architecture Rules

### Rule 1: No Business Logic in UI

**Why:** Business logic in UI cannot be unit tested, cannot be reused, and creates threading hazards.

```python
# WRONG
class ScriptPage(QWidget):
    def _on_generate(self):
        response = requests.post("https://api.openai.com/...", json={...})
        # Now this page knows about HTTP, API keys, and OpenAI's API format

# CORRECT
class ScriptPage(QWidget):
    def generate_script(self):
        request = ScriptRequest(topic=self._topic)
        self.task_manager.run_task(
            task_func=lambda tm: self.operator.execute(request),
            on_complete=self._on_script_ready,
        )
```

### Rule 2: Never Import Pages from Core

**Why:** Prevents circular imports. Core is the foundation — it must not depend on UI.

```
core/          →  (nothing outside core)
ui/            →  core/
operators/     →  providers/, core/
providers/     →  (nothing outside providers/)
```

### Rule 3: Never Import Providers Directly from Pages

**Why:** Pages should not know which provider is active. `ProviderManager` is the only gateway.

```python
# WRONG — in a page
from providers.gemini_provider import GeminiProvider

# CORRECT — go through Operator → ProviderManager
from operators.script.operator import ScriptOperator
```

## Code Style Rules

### Rule 4: Type Hints Required

**Why:** Type hints catch bugs at development time and make the code self-documenting.

```python
def create_project(self, name: str, topic: str, platform: str = "Long Form") -> Path:
```

All public methods and functions must have type hints for parameters and return values.

### Rule 5: Docstrings for Public Methods

**Why:** Explains purpose, parameters, return values, and raised exceptions.

```python
def generate(self, request: GenerationRequest) -> GenerationResponse:
    """Generate a text response for the given request.

    Args:
        request: Standard generation request with prompt and parameters.

    Returns:
        Standard generation response with text and usage metadata.

    Raises:
        ProviderNotConfiguredError: If no provider is configured.
        RateLimitedError: If rate-limited by the provider.
    """
```

### Rule 6: Consistent Import Ordering

**Why:** Predictable imports make it easy to find dependencies.

Order: 1) stdlib → 2) third-party → 3) project modules. One blank line between groups.

```python
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from core.project_manager import ProjectManager
from ui.theme_pyside import ThemeManager
```

### Rule 7: Descriptive Naming

**Why:** Code is read far more often than it is written.

| Element | Convention | Example |
|---|---|---|
| Classes | PascalCase | `ScriptOperator`, `ProjectManager` |
| Functions/Methods | snake_case | `generate_script()`, `load_project()` |
| Variables | snake_case | `project_name`, `workflow_state` |
| Constants | UPPER_CASE | `WORKFLOW_STAGES`, `FAILOVER_SEQUENCE` |
| Private methods | `_` prefix | `_validate_request()`, `_build()` |
| Protected attributes | `_` prefix | `_config`, `_initialized` |
| Dunder methods | `__` prefix | `__init__`, `__new__` |

## UI Rules

### Rule 8: Never Hardcode Colors

**Why:** Hardcoded colors break when the theme is switched. Every color must come from ThemeManager.

```python
# WRONG
label.setStyleSheet("color: #22C55E; font-weight: bold;")

# CORRECT
c = ThemeManager.instance().colors()
label.setStyleSheet(f"color: {c.PRIMARY}; font-weight: bold;")
```

### Rule 9: Use Reusable Widgets

**Why:** Consistency across the application is impossible when every page creates its own button styles.

Always use `ModernButton`, `ModernCard`, `HeaderLabel`, `SectionLabel`, `BodyLabel`, `MutedLabel`, `ProgressWidget`, and `SearchInput` from `ui/widgets/__init__.py`. If you need a new widget, add it there.

### Rule 10: Keep Pages Under 200 Lines

**Why:** A page that handles UI layout, data loading, user interaction, and background task coordination becomes unreadable beyond ~200 lines.

Extract reusable components. If logic grows complex, consider whether it belongs in an operator or service.

## File Organization Rules

### Rule 11: One Class Per File (for Pages)

**Why:** Each page file (`ui/pages/*.py`) should contain exactly one page class. This makes navigation predictable.

Exception: Small widgets in `ui/widgets/__init__.py` can co-exist in one file because they are tightly coupled.

### Rule 12: Private Methods Use Underscore Prefix

**Why:** Signals that a method is internal and should not be called from outside the class.

```python
class ScriptPage(QWidget):
    def generate_script(self):       # Public API
        self._start_animation()

    def _start_animation(self):      # Internal
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
```

### Rule 13: No Duplicate Code

**Why:** Every piece of logic should have one authoritative location. Duplicate code is a maintenance liability.

When you find yourself copying code a second time, extract it into a shared function, method, or widget.

## Error Handling Rules

### Rule 14: Handle Expected Errors Gracefully

**Why:** The application must never crash on bad user input, missing files, or network failures.

```python
try:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
except (OSError, json.JSONDecodeError):
    return {"prompts": []}
```

### Rule 15: Never Silence Exceptions

**Why:** Bare `except: pass` hides bugs. If you must catch a broad exception, log it.

```python
# WRONG
try:
    risky_operation()
except:
    pass

# CORRECT
try:
    risky_operation()
except Exception as e:
    get_logger().error("Component", f"Operation failed: {e}")
```

## Testing Rules

### Rule 16: Write Tests for Operators and Services

**Why:** The business logic in operators and core services is the most critical code. UI code is harder to test.

Focus tests on:
- Operator validation and execution
- Service CRUD operations
- Workflow state transitions
- Export formatting
- Error handling paths

### Rule 17: Verify Before Committing

Before every commit, verify:
1. `pytest` passes (or relevant tests pass)
2. Application launches without errors
3. All pages render correctly
4. Theme switching works (Dark ↔ Light)
5. No new warnings in the console