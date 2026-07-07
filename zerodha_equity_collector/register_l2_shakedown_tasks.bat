@echo off
setlocal
set "BASE=%~dp0"
set "COLLECTOR=%BASE%run_l2_depth_collector.bat"
set "AUDIT=%BASE%run_l2_daily_audit.bat"

REM Weekday schedule only. The collector also checks config\nse_holidays.csv
REM and auto-stops at the configured market_session.end time.
schtasks /Create /TN L2DepthCollector_Shakedown_0910 /TR "\"%COLLECTOR%\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 09:10 /F
schtasks /Create /TN L2DepthCollector_DailyAudit_1545 /TR "\"%AUDIT%\"" /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 15:45 /F

schtasks /Query /TN L2DepthCollector_Shakedown_0910 /FO LIST /V
schtasks /Query /TN L2DepthCollector_DailyAudit_1545 /FO LIST /V
endlocal
