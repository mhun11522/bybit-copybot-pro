#!/usr/bin/env python3
"""
Clean bot restart - Fixes Telegram session sync issues
"""

import os
import sys
import glob

print("=" * 70)
print("BOT CLEAN RESTART - TELEGRAM SESSION RESET")
print("=" * 70)

# Step 1: Find and backup session files
session_files = glob.glob("bybit_copybot_session.session*")

if session_files:
    print(f"\n📋 Found {len(session_files)} session files:")
    for f in session_files:
        print(f"   - {f}")
    
    print("\n🔄 These files will be regenerated on next startup")
    print("   (You may need to re-authenticate with Telegram)")
    
    # Ask for confirmation
    response = input("\n⚠️  Delete session files and restart fresh? (yes/no): ").strip().lower()
    
    if response == 'yes':
        for f in session_files:
            try:
                os.remove(f)
                print(f"   ✅ Deleted: {f}")
            except Exception as e:
                print(f"   ❌ Could not delete {f}: {e}")
        
        print("\n✅ Session files removed!")
        print("\n🚀 Now restart the bot with:")
        print("   python start_bot.py")
        print("\n⚠️  You may need to:")
        print("   1. Confirm Telegram authentication (phone number)")
        print("   2. Enter verification code")
        print("   3. Enter 2FA password (if enabled)")
    else:
        print("\n❌ Cancelled. Session files not deleted.")
        print("\nTo fix the 'Security error' issues, you need to reset the session.")
else:
    print("\n✅ No session files found")
    print("\n🚀 You can start the bot with:")
    print("   python start_bot.py")

