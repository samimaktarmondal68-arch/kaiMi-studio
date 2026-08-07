import json
import sys
import time
from pathlib import Path

_root = Path(__file__).resolve().parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from PySide6.QtWidgets import QApplication

from core.logger import get_logger
from core.crash_handler import install_crash_handler
from core.settings import AppSettings

CRITICAL_ASSETS = ["resources/branding/app_icon.png", "resources/branding/logo.png"]
CRITICAL_CONFIGS = ["config/providers.json"]


def _verify_integrity(log) -> bool:
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
    from core.version import APP_NAME, VERSION, AUTHOR, OFFICIAL_EMAIL
    if not APP_NAME or not VERSION or not AUTHOR or not OFFICIAL_EMAIL:
        log.error("Integrity", "Version metadata is incomplete.")
        all_ok = False
    if not all_ok:
        log.warning("Integrity", "Some integrity checks failed.")
    return all_ok


def _shutdown() -> None:
    """Flush pending autosaves, then stop the autosave timers.

    flush_all() must run before shutdown() so edits still inside the debounce
    window are persisted instead of being discarded (Sprint 3.4B / C1).
    """
    from core.autosave import get_autosave_manager
    manager = get_autosave_manager()
    manager.flush_all()
    manager.shutdown()


def main():
    install_crash_handler()
    log = get_logger()

    from core.version import APP_NAME, APP_NAME_SHORT, VERSION

    log.startup(f"{APP_NAME} v{VERSION} launching (Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro})")
    log.startup(f"Executable: {sys.executable}")
    log.startup(f"CWD: {Path.cwd()}")

    _verify_integrity(log)

    t0 = time.perf_counter()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(VERSION)
    app.setOrganizationName(APP_NAME_SHORT)

    from core.branding import app_icon
    app.setWindowIcon(app_icon())

    from ui.main_window import MainWindow

    log.startup("UI modules loaded")

    window = MainWindow()
    window.show()

    elapsed = time.perf_counter() - t0
    log.startup(f"Window created in {elapsed:.2f}s")
    log.info("App", "Application ready")

    settings = AppSettings()
    if settings.is_first_run():
        from ui.dialogs import FirstRunDialog

        def _on_first_run_close():
            settings.mark_not_first_run()

        dlg = FirstRunDialog(window, on_close=_on_first_run_close)
        dlg.exec()

    def _on_quit():
        log.shutdown("Application closed")
        _shutdown()

    app.aboutToQuit.connect(_on_quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
