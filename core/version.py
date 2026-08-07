# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Application identity and version metadata.

Single source of truth for every version, branding, author, and contact
string used across KaiMi Studio. Every UI page, dialog, error path, and
build resource (Windows version info, Inno Setup installer, build manifest)
must read from this module — never hardcode these values elsewhere.
"""

import json

APP_NAME = "KaiMi Studio"
APP_NAME_SHORT = "KaiMi"

VERSION = "1.0.0"
BUILD = "1"
CODENAME = "Aurora"

#: Release channel (e.g. "Release Candidate", "Stable").
RELEASE_CHANNEL = "Release Candidate"
#: ISO date the build was produced (YYYY-MM-DD).
BUILD_DATE = "2026-08-07"

#: Version of the generation engine this build ships with.
ENGINE_VERSION = "1.0.0"
#: Version of the Script -> Voice -> Image Prompts -> Export workflow.
WORKFLOW_VERSION = "1.0"
#: Version of the on-disk project schema.
SCHEMA_VERSION = "1"

AUTHOR = "Md Samim Aktar Mondal"
#: Publishing entity for the installer and Windows version resources.
#: For this release the author is the publisher.
COMPANY = AUTHOR
OFFICIAL_EMAIL = "kaimistudio07@gmail.com"
YEAR = "2026"
COPYRIGHT = f"\u00A9 {YEAR} {AUTHOR}. All rights reserved."

APP_DESCRIPTION = "AI-assisted educational content production studio."
APP_URL = "https://github.com/kaimi-studio/kaimi-studio"


def build_manifest() -> dict:
    """Return every release metadata field as a flat mapping.

    This is the canonical manifest source. Build resources — the Windows
    version info, the Inno Setup installer defines, and the JSON manifest —
    are all rendered from it (or from the module constants it mirrors).
    """
    return {
        "application": APP_NAME,
        "version": VERSION,
        "build": BUILD,
        "codename": CODENAME,
        "release_channel": RELEASE_CHANNEL,
        "build_date": BUILD_DATE,
        "author": AUTHOR,
        "official_email": OFFICIAL_EMAIL,
        "company": COMPANY,
        "copyright": COPYRIGHT,
        "engine_version": ENGINE_VERSION,
        "workflow_version": WORKFLOW_VERSION,
        "schema_version": SCHEMA_VERSION,
        "app_url": APP_URL,
    }


def render_manifest_json(indent: int = 2) -> str:
    """Render the build manifest as pretty-printed JSON text."""
    return json.dumps(build_manifest(), indent=indent, ensure_ascii=False) + "\n"


def _version_tuple4(version: str) -> tuple:
    """Split a dotted version string into a 4-part numeric tuple."""
    parts = [int(p) for p in str(version).split(".") if p.isdigit()]
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def render_version_info() -> str:
    """Render the PyInstaller VSVersionInfo text for ``file_version_info.txt``.

    All identity values come from this module, so the executable's Windows
    version resources can never drift from the application metadata.
    """
    filever = _version_tuple4(VERSION)
    return (
        "VSVersionInfo(\n"
        "  ffi=FixedFileInfo(\n"
        f"    filevers={filever},\n"
        f"    prodvers={filever},\n"
        "    mask=0x3f,\n"
        "    flags=0x0,\n"
        "    OS=0x40004,\n"
        "    fileType=0x1,\n"
        "    subtype=0x0,\n"
        "    date=(0, 0)\n"
        "  ),\n"
        "  kids=[\n"
        "    StringFileInfo(\n"
        "      [\n"
        "        StringTable(\n"
        "          u'040904B0',\n"
        "          [\n"
        f"            StringStruct(u'CompanyName', u'{COMPANY}'),\n"
        f"            StringStruct(u'FileDescription', u'{APP_NAME}'),\n"
        f"            StringStruct(u'FileVersion', u'{VERSION}.0'),\n"
        "            StringStruct(u'InternalName', u'kaimi_studio'),\n"
        f"            StringStruct(u'OriginalFilename', u'{APP_NAME}.exe'),\n"
        f"            StringStruct(u'ProductName', u'{APP_NAME}'),\n"
        f"            StringStruct(u'ProductVersion', u'{VERSION}.0'),\n"
        f"            StringStruct(u'LegalCopyright', u'{COPYRIGHT}'),\n"
        "          ]\n"
        "        )\n"
        "      ]\n"
        "    ),\n"
        "    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])\n"
        "  ]\n"
        ")\n"
    )


def render_iss_defines() -> str:
    """Render the Inno Setup ``#define`` fragment for ``installer_metadata.iss``.

    ``installer.iss`` includes this generated fragment so the installer's
    name, version, publisher, URL, executable, and copyright always match
    this module.
    """
    return (
        f'#define MyAppName "{APP_NAME}"\n'
        f'#define MyAppVersion "{VERSION}"\n'
        f'#define MyAppPublisher "{COMPANY}"\n'
        f'#define MyAppURL "{APP_URL}"\n'
        f'#define MyAppExeName "{APP_NAME}.exe"\n'
        f'#define MyAppCopyright "{COPYRIGHT}"\n'
    )
