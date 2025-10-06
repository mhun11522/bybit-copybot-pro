"""Synchronize bot reports with actual Bybit data (client recommendation)."""

import asyncio
from typing import Dict, List, Any, Optional
from decimal import Decimal
from app.bybit.client import get_bybit_client
from app.core.logging import system_logger

class BybitDataSync:
    """Synchronize bot reports with actual Bybit data."""
    
    def __init__(self):
        self.bybit = get_bybit_client()
    
    async def get_real_positions(self) -> List[Dict[str, Any]]:
        """Get current open positions from Bybit API (not cached data)."""
        try:
            response = await self.bybit.get_positions()
            if response and response.get('retCode') == 0:
                positions = response.get('result', {}).get('list', [])
                # Filter out zero-size positions
                active_positions = [pos for pos in positions if float(pos.get('size', 0)) > 0]
                system_logger.info(f"Retrieved {len(active_positions)} active positions from Bybit")
                return active_positions
            else:
                system_logger.error(f"Failed to get positions: {response}")
                return []
        except Exception as e:
            system_logger.error(f"Error getting positions: {e}", exc_info=True)
            return []
    
    async def get_real_orders(self) -> List[Dict[str, Any]]:
        """Get current open orders from Bybit API (not cached data)."""
        try:
            response = await self.bybit.get_orders()
            if response and response.get('retCode') == 0:
                orders = response.get('result', {}).get('list', [])
                # Filter out cancelled/filled orders
                open_orders = [order for order in orders if order.get('orderStatus') in ['New', 'PartiallyFilled']]
                system_logger.info(f"Retrieved {len(open_orders)} open orders from Bybit")
                return open_orders
            else:
                system_logger.error(f"Failed to get orders: {response}")
                return []
        except Exception as e:
            system_logger.error(f"Error getting orders: {e}", exc_info=True)
            return []
    
    async def get_real_trade_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent trade executions from Bybit API."""
        try:
            # This would need to be implemented in the BybitClient
            # For now, return empty list
            system_logger.info("Trade history retrieval not yet implemented")
            return []
        except Exception as e:
            system_logger.error(f"Error getting trade history: {e}", exc_info=True)
            return []
    
    async def calculate_real_metrics(self) -> Dict[str, Any]:
        """Calculate real trading metrics from Bybit data."""
        try:
            positions = await self.get_real_positions()
            orders = await self.get_real_orders()
            
            # Calculate total notional value
            total_notional = Decimal("0")
            total_pnl = Decimal("0")
            
            for pos in positions:
                size = Decimal(str(pos.get('size', 0)))
                mark_price = Decimal(str(pos.get('markPrice', 0)))
                unrealised_pnl = Decimal(str(pos.get('unrealisedPnl', 0)))
                
                notional = size * mark_price
                total_notional += notional
                total_pnl += unrealised_pnl
            
            # Count active positions and orders
            active_positions_count = len(positions)
            open_orders_count = len(orders)
            
            # Calculate win rate (positions with positive PnL)
            winning_positions = [pos for pos in positions if float(pos.get('unrealisedPnl', 0)) > 0]
            win_rate = len(winning_positions) / len(positions) * 100 if positions else 0
            
            metrics = {
                'active_positions': active_positions_count,
                'open_orders': open_orders_count,
                'total_notional': float(total_notional),
                'total_pnl': float(total_pnl),
                'win_rate': win_rate,
                'data_source': 'bybit_api_live'
            }
            
            system_logger.info(f"Real metrics calculated: {metrics}")
            return metrics
            
        except Exception as e:
            system_logger.error(f"Error calculating real metrics: {e}", exc_info=True)
            return {
                'active_positions': 0,
                'open_orders': 0,
                'total_notional': 0.0,
                'total_pnl': 0.0,
                'win_rate': 0.0,
                'data_source': 'error'
            }
    
    async def verify_bot_reports(self, bot_reports: Dict[str, Any]) -> Dict[str, Any]:
        """Verify bot reports against real Bybit data."""
        try:
            real_metrics = await self.calculate_real_metrics()
            
            verification = {
                'bot_reports': bot_reports,
                'real_data': real_metrics,
                'discrepancies': [],
                'verified': True
            }
            
            # Check for discrepancies
            if bot_reports.get('active_positions', 0) != real_metrics['active_positions']:
                verification['discrepancies'].append({
                    'field': 'active_positions',
                    'bot_value': bot_reports.get('active_positions', 0),
                    'real_value': real_metrics['active_positions'],
                    'issue': 'Bot reports cached/historical data instead of live data'
                })
                verification['verified'] = False
            
            if bot_reports.get('open_orders', 0) != real_metrics['open_orders']:
                verification['discrepancies'].append({
                    'field': 'open_orders',
                    'bot_value': bot_reports.get('open_orders', 0),
                    'real_value': real_metrics['open_orders'],
                    'issue': 'Bot reports cached/historical data instead of live data'
                })
                verification['verified'] = False
            
            if verification['discrepancies']:
                system_logger.warning(f"Bot report discrepancies found: {verification['discrepancies']}")
            else:
                system_logger.info("Bot reports verified against real Bybit data")
            
            return verification
            
        except Exception as e:
            system_logger.error(f"Error verifying bot reports: {e}", exc_info=True)
            return {
                'bot_reports': bot_reports,
                'real_data': {},
                'discrepancies': [{'error': str(e)}],
                'verified': False
            }

# Global instance
_bybit_data_sync = None

def get_bybit_data_sync() -> BybitDataSync:
    """Get global BybitDataSync instance."""
    global _bybit_data_sync
    if _bybit_data_sync is None:
        _bybit_data_sync = BybitDataSync()
    return _bybit_data_sync
