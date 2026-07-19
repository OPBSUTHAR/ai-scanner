@echo off
cd /d "%~dp0"
echo ====================================
echo   AI Document Scanner - Web Server
echo ====================================
echo.
echo Access from any device on your network:
echo   http://YOUR_PC_IP:5000
echo.
python -m src.web_app
pause
