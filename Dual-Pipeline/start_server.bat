@echo off
title Spatial Intelligence Pipeline Server

echo ======================================================
echo   Launching Spatial Intelligence Pipeline Server
echo ======================================================

:: 1. Activate depth_env using your Miniconda path
call C:\Users\dpool\miniconda3\condabin\conda.bat activate depth_env

:: 2. Navigate to your project folder
cd /d "C:\DEV\Squid\SquidBlack\Spatial-Intelligence-Development-Base\Dual-Pipeline"

:: 3. Start Uvicorn Server
echo [INFO] Active Environment: depth_env
echo [INFO] Server running at: http://localhost:8000/
echo.

python -m uvicorn server:app --reload --port 8000

pause