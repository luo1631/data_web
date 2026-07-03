@echo off
cd /d "%~dp0backend"
echo Backend: http://localhost:8001
echo Swagger: http://localhost:8001/docs
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
pause
