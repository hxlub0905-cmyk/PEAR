@echo off
rem Start PEAR. Uses the virtual environment install.bat made, if it is there.
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\pythonw.exe" start "PEAR" "%~dp0.venv\Scripts\pythonw.exe" -m pear
if exist "%~dp0.venv\Scripts\pythonw.exe" exit /b
start "PEAR" pythonw -m pear
