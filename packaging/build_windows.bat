@echo off
REM Windows kurulum dosyasını üretir (Windows PC'de çalıştırın).
REM Gerekenler: Python 3.12 (python.org), Inno Setup 6 (jrsoftware.org/isinfo.php)
setlocal
cd /d "%~dp0\.."
python -m venv .venv-win || exit /b 1
call .venv-win\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt pyinstaller || exit /b 1
rmdir /s /q build dist 2>nul
pyinstaller packaging\edifice.spec --noconfirm --log-level WARN || exit /b 1
set QT_QPA_PLATFORM=offscreen
set EDIFICE_DB=%TEMP%\edifice_selftest.db
dist\EDIFICE\EDIFICE.exe --selftest || exit /b 1
for /f %%v in ('python -c "import edifice;print(edifice.__version__)"') do set VER=%%v
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
%ISCC% /DMyVersion=%VER% packaging\installer.iss || exit /b 1
echo Hazir: dist\EDIFICE-Setup-%VER%.exe
