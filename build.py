# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Build script for KaiMi Studio.

Creates a production-hardened Windows executable using PyInstaller.

Usage:
    python build.py              # Build in dist/
    python build.py --clean      # Clean previous builds first
    python build.py --onefile    # Single-file executable
"""

import compileall
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import APP_NAME, VERSION

DIST = ROOT / "dist"
BUILD = ROOT / "build"


def write_release_metadata():
    """Regenerate build resources from core.version (single source of truth).

    ``file_version_info.txt``, ``installer_metadata.iss``, and
    ``build_manifest.json`` are derived artifacts and must never be
    hand-edited — always regenerate them through this function.
    """
    from core.version import (
        render_iss_defines,
        render_manifest_json,
        render_version_info,
    )
    (ROOT / "file_version_info.txt").write_text(render_version_info(), encoding="utf-8")
    (ROOT / "installer_metadata.iss").write_text(render_iss_defines(), encoding="utf-8")
    (ROOT / "build_manifest.json").write_text(render_manifest_json(), encoding="utf-8")
    print(
        "Release metadata regenerated: "
        "file_version_info.txt, installer_metadata.iss, build_manifest.json"
    )


def write_branding_icon():
    """Regenerate all derived branding assets from the official logo.

    Produces app_icon.ico (consumed by PyInstaller and the Inno installer)
    and the two Inno Setup wizard bitmaps. These are build-time-only
    artifacts: the running app uses app_icon.png / logo.png directly. All
    are kept fresh from the single branding source so a swapped official
    logo is always picked up without touching build code.
    """
    # generate_icon.py already fails loudly with a Pillow install hint.
    from generate_icon import ensure_app_icon_ico, ensure_installer_wizard_images
    ensure_app_icon_ico()
    ensure_installer_wizard_images()


def clean():
    """Remove previous build artifacts."""
    for d in [DIST, BUILD]:
        if d.exists():
            shutil.rmtree(d)
            print(f"Cleaned: {d}")
    for f in ROOT.glob("*.spec"):
        if f.name != f"{APP_NAME}.spec":
            f.unlink()
    print("Clean complete.")


def compile_bytecode():
    """Compile all .py files to .pyc bytecode before packaging."""
    print("Compiling bytecode...")
    count = compileall.compile_dir(
        str(ROOT), quiet=1, force=True,
        rx=re.compile(r'(__pycache__|\.venv|dist|build|\.git)'),
    )
    print(f"Compiled {count} files.")


def build(onefile: bool = False):
    """Run PyInstaller with production hardening."""
    os.environ["PYTHONDONTWRITEBYTECODE"] = "0"

    write_release_metadata()
    write_branding_icon()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        # The committed "KaiMi Studio.spec" is the reviewed, centralized
        # configuration (identity via core.version, branding via
        # resources/branding). PyInstaller always writes a generated spec
        # next to the build, so divert it into build/ to keep the committed
        # spec intact and reproducible.
        "--specpath", str(BUILD),
        "--name", APP_NAME,
        "--windowed",
        "--icon", str(ROOT / "resources" / "branding" / "app_icon.ico"),
        "--version-file", str(ROOT / "file_version_info.txt"),
        # Absolute source paths: the generated spec is written into build/
        # (--specpath) and PyInstaller resolves relative data sources against
        # the spec's own directory.
        "--add-data", f"{ROOT / 'resources'}{os.pathsep}resources",
        "--add-data", f"{ROOT / 'config'}{os.pathsep}config",
        "--strip",
        "--exclude-module", "tkinter.test",
        "--exclude-module", "unittest",
        "--exclude-module", "test",
        # distutils is intentionally NOT excluded: on Python 3.12+ it is
        # only a setuptools shim and PyInstaller's hook-distutils aliases
        # it; excluding it makes that hook raise "already imported as
        # ExcludedModule" and abort the release build.
        "--exclude-module", "setuptools",
        "--exclude-module", "pip",
        "--exclude-module", "pytest",
        "--exclude-module", "_pytest",
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
        "--hidden-import", "core.research_storage",
        "--hidden-import", "core.script_storage",
        "--hidden-import", "core.storyboard_storage",
        "--hidden-import", "core.image_prompt_storage",
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
        "--hidden-import", "ui.global_search",
        "--hidden-import", "providers.provider_manager",
        "--hidden-import", "providers.registry",
        "--hidden-import", "providers.base_provider",
        "--hidden-import", "providers.exceptions",
        "--hidden-import", "providers.models",
        "--hidden-import", "providers.gemini_provider",
        "--hidden-import", "providers.opencode_provider",
        "--hidden-import", "operators.research.operator",
        "--hidden-import", "operators.research.prompt_builder",
        "--hidden-import", "operators.research.critic",
        "--hidden-import", "operators.script.operator",
        "--hidden-import", "operators.script.prompt_builder",
        "--hidden-import", "operators.script.models",
        "--hidden-import", "operators.storyboard.operator",
        "--hidden-import", "operators.storyboard.prompt_builder",
        "--hidden-import", "operators.storyboard.parser",
        "--hidden-import", "operators.storyboard.models",
        "--hidden-import", "operators.image_prompt.operator",
        "--hidden-import", "operators.image_prompt.prompt_builder",
        "--hidden-import", "operators.image_prompt.parser",
        "--hidden-import", "operators.image_prompt.models",
        "main.py",
    ]

    if onefile:
        cmd.insert(cmd.index("main.py"), "--onefile")

    print(f"Building {APP_NAME} v{VERSION} (production)...")
    print(f"Command: {' '.join(cmd[-5:])}")
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode == 0:
        exe_path = DIST / APP_NAME / f"{APP_NAME}.exe"
        if not exe_path.exists():
            exe_path = DIST / f"{APP_NAME}.exe"
        print(f"\nBuild successful!")
        print(f"Output: {exe_path}")
        print(f"Build is production-hardened with bytecode compilation and symbol stripping.")
    else:
        print(f"\nBuild failed with exit code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--clean" in args:
        clean()

    if "--compile" in args:
        compile_bytecode()

    onefile = "--onefile" in args
    build(onefile=onefile)
