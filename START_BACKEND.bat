@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -m venv .venv
call .venv\Scripts\activate.bat
pip install -r backend\requirements.txt
cd backend
uvicorn app:app --reload --host 127.0.0.1 --port 8000
