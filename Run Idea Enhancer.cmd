@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0src\main.py" (
  echo This launcher must stay in the Idea Enhancer project folder.
  pause
  exit /b 1
)

set "WSL_PROJECT=/mnt/c/Users/seepa/Desktop/Idea-Enhancer"
set "WSL_PYTHON=/home/onyx/.venvs/idea-enhancer-core-314/bin/python"
wsl.exe -d Ubuntu -- bash -lc "test -x '%WSL_PYTHON%'"
if errorlevel 1 (
  echo The prepared Ubuntu Python environment was not found.
  echo Ask your project mentor to set up this laptop.
  pause
  exit /b 1
)

start "Idea Enhancer API" wsl.exe -d Ubuntu -- bash -lc "cd '%WSL_PROJECT%' && exec '%WSL_PYTHON%' -m uvicorn src.main:app --host 127.0.0.1"
start "Idea Enhancer Frontend" wsl.exe -d Ubuntu -- bash -lc "cd '%WSL_PROJECT%' && exec '%WSL_PYTHON%' -m http.server 5500 --bind 127.0.0.1"

timeout /t 4 /nobreak >nul
start "" "http://localhost:5500"
echo Idea Enhancer is running. Keep both server windows open while presenting.
echo Before the presentation, run one live search so the local index is ready.
echo Close both server windows to stop Idea Enhancer.
pause
