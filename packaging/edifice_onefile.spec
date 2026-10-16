# -*- mode: python ; coding: utf-8 -*-
# Tek dosyalık Windows exe: kurulum ve ek klasör gerektirmez (açılırken geçici klasöre ayıklanır, ilk açılış birkaç sn sürer).
# Kullanım: pyinstaller packaging/edifice_onefile.spec --noconfirm   (çıktı: dist/EDIFICE-portable.exe)
import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent
EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtQuickWidgets", "PySide6.Qt3DCore", "PySide6.Qt3DRender",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets", "PySide6.QtDataVisualization", "PySide6.QtCharts",
    "PySide6.QtBluetooth", "PySide6.QtSensors", "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtNetworkAuth",
    "PySide6.QtLocation", "PySide6.QtPositioning", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
    "PySide6.QtHelp", "PySide6.QtOpenGL", "PySide6.QtSvg", "PySide6.QtSvgWidgets", "PySide6.QtRemoteObjects",
    "PySide6.QtSerialPort", "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech", "PySide6.QtScxml", "PySide6.QtStateMachine",
    "tkinter", "matplotlib", "pandas", "scipy",      # numpy KALMALI
]

a = Analysis([str(ROOT / "main.py")], pathex=[str(ROOT)],
             datas=[(str(ROOT / "edifice" / "assets"), "edifice/assets")],
             hiddenimports=[], excludes=EXCLUDES, noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="EDIFICE-portable", console=False,
          icon=str(ROOT / "packaging" / "icon.ico"), disable_windowed_traceback=False, argv_emulation=False, upx=False)
