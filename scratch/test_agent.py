import asyncio
import sys
import threading
import uvicorn
from app.main import app
from app.ai.coordinator import Coordinator
import time

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

def main():
    # Start server in a background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for server to boot
    time.sleep(2)
    
    coordinator = Coordinator()
    print("\n--- Testing Agent Hierarchy ---")
    
    print("\nUser: Give me the weekly briefing for Downtown.")
    response1 = coordinator.handle_message("Give me the weekly briefing for Downtown.")
    print(f"\nAgent:\n{response1}")
    
    print("\nUser: Drill down into labor overtime, please.")
    response2 = coordinator.handle_message("Drill down into labor overtime, please.")
    print(f"\nAgent:\n{response2}")
    
    sys.exit(0)

if __name__ == "__main__":
    main()
