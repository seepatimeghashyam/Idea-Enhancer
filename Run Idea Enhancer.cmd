@echo off
setlocal
cd /d "%~dp0"

if not exist "%~dp0src\main.py" (
  echo This launcher must stay in the Idea Enhancer project folder.
  pause
  exit /b 1
)

set "WINDOWS_PROJECT=%~dp0"
set "WINDOWS_PROJECT=%WINDOWS_PROJECT:\=/%"
for /f "delims=" %%I in ('wsl.exe -d Ubuntu -- wslpath -a "%WINDOWS_PROJECT%"') do set "WSL_PROJECT=%%I"
if not defined WSL_PROJECT (
  echo Could not translate the project path for WSL.
  pause
  exit /b 1
)

set "WSL_HOME="
for /f "delims=" %%I in ('wsl.exe -d Ubuntu -- printenv HOME') do set "WSL_HOME=%%I"
if not defined WSL_HOME (
  echo Could not find the Ubuntu WSL home directory.
  pause
  exit /b 1
)

set "WSL_PYTHON="
if defined IDEA_ENHANCER_WSL_PYTHON set "WSL_PYTHON=%IDEA_ENHANCER_WSL_PYTHON%"
if not defined WSL_PYTHON set "WSL_PYTHON=%WSL_HOME%/.venvs/idea-enhancer-py312/bin/python"
wsl.exe -d Ubuntu -- "%WSL_PYTHON%" -c "import sys; assert sys.version_info[:2] == (3, 12); import fastapi, uvicorn, httpx, chromadb, rank_bm25, sentence_transformers, dotenv, pydantic"
if errorlevel 1 (
  echo The project requires Python 3.12 with its API and search dependencies.
  echo Expected environment: %WSL_PYTHON%
  echo Set IDEA_ENHANCER_WSL_PYTHON to another compatible Python 3.12 executable if needed.
  pause
  exit /b 1
)

start "Idea Enhancer API" wsl.exe -d Ubuntu --cd "%WSL_PROJECT%" -- "%WSL_PYTHON%" -m uvicorn src.main:app --host 127.0.0.1
start "Idea Enhancer Frontend" wsl.exe -d Ubuntu --cd "%WSL_PROJECT%" -- "%WSL_PYTHON%" -m http.server 5500 --bind 127.0.0.1

timeout /t 4 /nobreak >nul
start "" "http://localhost:5500"
echo Idea Enhancer is running. Keep both server windows open while presenting.
echo Before the presentation, run one live search so the local index is ready.
echo Close both server windows to stop Idea Enhancer.
pause
