@echo off
echo ========================================
echo Starting OCRMill - Invoice Processing Suite
echo ========================================
echo.

echo Starting unified OCRMill application...
start "OCRMill" .venv\Scripts\python.exe invoice_processor_gui.py

echo.
echo ========================================
echo OCRMill application started!
echo ========================================
echo.
echo You can now close this window.
pause
