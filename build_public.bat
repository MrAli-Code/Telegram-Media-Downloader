@echo off
rem Build the Public edition (user-provided API credentials) -> release\Public\
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build\build_edition.ps1" -Edition public %*
if errorlevel 1 (
    echo [build_public] FAILED
    exit /b 1
)