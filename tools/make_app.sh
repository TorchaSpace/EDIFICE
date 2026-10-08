#!/bin/bash
# EDIFICE.app başlatıcısını oluşturur. Kullanım: tools/make_app.sh [hedef_klasör]  (varsayılan: proje klasörü)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-$ROOT}"
APP="$DEST/EDIFICE.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cat > "$APP/Contents/Info.plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>EDIFICE</string>
<key>CFBundleDisplayName</key><string>EDIFI'CE</string>
<key>CFBundleIdentifier</key><string>com.edifice.app</string>
<key>CFBundleExecutable</key><string>edifice</string>
<key>CFBundleIconFile</key><string>icon</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSMinimumSystemVersion</key><string>11.0</string>
</dict></plist>
PL
cat > "$APP/Contents/MacOS/edifice" <<'SH'
#!/bin/bash
# Proje klasörü: EDIFICE.app'in bulunduğu klasör (symlink ile de çalışır)
SELF="$(python3 -c 'import os,sys;print(os.path.realpath(sys.argv[1]))' "$0")"
ROOT="$(cd "$(dirname "$SELF")/../../.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python3"
exec "$PY" "$ROOT/main.py"
SH
chmod +x "$APP/Contents/MacOS/edifice"
TMP="$(mktemp -d)"
"$ROOT/.venv/bin/python" "$ROOT/tools/make_icon.py" "$TMP/icon.png"
mkdir "$TMP/icon.iconset"
for s in 16 32 128 256 512; do
  sips -z $s $s "$TMP/icon.png" --out "$TMP/icon.iconset/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) "$TMP/icon.png" --out "$TMP/icon.iconset/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$TMP/icon.iconset" -o "$APP/Contents/Resources/icon.icns"
rm -rf "$TMP"
touch "$APP"
echo "Oluşturuldu: $APP"
