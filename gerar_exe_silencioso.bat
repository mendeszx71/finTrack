@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 exit /b 1
py -m pip install -r requirements-desktop.txt
if errorlevel 1 exit /b 1
py -m PyInstaller --noconfirm --clean --onefile --windowed --name FinTrackAdvanced --icon FinTrackAdvanced.ico --add-data "static;static" --hidden-import=webview.platforms.edgechromium desktop.py
exit /b %errorlevel%
