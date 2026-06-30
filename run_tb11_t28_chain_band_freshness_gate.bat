@echo off
setlocal

REM TB11 T28 current-expiry NIFTY chain-band quote capture plus transition gate.
REM Runs: T28 chain-band quote collector -> T28 freshness gate -> Phase 2 readiness -> transition controller.
REM Broker orders remain blocked in ssell1.py.

cd /d C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1

set PYTHONDONTWRITEBYTECODE=1
set PYTHONPYCACHEPREFIX=%TEMP%\codex_pycache
set PYTHONUNBUFFERED=1
set SSELL1_NONINTERACTIVE=1
set COLLECTOR_MODE=signal_baseline_tb11_options_nifty_chain_band_quote_collector
set GATE_MODE=signal_baseline_tb11_options_t28_freshness_gate
set READINESS_MODE=signal_baseline_tb11_options_phase2_paper_price_reconciliation_readiness
set TRANSITION_MODE=signal_baseline_tb11_options_phase2_transition_controller
set PYTHON_EXE=C:\Users\Ramic\AppData\Local\Programs\Python\Python313\python.exe

set LOG_DIR=%CD%\results\log_runs
if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set RUN_TS=%%I
set LOG_FILE=%LOG_DIR%\tb11_t28_chain_band_freshness_gate_%RUN_TS%_scheduled.log
type nul > "%LOG_FILE%"
echo %LOG_FILE%> "%LOG_DIR%\latest_mode_log.txt"

echo [Scheduler] started at %RUN_TS%>> "%LOG_FILE%"
echo [Scheduler] cwd=%CD%>> "%LOG_FILE%"
echo [Scheduler] collector_mode=%COLLECTOR_MODE%>> "%LOG_FILE%"
echo [Scheduler] gate_mode=%GATE_MODE%>> "%LOG_FILE%"
echo [Scheduler] readiness_mode=%READINESS_MODE%>> "%LOG_FILE%"
echo [Scheduler] transition_mode=%TRANSITION_MODE%>> "%LOG_FILE%"
echo [Scheduler] python=%PYTHON_EXE%>> "%LOG_FILE%"
"%PYTHON_EXE%" --version>> "%LOG_FILE%" 2>&1

echo [Scheduler] running collector>> "%LOG_FILE%"
"%PYTHON_EXE%" -u -B ssell1.py --mode %COLLECTOR_MODE%>> "%LOG_FILE%" 2>&1
set COLLECTOR_EXIT=%ERRORLEVEL%
echo [Scheduler] collector_exit=%COLLECTOR_EXIT% >> "%LOG_FILE%"

echo [Scheduler] running freshness gate>> "%LOG_FILE%"
"%PYTHON_EXE%" -u -B ssell1.py --mode %GATE_MODE%>> "%LOG_FILE%" 2>&1
set GATE_EXIT=%ERRORLEVEL%
echo [Scheduler] gate_exit=%GATE_EXIT% >> "%LOG_FILE%"

echo [Scheduler] running phase2 readiness>> "%LOG_FILE%"
"%PYTHON_EXE%" -u -B ssell1.py --mode %READINESS_MODE%>> "%LOG_FILE%" 2>&1
set READINESS_EXIT=%ERRORLEVEL%
echo [Scheduler] readiness_exit=%READINESS_EXIT% >> "%LOG_FILE%"

echo [Scheduler] running transition controller>> "%LOG_FILE%"
"%PYTHON_EXE%" -u -B ssell1.py --mode %TRANSITION_MODE%>> "%LOG_FILE%" 2>&1
set TRANSITION_EXIT=%ERRORLEVEL%
echo [Scheduler] transition_exit=%TRANSITION_EXIT% >> "%LOG_FILE%"

if NOT "%COLLECTOR_EXIT%"=="0" (
    exit /b %COLLECTOR_EXIT%
)

if NOT "%GATE_EXIT%"=="0" (
    exit /b %GATE_EXIT%
)

if NOT "%READINESS_EXIT%"=="0" (
    exit /b %READINESS_EXIT%
)

exit /b %TRANSITION_EXIT%
