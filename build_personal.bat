@echo off
rem Build the Personal edition (embedded credentials) -> release\Personal\
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build\build_edition.ps1" -Edition personal %*
if errorlevel 1 (
    echo [build_personal] FAILED
    exit /b 1
)