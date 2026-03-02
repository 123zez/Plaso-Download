import sys
import os
import time
import webbrowser
import threading
import multiprocessing
from rich.console import Console

# Adjust path if running from source (not frozen)
if not getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

console = Console()

def open_browser():
    time.sleep(2)
    webbrowser.open("http://127.0.0.1:8000")

def main():
    console.print("[bold cyan]=========================================[/bold cyan]")
    console.print("[bold cyan]  欢迎使用 Plaso-DL (伯索云学堂下载器)  [/bold cyan]")
    console.print("[bold cyan]=========================================[/bold cyan]")
    console.print("\n请选择启动模式:")
    console.print("1) 赛博网页版 (推荐，可视化操作)")
    console.print("2) 经典命令行 (终端交互)")
    
    try:
        choice = input("\n请输入 1 或 2 (默认1): ").strip()
    except EOFError:
        choice = "1"
    
    if choice == "2":
        from plaso_dl.launcher import main as cli_main
        cli_main()
    else:
        console.print("\n[bold green]正在启动赛博网页版...[/bold green]")
        console.print("如果浏览器没有自动打开，请手动访问: http://127.0.0.1:8000")
        console.print("如需退出，请直接关闭此控制台窗口。")
        
        # Start browser in a background thread
        threading.Thread(target=open_browser, daemon=True).start()
        
        # Import after path adjustment
        import uvicorn
        from plaso_dl.server import app
        
        # Run server (single worker to avoid PyInstaller multiprocessing issues)
        uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    # Required for multiprocessing support in PyInstaller (e.g. if uvicorn tries to fork)
    multiprocessing.freeze_support()
    main()
