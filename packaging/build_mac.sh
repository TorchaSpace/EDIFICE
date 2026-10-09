#!/bin/bash
# macOS (Apple Silicon) için EDIFICE.app ve .dmg üretir. Kullanım: packaging/build_mac.sh   (çıktı: dist/)
set -e
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
VER=$($PY -c "import edifice;print(edifice.__version__)")
ARCH=$(uname -m)
rm -rf build dist
$PY -m PyInstaller packaging/edifice.spec --noconfirm --log-level WARN
# Apple Silicon çalıştırılabilirleri imza ister: geliştirici sertifikası yoksa ad-hoc imza
codesign --force --deep --sign - dist/EDIFICE.app
EDIFICE_DB=/tmp/edifice_selftest.db QT_QPA_PLATFORM=offscreen dist/EDIFICE.app/Contents/MacOS/EDIFICE --selftest
STAGE=$(mktemp -d)
cp -R dist/EDIFICE.app "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "EDIFICE" -srcfolder "$STAGE" -ov -format UDZO "dist/EDIFICE-$VER-macOS-$ARCH.dmg"
rm -rf "$STAGE"
ls -lh dist/*.dmg
