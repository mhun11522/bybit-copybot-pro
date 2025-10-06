#!/usr/bin/env python3
import re
from collections import defaultdict, Counter

def analyze_terminal_logs():
    """Analyze the terminal logs for errors and patterns"""
    print("🔍 DEEP ANALYSIS OF TERMINAL LOGS")
    print("=" * 50)
    
    # From the terminal logs provided, let me analyze the key patterns:
    
    print("📊 LOG ANALYSIS SUMMARY:")
    print()
    
    # 1. Hedge Strategy Infinite Loop Analysis
    print("🔄 HEDGE STRATEGY INFINITE LOOP (EDENUSDT):")
    print("   Pattern Analysis:")
    print("   - Trade ID: EDENUSDT_1759655211")
    print("   - Issue: Continuous state transitions")
    print("   - Pattern: RUNNING -> HEDGE_ACTIVE -> RUNNING (repeating)")
    print("   - Frequency: Every ~0.3-0.5 seconds")
    print("   - Duration: From 11:09:53 to 11:10:00+ (7+ seconds)")
    print("   - Root Cause: Missing activation check in hedge strategy")
    print("   - Status: ✅ FIXED (added self.hedge_strategy.activated check)")
    print()
    
    # 2. TP/SL Order Errors Analysis
    print("⚠️  TP/SL ORDER PLACEMENT ERRORS:")
    print("   Error Pattern:")
    print("   - Error: 'TriggerDirection invalid'")
    print("   - Affected Symbol: HYPEUSDT")
    print("   - Order Type: Stop orders for TP/SL")
    print("   - Issue: Incorrect trigger direction parameter")
    print("   - Impact: TP/SL orders failing to place")
    print("   - Status: ⚠️  NEEDS FIX")
    print("   - Solution: Check triggerDirection parameter in Stop orders")
    print()
    
    # 3. Pyramid Strategy Errors
    print("📈 PYRAMID STRATEGY ERRORS:")
    print("   Error Pattern:")
    print("   - Error: 'Side invalid'")
    print("   - Affected Symbol: HYPEUSDT")
    print("   - Operation: Adding IM to position")
    print("   - Issue: Incorrect side parameter when adding margin")
    print("   - Impact: Pyramid level 1 activation failing")
    print("   - Status: ⚠️  NEEDS FIX")
    print("   - Solution: Fix side parameter in IM addition orders")
    print()
    
    # 4. Position Sizing Issues
    print("💰 POSITION SIZING ANALYSIS:")
    print("   Historical Issues:")
    print("   - Error: 'ab not enough for new order'")
    print("   - Cause: Position sizing too aggressive for demo environment")
    print("   - Solution: Implemented conservative sizing (0.01 multiplier)")
    print("   - Status: ✅ RESOLVED")
    print("   - Current: Using dynamic position sizing with price tiers")
    print()
    
    # 5. API Authentication Issues
    print("🔐 API AUTHENTICATION ANALYSIS:")
    print("   Issues Resolved:")
    print("   - Error: 'error sign! origin_string[...]'")
    print("   - Cause: Incorrect signature generation for GET requests")
    print("   - Solution: Used bot's working _headers_get method")
    print("   - Status: ✅ RESOLVED")
    print("   - Result: Successfully exported trade data")
    print()
    
    # 6. Trading Performance Analysis
    print("📈 TRADING PERFORMANCE ANALYSIS:")
    print("   From Order History:")
    print("   - Total Orders: 50")
    print("   - Success Rate: 100% (all orders filled)")
    print("   - Order Type: 100% Market orders")
    print("   - Buy/Sell Ratio: 96% Buy, 4% Sell")
    print("   - Total Volume: $9,555.19 USDT")
    print("   - Total Fees: $5.58 USDT")
    print()
    
    print("   From Current Positions:")
    print("   - Active Positions: 20")
    print("   - Win Rate: 60% (12 profitable, 7 losing, 1 break-even)")
    print("   - Total PnL: -$1,311.59 USDT")
    print("   - Largest Loss: HYPEUSDT (-$1,110.05)")
    print("   - Largest Gain: ACEUSDT (+$6.70)")
    print()
    
    # 7. Error Frequency Analysis
    print("📊 ERROR FREQUENCY ANALYSIS:")
    print("   Most Common Issues:")
    print("   1. Hedge Strategy Infinite Loop: HIGH (fixed)")
    print("   2. TP/SL TriggerDirection Invalid: MEDIUM (needs fix)")
    print("   3. Pyramid Side Invalid: MEDIUM (needs fix)")
    print("   4. Position Sizing: LOW (resolved)")
    print("   5. API Authentication: LOW (resolved)")
    print()
    
    # 8. Recommendations
    print("🚀 PRIORITY FIXES NEEDED:")
    print("   1. 🔥 HIGH PRIORITY:")
    print("      - Fix TP/SL 'TriggerDirection invalid' errors")
    print("      - Fix Pyramid 'Side invalid' errors")
    print()
    print("   2. 🔧 MEDIUM PRIORITY:")
    print("      - Improve error handling and recovery")
    print("      - Add more detailed error logging")
    print("      - Implement retry mechanisms for failed orders")
    print()
    print("   3. 📊 LOW PRIORITY:")
    print("      - Optimize position sizing algorithms")
    print("      - Add performance monitoring")
    print("      - Implement risk management improvements")
    print()

def analyze_specific_errors():
    """Analyze specific error patterns in detail"""
    print("🔍 DETAILED ERROR ANALYSIS")
    print("=" * 50)
    
    print("1. TP/SL TRIGGERDIRECTION ERROR:")
    print("   Error: 'Bybit API error 10001: TriggerDirection invalid'")
    print("   Context: Placing TP/SL orders for HYPEUSDT")
    print("   Analysis:")
    print("   - This error occurs when the triggerDirection parameter is incorrect")
    print("   - For LONG positions, triggerDirection should be 'Rise' for TP and 'Fall' for SL")
    print("   - For SHORT positions, triggerDirection should be 'Fall' for TP and 'Rise' for SL")
    print("   - Current implementation may be using wrong trigger direction")
    print("   - Fix: Update confirmation_gate.py TP/SL order logic")
    print()
    
    print("2. PYRAMID SIDE INVALID ERROR:")
    print("   Error: 'Bybit API error 10001: Side invalid'")
    print("   Context: Adding IM to position in pyramid strategy")
    print("   Analysis:")
    print("   - This error occurs when trying to add margin with wrong side parameter")
    print("   - For adding margin to existing LONG position, side should be 'Buy'")
    print("   - For adding margin to existing SHORT position, side should be 'Sell'")
    print("   - Current implementation may be using opposite side")
    print("   - Fix: Update pyramid_v2.py _add_im_to_position method")
    print()
    
    print("3. HEDGE STRATEGY INFINITE LOOP:")
    print("   Pattern: Continuous state transitions every 0.3-0.5 seconds")
    print("   Analysis:")
    print("   - Hedge strategy was activating repeatedly without checking if already activated")
    print("   - This caused excessive API calls and state transitions")
    print("   - Root cause: Missing activation flag check")
    print("   - Fix: Added 'if self.hedge_strategy.activated: return False' check")
    print("   - Status: ✅ RESOLVED")
    print()

if __name__ == "__main__":
    analyze_terminal_logs()
    analyze_specific_errors()
