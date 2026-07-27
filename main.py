# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""KaiMi Studio — Entry Point.

Initializes logging, crash handling, settings, and launches the main window.
Includes startup integrity verification to detect tampered or missing assets.
"""

import json
import sys
import time
from pathlib import Path

# Ensure project root is on the path
_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from core.logger import get_logger
from core.crash_handler import install_crash_handler
from core.settings import AppSettings


CRITICAL_ASSETS = [
    "assets/icons/kaimi.ico",
]

CRITICAL_CONFIGS = [
    "config/providers.json",
]


def _verify_integrity(log) -> bool:
    """Verify critical application files exist and are valid.

    Returns True if all checks pass, False if critical issues detected.
    """
    all_ok = True

    for asset in CRITICAL_ASSETS:
        path = _root / asset
        if not path.exists():
            log.error("Integrity", f"Missing critical asset: {asset}")
            all_ok = False

    for config in CRITICAL_CONFIGS:
        path = _root / config
        if not path.exists():
            log.warning("Integrity", f"Missing config file (will use defaults): {config}")
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            log.error("Integrity", f"Corrupted config file: {config} ({e})")
            all_ok = False

    from core.version import APP_NAME, VERSION, AUTHOR, COPYRIGHT
    if not APP_NAME or not VERSION or not AUTHOR:
        log.error("Integrity", "Version metadata is incomplete.")
        all_ok = False

    if not all_ok:
        log.warning("Integrity", "Some integrity checks failed. Application may not function correctly.")

    return all_ok


def main():
    install_crash_handler()
    log = get_logger()

    log.startup(f"KaiMi Studio launching (Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro})")
    log.startup(f"Executable: {sys.executable}")
    log.startup(f"CWD: {Path.cwd()}")

    _verify_integrity(log)

    t0 = time.perf_counter()

    from ui.home import HomeWindow

    log.startup("UI modules loaded")

    app = HomeWindow()

    elapsed = time.perf_counter() - t0
    log.startup(f"Window created in {elapsed:.2f}s")
    log.info("App", "Application ready")

    settings = AppSettings()
    if settings.is_first_run():
        from ui.dialogs import FirstRunDialog

        def _on_first_run_close():
            settings.mark_not_first_run()

        FirstRunDialog(app.app, on_close=_on_first_run_close)

    app.run()

    log.shutdown("Application closed")


if __name__ == "__main__":
    main()
