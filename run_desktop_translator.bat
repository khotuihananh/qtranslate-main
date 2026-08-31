@echo off
setlocal
cd /d "%~dp0"

if exist "LensTranslate.exe" (
    start "LensTranslate" "LensTranslate.exe"
    exit /b 0
)
if exist "QTranslateLite.exe" (
    start "QTranslate Lite" "QTranslateLite.exe"
    exit /b 0
)
if exist "dist\LensTranslate\LensTranslate.exe" (
    start "LensTranslate" "dist\LensTranslate\LensTranslate.exe"
    exit /b 0
)

set "PYTHON_CMD="
where py >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=py -3.13"
if not defined PYTHON_CMD (
    where python >nul 2>nul
    if %errorlevel%==0 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo Khong tim thay Python 3 tren may.
    echo Hay cai Python tu https://www.python.org/downloads/windows/
    pause
    exit /b 1
)

%PYTHON_CMD% desktop_translator.py
if not %errorlevel%==0 (
    echo.
    echo Ung dung gap loi khi khoi dong. Ma loi: %errorlevel%
    pause
)
