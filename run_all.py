import subprocess
import sys
import os
import time

def start_services():
    print("Starting AI News Agent Services...")
    
    # 1. Start the Ingestion Scheduler
    ingestion_process = subprocess.Popen(
        [sys.executable, "main.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    )
    print("Started Ingestion Scheduler (main.py)")
    
    # 2. Start the Voice Dashboard Server
    dashboard_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "web_app:app", "--host", "0.0.0.0", "--port", "5000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    )
    print("Started Voice Dashboard Server (web_app.py) on port 5000")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down services...")
        ingestion_process.terminate()
        dashboard_process.terminate()
        print("Done.")

if __name__ == "__main__":
    start_services()
