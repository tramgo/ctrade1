@echo off
setlocal
cd /d "%~dp0\.."
if not exist "zerodha_equity_collector\data_l2\logs" mkdir "zerodha_equity_collector\data_l2\logs"
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-market-check >> zerodha_equity_collector\data_l2\logs\l2_depth_collector.log 2>&1
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-preflight >> zerodha_equity_collector\data_l2\logs\l2_depth_collector.log 2>&1
if errorlevel 1 exit /b %errorlevel%
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-live >> zerodha_equity_collector\data_l2\logs\l2_depth_collector.log 2>&1
endlocal
