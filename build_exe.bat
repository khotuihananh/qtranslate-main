@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD=python"

echo Using: %PYTHON_CMD%
%PYTHON_CMD% --version
if errorlevel 1 (
    echo.
    echo Khong tim thay lenh "python". Hay dam bao Python da duoc cai va them vao PATH.
    pause
    exit /b 1
)

%PYTHON_CMD% -m pip install --user Pillow pytesseract pystray pyinstaller
if errorlevel 1 (
    echo.
    echo Could not install the build dependencies.
    pause
    exit /b 1
)

if not exist "tessdata" mkdir "tessdata"
if not exist "tessdata\eng.traineddata" curl.exe -L --retry 3 "https://github.com/tesseract-ocr/tessdata/raw/refs/heads/main/eng.traineddata" -o "tessdata\eng.traineddata"
if not exist "tessdata\vie.traineddata" curl.exe -L --retry 3 "https://github.com/tesseract-ocr/tessdata/raw/refs/heads/main/vie.traineddata" -o "tessdata\vie.traineddata"

%PYTHON_CMD% -m PyInstaller --noconfirm --clean --onefile --windowed --name LensTranslate --distpath . --workpath build_lens --specpath . --add-data "tessdata;tessdata" --add-data "tesseract;tesseract" --hidden-import pytesseract --hidden-import pystray --hidden-import PIL desktop_translator.py
if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Done. The executable is: LensTranslate.exe
echo OCR engine and English/Vietnamese models are bundled in the executable.
pause
