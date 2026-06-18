@echo off
cd /d "%~dp0.."
".venv\Scripts\python.exe" "scripts\garmin_sync.py" >> "scripts\sync.log" 2>&1
