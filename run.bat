@echo off
REM Double-click to install packages and start the app (Windows)
if not exist venv ( python -m venv venv )
call venv\Scripts\activate
pip install -r requirements.txt
python app.py
pause
