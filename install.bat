@echo off
rem PEAR one-click install. Everything happens in tools\install_windows.py --
rem this file stays flat (no blocks, no goto) so it works with LF endings,
rem which the plain-text bundle requires.
py -3 "%~dp0tools\install_windows.py" %* || python "%~dp0tools\install_windows.py" %*
pause
