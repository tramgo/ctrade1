@echo off
setlocal

REM ============================================================
REM Codex / Anaconda Environment Check
REM Project: Intraday Signal Research
REM ============================================================

cd /d C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1

call C:\ProgramData\anaconda3\Scripts\activate.bat C:\ProgramData\anaconda3

echo.
echo ============================================================
echo Current directory
echo ============================================================
cd

echo.
echo ============================================================
echo Python location
echo ============================================================
where python

echo.
echo ============================================================
echo Python version
echo ============================================================
python --version

echo.
echo ============================================================
echo Conda location
echo ============================================================
where conda

echo.
echo ============================================================
echo Checking core packages
echo ============================================================
python -c "import pandas, numpy, sklearn; print('Core imports OK')"

echo.
echo ============================================================
echo Environment check completed
echo ============================================================

endlocal
