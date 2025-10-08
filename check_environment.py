#!/usr/bin/env python3
"""
Check environment detection and TP/SL strategy
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def check_environment():
    """Check environment detection and TP/SL strategy"""
    try:
        from app.core.environment_detector import get_environment_detector
        
        print("🔍 Checking Environment Detection...")
        print("=" * 50)
        
        detector = get_environment_detector()
        await detector.detect_environment()
        
        print(f"Environment: {detector.environment}")
        print(f"TP/SL Strategy: {detector.tpsl_strategy}")
        
        capabilities = detector.get_capabilities()
        print(f"Native TP/SL Available: {capabilities['native_tpsl_available']}")
        print(f"Available Symbols: {capabilities['symbols_available']}")
        
        # Test native TP/SL API directly
        print("\n🧪 Testing Native TP/SL API...")
        from app.bybit.client import get_bybit_client
        client = get_bybit_client()
        
        # Try to set TP/SL on the existing BIOUSDT position
        try:
            result = await client.set_trading_stop(
                category="linear",
                symbol="BIOUSDT",
                take_profit=Decimal("0.12"),  # Test TP
                stop_loss=Decimal("0.15"),    # Test SL
                tp_order_type="Market",
                sl_order_type="Market"
            )
            print(f"✅ Native TP/SL API works: {result}")
        except Exception as e:
            print(f"❌ Native TP/SL API failed: {e}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    from decimal import Decimal
    asyncio.run(check_environment())
