@echo off

echo Starting FastAPI Tool Server...

venv\Scripts\python -m pip install -r requirements.txt >nul 2>&1

IF %ERRORLEVEL% NEQ 0 (
    echo Failed to install dependencies!
    pause
    exit /b
)


REM Start server in background
start "" venv\Scripts\python -m uvicorn app:app --host localhost --port 5555

REM Wait a bit for server to start
timeout /t 2 >nul

REM Open browser
start http://localhost:5555

echo Server started at http://localhost:5555
