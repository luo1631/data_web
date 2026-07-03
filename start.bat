@echo off
cd /d "%~dp0"

echo === Chongqing Housing Data Platform ===
echo.

where python >nul 2>&1 || (echo [ERROR] Python not found & pause & exit /b 1)
where node   >nul 2>&1 || (echo [ERROR] Node.js not found   & pause & exit /b 1)

echo [1/3] Init backend...
cd /d "%~dp0backend"
if not exist cq_house.db (
    echo     Seeding database...
    python seed_data.py || (pause & exit /b 1)
) else (echo     Database OK)

echo.
echo [2/3] Init frontend...
cd /d "%~dp0frontend"
if not exist node_modules (
    echo     Installing npm...
    call npm install || (pause & exit /b 1)
) else (echo     node_modules OK)

cd /d "%~dp0"
echo.
echo [3/3] Starting...
start "Backend"  "%~dp0_run_backend.bat"
start "Frontend" "%~dp0_run_frontend.bat"

echo     Backend  : http://localhost:8001
echo     Frontend : http://localhost:5173
echo     Swagger  : http://localhost:8001/docs
echo.
echo Close the two opened windows to stop.
pause
