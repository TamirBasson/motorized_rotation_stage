@echo off
setlocal

cd /d "%~dp0"
title Motion Control Dashboard Launcher

echo Starting Motion Control Dashboard...
echo.

set "PYTHON_CMD="
set "PIP_INSTALL_CMD="

REM Use chained checks (not nested "if %%ERRORLEVEL%%" inside else blocks). In CMD,
REM %%ERRORLEVEL%% inside parenthesized blocks is expanded at parse time, so after
REM "where py" fails the inner "where python" success is invisible to "if %%ERRORLEVEL%%==0".

where py >nul 2>nul && (
    set "PYTHON_CMD=py -3"
    set "PIP_INSTALL_CMD=py -3 -m pip install -r requirements.txt"
)
if not defined PYTHON_CMD where python >nul 2>nul && (
    set "PYTHON_CMD=python"
    set "PIP_INSTALL_CMD=python -m pip install -r requirements.txt"
)
if not defined PYTHON_CMD where python3 >nul 2>nul && (
    set "PYTHON_CMD=python3"
    set "PIP_INSTALL_CMD=python3 -m pip install -r requirements.txt"
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
    echo Required Python dependency "pyserial" is not installed.
    echo Attempting to install requirements automatically...
    echo.
    %PIP_INSTALL_CMD%
    if errorlevel 1 (
        echo.
        echo ERROR: Automatic dependency installation failed.
        echo Please run: %PIP_INSTALL_CMD%
        echo.
        pause
        exit /b 1
    )

    %PYTHON_CMD% -c "import serial" >nul 2>nul
    if errorlevel 1 (
        echo.
        echo ERROR: Requirements were installed, but "pyserial" is still unavailable.
        echo Please run: %PIP_INSTALL_CMD%
        echo.
        pause
        exit /b 1
    )

    echo.
    echo Requirements installed successfully.
    echo Restarting launch with the updated environment...
    echo.
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
