@echo off
setlocal

REM TB11 Phase 1 automated quote-only observation.
REM Runs: T25 current NFO resolver -> T24 Zerodha quote collector -> T26 append-only ledger.
REM Broker orders remain blocked in ssell1.py.

cd /d C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1

set PYTHONDONTWRITEBYTECODE=1
set PYTHONPYCACHEPREFIX=%TEMP%\codex_pycache
set PYTHONUNBUFFERED=1
set SSELL1_NONINTERACTIVE=1
set MODE=signal_baseline_tb11_options_phase1_auto_quote_observation
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
echo [Scheduler] python=%PYTHON_EXE%>> "%LOG_FILE%"
"%PYTHON_EXE%" --version>> "%LOG_FILE%" 2>&1

"%PYTHON_EXE%" -u -B ssell1.py --mode %MODE%>> "%LOG_FILE%" 2>&1

exit /b %ERRORLEVEL%
