@echo off
setlocal
title Viewfinder: end of day

rem ---------------------------------------------------------------
rem  Viewfinder end-of-day routine
rem  1. Backs up run folders and series manifests to the D: drive
rem  2. Checks the backup holds every run folder
rem  3. Shows git's state, so you can commit before stopping
rem  Place this file in the Dual-Pipeline folder and double-click it.
rem  It never deletes anything, on C: or D:.
rem ---------------------------------------------------------------

set "PROJ=%~dp0"
set "PROJ=%PROJ:~0,-1%"
set "BACKUP=D:\Viewfinder-Backup"
set "LOGDIR=%BACKUP%\logs"

if not exist D:\ (
  echo.
  echo  The D: drive was not found. Connect the backup drive and run this again.
  echo.
  pause
  exit /b 1
)
if not exist "%LOGDIR%" mkdir "%LOGDIR%"

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%i"
set "LOG=%LOGDIR%\eod_%STAMP%.log"

echo.
echo  === 1. Backing up to %BACKUP% ===
echo.
robocopy "%PROJ%\spatial_twin_runs" "%BACKUP%\spatial_twin_runs" /E /XO /R:2 /W:5 /NP /NFL /NDL /LOG+:"%LOG%" /TEE
set "RC1=%ERRORLEVEL%"
robocopy "%PROJ%\spatial_twin_series" "%BACKUP%\spatial_twin_series" /E /XO /R:2 /W:5 /NP /NFL /NDL /LOG+:"%LOG%" /TEE
set "RC2=%ERRORLEVEL%"
robocopy "%PROJ%" "%BACKUP%\records" saved_views.json keystones.json phenology_cache.json /XO /R:2 /W:5 /NP /NFL /NDL /LOG+:"%LOG%" /TEE
set "RC3=%ERRORLEVEL%"

rem Robocopy exit codes 0-7 mean success; 8 or higher means something failed to copy.
set "FAILED="
if %RC1% GEQ 8 set "FAILED=1"
if %RC2% GEQ 8 set "FAILED=1"
if %RC3% GEQ 8 set "FAILED=1"

echo.
echo  === 2. Checking the backup ===
echo.
for /f %%c in ('powershell -NoProfile -Command "(Get-ChildItem '%PROJ%\spatial_twin_runs' -Directory).Count"') do set "SRC=%%c"
for /f %%c in ('powershell -NoProfile -Command "(Get-ChildItem '%BACKUP%\spatial_twin_runs' -Directory).Count"') do set "DST=%%c"
echo  Run folders on this PC: %SRC%
echo  Run folders on D:     : %DST%
if defined FAILED (
  echo.
  echo  WARNING: some files failed to copy. Details are in:
  echo  %LOG%
) else (
  if %DST% LSS %SRC% (
    echo.
    echo  WARNING: the backup has fewer run folders than this PC. Check the log:
    echo  %LOG%
  ) else (
    echo  Backup OK.
  )
)

echo.
echo  === 3. Git ===
echo.
echo  Last commit:
git -C "%PROJ%" log -1 --oneline
echo.
echo  Uncommitted changes (blank means none):
git -C "%PROJ%" status --short
echo.
echo  If changes are listed above, commit them with a summary before you stop,
echo  then run: git push
echo.
pause
