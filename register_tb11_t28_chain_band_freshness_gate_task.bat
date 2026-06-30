@echo off
setlocal

REM Registers the TB11 no-order chain-band/readiness/transition wrapper for fresh intraday capture.
REM This schedules the collector, freshness gate, readiness check, and transition controller on weekdays at 09:45 IST.

cd /d C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1

set TASK_NAME=TB11_T28_ChainBandFreshness_0945
set TASK_CMD=C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1\run_tb11_t28_chain_band_freshness_gate.bat

echo Registering task: %TASK_NAME%
echo Command: %TASK_CMD%

schtasks /Create /TN "%TASK_NAME%" /TR "\"%TASK_CMD%\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:45 /F
set CREATE_EXIT=%ERRORLEVEL%

if NOT "%CREATE_EXIT%"=="0" (
    echo ERROR: schtasks /Create failed with exit code %CREATE_EXIT%.
    exit /b %CREATE_EXIT%
)

echo.
echo Querying registered task:
schtasks /Query /TN "%TASK_NAME%" /FO LIST /V
set QUERY_EXIT=%ERRORLEVEL%

if NOT "%QUERY_EXIT%"=="0" (
    echo ERROR: schtasks /Query failed with exit code %QUERY_EXIT%.
    exit /b %QUERY_EXIT%
)

echo.
echo Registered %TASK_NAME% successfully.
echo Wrapper order: T28 collector ^> freshness gate ^> Phase 2 readiness ^> transition controller.
exit /b 0
