@echo off
setlocal

cd /d "%~dp0"
title Motion Control Dashboard Launcher

echo Starting Motion Control Dashboard...
echo.

set "PYTHON_CMD="

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 (
        set "PYTHON_CMD=python"
    )
)

if not defined PYTHON_CMD (
    echo ERROR: Python was not found on this computer.
    echo Install Python 3 and make sure it is available in PATH.
    echo.
    pause
    exit /b 1
)

%PYTHON_CMD% -c "import serial" >nul 2>nul
if errorlevel 1 (
    echo ERROR: Required Python dependency "pyserial" is not installed.
    echo Run: pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo Launching the real hardware UI...
echo If auto-detection fails, make sure the Arduino is connected over USB.
echo.

%PYTHON_CMD% -m pc_app.ui.hardware_app
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo The dashboard closed with error code %EXIT_CODE%.
    echo Check the message above for details.
    echo Common causes:
    echo - Arduino is not connected over USB
    echo - Windows did not create a COM port for the controller
    echo - Multiple serial devices are connected and the port is ambiguous
    echo.
    pause
)

endlocal & exit /b %EXIT_CODE%
