# -*- mode: python ; coding: utf-8 -*-
"""KaiMi Studio — PyInstaller build specification.

This is the documented, centralized PyInstaller configuration (see
docs/BUILD_REPRODUCIBILITY.md). Identity and branding are never hardcoded
here: the product name comes from ``core.version`` (the single source of
truth) and the executable icon comes from ``resources/branding`` (the
single branding source). ``build.py`` regenerates the derived branding
assets before invoking PyInstaller, and the on-disk ``file_version_info.txt``
provides the Windows version resources.

PyInstaller writes a generated spec next to the build invocation; build.py
directs that artifact into ``build/`` (via ``--specpath``) so this committed
spec remains the stable, reviewed configuration.
"""
from pathlib import Path

from core.version import APP_NAME

#: Directory that contains this spec file (provided by PyInstaller).
ROOT = Path(SPECPATH)

a = Analysis(
    ['main.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[('resources', 'resources'), ('config', 'config')],
    hiddenimports=[
        'core.theme',
        'core.version',
        'core.settings',
        'core.logger',
        'core.crash_handler',
        'core.project_manager',
        'core.export_service',
        'core.history_manager',
        'core.notifications',
        'core.shortcuts',
        'core.task_manager',
        'core.workflow',
        'core.research_storage',
        'core.script_storage',
        'core.storyboard_storage',
        'core.image_prompt_storage',
        'ui.home',
        'ui.sidebar',
        'ui.dashboard',
        'ui.projects',
        'ui.workspace',
        'ui.templates',
        'ui.export',
        'ui.settings_page',
        'ui.about',
        'ui.whats_new',
        'ui.dialogs',
        'ui.global_search',
        'providers.provider_manager',
        'providers.registry',
        'providers.base_provider',
        'providers.exceptions',
        'providers.models',
        'providers.gemini_provider',
        'providers.opencode_provider',
        'operators.research.operator',
        'operators.research.prompt_builder',
        'operators.research.critic',
        'operators.script.operator',
        'operators.script.prompt_builder',
        'operators.script.models',
        'operators.storyboard.operator',
        'operators.storyboard.prompt_builder',
        'operators.storyboard.parser',
        'operators.storyboard.models',
        'operators.image_prompt.operator',
        'operators.image_prompt.prompt_builder',
        'operators.image_prompt.parser',
        'operators.image_prompt.models',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter.test',
        'unittest',
        'test',
        # distutils is intentionally NOT excluded: on Python 3.12+ it is
        # only a setuptools shim and PyInstaller's hook-distutils aliases
        # it; excluding it makes that hook raise "already imported as
        # ExcludedModule" and abort the release build.
        'setuptools',
        'pip',
        'pytest',
        '_pytest',
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(ROOT / 'file_version_info.txt'),
    icon=[str(ROOT / 'resources/branding/app_icon.ico')],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=True,
    upx_exclude=[],
    name=APP_NAME,
)
