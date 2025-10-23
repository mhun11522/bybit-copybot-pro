"""Advanced report generator with comprehensive trade analysis."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from decimal import Decimal
import aiosqlite
from app.core.logging import system_logger
from app.storage.db import get_db_connection

class ReportGeneratorV2:
    """Advanced report generator with comprehensive trade analysis."""
    
    def __init__(self):
        self.db_path = "trades.sqlite"
    
    async def generate_daily_report(self) -> Dict[str, Any]:
        """Generate daily report data."""
        try:
            # Get today's date range
            today = datetime.now().date()
            start_time = datetime.combine(today, datetime.min.time())
            end_time = datetime.combine(today, datetime.max.time())
            
            # CRITICAL FIX: Use single database connection for all queries
            db = await get_db_connection()
            try:
                # Get all data in one connection to avoid threading issues
                trades, error_count, order_errors, parsing_errors = await self._get_all_report_data(db, start_time, end_time)
                
                # Calculate statistics
                total_trades = len(trades)
                winning_trades = len([t for t in trades if t.get('profit', 0) > 0])
                losing_trades = len([t for t in trades if t.get('profit', 0) < 0])
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                total_profit = sum(t.get('profit', 0) for t in trades)
                avg_profit = total_profit / total_trades if total_trades > 0 else 0
                max_profit = max((t.get('profit', 0) for t in trades), default=0)
                max_loss = min((t.get('profit', 0) for t in trades), default=0)
                
                # Strategy statistics
                breakeven_count = len([t for t in trades if t.get('breakeven_activated', False)])
                pyramid_levels = sum(t.get('pyramid_levels', 0) for t in trades)
                trailing_stops = len([t for t in trades if t.get('trailing_activated', False)])
                hedges = len([t for t in trades if t.get('hedge_activated', False)])
                reentries = sum(t.get('reentry_attempts', 0) for t in trades)
            finally:
                await db.close()
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_profit': total_profit,
                'avg_profit': avg_profit,
                'max_profit': max_profit,
                'max_loss': max_loss,
                'breakeven_count': breakeven_count,
                'pyramid_levels': pyramid_levels,
                'trailing_stops': trailing_stops,
                'hedges': hedges,
                'reentries': reentries,
                'error_count': error_count,
                'order_errors': order_errors,
                'parsing_errors': parsing_errors
            }
            
        except Exception as e:
            system_logger.error(f"Error generating daily report: {e}", exc_info=True)
            return self._get_empty_report()
    
    async def generate_weekly_report(self) -> Dict[str, Any]:
        """Generate weekly report data."""
        try:
            # Get this week's date range
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())
            start_time = datetime.combine(week_start, datetime.min.time())
            end_time = datetime.combine(today, datetime.max.time())
            
            # Get trade data
            trades = await self._get_trades_in_range(start_time, end_time)
            
            # Calculate statistics (same as daily but for week)
            total_trades = len(trades)
            winning_trades = len([t for t in trades if t.get('profit', 0) > 0])
            losing_trades = len([t for t in trades if t.get('profit', 0) < 0])
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            total_profit = sum(t.get('profit', 0) for t in trades)
            avg_profit = total_profit / total_trades if total_trades > 0 else 0
            max_profit = max((t.get('profit', 0) for t in trades), default=0)
            max_loss = min((t.get('profit', 0) for t in trades), default=0)
            
            # Strategy statistics
            breakeven_count = len([t for t in trades if t.get('breakeven_activated', False)])
            pyramid_levels = sum(t.get('pyramid_levels', 0) for t in trades)
            trailing_stops = len([t for t in trades if t.get('trailing_activated', False)])
            hedges = len([t for t in trades if t.get('hedge_activated', False)])
            reentries = sum(t.get('reentry_attempts', 0) for t in trades)
            
            # Error statistics
            error_count = await self._get_error_count(start_time, end_time)
            order_errors = await self._get_order_error_count(start_time, end_time)
            parsing_errors = await self._get_parsing_error_count(start_time, end_time)
            
            # Top performing symbols
            top_symbols = await self._get_top_symbols(start_time, end_time)
            
            return {
                'total_trades': total_trades,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate': win_rate,
                'total_profit': total_profit,
                'avg_profit': avg_profit,
                'max_profit': max_profit,
                'max_loss': max_loss,
                'breakeven_count': breakeven_count,
                'pyramid_levels': pyramid_levels,
                'trailing_stops': trailing_stops,
                'hedges': hedges,
                'reentries': reentries,
                'error_count': error_count,
                'order_errors': order_errors,
                'parsing_errors': parsing_errors,
                'top_symbols': top_symbols
            }
            
        except Exception as e:
            system_logger.error(f"Error generating weekly report: {e}", exc_info=True)
            return self._get_empty_report()
    
    async def _get_all_report_data(self, db, start_time: datetime, end_time: datetime) -> tuple:
        """Get all report data in a single database connection to avoid threading issues."""
        try:
            # Get trades
            cursor = await db.execute("""
                SELECT * FROM trades 
                WHERE created_at >= ? AND created_at <= ?
                ORDER BY created_at DESC
            """, (start_time.isoformat(), end_time.isoformat()))
            
            rows = await cursor.fetchall()
            columns = [description[0] for description in cursor.description]
            trades = [dict(zip(columns, row)) for row in rows]
            
            # Get error counts (handle missing error_logs table gracefully)
            try:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM error_logs 
                    WHERE timestamp >= ? AND timestamp <= ?
                """, (start_time.isoformat(), end_time.isoformat()))
                result = await cursor.fetchone()
                error_count = result[0] if result else 0
            except Exception:
                error_count = 0  # Table doesn't exist yet
                
            try:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM error_logs 
                    WHERE timestamp >= ? AND timestamp <= ? AND error_type LIKE '%order%'
                """, (start_time.isoformat(), end_time.isoformat()))
                result = await cursor.fetchone()
                order_error_count = result[0] if result else 0
            except Exception:
                order_error_count = 0  # Table doesn't exist yet
                
            try:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM error_logs 
                    WHERE timestamp >= ? AND timestamp <= ? AND error_type LIKE '%parsing%'
                """, (start_time.isoformat(), end_time.isoformat()))
                result = await cursor.fetchone()
                parsing_error_count = result[0] if result else 0
            except Exception:
                parsing_error_count = 0  # Table doesn't exist yet
            
            return trades, error_count, order_error_count, parsing_error_count
            
        except Exception as e:
            system_logger.error(f"Error getting all report data: {e}", exc_info=True)
            return [], 0, 0, 0

    async def _get_trades_in_range(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get trades within time range."""
        try:
            db = await get_db_connection()
            async with db:
                cursor = await db.execute("""
                    SELECT * FROM trades 
                    WHERE created_at >= ? AND created_at <= ?
                    ORDER BY created_at DESC
                """, (start_time.isoformat(), end_time.isoformat()))
                
                rows = await cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                
                return [dict(zip(columns, row)) for row in rows]
                
        except Exception as e:
            system_logger.error(f"Error getting trades in range: {e}", exc_info=True)
            return []
    
    async def _get_error_count(self, start_time: datetime, end_time: datetime) -> int:
        """Get total error count in time range."""
        try:
            db = await get_db_connection()
            async with db:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM error_logs 
                    WHERE timestamp >= ? AND timestamp <= ?
                """, (start_time.isoformat(), end_time.isoformat()))
                
                result = await cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            system_logger.error(f"Error getting error count: {e}", exc_info=True)
            return 0
    
    async def _get_order_error_count(self, start_time: datetime, end_time: datetime) -> int:
        """Get order error count in time range."""
        try:
            db = await get_db_connection()
            async with db:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM error_logs 
                    WHERE timestamp >= ? AND timestamp <= ? 
                    AND error_type LIKE '%order%'
                """, (start_time.isoformat(), end_time.isoformat()))
                
                result = await cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            system_logger.error(f"Error getting order error count: {e}", exc_info=True)
            return 0
    
    async def _get_parsing_error_count(self, start_time: datetime, end_time: datetime) -> int:
        """Get parsing error count in time range."""
        try:
            db = await get_db_connection()
            async with db:
                cursor = await db.execute("""
                    SELECT COUNT(*) FROM error_logs 
                    WHERE timestamp >= ? AND timestamp <= ? 
                    AND error_type LIKE '%parsing%'
                """, (start_time.isoformat(), end_time.isoformat()))
                
                result = await cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            system_logger.error(f"Error getting parsing error count: {e}", exc_info=True)
            return 0
    
    async def _get_top_symbols(self, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get top performing symbols in time range."""
        try:
            db = await get_db_connection()
            async with db:
                cursor = await db.execute("""
                    SELECT symbol, 
                           SUM(profit) as total_profit,
                           COUNT(*) as trade_count
                    FROM trades 
                    WHERE created_at >= ? AND created_at <= ?
                    GROUP BY symbol
                    ORDER BY total_profit DESC
                    LIMIT 10
                """, (start_time.isoformat(), end_time.isoformat()))
                
                rows = await cursor.fetchall()
                return [
                    {
                        'symbol': row[0],
                        'profit': row[1],
                        'trades': row[2]
                    }
                    for row in rows
                ]
                
        except Exception as e:
            system_logger.error(f"Error getting top symbols: {e}", exc_info=True)
            return []
    
    async def generate_group_daily(self) -> Dict[str, Any]:
        """
        Generate group daily report (CLIENT SPEC).
        
        Returns symbol-by-symbol breakdown with %/USDT for today.
        
        Returns:
            {
                'group_name': str,
                'rows': [{'symbol': str, 'pct': float, 'usdt': float}, ...],
                'count': int,
                'sum_usdt': float,
                'sum_pct': float
            }
        """
        try:
            today = datetime.now().date()
            start_time = datetime.combine(today, datetime.min.time())
            end_time = datetime.combine(today, datetime.max.time())
            
            # CRITICAL FIX: Use single database connection to avoid threading issues
            db = await get_db_connection()
            try:
                # Get grouped trades data in one connection
                trades = await self._get_trades_today_grouped(db, start_time, end_time)
            finally:
                await db.close()
            
            group_name = trades.get("group_name", "ALL SOURCES")
            rows = trades.get("rows", [])
            count = len(rows)
            sum_usdt = sum(r.get("usdt", 0.0) for r in rows)
            sum_pct = sum(r.get("pct", 0.0) for r in rows)
            
            return {
                "group_name": group_name,
                "rows": rows,
                "count": count,
                "sum_usdt": sum_usdt,
                "sum_pct": sum_pct
            }
            
        except Exception as e:
            system_logger.error(f"Error generating group daily report: {e}", exc_info=True)
            return {
                "group_name": "ERROR",
                "rows": [],
                "count": 0,
                "sum_usdt": 0.0,
                "sum_pct": 0.0
            }
    
    async def _get_trades_today_grouped(self, db, start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """
        Get today's trades grouped by symbol for group report (CLIENT SPEC).
        
        Returns:
            {
                'group_name': str,
                'rows': [{'symbol': str, 'pct': float, 'usdt': float}, ...]
            }
        """
        try:
            # Get grouped data by symbol
            cursor = await db.execute("""
                SELECT 
                    symbol,
                    SUM(profit) as profit_usdt,
                    AVG(profit_percent) as profit_pct,
                    channel_name
                FROM trades
                WHERE created_at >= ? AND created_at <= ?
                GROUP BY symbol
                ORDER BY symbol
            """, (start_time.isoformat(), end_time.isoformat()))
            
            rows_data = await cursor.fetchall()
            
            rows = []
            group_name = "ALL SOURCES"
            
            for row in rows_data:
                symbol, profit_usdt, profit_pct, channel = row
                
                if channel:
                    group_name = channel  # Use last channel as group name
                
                rows.append({
                    "symbol": symbol or "UNKNOWN",
                    "pct": float(profit_pct or 0),
                    "usdt": float(profit_usdt or 0)
                })
            
            return {
                "group_name": group_name,
                "rows": rows
            }
                
        except Exception as e:
            system_logger.error(f"Error getting grouped trades: {e}", exc_info=True)
            return {
                "group_name": "ERROR",
                "rows": []
            }
    
    def _get_empty_report(self) -> Dict[str, Any]:
        """Get empty report data."""
        return {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'win_rate': 0,
            'total_profit': 0,
            'avg_profit': 0,
            'max_profit': 0,
            'max_loss': 0,
            'breakeven_count': 0,
            'pyramid_levels': 0,
            'trailing_stops': 0,
            'hedges': 0,
            'reentries': 0,
            'error_count': 0,
            'order_errors': 0,
            'parsing_errors': 0,
            'top_symbols': []
        }
