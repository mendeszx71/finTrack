@echo off
setlocal
cd /d "%~dp0"
call gerar_exe_silencioso.bat
if errorlevel 1 goto error
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
 echo ERRO: Instale o Inno Setup 6 em https://jrsoftware.org/isinfo.php
 pause
 exit /b 1
)
"%ISCC%" instalador.iss
if errorlevel 1 goto error
echo.
echo PRONTO: instalador\FinTrackAdvanced_Setup.exe
pause
exit /b 0
:error
echo ERRO: nao foi possivel criar o instalador.
pause
exit /b 1
