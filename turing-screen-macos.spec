# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec of the macOS app "Turing Screen.app": system monitor + fun mode + configuration, in the menu bar.
# Build with tools/build-macos-app.sh. Only 3.5" themes and the fonts they use are bundled, to keep the app light.

import ast
from pathlib import Path

import yaml
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)
DISPLAY_SIZE = '3.5"'

# Scripts run by the launcher (turing-screen-app.py) with runpy: bundled as plain files, not analysed as entry points
SCRIPTS = ["main.py", "fun.py", "configure.py", "theme-editor.py"]

# Fonts used in code without being named in a theme (NotoColorEmoji: configure.py button icons on macOS/Linux)
CODE_FONTS = {"roboto", "roboto-mono", "jetbrains-mono", "NotoColorEmoji"}

# Windows / Linux only modules imported by the scripts
PLATFORM_EXCLUDES = ["win32api", "win32con", "win32gui", "pywinstyles", "clr", "pythonnet", "pyadl", "pyamdgpuinfo"]


def _theme_fonts(node, fonts):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "FONT" and isinstance(value, str):
                fonts.add(value.split("/")[0])
            _theme_fonts(value, fonts)
    elif isinstance(node, list):
        for value in node:
            _theme_fonts(value, fonts)


def themes_and_fonts():
    themes, fonts = [], set(CODE_FONTS)
    for theme in sorted((ROOT / "res/themes").iterdir()):
        theme_file = theme / "theme.yaml"
        if not theme_file.is_file():
            continue
        data = yaml.safe_load(theme_file.read_text(encoding="utf8")) or {}
        if (data.get("display") or {}).get("DISPLAY_SIZE", '3.5"') == DISPLAY_SIZE:
            themes.append(theme)
            _theme_fonts(data, fonts)
    _theme_fonts(yaml.safe_load((ROOT / "res/themes/default.yaml").read_text(encoding="utf8")), fonts)
    return themes, sorted(fonts)


def script_imports():
    """Top-level modules imported by the bundled scripts, so that PyInstaller collects them"""
    modules = set()
    for script in SCRIPTS:
        for node in ast.walk(ast.parse((ROOT / script).read_text(encoding="utf8"))):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                modules.add(node.module)
    return sorted(m for m in modules if m.split(".")[0] not in PLATFORM_EXCLUDES)


themes, fonts = themes_and_fonts()

datas = [(str(ROOT / script), ".") for script in SCRIPTS]
datas += [(str(ROOT / "config.yaml"), ".")]
datas += [(str(path), "res/themes") for path in (ROOT / "res/themes").iterdir() if path.is_file()]
datas += [(str(theme), f"res/themes/{theme.name}") for theme in themes]
datas += [(str(ROOT / "res/fonts" / font), f"res/fonts/{font}") for font in fonts]
datas += [(str(ROOT / "res/icons"), "res/icons")]
datas += [(str(ROOT / "res/backgrounds/circular-mask.png"), "res/backgrounds")]
datas += [(str(ROOT / "res/docs" / name), "res/docs") for name in ("no-preview.png", "error-in-theme.png")]

hiddenimports = script_imports()
hiddenimports += collect_submodules("library", filter=lambda name: "librehardwaremonitor" not in name)

# Same name as library/lcd/lcd_comm_rev_a_usb.py BUNDLED_LIBUSB, found there through sys._MEIPASS
binaries = [("/opt/homebrew/lib/libusb-1.0.0.dylib", ".")]

print(f"Bundling {len(themes)} themes ({DISPLAY_SIZE}) and fonts: {', '.join(fonts)}")

a = Analysis(
    ["turing-screen-app.py"],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=PLATFORM_EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Turing Screen",
    console=False,
    argv_emulation=False,
    icon=str(ROOT / "res/icons/monitor-icon-17865/icon.icns"),
)

coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Turing Screen")

app = BUNDLE(
    coll,
    name="Turing Screen.app",
    icon=str(ROOT / "res/icons/monitor-icon-17865/icon.icns"),
    bundle_identifier="io.github.tapsu01.turing-screen",
    info_plist={
        "CFBundleDisplayName": "Turing Screen",
        "CFBundleShortVersionString": "1.0.0",
        "LSUIElement": True,  # Menu bar only, no Dock icon
        "NSHighResolutionCapable": True,
    },
)
