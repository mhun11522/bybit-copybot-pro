"""Advanced report scheduler with exact Stockholm time requirements."""

import asyncio
from datetime import datetime, time
from typing import Dict, Any
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.logging import system_logger
from app.reports.generator_v2 import ReportGeneratorV2
from app.telegram.output import send_message

class ReportSchedulerV2:
    """Advanced report scheduler with exact client requirements."""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.report_generator = ReportGeneratorV2()
        self.stockholm_tz = pytz.timezone('Europe/Stockholm')
        self.running = False
    
    async def start(self):
        """Start the report scheduler."""
        try:
            # Daily report at 08:00 Stockholm time
            self.scheduler.add_job(
                self._send_daily_report,
                CronTrigger(hour=8, minute=0, timezone=self.stockholm_tz),
                id='daily_report',
                name='Daily Report 08:00 Stockholm',
                replace_existing=True
            )
            
            # Weekly report on Saturday at 22:00 Stockholm time
            self.scheduler.add_job(
                self._send_weekly_report,
                CronTrigger(day_of_week=5, hour=22, minute=0, timezone=self.stockholm_tz),  # Saturday = 5
                id='weekly_report',
                name='Weekly Report Saturday 22:00 Stockholm',
                replace_existing=True
            )
            
            self.scheduler.start()
            self.running = True
            
            system_logger.info("Report scheduler started", {
                "daily_hour": 8,
                "weekly_hour": 22,
                "weekly_day": 5,
                "timezone": "Europe/Stockholm"
            })
            
        except Exception as e:
            system_logger.error(f"Failed to start report scheduler: {e}", exc_info=True)
    
    async def stop(self):
        """Stop the report scheduler."""
        try:
            if self.running:
                self.scheduler.shutdown()
                self.running = False
                system_logger.info("Report scheduler stopped")
        except Exception as e:
            system_logger.error(f"Error stopping report scheduler: {e}", exc_info=True)
    
    async def _send_daily_report(self):
        """Send daily report."""
        try:
            system_logger.info("Generating daily report")
            
            # Generate daily report
            report_data = await self.report_generator.generate_daily_report()
            
            # Format and send report
            message = self._format_daily_report(report_data)
            await send_message(message)
            
            system_logger.info("Daily report sent successfully")
            
        except Exception as e:
            system_logger.error(f"Error sending daily report: {e}", exc_info=True)
    
    async def _send_weekly_report(self):
        """Send weekly report."""
        try:
            system_logger.info("Generating weekly report")
            
            # Generate weekly report
            report_data = await self.report_generator.generate_weekly_report()
            
            # Format and send report
            message = self._format_weekly_report(report_data)
            await send_message(message)
            
            system_logger.info("Weekly report sent successfully")
            
        except Exception as e:
            system_logger.error(f"Error sending weekly report: {e}", exc_info=True)
    
    def _format_daily_report(self, report_data: Dict[str, Any]) -> str:
        """Format daily report message."""
        date = datetime.now(self.stockholm_tz).strftime("%Y-%m-%d")
        
        return f"""📊 **DAGLIG RAPPORT - {date}**

📈 **Handelsstatistik:**
• Totalt antal trades: {report_data.get('total_trades', 0)}
• Vinnande trades: {report_data.get('winning_trades', 0)}
• Förlorande trades: {report_data.get('losing_trades', 0)}
• Vinstprocent: {report_data.get('win_rate', 0):.1f}%

💰 **Finansiell Prestanda:**
• Total vinst: {report_data.get('total_profit', 0):.2f} USDT
• Genomsnittlig vinst: {report_data.get('avg_profit', 0):.2f} USDT
• Max vinst: {report_data.get('max_profit', 0):.2f} USDT
• Max förlust: {report_data.get('max_loss', 0):.2f} USDT

🎯 **Strategi Prestanda:**
• Breakeven aktiverade: {report_data.get('breakeven_count', 0)}
• Pyramid nivåer: {report_data.get('pyramid_levels', 0)}
• Trailing stops: {report_data.get('trailing_stops', 0)}
• Hedges: {report_data.get('hedges', 0)}
• Re-entries: {report_data.get('reentries', 0)}

⚠️ **Fel & Varningar:**
• Totalt antal fel: {report_data.get('error_count', 0)}
• Order fel: {report_data.get('order_errors', 0)}
• Parsing fel: {report_data.get('parsing_errors', 0)}

🕐 Rapport genererad: {datetime.now(self.stockholm_tz).strftime("%H:%M:%S")} Stockholm tid"""
    
    def _format_weekly_report(self, report_data: Dict[str, Any]) -> str:
        """Format weekly report message."""
        week_start = datetime.now(self.stockholm_tz).strftime("%Y-%m-%d")
        
        return f"""📊 **VECKORAPPORT - Vecka {datetime.now(self.stockholm_tz).strftime("%U")}**

📈 **Veckans Handelsstatistik:**
• Totalt antal trades: {report_data.get('total_trades', 0)}
• Vinnande trades: {report_data.get('winning_trades', 0)}
• Förlorande trades: {report_data.get('losing_trades', 0)}
• Vinstprocent: {report_data.get('win_rate', 0):.1f}%

💰 **Veckans Finansiell Prestanda:**
• Total vinst: {report_data.get('total_profit', 0):.2f} USDT
• Genomsnittlig vinst: {report_data.get('avg_profit', 0):.2f} USDT
• Max vinst: {report_data.get('max_profit', 0):.2f} USDT
• Max förlust: {report_data.get('max_loss', 0):.2f} USDT

🎯 **Veckans Strategi Prestanda:**
• Breakeven aktiverade: {report_data.get('breakeven_count', 0)}
• Pyramid nivåer: {report_data.get('pyramid_levels', 0)}
• Trailing stops: {report_data.get('trailing_stops', 0)}
• Hedges: {report_data.get('hedges', 0)}
• Re-entries: {report_data.get('reentries', 0)}

📊 **Top Presterande Symboler:**
{self._format_top_symbols(report_data.get('top_symbols', []))}

⚠️ **Veckans Fel & Varningar:**
• Totalt antal fel: {report_data.get('error_count', 0)}
• Order fel: {report_data.get('order_errors', 0)}
• Parsing fel: {report_data.get('parsing_errors', 0)}

🕐 Rapport genererad: {datetime.now(self.stockholm_tz).strftime("%Y-%m-%d %H:%M:%S")} Stockholm tid"""
    
    def _format_top_symbols(self, top_symbols: list) -> str:
        """Format top performing symbols."""
        if not top_symbols:
            return "• Ingen data tillgänglig"
        
        formatted = ""
        for i, symbol_data in enumerate(top_symbols[:5], 1):
            symbol = symbol_data.get('symbol', '')
            profit = symbol_data.get('profit', 0)
            trades = symbol_data.get('trades', 0)
            formatted += f"• {i}. {symbol}: {profit:.2f} USDT ({trades} trades)\n"
        
        return formatted.rstrip('\n')

# Global scheduler instance
_scheduler_instance = None

async def get_report_scheduler() -> ReportSchedulerV2:
    """Get global report scheduler instance."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = ReportSchedulerV2()
    return _scheduler_instance
