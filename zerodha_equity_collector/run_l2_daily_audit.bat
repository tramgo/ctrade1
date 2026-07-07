@echo off
setlocal
cd /d "%~dp0\.."
if not exist "zerodha_equity_collector\data_l2\logs" mkdir "zerodha_equity_collector\data_l2\logs"
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-audit >> zerodha_equity_collector\data_l2\logs\l2_daily_audit.log 2>&1
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-shakedown-report >> zerodha_equity_collector\data_l2\logs\l2_daily_audit.log 2>&1
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-plan-status >> zerodha_equity_collector\data_l2\logs\l2_daily_audit.log 2>&1
python -m zerodha_equity_collector.collector --config zerodha_equity_collector\config\l2_collector_config.json l2-status >> zerodha_equity_collector\data_l2\logs\l2_daily_audit.log 2>&1
endlocal
