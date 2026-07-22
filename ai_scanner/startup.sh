#!/bin/bash
PORT=${PORT:-8000}
echo "========================================="
echo "  ◈ AI SCANNER // NEXUS-OS v3.0"
echo "========================================="
echo "  Starting server on port $PORT..."
echo "========================================="
echo "  Access from another device on same WiFi:"
echo "  Open http://<YOUR_IP>:$PORT on your phone"
echo "  Find YOUR_IP in Wireless > PHONE tab"
echo "========================================="
echo "  For public access:"
echo "  Install ngrok (free): https://ngrok.com"
echo "  Then run: ngrok http $PORT"
echo "========================================="
gunicorn --bind=0.0.0.0:$PORT --workers=2 --timeout=120 --access-logfile=- --error-logfile=- src.web_app:app
