#!/usr/bin/env python3
"""
Proper bot startup script with Windows asyncio compatibility.
"""

import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_windows_asyncio():
    """Setup Windows-compatible asyncio event loop."""
    if sys.platform == "win32":
        try:
            from asyncio import WindowsProactorEventLoopPolicy
            asyncio.set_event_loop_policy(WindowsProactorEventLoopPolicy())
            print("Windows ProactorEventLoop policy set")
        except Exception as e:
            print(f"Could not set Windows asyncio policy: {e}")

async def main():
    """Main bot startup function."""
    try:
        print("Starting Bybit Copybot...")
        
        # Import and start the bot
        from app.main import main as bot_main
        await bot_main()
        
    except Exception as e:
        print(f"Bot startup failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    # Setup Windows asyncio compatibility
    setup_windows_asyncio()
    
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Bot crashed: {e}")
        import traceback
        traceback.print_exc()
