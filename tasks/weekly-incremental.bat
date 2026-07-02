@echo off
chcp 65001 >nul
set ROOT=%~dp0..
cd /d "%ROOT%\backend"
call .venv\Scripts\activate.bat
python -m crawler incremental --max-pages 2
