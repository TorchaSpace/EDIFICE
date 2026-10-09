# -*- mode: python ; coding: utf-8 -*-
# PyInstaller tanımı: macOS (.app) ve Windows (klasör) için ortak. Kullanım: pyinstaller packaging/edifice.spec --noconfirm
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
VERSION = "1.0.0"
mac, win = sys.platform == "darwin", sys.platform.startswith("win")

EXCLUDES = [  # uygulamanın kullanmadığı büyük Qt modülleri
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtQuickWidgets", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtDataVisualization", "PySide6.QtCharts",
    "PySide6.QtBluetooth", "PySide6.QtSensors", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtNetworkAuth",
    "PySide6.QtLocation", "PySide6.QtPositioning", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtOpenGL", "PySide6.QtSvg", "PySide6.QtSvgWidgets", "PySide6.QtRemoteObjects",
    "PySide6.QtSerialPort", "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech", "PySide6.QtScxml", "PySide6.QtStateMachine",
    "tkinter", "matplotlib", "numpy", "pandas", "scipy",
]

a = Analysis([str(ROOT / "main.py")], pathex=[str(ROOT)],
             datas=[(str(ROOT / "edifice" / "assets"), "edifice/assets")],
             hiddenimports=[], excludes=EXCLUDES, noarchive=False)
pyz = PYZ(a.pure)
icon = str(ROOT / "packaging" / ("icon.icns" if mac else "icon.ico"))
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="EDIFICE", console=False, icon=icon,
          disable_windowed_traceback=False, argv_emulation=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="EDIFICE")
if mac:
    app = BUNDLE(coll, name="EDIFICE.app", icon=icon, bundle_identifier="com.edifice.app", version=VERSION,
                 info_plist={"CFBundleDisplayName": "EDIFI'CE", "CFBundleName": "EDIFICE", "NSHighResolutionCapable": True,
                             "LSMinimumSystemVersion": "11.0", "CFBundleShortVersionString": VERSION})
