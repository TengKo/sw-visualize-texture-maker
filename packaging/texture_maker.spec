# -*- mode: python ; coding: utf-8 -*-
# PyInstaller recipe.  From the repo root:
#   pyinstaller --noconfirm --clean packaging/texture_maker.spec                 -> dist/SW-Visualize-Texture-Maker.exe (one file)
#   set TM_ONEFILE=0 && pyinstaller --noconfirm packaging/texture_maker.spec     -> dist/SW-Visualize-Texture-Maker/ (folder, faster start)
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # noqa: F821 (SPECPATH is set by PyInstaller)
ONEFILE = os.environ.get("TM_ONEFILE", "1") == "1"
NAME = "SW-Visualize-Texture-Maker"
ICON = os.path.join(ROOT, "texture_maker", "assets", "icon.ico")

datas = [
    (os.path.join(ROOT, "texture_maker", "engine", "template", "Material.xml"), os.path.join("texture_maker", "engine", "template")),
    (os.path.join(ROOT, "texture_maker", "assets", "icon.png"), os.path.join("texture_maker", "assets")),
]

excludes = [
    "tkinter", "matplotlib", "IPython", "pytest", "pandas",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtPositioning",
    "PySide6.QtSerialPort", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
]

a = Analysis(  # noqa: F821
    [os.path.join(ROOT, "run.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    excludes=excludes,
    noarchive=False,
)
# Drop Qt pieces the app never uses (they get dragged in by plugins) - keeps the download smaller.
_DROP = ("qt6quick", "qt6qml", "qt6pdf", "qt6virtualkeyboard", "qtvirtualkeyboard", "imageformats/qpdf",
         "imageformats\\qpdf", "qt/translations", "qt\\translations", "opengl32sw")


def _keep(entry):
    dest = entry[0].lower()
    return not any(d in dest for d in _DROP)


a.binaries = [b for b in a.binaries if _keep(b)]
a.datas = [d for d in a.datas if _keep(d)]

pyz = PYZ(a.pure)  # noqa: F821

if ONEFILE:
    exe = EXE(  # noqa: F821
        pyz, a.scripts, a.binaries, a.datas, [],
        name=NAME, icon=ICON, console=False, upx=False, debug=False, strip=False,
        runtime_tmpdir=None, disable_windowed_traceback=False,
    )
else:
    exe = EXE(  # noqa: F821
        pyz, a.scripts, [], exclude_binaries=True,
        name=NAME, icon=ICON, console=False, upx=False, debug=False, strip=False,
    )
    coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False, strip=False)  # noqa: F821
