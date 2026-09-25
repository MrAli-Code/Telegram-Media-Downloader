@echo off
rem Build both editions: Personal then Public.
call "%~dp0build_personal.bat" %*
if errorlevel 1 goto :fail
call "%~dp0build_public.bat" %*
if errorlevel 1 goto :fail
echo [build_all] done.
exit /b 0
:fail
echo [build_all] FAILED
exit /b 1