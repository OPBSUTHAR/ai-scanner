@echo off
cd /d "%~dp0"
echo ====================================
echo   AI Document Scanner - Web Server
echo ====================================
echo.
echo Starting with HTTPS (self-signed cert) - REQUIRED for phone camera access
echo.
echo On this PC:        https://localhost:5000  (accept the browser warning once)
echo On phone (Wi-Fi):  scan the QR from Settings, or open https://YOUR_PC_IP:5000
echo                    - tap "Advanced" then "Proceed" on the certificate warning
echo.

if exist ".venv\Scripts\python.exe" (
  echo Using project virtual environment (.venv)
  .venv\Scripts\python -m src.web_app --ssl
) else (
  echo No .venv found - using system Python
  echo Tip: run "python -m venv .venv" then ".venv\Scripts\pip install -r requirements.txt"
  python -m src.web_app --ssl
)
pause
