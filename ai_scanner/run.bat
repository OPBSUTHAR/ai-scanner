@echo off
cd /d "%~dp0"
echo ====================================
echo   AI Document Scanner - Web Server
echo ====================================
echo.
echo Access from any device on your network:
echo   http://YOUR_PC_IP:5000
echo.

if exist ".venv\Scripts\python.exe" (
  echo Using project virtual environment (.venv)
  .venv\Scripts\python -m src.web_app
) else (
  echo No .venv found - using system Python
  echo Tip: run "python -m venv .venv" then ".venv\Scripts\pip install -r requirements.txt"
  python -m src.web_app
)
pause
