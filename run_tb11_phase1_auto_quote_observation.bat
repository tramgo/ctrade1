@echo off
setlocal

REM TB11 Phase 1 automated quote-only observation plus transition gate.
REM Runs: T25 current NFO resolver -> T24 Zerodha quote collector -> T26 append-only ledger
REM       -> Phase 2 readiness -> transition controller.
REM Broker orders remain blocked in ssell1.py.

cd /d C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1

set PYTHONDONTWRITEBYTECODE=1
set PYTHONPYCACHEPREFIX=%TEMP%\codex_pycache
set PYTHONUNBUFFERED=1
set SSELL1_NONINTERACTIVE=1
set MODE=signal_baseline_tb11_options_phase1_auto_quote_observation
set READINESS_MODE=signal_baseline_tb11_options_phase2_paper_price_reconciliation_readiness
set TRANSITION_MODE=signal_baseline_tb11_options_phase2_transition_controller
set PYTHON_EXE=C:\Users\Ramic\AppData\Local\Programs\Python\Python313\python.exe

set LOG_DIR=%CD%\results\log_runs
if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set RUN_TS=%%I
set LOG_FILE=%LOG_DIR%\%MODE%_%RUN_TS%_scheduled.log
type nul > "%LOG_FILE%"
echo %LOG_FILE%> "%LOG_DIR%\latest_mode_log.txt"

echo [Scheduler] started at %RUN_TS%>> "%LOG_FILE%"
echo [Scheduler] cwd=%CD%>> "%LOG_FILE%"
echo [Scheduler] mode=%MODE%>> "%LOG_FILE%"
echo [Scheduler] readiness_mode=%READINESS_MODE%>> "%LOG_FILE%"
echo [Scheduler] transition_mode=%TRANSITION_MODE%>> "%LOG_FILE%"
echo [Scheduler] python=%PYTHON_EXE%>> "%LOG_FILE%"
"%PYTHON_EXE%" --version>> "%LOG_FILE%" 2>&1

"%PYTHON_EXE%" -u -B ssell1.py --mode %MODE%>> "%LOG_FILE%" 2>&1
set PHASE1_EXIT=%ERRORLEVEL%
echo [Scheduler] phase1_exit=%PHASE1_EXIT% >> "%LOG_FILE%"

if NOT "%PHASE1_EXIT%"=="0" (
    exit /b %PHASE1_EXIT%
)

echo [Scheduler] running phase2 readiness>> "%LOG_FILE%"
"%PYTHON_EXE%" -u -B ssell1.py --mode %READINESS_MODE%>> "%LOG_FILE%" 2>&1
set READINESS_EXIT=%ERRORLEVEL%
echo [Scheduler] readiness_exit=%READINESS_EXIT% >> "%LOG_FILE%"

if NOT "%READINESS_EXIT%"=="0" (
    exit /b %READINESS_EXIT%
)

echo [Scheduler] running transition controller>> "%LOG_FILE%"
"%PYTHON_EXE%" -u -B ssell1.py --mode %TRANSITION_MODE%>> "%LOG_FILE%" 2>&1
set TRANSITION_EXIT=%ERRORLEVEL%
echo [Scheduler] transition_exit=%TRANSITION_EXIT% >> "%LOG_FILE%"

exit /b %TRANSITION_EXIT%
