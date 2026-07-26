"""Build script for KaiMi Studio.

Creates a Windows executable using PyInstaller.

Usage:
    python build.py              # Build in dist/
    python build.py --clean      # Clean previous builds first
    python build.py --onefile    # Single-file executable
"""

import subprocess
import sys
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"


def clean():
    """Remove previous build artifacts."""
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
            print(f"Cleaned: {d}")
    for f in ROOT.glob("*.spec"):
        if f.name != "KaiMi Studio.spec":
            f.unlink()
    print("Clean complete.")


def build(onefile: bool = False):
    """Run PyInstaller."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", "KaiMi Studio",
        "--windowed",
        "--icon", str(ROOT / "assets" / "icons" / "kaimi.ico"),
        "--add-data", f"assets{os.pathsep}assets",
        "--add-data", f"config{os.pathsep}config",
        "--hidden-import", "core.theme",
        "--hidden-import", "core.version",
        "--hidden-import", "core.settings",
        "--hidden-import", "core.logger",
        "--hidden-import", "core.crash_handler",
        "--hidden-import", "core.project_manager",
        "--hidden-import", "core.export_service",
        "--hidden-import", "core.history_manager",
        "--hidden-import", "core.notifications",
        "--hidden-import", "core.shortcuts",
        "--hidden-import", "core.task_manager",
        "--hidden-import", "core.workflow",
        "--hidden-import", "ui.home",
        "--hidden-import", "ui.sidebar",
        "--hidden-import", "ui.dashboard",
        "--hidden-import", "ui.projects",
        "--hidden-import", "ui.workspace",
        "--hidden-import", "ui.templates",
        "--hidden-import", "ui.export",
        "--hidden-import", "ui.settings_page",
        "--hidden-import", "ui.about",
        "--hidden-import", "ui.whats_new",
        "--hidden-import", "ui.dialogs",
        "--hidden-import", "ui.assets",
        "--hidden-import", "ui.global_search",
        "--hidden-import", "providers.provider_manager",
        "--hidden-import", "providers.registry",
        "--hidden-import", "providers.base_provider",
        "--hidden-import", "providers.exceptions",
        "--hidden-import", "providers.models",
        "--hidden-import", "providers.gemini_provider",
        "--hidden-import", "providers.opencode_provider",
        "--hidden-import", "operators.research",
        "--hidden-import", "operators.script",
        "--hidden-import", "operators.storyboard",
        "--hidden-import", "operators.image_prompt",
        "main.py",
    ]

    if onefile:
        cmd.insert(cmd.index("main.py"), "--onefile")

    print(f"Building KaiMi Studio...")
    print(f"Command: {' '.join(cmd[-5:])}")
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode == 0:
        exe_path = DIST / "KaiMi Studio" / "KaiMi Studio.exe"
        if not exe_path.exists():
            exe_path = DIST / "KaiMi Studio.exe"
        print(f"\nBuild successful!")
        print(f"Output: {exe_path}")
    else:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    import os
    args = sys.argv[1:]

    if "--clean" in args:
        clean()

    onefile = "--onefile" in args
    build(onefile=onefile)
