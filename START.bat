@echo off
setlocal EnableExtensions
cd /d "%~dp0"

rem Prefer the Windows Python launcher; fall back to Python on PATH.
set "PYTHON_CMD=py -3"
py -3 -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if not errorlevel 1 goto python_found
set "PYTHON_CMD=python"
python -c "import sys; assert sys.version_info >= (3,10)" >nul 2>&1
if errorlevel 1 goto no_python

:python_found
rem A copied .venv may contain an absolute path to Python on another PC.
rem Recreate it if its interpreter fails to start.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import sys" >nul 2>&1
    if errorlevel 1 goto rebuild_venv
) else (
    goto create_venv
)
goto check_dependencies

:rebuild_venv
echo Existing virtual environment is broken. Recreating it...
if exist ".venv" rmdir /s /q ".venv"
if exist ".venv" goto failed

:create_venv
echo Creating local Python environment...
%PYTHON_CMD% -m venv ".venv"
if errorlevel 1 goto failed

:check_dependencies
".venv\Scripts\python.exe" -c "import serial, tkinter, docx; from PIL import ImageGrab" >nul 2>&1
if errorlevel 1 goto install

goto run

:install
echo Installing required packages...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed

:run
".venv\Scripts\python.exe" console_capture.py
if errorlevel 1 goto failed
exit /b 0

:no_python
echo Python 3.10 or newer is required. Install Python with Tkinter enabled.
pause
exit /b 1

:failed
echo Setup or application failed. Please copy the error above for troubleshooting.
pause
exit /b 1
