@echo off
title Spatial Twin Intelligence Server
cd /d "%~dp0"

echo [INFO] Checking for and clearing existing processes on ports 8000 and 8001...
for %%p in (8000 8001) do (
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%%p ^| findstr LISTENING') do (
        taskkill /F /PID %%a >nul 2>&1
    )
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
) else (
    call conda activate depth_env
)

echo [INFO] Starting LSA Studio on port 8001 in its own window...
start "LSA Studio Server" cmd /k python -m uvicorn lsa_server:app --reload --port 8001

echo [INFO] Starting Viewfinder on port 8000...
python -m uvicorn server:app --reload --port 8000
pause