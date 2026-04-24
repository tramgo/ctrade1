@echo off
setlocal

REM ============================================================
REM Compile / Import Check before long Codex research runs
REM ============================================================

cd /d C:\Ramgo\Business\Trading\India2026\Gitrade1\ctrade1

call C:\ProgramData\anaconda3\Scripts\activate.bat C:\ProgramData\anaconda3

set PYTHONDONTWRITEBYTECODE=1
set PYTHONPYCACHEPREFIX=%TEMP%\codex_pycache

echo.
echo ============================================================
echo Running Python compile check
echo ============================================================

python -B -c "import ast, pathlib; p=pathlib.Path('ssell1.py'); ast.parse(p.read_text(encoding='utf-8'), filename=str(p)); print('AST syntax check OK')"

set COMPILE_EXIT=%ERRORLEVEL%

if NOT "%COMPILE_EXIT%"=="0" (
    echo ERROR: Compile check failed with exit code %COMPILE_EXIT%.
    exit /b %COMPILE_EXIT%
)

echo.
echo ============================================================
echo Running core import check
echo ============================================================

python -B -c "import pandas, numpy, sklearn; print('Core imports OK')"

set IMPORT_EXIT=%ERRORLEVEL%

if NOT "%IMPORT_EXIT%"=="0" (
    echo ERROR: Import check failed with exit code %IMPORT_EXIT%.
    exit /b %IMPORT_EXIT%
)

echo.
echo ============================================================
echo Compile and import checks completed successfully
echo ============================================================

endlocal
