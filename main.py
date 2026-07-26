"""KaiMi Studio — Entry Point.

Initializes logging, crash handling, settings, and launches the main window.
"""

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


def main():
    install_crash_handler()
    log = get_logger()

    log.startup(f"KaiMi Studio launching (Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro})")
    log.startup(f"Executable: {sys.executable}")
    log.startup(f"CWD: {Path.cwd()}")

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
