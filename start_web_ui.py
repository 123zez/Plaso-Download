import os
import sys
import webbrowser
import uvicorn
from multiprocessing import Process
import time

# Ensure the src directory is in sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

def open_browser():
    """Wait for server to start then open browser."""
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    print("=" * 50)
    print("PLASO-DL CYBER WEB UI INITIALIZING...")
    print("=" * 50)
    
    # Start browser in a separate thread/process is not needed 
    # if we just use a small delay or do it before run.
    # But uvicorn.run is blocking.
    
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    uvicorn.run("plaso_dl.server:app", host="127.0.0.1", port=8000, reload=False)
