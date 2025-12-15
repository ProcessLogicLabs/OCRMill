@echo off
REM Prepare OCRMill distribution package
REM This script copies necessary runtime files to the distribution folder

echo ===============================================
echo Preparing OCRMill Distribution Package
echo ===============================================
echo.

set DIST_DIR=dist\OCRMill

if not exist "%DIST_DIR%" (
    echo ERROR: Distribution folder not found!
    echo Please run build_exe.bat first.
    pause
    exit /b 1
)

echo Copying runtime files to distribution...

REM Copy database if it exists
if exist "parts_database.db" (
    copy /Y "parts_database.db" "%DIST_DIR%\"
    echo   - Copied parts_database.db
)

REM Copy config if it exists
if exist "config.json" (
    copy /Y "config.json" "%DIST_DIR%\"
    echo   - Copied config.json
)

REM Copy distribution README
if exist "DISTRIBUTION.md" (
    copy /Y "DISTRIBUTION.md" "%DIST_DIR%\README.md"
    echo   - Copied DISTRIBUTION.md as README.md
)

REM Create directories
mkdir "%DIST_DIR%\input" 2>nul
mkdir "%DIST_DIR%\output" 2>nul
mkdir "%DIST_DIR%\output\CBP_Export" 2>nul
mkdir "%DIST_DIR%\output\Processed" 2>nul
mkdir "%DIST_DIR%\reports" 2>nul
echo   - Created directory structure

echo.
echo ===============================================
echo Distribution package ready!
echo ===============================================
echo.
echo Location: %DIST_DIR%
echo.
echo To distribute:
echo   1. Zip the entire '%DIST_DIR%' folder
echo   2. Users extract and run OCRMill.exe
echo.
echo Creating zip file...

REM Create zip file using PowerShell
powershell -command "Compress-Archive -Path '%DIST_DIR%' -DestinationPath 'OCRMill-v2.4.0-Windows.zip' -Force"

if %errorlevel% equ 0 (
    echo.
    echo Zip file created: OCRMill-v2.4.0-Windows.zip
    echo File size:
    dir "OCRMill-v2.4.0-Windows.zip" | findstr "OCRMill"
    echo.
    echo Ready to distribute!
) else (
    echo.
    echo Note: Could not create zip file automatically.
    echo Please zip the '%DIST_DIR%' folder manually.
)

echo.
echo ===============================================
pause
