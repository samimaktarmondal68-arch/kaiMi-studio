# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Global crash handler for KaiMi Studio.

Catches unhandled exceptions, logs them with full tracebacks,
and shows a user-friendly error dialog instead of a raw Python
traceback window.

Crash logs are sanitized to prevent secret leakage.
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

from core.logger import get_logger, mask_secrets


def _get_log_path() -> str:
    base = Path(__file__).resolve().parent.parent / "logs"
    return str(base / "crash.log")


def _write_crash_log(exc_type, exc_value, exc_tb) -> str:
    """Write full traceback to crash.log. Returns the file path."""
    log_path = _get_log_path()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    tb_text = "".join(tb_lines)

    entry = (
        f"\n{'=' * 72}\n"
        f"CRASH — {timestamp}\n"
        f"Python {sys.version}\n"
        f"Platform: {sys.platform}\n"
        f"CWD: {os.getcwd()}\n"
        f"{'=' * 72}\n"
        f"{tb_text}\n"
    )

    entry = mask_secrets(entry)

    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass

    return log_path


def _show_error_dialog(exc_type, exc_value, log_path: str) -> None:
    """Show a friendly error dialog using tkinter (works even if CustomTkinter fails)."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()

        from core.version import APP_NAME, OFFICIAL_EMAIL

        title = f"{APP_NAME} — Unexpected Error"
        message = (
            f"{APP_NAME} encountered an unexpected error.\n\n"
            f"Error: {exc_type.__name__}: {exc_value}\n\n"
            f"A crash log has been saved to:\n{log_path}\n\n"
            f"Please restart the application.\n"
            f"If this problem persists, report the issue with the crash log "
            f"to {OFFICIAL_EMAIL}."
        )

        messagebox.showerror(title, message)

        root.destroy()
    except Exception:
        pass


def install_crash_handler() -> None:
    """Install the global exception handler."""
    _original_excepthook = sys.excepthook

    def _handle_exception(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        log_path = _write_crash_log(exc_type, exc_value, exc_tb)

        try:
            log = get_logger()
            log.error(
                "CrashHandler",
                f"Unhandled exception: {exc_type.__name__}: {exc_value}",
                exc=exc_value,
            )
        except Exception:
            pass

        _show_error_dialog(exc_type, exc_value, log_path)

    sys.excepthook = _handle_exception


def uninstall_crash_handler() -> None:
    """Restore the original exception handler."""
    sys.excepthook = sys.__excepthook__
