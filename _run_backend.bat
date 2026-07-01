@echo off
cd /d "%~dp0backend"
echo Backend: http://localhost:8000
echo Swagger: http://localhost:8000/docs
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
