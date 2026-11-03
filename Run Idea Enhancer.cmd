@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0src\main.py" (
  echo This launcher must stay in the Idea Enhancer project folder.
  pause
  exit /b 1
)

for /f "delims=" %%I in ('wsl.exe -d Ubuntu -- wslpath -a "%~dp0"') do set "WSL_PROJECT=%%I"
if not defined WSL_PROJECT (
  echo Could not translate the project path for WSL.
  pause
  exit /b 1
)

set "WSL_PYTHON="
if defined IDEA_ENHANCER_WSL_PYTHON set "WSL_PYTHON=%IDEA_ENHANCER_WSL_PYTHON%"
if not defined WSL_PYTHON (
  wsl.exe -d Ubuntu -- bash -lc "python3 -c 'import uvicorn, chromadb, rank_bm25' >/dev/null 2>&1"
  if not errorlevel 1 set "WSL_PYTHON=python3"
)
if not defined WSL_PYTHON (
  for /f "delims=" %%I in ('wsl.exe -d Ubuntu -- bash -lc "for p in /home/*/.venvs/*/bin/python; do if test -x \"$p\"; then echo \"$p\"; break; fi; done"') do set "WSL_PYTHON=%%I"
)
if not defined WSL_PYTHON (
  echo No WSL Python environment with the required API dependencies was found.
  echo Set IDEA_ENHANCER_WSL_PYTHON to an existing project environment if needed.
  pause
  exit /b 1
)
wsl.exe -d Ubuntu -- bash -lc "'%WSL_PYTHON%' -c 'import uvicorn, chromadb, rank_bm25' >/dev/null 2>&1"
if errorlevel 1 (
  echo The configured WSL Python command was not found: %WSL_PYTHON%
  echo Set IDEA_ENHANCER_WSL_PYTHON to an existing project environment if needed.
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
