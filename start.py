#!/usr/bin/env python3
"""
Bybit Copybot Pro - Main Startup Script
Single entry point for all bot operations

Usage:
    python start.py                    # Normal startup
    python start.py --audit            # With audit logger
    python start.py --clean            # Clean restart (reset session)
    python start.py --audit --backfill # With audit + backfill last 7 days
"""

import os
import sys
import subprocess
import time
import glob
import argparse
from pathlib import Path


def setup_environment():
    """Setup Python path and environment"""
    # Add project root to path
    project_root = Path(__file__).parent.resolve()
    sys.path.insert(0, str(project_root))
    
    # Set PYTHONPATH for subprocesses
    os.environ["PYTHONPATH"] = str(project_root)
    
    # Fix Windows console encoding for emojis
    if sys.platform.startswith("win"):
        import codecs
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        try:
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            else:
                sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, errors='replace')
        except:
            pass
        try:
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
            else:
                sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, errors='replace')
        except:
            pass
    
    return project_root


def clean_session():
    """Clean Telegram session files for fresh start"""
    print("=" * 70)
    print("CLEAN RESTART - TELEGRAM SESSION RESET")
    print("=" * 70)
    print()
    
    session_files = glob.glob("bybit_copybot_session.session*")
    
    if not session_files:
        print("[OK] No session files found - fresh start!")
        return True
    
    print(f"[*] Found {len(session_files)} session files:")
    for f in session_files:
        print(f"   - {f}")
    
    print("\n[WARNING] These files will be deleted and regenerated on next startup")
    print("   You may need to re-authenticate with Telegram")
    print()
    
    response = input("Delete session files? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("\n[CANCEL] Cancelled. Session files not deleted.")
        return False
    
    for f in session_files:
        try:
            os.remove(f)
            print(f"   [OK] Deleted: {f}")
        except Exception as e:
            print(f"   [ERROR] Could not delete {f}: {e}")
    
    print("\n[OK] Session files removed! Fresh start ready.")
    return True


def start_bot_process():
    """Start the main bot process"""
    print("\n[*] Starting Bybit Copybot Pro...")
    
    try:
        bot_process = subprocess.Popen(
            [sys.executable, "-m", "app.main"],
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        print(f"[OK] Bot started (PID: {bot_process.pid})")
        return bot_process
    except Exception as e:
        print(f"[ERROR] Failed to start bot: {e}")
        return None


def start_audit_process(backfill=False, days=7):
    """Start the audit logger process"""
    print("\n[*] Starting Audit Logger...")
    
    audit_cmd = [sys.executable, "bybit_demo_audit_logger.py"]
    
    if backfill:
        audit_cmd.extend(["--backfill", "--days", str(days)])
        print(f"   With backfill: last {days} days")
    
    try:
        audit_process = subprocess.Popen(
            audit_cmd,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        print(f"[OK] Audit Logger started (PID: {audit_process.pid})")
        return audit_process
    except Exception as e:
        print(f"[ERROR] Failed to start audit logger: {e}")
        return None


def main():
    """Main startup function"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Bybit Copybot Pro - Main Startup Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start.py                    # Normal startup
  python start.py --audit            # With audit logger
  python start.py --clean            # Clean restart
  python start.py --audit --backfill # With audit + backfill
        """
    )
    
    parser.add_argument(
        "--audit", "-a",
        action="store_true",
        help="Start with audit logger"
    )
    
    parser.add_argument(
        "--backfill", "-b",
        action="store_true",
        help="Backfill audit data (requires --audit)"
    )
    
    parser.add_argument(
        "--days", "-d",
        type=int,
        default=7,
        help="Days to backfill (default: 7)"
    )
    
    parser.add_argument(
        "--clean", "-c",
        action="store_true",
        help="Clean restart (reset Telegram session)"
    )
    
    args = parser.parse_args()
    
    # Setup environment
    project_root = setup_environment()
    
    # Display header
    print("=" * 70)
    print("BYBIT COPYBOT PRO - STARTUP")
    print("=" * 70)
    print(f"Directory: {project_root}")
    print(f"Python: {sys.executable}")
    print(f"Version: {sys.version.split()[0]}")
    print("=" * 70)
    
    # Handle clean restart
    if args.clean:
        if not clean_session():
            return
        print("\n" + "=" * 70)
        print("Ready for fresh start!")
        print("=" * 70)
        print()
    
    # Check for audit backfill without audit flag
    if args.backfill and not args.audit:
        print("\n[WARNING] --backfill requires --audit flag")
        print("   Use: python start.py --audit --backfill")
        return
    
    # Start processes
    processes = []
    
    try:
        # Start main bot
        bot_process = start_bot_process()
        if bot_process is None:
            return
        
        processes.append(("Bot", bot_process))
        time.sleep(3)  # Give bot time to initialize
        
        # Start audit logger if requested
        if args.audit:
            audit_process = start_audit_process(
                backfill=args.backfill,
                days=args.days
            )
            if audit_process:
                processes.append(("Audit Logger", audit_process))
        else:
            print("\n[INFO] Audit Logger not started")
            print("   Use --audit flag to enable")
        
        # Display status
        print("\n" + "=" * 70)
        print("[OK] ALL SYSTEMS RUNNING")
        print("=" * 70)
        print(f"\nRunning processes: {len(processes)}")
        for name, proc in processes:
            print(f"   - {name} (PID: {proc.pid})")
        print("\nPress Ctrl+C to stop all processes")
        print()
        
        # Monitor processes
        while True:
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"\n[WARNING] {name} exited with code {proc.returncode}")
                    raise KeyboardInterrupt
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n[STOP] Shutting down...")
        for name, proc in processes:
            try:
                print(f"   Stopping {name}...")
                proc.terminate()
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print(f"   Force killing {name}...")
                proc.kill()
        print("[OK] All processes stopped")
    
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Cleanup
        for name, proc in processes:
            try:
                proc.kill()
            except:
                pass


if __name__ == "__main__":
    main()

