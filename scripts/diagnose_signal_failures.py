"""
Comprehensive Signal Failure Diagnostic Script

This script diagnoses why trading signals fail to execute, based on the client's
comprehensive Bybit failure checklist. It checks both Bybit-side and bot-side issues.

CLIENT REQUIREMENT: 5-10% pending signals is normal, 90% pending means broken logic.

Usage:
    python scripts/diagnose_signal_failures.py
    
Output:
    - Detailed report of all signals and their execution status
    - Specific failure reasons for each blocked signal
    - Statistics on pending vs executed ratio
    - Recommendations for fixes
"""

import asyncio
import sys
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import aiosqlite

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.logging import system_logger
from app.bybit.client import get_bybit_client
from app.core.symbol_registry import get_symbol_registry
from app.core.strict_config import STRICT_CONFIG
from app.config.settings import CATEGORY


class SignalFailureDiagnostic:
    """Comprehensive diagnostic for signal execution failures."""
    
    def __init__(self):
        self.bybit_client = None
        self.symbol_registry = None
        self.results = {
            'total_signals': 0,
            'executed_signals': 0,
            'pending_signals': 0,
            'failed_signals': 0,
            'failure_reasons': {},
            'bybit_issues': [],
            'bot_issues': [],
            'recommendations': []
        }
    
    async def initialize(self):
        """Initialize clients and registries."""
        self.bybit_client = get_bybit_client()
        self.symbol_registry = get_symbol_registry()
        print("[OK] Diagnostic tools initialized")
    
    async def run_full_diagnostic(self):
        """Run complete diagnostic check."""
        print("\n" + "="*80)
        print("SIGNAL EXECUTION DIAGNOSTIC REPORT")
        print("="*80)
        print(f"Time: {datetime.now().isoformat()}")
        print(f"Environment: {'DEMO' if 'demo' in STRICT_CONFIG.bybit_endpoint else 'PRODUCTION'}")
        print("="*80 + "\n")
        
        # Step 1: Check database for signal execution status
        print("📊 STEP 1: Analyzing Signal Execution History...")
        await self._analyze_signal_history()
        
        # Step 2: Check Bybit account status
        print("\n💰 STEP 2: Checking Bybit Account Status...")
        await self._check_account_status()
        
        # Step 3: Check active orders and positions
        print("\n📈 STEP 3: Checking Active Orders & Positions...")
        await self._check_active_orders_and_positions()
        
        # Step 4: Validate symbol configurations
        print("\n🔧 STEP 4: Validating Symbol Configurations...")
        await self._validate_symbol_configurations()
        
        # Step 5: Check bot filters and guards
        print("\n🛡️ STEP 5: Checking Bot Filters & Guards...")
        await self._check_bot_filters()
        
        # Step 6: Check signal blocking system
        print("\n🚫 STEP 6: Checking Signal Blocking System...")
        await self._check_signal_blocking()
        
        # Step 7: Generate summary and recommendations
        print("\n📋 STEP 7: Generating Summary & Recommendations...")
        await self._generate_summary()
        
        print("\n" + "="*80)
        print("DIAGNOSTIC COMPLETE")
        print("="*80 + "\n")
    
    async def _analyze_signal_history(self):
        """Analyze signal execution history from database."""
        try:
            db_path = project_root / "trades.sqlite"
            if not db_path.exists():
                print(f"  ⚠️  Database not found: {db_path}")
                return
            
            async with aiosqlite.connect(str(db_path)) as db:
                # Get all signals from last 24 hours
                yesterday = (datetime.now() - timedelta(days=1)).isoformat()
                
                # Check trades_new table
                cursor = await db.execute("""
                    SELECT 
                        trade_id,
                        symbol,
                        direction,
                        state,
                        created_at,
                        leverage,
                        position_size,
                        entry_price
                    FROM trades_new
                    WHERE created_at > ?
                    ORDER BY created_at DESC
                """, (yesterday,))
                
                trades = await cursor.fetchall()
                
                if not trades:
                    print("  ℹ️  No trades found in last 24 hours")
                    print("  💡 This might indicate signals are not reaching the execution stage!")
                    self.results['bot_issues'].append("No trades created in 24h - signals may be blocked before FSM")
                    return
                
                # Analyze trade states
                state_counts = {}
                pending_trades = []
                failed_trades = []
                
                for trade in trades:
                    trade_id, symbol, direction, state, created_at, leverage, position_size, entry_price = trade
                    self.results['total_signals'] += 1
                    
                    state_counts[state] = state_counts.get(state, 0) + 1
                    
                    if state in ['INIT', 'LEVERAGE_SET', 'ENTRY_PLACED']:
                        self.results['pending_signals'] += 1
                        pending_trades.append({
                            'trade_id': trade_id,
                            'symbol': symbol,
                            'state': state,
                            'created_at': created_at
                        })
                    elif state in ['ENTRY_FILLED', 'TP_SL_PLACED', 'RUNNING']:
                        self.results['executed_signals'] += 1
                    elif state in ['ERROR', 'CLOSED']:
                        self.results['failed_signals'] += 1
                        failed_trades.append({
                            'trade_id': trade_id,
                            'symbol': symbol,
                            'state': state,
                            'created_at': created_at
                        })
                
                # Calculate percentages
                total = self.results['total_signals']
                pending_pct = (self.results['pending_signals'] / total * 100) if total > 0 else 0
                executed_pct = (self.results['executed_signals'] / total * 100) if total > 0 else 0
                failed_pct = (self.results['failed_signals'] / total * 100) if total > 0 else 0
                
                print(f"\n  Total Signals (24h): {total}")
                print(f"  ✅ Executed: {self.results['executed_signals']} ({executed_pct:.1f}%)")
                print(f"  ⏳ Pending: {self.results['pending_signals']} ({pending_pct:.1f}%)")
                print(f"  ❌ Failed: {self.results['failed_signals']} ({failed_pct:.1f}%)")
                
                print(f"\n  📊 State Distribution:")
                for state, count in sorted(state_counts.items(), key=lambda x: -x[1]):
                    pct = (count / total * 100) if total > 0 else 0
                    print(f"     {state}: {count} ({pct:.1f}%)")
                
                # CLIENT SPEC: Flag if >10% are pending
                if pending_pct > 10:
                    print(f"\n  🚨 CRITICAL: {pending_pct:.1f}% of signals are pending!")
                    print(f"     Expected: 5-10% pending")
                    print(f"     Current: {pending_pct:.1f}% pending (ABNORMAL)")
                    self.results['bot_issues'].append(f"High pending rate: {pending_pct:.1f}% (expected 5-10%)")
                    
                    # Show pending trades
                    if pending_trades:
                        print(f"\n  📋 Pending Trades (showing first 10):")
                        for trade in pending_trades[:10]:
                            age = self._calculate_age(trade['created_at'])
                            print(f"     - {trade['symbol']} ({trade['state']}) - Age: {age}")
                
                # Show failed trades
                if failed_trades:
                    print(f"\n  ❌ Failed Trades (showing first 5):")
                    for trade in failed_trades[:5]:
                        age = self._calculate_age(trade['created_at'])
                        print(f"     - {trade['symbol']} ({trade['state']}) - Age: {age}")
                        
                        # Get error details if available
                        await self._get_trade_error_details(db, trade['trade_id'])
                
        except Exception as e:
            print(f"  ❌ Error analyzing signal history: {e}")
            import traceback
            traceback.print_exc()
    
    def _calculate_age(self, created_at: str) -> str:
        """Calculate how long ago the trade was created."""
        try:
            created = datetime.fromisoformat(created_at)
            age = datetime.now() - created
            
            if age.days > 0:
                return f"{age.days}d {age.seconds // 3600}h ago"
            elif age.seconds >= 3600:
                return f"{age.seconds // 3600}h ago"
            elif age.seconds >= 60:
                return f"{age.seconds // 60}m ago"
            else:
                return f"{age.seconds}s ago"
        except:
            return "unknown"
    
    async def _get_trade_error_details(self, db, trade_id: str):
        """Get error details for a failed trade from system logs."""
        # This would require parsing system.log file
        # For now, just note that we should check logs
        pass
    
    async def _check_account_status(self):
        """Check Bybit account status and available margin."""
        try:
            # Get wallet balance
            balance_result = await self.bybit_client.wallet_balance("USDT")
            
            if not balance_result or balance_result.get('retCode') != 0:
                print(f"  ❌ Failed to get account balance: {balance_result}")
                self.results['bybit_issues'].append("Cannot retrieve account balance from Bybit")
                return
            
            # Extract balance data
            if 'result' in balance_result and 'list' in balance_result['result']:
                account_info = balance_result['result']['list'][0]
                total_balance = Decimal(account_info.get('totalWalletBalance', '0'))
                available_balance = Decimal(account_info.get('availableBalance', '0'))
                total_margin = Decimal(account_info.get('totalPositionMM', '0'))
                
                print(f"\n  💰 Account Balance:")
                print(f"     Total Balance: {total_balance} USDT")
                print(f"     Available: {available_balance} USDT")
                print(f"     Used Margin: {total_margin} USDT")
                
                # Check if balance is sufficient
                if total_balance < Decimal("10"):
                    print(f"  ⚠️  LOW BALANCE: {total_balance} USDT")
                    self.results['bybit_issues'].append(f"Low account balance: {total_balance} USDT")
                    self.results['recommendations'].append("Deposit more funds to Bybit account")
                
                if available_balance < Decimal("5"):
                    print(f"  ⚠️  LOW AVAILABLE BALANCE: {available_balance} USDT")
                    self.results['bybit_issues'].append(f"Low available balance: {available_balance} USDT")
                    self.results['recommendations'].append("Free up margin or deposit more funds")
            else:
                print(f"  ⚠️  Unexpected balance format: {balance_result}")
        
        except Exception as e:
            print(f"  ❌ Error checking account status: {e}")
            self.results['bybit_issues'].append(f"Account status check failed: {e}")
    
    async def _check_active_orders_and_positions(self):
        """Check active orders and positions on Bybit."""
        try:
            # Get active orders
            orders_result = await self.bybit_client.get_open_orders(CATEGORY, settleCoin="USDT")
            
            if orders_result and orders_result.get('retCode') == 0:
                orders = orders_result.get('result', {}).get('list', [])
                print(f"\n  📊 Active Orders: {len(orders)}")
                
                if orders:
                    # Group by symbol
                    by_symbol = {}
                    for order in orders:
                        symbol = order.get('symbol')
                        by_symbol.setdefault(symbol, []).append(order)
                    
                    for symbol, symbol_orders in by_symbol.items():
                        print(f"     {symbol}: {len(symbol_orders)} orders")
                        for order in symbol_orders[:3]:  # Show first 3
                            order_type = order.get('orderType')
                            side = order.get('side')
                            price = order.get('price')
                            qty = order.get('qty')
                            status = order.get('orderStatus')
                            print(f"       - {side} {order_type} @ {price} (qty: {qty}, status: {status})")
            
            # Get active positions
            positions_result = await self.bybit_client.get_position(CATEGORY)
            
            if positions_result and positions_result.get('retCode') == 0:
                positions = positions_result.get('result', {}).get('list', [])
                active_positions = [p for p in positions if float(p.get('size', 0)) > 0]
                
                print(f"\n  📈 Active Positions: {len(active_positions)}")
                
                if active_positions:
                    for pos in active_positions:
                        symbol = pos.get('symbol')
                        side = pos.get('side')
                        size = pos.get('size')
                        entry_price = pos.get('avgPrice')
                        unrealized_pnl = pos.get('unrealisedPnl')
                        leverage = pos.get('leverage')
                        print(f"     {symbol}: {side} {size} contracts @ {entry_price} (leverage: {leverage}x, PnL: {unrealized_pnl})")
        
        except Exception as e:
            print(f"  ❌ Error checking orders/positions: {e}")
    
    async def _validate_symbol_configurations(self):
        """Validate symbol configurations against Bybit requirements."""
        try:
            # Get unique symbols from recent trades
            db_path = project_root / "trades.sqlite"
            if not db_path.exists():
                return
            
            async with aiosqlite.connect(str(db_path)) as db:
                cursor = await db.execute("""
                    SELECT DISTINCT symbol 
                    FROM trades_new 
                    WHERE created_at > datetime('now', '-7 days')
                """)
                symbols = [row[0] for row in await cursor.fetchall()]
            
            if not symbols:
                print("  ℹ️  No symbols found in recent trades")
                return
            
            print(f"\n  🔧 Validating {len(symbols)} symbols...")
            
            validation_issues = []
            
            for symbol in symbols:
                symbol_info = await self.symbol_registry.get_symbol_info(symbol)
                
                if not symbol_info:
                    print(f"  ❌ {symbol}: NOT FOUND IN BYBIT")
                    validation_issues.append(f"{symbol}: Not available on Bybit")
                    self.results['bybit_issues'].append(f"Symbol {symbol} not found on Bybit")
                    continue
                
                # Check if symbol is tradable
                if symbol_info.status != "Trading":
                    print(f"  ⚠️  {symbol}: Status = {symbol_info.status} (NOT TRADING)")
                    validation_issues.append(f"{symbol}: Status {symbol_info.status}")
                    self.results['bybit_issues'].append(f"Symbol {symbol} is not trading (status: {symbol_info.status})")
                    continue
                
                # Check tick size and step size
                print(f"  ✅ {symbol}: OK (tick: {symbol_info.tick_size}, step: {symbol_info.step_size}, max_leverage: {symbol_info.max_leverage})")
            
            if validation_issues:
                print(f"\n  ⚠️  Found {len(validation_issues)} symbol validation issues")
                self.results['recommendations'].append("Remove or fix non-tradable symbols from signal channels")
        
        except Exception as e:
            print(f"  ❌ Error validating symbols: {e}")
    
    async def _check_bot_filters(self):
        """Check bot-side filters and guards."""
        try:
            # Check market guards
            from app.core.market_guards import get_market_guards
            guards = get_market_guards()
            
            print(f"\n  🛡️  Market Guards Configuration:")
            print(f"     Volatility threshold: {guards.volatility_threshold}%")
            print(f"     Spread threshold: {guards.spread_threshold}%")
            print(f"     Volume threshold: {guards.volume_threshold}%")
            
            # Check trade limiter
            from app.core.trade_limiter import get_trade_limiter
            limiter = get_trade_limiter()
            active_trades_info = limiter.get_active_trades()
            
            print(f"\n  📊 Trade Limiter:")
            print(f"     Max trades: {limiter.max_trades}")
            print(f"     Active trades: {active_trades_info['count']}")
            print(f"     Max per symbol: {limiter.max_trades_per_symbol}")
            
            if active_trades_info['count'] >= limiter.max_trades:
                print(f"  ⚠️  TRADE LIMIT REACHED!")
                self.results['bot_issues'].append("Trade limit reached - new signals will be rejected")
                self.results['recommendations'].append("Close some positions to free up trade slots")
            
            # Check circuit breaker
            from app.core.circuit_breaker import get_circuit_breaker
            breaker = get_circuit_breaker()
            breaker_status = breaker.get_status()
            
            print(f"\n  🔌 Circuit Breaker:")
            print(f"     State: {breaker_status['state']}")
            print(f"     Consecutive failures: {breaker_status['consecutive_failures']}")
            
            if breaker_status['state'] == 'OPEN':
                print(f"  🚨 CIRCUIT BREAKER IS OPEN - ALL TRADING BLOCKED!")
                self.results['bot_issues'].append("Circuit breaker is OPEN - all trading is blocked")
                self.results['recommendations'].append("Investigate circuit breaker trigger cause and reset")
            
            # Check NTP sync
            from app.core.ntp_sync import get_ntp_monitor
            ntp_monitor = get_ntp_monitor()
            
            if ntp_monitor.trading_blocked:
                print(f"  🚨 NTP CLOCK DRIFT DETECTED - TRADING BLOCKED!")
                print(f"     Drift: {ntp_monitor.last_drift * 1000:.1f}ms")
                self.results['bot_issues'].append(f"Clock drift detected: {ntp_monitor.last_drift * 1000:.1f}ms - trading blocked")
                self.results['recommendations'].append("Sync system clock or restart bot to fix NTP drift")
        
        except Exception as e:
            print(f"  ❌ Error checking bot filters: {e}")
            import traceback
            traceback.print_exc()
    
    async def _check_signal_blocking(self):
        """Check signal blocking system."""
        try:
            from app.core.signal_blocking import get_signal_blocking_manager
            blocking_mgr = get_signal_blocking_manager()
            
            stats = blocking_mgr.get_blocking_stats()
            
            print(f"\n  🚫 Signal Blocking System:")
            print(f"     Total blocked signals: {stats['total_blocked_signals']}")
            print(f"     Active blocks: {stats['active_blocks']}")
            print(f"     Block duration: {stats['block_duration_hours']} hours")
            print(f"     Tolerance: {stats['tolerance_percent']}%")
            
            if stats['active_blocks'] > 10:
                print(f"  ⚠️  HIGH NUMBER OF ACTIVE BLOCKS: {stats['active_blocks']}")
                self.results['bot_issues'].append(f"High number of blocked signals: {stats['active_blocks']}")
                self.results['recommendations'].append("Review signal blocking rules - may be too aggressive")
        
        except Exception as e:
            print(f"  ❌ Error checking signal blocking: {e}")
    
    async def _generate_summary(self):
        """Generate summary and recommendations."""
        print(f"\n" + "="*80)
        print("SUMMARY & RECOMMENDATIONS")
        print("="*80)
        
        # Calculate health score
        total = self.results['total_signals']
        if total == 0:
            print("\n⚠️  NO SIGNALS FOUND - Bot may not be receiving signals!")
            print("\nPossible causes:")
            print("  1. Telegram client not connected")
            print("  2. No whitelisted channels configured")
            print("  3. Signal parser failing to parse all messages")
            print("  4. Bot not running")
            return
        
        pending_pct = (self.results['pending_signals'] / total * 100)
        executed_pct = (self.results['executed_signals'] / total * 100)
        failed_pct = (self.results['failed_signals'] / total * 100)
        
        print(f"\n📈 Execution Performance:")
        print(f"   Executed: {executed_pct:.1f}% (Target: >80%)")
        print(f"   Pending:  {pending_pct:.1f}% (Target: 5-10%)")
        print(f"   Failed:   {failed_pct:.1f}% (Target: <10%)")
        
        # Health assessment
        if pending_pct <= 10 and executed_pct >= 80:
            print(f"\n✅ HEALTH: GOOD")
        elif pending_pct <= 20 and executed_pct >= 60:
            print(f"\n⚠️  HEALTH: MODERATE - Needs attention")
        else:
            print(f"\n🚨 HEALTH: POOR - Immediate action required")
        
        # Bybit Issues
        if self.results['bybit_issues']:
            print(f"\n🔴 Bybit-Side Issues Found ({len(self.results['bybit_issues'])}):")
            for i, issue in enumerate(self.results['bybit_issues'][:10], 1):
                print(f"   {i}. {issue}")
        
        # Bot Issues
        if self.results['bot_issues']:
            print(f"\n🟡 Bot-Side Issues Found ({len(self.results['bot_issues'])}):")
            for i, issue in enumerate(self.results['bot_issues'][:10], 1):
                print(f"   {i}. {issue}")
        
        # Recommendations
        if self.results['recommendations']:
            print(f"\n💡 Recommendations:")
            for i, rec in enumerate(self.results['recommendations'][:10], 1):
                print(f"   {i}. {rec}")
        
        if not self.results['bybit_issues'] and not self.results['bot_issues']:
            print(f"\n✅ No critical issues found")
            if pending_pct > 10:
                print(f"\n💡 However, pending rate is high ({pending_pct:.1f}%)")
                print(f"   This could indicate:")
                print(f"   - PostOnly orders waiting for exact price")
                print(f"   - Market volatility preventing fills")
                print(f"   - Price gaps in limit orders")
                print(f"   - Symbol-specific issues")


async def main():
    """Main diagnostic entry point."""
    diagnostic = SignalFailureDiagnostic()
    
    try:
        await diagnostic.initialize()
        await diagnostic.run_full_diagnostic()
    except KeyboardInterrupt:
        print("\n\n❌ Diagnostic interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Diagnostic failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

