@echo off
title LSA Dispatcher
cd /d "%~dp0"

echo [INFO] Checking for and clearing existing processes on port 5057...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5057 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo [INFO] Activating depth_env...
if exist "%USERPROFILE%\miniconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\miniconda3\Scripts\activate.bat" depth_env
) else if exist "%USERPROFILE%\anaconda3\Scripts\activate.bat" (
    call "%USERPROFILE%\anaconda3\Scripts\activate.bat" depth_env
) else if exist "C:\ProgramData\miniconda3\Scripts\activate.bat" (
    call "C:\ProgramData\miniconda3\Scripts\activate.bat" depth_env
) else if exist "C:\miniconda3\Scripts\activate.bat" (
    call "C:\miniconda3\Scripts\activate.bat" depth_env
)

start "" http://127.0.0.1:5057
python server.py
pause
