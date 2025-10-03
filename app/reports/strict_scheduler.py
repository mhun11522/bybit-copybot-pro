"""Strict report scheduler with exact client timing requirements."""

import asyncio
from datetime import datetime, time, timedelta
from typing import Dict, Any, List, Tuple
from decimal import Decimal
from app.core.strict_config import STRICT_CONFIG
from app.core.logging import system_logger
from app.telegram.swedish_templates import get_swedish_templates
from app.telegram.output import send_message
from app.storage.db import get_db_connection

class StrictReportScheduler:
    """Report scheduler with exact client timing requirements."""
    
    def __init__(self):
        self.templates = get_swedish_templates()
        self.timezone = STRICT_CONFIG.get_timezone()
        self.daily_hour = STRICT_CONFIG.daily_report_hour
        self.weekly_hour = STRICT_CONFIG.weekly_report_hour
        self.weekly_day = STRICT_CONFIG.weekly_report_day  # Saturday
        self.running = False
    
    async def start(self):
        """Start the report scheduler."""
        if self.running:
            return
        
        self.running = True
        system_logger.info("Starting strict report scheduler", {
            'daily_hour': self.daily_hour,
            'weekly_hour': self.weekly_hour,
            'weekly_day': self.weekly_day,
            'timezone': str(self.timezone)
        })
        
        # Start both daily and weekly schedulers
        asyncio.create_task(self._daily_scheduler())
        asyncio.create_task(self._weekly_scheduler())
    
    async def stop(self):
        """Stop the report scheduler."""
        self.running = False
        system_logger.info("Stopped strict report scheduler")
    
    async def _daily_scheduler(self):
        """Daily report scheduler - 08:00 Stockholm time."""
        while self.running:
            try:
                now = datetime.now(self.timezone)
                next_report = now.replace(
                    hour=self.daily_hour, 
                    minute=0, 
                    second=0, 
                    microsecond=0
                )
                
                # If it's already past today's report time, schedule for tomorrow
                if now >= next_report:
                    next_report += timedelta(days=1)
                
                # Calculate sleep time
                sleep_seconds = (next_report - now).total_seconds()
                
                system_logger.info(f"Next daily report scheduled for {next_report}", {
                    'sleep_seconds': sleep_seconds,
                    'timezone': str(self.timezone)
                })
                
                # Sleep until next report time
                await asyncio.sleep(sleep_seconds)
                
                if self.running:
                    await self._generate_daily_report()
                    
            except Exception as e:
                system_logger.error(f"Daily scheduler error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def _weekly_scheduler(self):
        """Weekly report scheduler - Saturday 22:00 Stockholm time."""
        while self.running:
            try:
                now = datetime.now(self.timezone)
                
                # Find next Saturday at 22:00
                days_ahead = (self.weekly_day - now.weekday()) % 7
                if days_ahead == 0 and now.hour >= self.weekly_hour:
                    days_ahead = 7  # Next week
                
                next_report = now.replace(
                    hour=self.weekly_hour,
                    minute=0,
                    second=0,
                    microsecond=0
                ) + timedelta(days=days_ahead)
                
                # Calculate sleep time
                sleep_seconds = (next_report - now).total_seconds()
                
                system_logger.info(f"Next weekly report scheduled for {next_report}", {
                    'sleep_seconds': sleep_seconds,
                    'timezone': str(self.timezone)
                })
                
                # Sleep until next report time
                await asyncio.sleep(sleep_seconds)
                
                if self.running:
                    await self._generate_weekly_report()
                    
            except Exception as e:
                system_logger.error(f"Weekly scheduler error: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute before retry
    
    async def _generate_daily_report(self):
        """Generate and send daily report."""
        try:
            system_logger.info("Generating daily report")
            
            # Get report data
            report_data = await self._get_daily_report_data()
            
            # Generate message
            message = self.templates.daily_report(report_data)
            
            # Send message
            await send_message(message)
            
            system_logger.info("Daily report sent successfully")
            
        except Exception as e:
            system_logger.error(f"Error generating daily report: {e}", exc_info=True)
    
    async def _generate_weekly_report(self):
        """Generate and send weekly report."""
        try:
            system_logger.info("Generating weekly report")
            
            # Get report data
            report_data = await self._get_weekly_report_data()
            
            # Generate message
            message = self.templates.weekly_report(report_data)
            
            # Send message
            await send_message(message)
            
            system_logger.info("Weekly report sent successfully")
            
        except Exception as e:
            system_logger.error(f"Error generating weekly report: {e}", exc_info=True)
    
    async def _get_daily_report_data(self) -> Dict[str, Any]:
        """Get daily report data from database."""
        try:
            db = await get_db_connection()
            async with db:
                # Get today's date
                today = datetime.now(self.timezone).date()
                
                # Get trades for today
                cursor = await db.execute("""
                    SELECT 
                        symbol,
                        direction,
                        pnl,
                        pnl_pct,
                        status,
                        created_at
                    FROM trades 
                    WHERE DATE(created_at) = ? 
                    AND status IN ('closed', 'tp_hit', 'sl_hit')
                """, (today,))
                
                trades = await cursor.fetchall()
                
                # Calculate statistics
                total_trades = len(trades)
                winning_trades = sum(1 for trade in trades if float(trade[2]) > 0)
                losing_trades = sum(1 for trade in trades if float(trade[2]) < 0)
                winrate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                total_pnl = sum(float(trade[2]) for trade in trades)
                total_pnl_pct = sum(float(trade[3]) for trade in trades)
                
                # Get top symbols by PnL
                symbol_pnl = {}
                for trade in trades:
                    symbol = trade[0]
                    pnl = float(trade[2])
                    if symbol in symbol_pnl:
                        symbol_pnl[symbol] += pnl
                    else:
                        symbol_pnl[symbol] = pnl
                
                top_symbols = sorted(symbol_pnl.items(), key=lambda x: x[1], reverse=True)[:5]
                
                return {
                    'date': today.strftime('%Y-%m-%d'),
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'losing_trades': losing_trades,
                    'winrate': winrate,
                    'total_pnl': total_pnl,
                    'total_pnl_pct': total_pnl_pct,
                    'top_symbols': top_symbols
                }
                
        except Exception as e:
            system_logger.error(f"Error getting daily report data: {e}", exc_info=True)
            return {
                'date': datetime.now(self.timezone).date().strftime('%Y-%m-%d'),
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'winrate': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'top_symbols': []
            }
    
    async def _get_weekly_report_data(self) -> Dict[str, Any]:
        """Get weekly report data from database."""
        try:
            db = await get_db_connection()
            async with db:
                # Get this week's date range
                now = datetime.now(self.timezone)
                week_start = now - timedelta(days=now.weekday())
                week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                week_end = week_start + timedelta(days=7)
                
                # Get trades for this week
                cursor = await db.execute("""
                    SELECT 
                        symbol,
                        direction,
                        pnl,
                        pnl_pct,
                        status,
                        pyramid_level,
                        hedge_count,
                        reentry_count,
                        error_type,
                        created_at
                    FROM trades 
                    WHERE created_at >= ? AND created_at < ?
                    AND status IN ('closed', 'tp_hit', 'sl_hit')
                """, (week_start, week_end))
                
                trades = await cursor.fetchall()
                
                # Calculate statistics
                total_trades = len(trades)
                winning_trades = sum(1 for trade in trades if float(trade[2]) > 0)
                winrate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                total_pnl = sum(float(trade[2]) for trade in trades)
                total_pnl_pct = sum(float(trade[3]) for trade in trades)
                
                # Strategy statistics
                reentries = sum(trade[7] for trade in trades if trade[7])
                hedges = sum(trade[6] for trade in trades if trade[6])
                max_pyramid = max((trade[5] for trade in trades if trade[5]), default=0)
                
                # Error tally
                error_tally = {}
                for trade in trades:
                    error_type = trade[8]
                    if error_type:
                        error_tally[error_type] = error_tally.get(error_type, 0) + 1
                
                return {
                    'week': week_start.strftime('%Y-W%U'),
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'winrate': winrate,
                    'total_pnl': total_pnl,
                    'total_pnl_pct': total_pnl_pct,
                    'reentries': reentries,
                    'hedges': hedges,
                    'max_pyramid': max_pyramid,
                    'error_tally': error_tally
                }
                
        except Exception as e:
            system_logger.error(f"Error getting weekly report data: {e}", exc_info=True)
            return {
                'week': datetime.now(self.timezone).strftime('%Y-W%U'),
                'total_trades': 0,
                'winning_trades': 0,
                'winrate': 0,
                'total_pnl': 0,
                'total_pnl_pct': 0,
                'reentries': 0,
                'hedges': 0,
                'max_pyramid': 0,
                'error_tally': {}
            }
    
    async def force_daily_report(self):
        """Force generate daily report immediately."""
        await self._generate_daily_report()
    
    async def force_weekly_report(self):
        """Force generate weekly report immediately."""
        await self._generate_weekly_report()

# Global report scheduler instance
_scheduler_instance = None

async def get_strict_report_scheduler() -> StrictReportScheduler:
    """Get global strict report scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = StrictReportScheduler()
    return _scheduler_instance

async def start_strict_report_scheduler():
    """Start the strict report scheduler."""
    scheduler = await get_strict_report_scheduler()
    await scheduler.start()

async def stop_strict_report_scheduler():
    """Stop the strict report scheduler."""
    scheduler = await get_strict_report_scheduler()
    await scheduler.stop()