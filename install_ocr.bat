@echo off
setlocal
cd /d "%~dp0"

echo Installing Python packages for screenshot OCR...
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Could not install the Python packages.
    pause
    exit /b 1
)

echo.
echo Python packages installed.
echo.
echo You must also install Tesseract OCR for Windows and include the language data you need.
echo Official installation guidance: https://tesseract-ocr.github.io/tessdoc/Installation.html
pause
