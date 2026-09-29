@echo off
cd /d "%~dp0.."
py 07_SCRIPTS\generate_prompt.py --count 20
pause
