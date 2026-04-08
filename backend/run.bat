@echo off
setlocal
cd /d "%~dp0"

set PORT=%1
if "%PORT%"=="" set PORT=8000

set HOST=%2
if "%HOST%"=="" set HOST=127.0.0.1

set RELOAD=%3
if /I "%RELOAD%"=="reload" (
  set UVICORN_RELOAD=--reload
) else (
  set UVICORN_RELOAD=
)

echo Cleaning old backend process on port %PORT% ...
call "%~dp0kill_backend.bat" %PORT% >nul 2>nul

echo Starting backend: %HOST%:%PORT% %UVICORN_RELOAD%
python -m uvicorn main:app --host %HOST% --port %PORT% %UVICORN_RELOAD%