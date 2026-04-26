@echo off
echo Starting AI News Agent (Visible Mode)...

:: Start the Ingestion Engine in a new visible window
start "AI News Ingestion Engine" cmd /k "python main.py"

:: Start the Web Dashboard Server in a new visible window
start "AI Voice Dashboard Server" cmd /k "python -m uvicorn web_app:app --host 0.0.0.0 --port 5000"

echo Both processes have been launched in new windows!
echo You can safely close this small window.
exit
