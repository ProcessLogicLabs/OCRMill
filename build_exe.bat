@echo off
REM Build script for OCRMill executable
REM This script builds a standalone Windows executable using PyInstaller

echo ===============================================
echo Building OCRMill Executable
echo ===============================================
echo.

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Clean previous builds
echo Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Build the executable
echo.
echo Building executable...
pyinstaller --clean OCRMill.spec

REM Check if build was successful
if %errorlevel% equ 0 (
    echo.
    echo ===============================================
    echo Build completed successfully!
    echo ===============================================
    echo.
    echo Executable location: dist\OCRMill\OCRMill.exe
    echo.
    echo To run the application:
    echo   1. Navigate to dist\OCRMill\
    echo   2. Run OCRMill.exe
    echo.
    echo You can copy the entire dist\OCRMill\ folder
    echo to distribute the application.
    echo ===============================================
) else (
    echo.
    echo ===============================================
    echo Build FAILED! Check the error messages above.
    echo ===============================================
)

pause
