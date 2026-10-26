@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
 echo ERRO: Python nao encontrado. Instale Python 3.11 ou 3.12 e habilite o Python Launcher.
 pause
 exit /b 1
)
py -m pip install -r requirements-desktop.txt
if errorlevel 1 goto error
py -m PyInstaller --noconfirm --clean --onefile --windowed --name FinTrackAdvanced --icon FinTrackAdvanced.ico --add-data "static;static" --hidden-import=webview.platforms.edgechromium desktop.py
if errorlevel 1 goto error
echo.
echo Executavel criado em dist\FinTrackAdvanced.exe
pause
exit /b 0
:error
echo ERRO: Falha ao gerar executavel.
pause
exit /b 1
