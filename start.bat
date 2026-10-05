@echo off
cd /d "%~dp0"
title Baidu API Push Tool
echo ========================================================
echo   Starting Baidu API Push Dashboard...
echo   Dashboard URL: http://127.0.0.1:5000
echo ========================================================
echo.
python app.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application stopped with error code %ERRORLEVEL%.
    pause
)
