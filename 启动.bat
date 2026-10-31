@echo off
REM Material manager launcher. Works from any working directory.
cd /d "%~dp0"
python "%~dp0index\serve.py" %*
if errorlevel 1 pause
