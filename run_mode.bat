@echo off
setlocal

REM ============================================================
REM Generic Codex Research Mode Runner
REM Usage:
REM   run_mode.bat <MODE_NAME>
REM Example:
REM   run_mode.bat signal_research_native_15m_breadth_event
REM ============================================================

cd /d C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1

call C:\ProgramData\anaconda3\Scripts\activate.bat C:\ProgramData\anaconda3

set PYTHONDONTWRITEBYTECODE=1
set PYTHONPYCACHEPREFIX=%TEMP%\codex_pycache
set PYTHONUNBUFFERED=1

set MODE=%1

if "%MODE%"=="" (
    echo ERROR: Missing mode argument.
    echo Usage: run_mode.bat signal_research_native_15m_breadth_event
    exit /b 1
)

echo.
echo ============================================================
echo Running mode: %MODE%
echo ============================================================

echo Project folder:
cd

echo.
echo Python location:
where python

echo.
echo Starting command:
echo python -B ssell1.py --mode %MODE%
echo.

set LOG_DIR=%CD%\results\log_runs
if not exist "%LOG_DIR%" (
    mkdir "%LOG_DIR%"
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set RUN_TS=%%I
set LOG_FILE=%LOG_DIR%\%MODE%_%RUN_TS%.log
type nul > "%LOG_FILE%"

echo Log file:
echo %LOG_FILE%
echo %LOG_FILE%> "%LOG_DIR%\latest_mode_log.txt"
echo [Runner] log file initialized at %RUN_TS%>> "%LOG_FILE%"
echo.
echo Live console streaming enabled. Key progress will print below.
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command "$log = [System.IO.Path]::GetFullPath('%LOG_FILE%'); & python -u -B ssell1.py --mode '%MODE%' 2>&1 | Tee-Object -FilePath $log -Append; exit $LASTEXITCODE"

set EXITCODE=%ERRORLEVEL%

echo.
echo ============================================================
echo Finished mode: %MODE%
echo Exit code: %EXITCODE%
echo ============================================================

exit /b %EXITCODE%
