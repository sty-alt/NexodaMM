@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Nexoda Booking Bot

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo.
    echo  Создан файл .env. Впиши BOT_TOKEN и ADMIN_IDS, сохрани файл и запусти start.bat снова.
    echo.
    notepad ".env"
    pause
    exit /b
)

if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo.
echo  Запускаю бота. Не закрывай это окно — пока оно открыто, бот работает.
echo.
".venv\Scripts\python.exe" main.py
pause
