@echo off
REM Scheduled run: refresh providers, rebuild CSVs, send the daily brief.
REM Add --no-brief to main.py below to send only the refresh report.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" main.py
) else (
    python main.py
)
