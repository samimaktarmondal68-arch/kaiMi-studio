# Build Reproducibility — KaiMi Studio v1.0.0

## Build Environment

- **OS**: Windows 10/11 (64-bit)
- **Python**: 3.14.6
- **PyInstaller**: 6.21.0
- **Build Script**: `build.py`
- **Spec File**: `KaiMi Studio.spec`

## Build Steps

### Clean Build (Recommended)

```powershell
# 1. Create fresh virtual environment
python -m venv .venv
. .\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt
pip install pyinstaller

# 3. Clean previous builds
python build.py --clean

# 4. Build
python build.py

# 5. Output location
dist\KaiMi Studio\KaiMi Studio.exe
```

### Quick Build

```powershell
python build.py
```

### Single-File Build

```powershell
python build.py --onefile
```

### Build Installer (Inno Setup 6.3+)

The installer (`KaiMiStudio-Setup-{version}.exe`) is compiled from
`installer.iss` with Inno Setup's command-line compiler `ISCC.exe`.

```powershell
# 1. Install Inno Setup 6 (https://jrsoftware.org/isinfo.php) or:
winget install JRSoftware.InnoSetup

# 2. Build the executable first (installer packages dist\KaiMi Studio)
python build.py

# 3. Compile the installer
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

# 4. Output location
installer_output\KaiMiStudio-Setup-1.0.0.exe
```

The installer metadata (`installer_metadata.iss`) and the branded wizard
bitmaps (`resources\branding\installer_wizard.bmp`, `installer_wizard_small.bmp`)
are regenerated automatically by `python build.py` from `core/version.py` and
`resources/branding/logo.png`.

## Build Output

```
dist/
└── KaiMi Studio/
    ├── KaiMi Studio.exe      # Main executable
    ├── _internal/             # Python runtime + dependencies
    │   ├── assets/            # Icons, themes
    │   ├── config/            # Provider config
    │   └── ...                # DLLs, .pyd files
    └── ...
```

## Build Flags

| Flag | Purpose |
|------|---------|
| `--strip` | Remove debug symbols |
| `--optimize=2` | Compile to .pyc with optimization |
| `--windowed` | No console window |
| `--noconfirm` | Overwrite without asking |
| `--clean` | Clean PyInstaller cache |

## Excluded Modules

```
tkinter.test, unittest, test, distutils, setuptools, pip, pytest, _pytest
```

## Reproducibility Notes

1. Pin all dependency versions in `requirements.txt` before building
2. Use a clean virtual environment for each build
3. Run `python build.py --clean` to remove stale artifacts
4. The build is deterministic for the same input files and dependencies

## Release Checklist

- [ ] All tests pass (`pytest tests/ -v`)
- [ ] No unused imports (audit complete)
- [ ] Version matches in `core/version.py` and `file_version_info.txt`
- [ ] API keys cleared from `config/providers.json`
- [ ] `.gitignore` blocks secrets
- [ ] CHANGELOG.md updated
- [ ] README.md accurate
- [ ] Build tested on clean Windows install
- [ ] Code signing applied (if certificate available)
