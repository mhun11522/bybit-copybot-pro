"""
Telegram Template Engine (CLIENT SPEC Compliance).

Single normative rendering path for all Telegram messages.
All operational messages go through TemplateEngine.render().
"""

from typing import Dict, Any, Optional
from decimal import Decimal
from app.telegram.formatting import (
    fmt_usdt, fmt_leverage, fmt_price, fmt_percent, fmt_quantity,
    now_hms_stockholm, symbol_hashtags, ensure_trade_id
)
from app.core.logging import system_logger


class TemplateGuards:
    """
    Validate required fields before rendering templates.
    
    CLIENT SPEC: Certain messages require Bybit confirmation before sending.
    This class enforces those requirements.
    """
    
    # Templates that require Bybit-confirmed fields
    REQUIRED_BYBIT_FIELDS = {
        "ORDER_PLACED",
        "POSITION_OPENED",
        "ENTRY_TAKEN",
        "TP_TAKEN",
        "POSITION_CLOSED"
    }
    
    def check(self, key: str, d: Dict[str, Any]) -> None:
        """
        Validate required fields for a template.
        
        Raises:
            AssertionError: If required fields are missing
        """
        if key in self.REQUIRED_BYBIT_FIELDS:
            # These templates require Bybit confirmation
            if key in ["ORDER_PLACED", "POSITION_OPENED"]:
                assert d.get("order_id"), f"{key}: order_id missing (must confirm from Bybit)"
                assert d.get("post_only") in (True, False), f"{key}: post_only missing"
                assert d.get("reduce_only") in (True, False), f"{key}: reduce_only missing"
                
                im = d.get("im_confirmed")
                assert im is not None and str(im) not in ("", "None"), \
                    f"{key}: im_confirmed missing (must confirm from Bybit)"
            
            # All require basic fields
            assert d.get("symbol"), f"{key}: symbol missing"
            assert d.get("source_name"), f"{key}: source_name missing"


class TemplateRegistry:
    """
    Registry of all Telegram message templates.
    
    CLIENT SPEC: Exact formatting with bold labels, regular values,
    hashtags, and Trade ID at the end of every message.
    """
    
    def signal_received(self, d: Dict[str, Any]) -> str:
        """
        Signal received & copied (ONLY pre-Bybit message allowed).
        
        CLIENT SPEC: This is the ONLY message that can be sent before
        Bybit confirmation.
        """
        t = now_hms_stockholm()
        lines = [
            "**🎯 Signal mottagen & kopierad**",
            "",
            f"📢 **Från kanal:** {d['source_name']}",
            f"📊 **Symbol:** {d['symbol']}",
            f"📈 **Riktning:** {d['side']}",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def order_placed(self, d: Dict[str, Any]) -> str:
        """
        Order placed - Waiting for fill (after Bybit confirmation).
        
        CLIENT SPEC: Must include order_id, post_only, reduce_only, im_confirmed.
        """
        t = now_hms_stockholm()
        im = fmt_usdt(d["im_confirmed"])
        lev = fmt_leverage(d["leverage"])
        
        lines = [
            "**✅ Order placerad - Väntar på fyllning**",
            "",
            f"📊 **Symbol:** {d['symbol']}",
            f"📈 **Riktning:** {d['side']}",
            f"💰 **Storlek:** {fmt_quantity(d['qty'])}",
            f"⚡️ **Hävstång:** {lev}",
            f"📺 **Källa:** {d['source_name']}",
            f"⏰ **Tid:** {t}",
            "",
            f"☑️ **Post-Only:** {str(bool(d['post_only'])).upper()}",
            f"☑️ **Reduce-Only:** {str(bool(d['reduce_only'])).upper()}",
            f"🔑 **Order-ID:** {d['order_id']}",
            f"💰 **IM:** {im}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def entry_taken(self, d: Dict[str, Any]) -> str:
        """
        ENTRY 1 or ENTRY 2 taken (dual-limit requirement).
        
        CLIENT SPEC: Show individual entry fills with IM for that entry
        and total IM.
        """
        entry_no = d.get("entry_no", 1)
        t = now_hms_stockholm()
        im = fmt_usdt(d["im"])
        im_total = fmt_usdt(d["im_total"])
        
        lines = [
            f"**📌 ENTRY {entry_no} TAGEN**",
            "",
            f"📢 **Från kanal:** {d['source_name']}",
            f"📊 **Symbol:** {d['symbol']}",
            "",
            f"💥 **Entry:** {fmt_price(d['price'])}",
            f"💵 **Kvantitet:** {fmt_quantity(d['qty'])}",
            f"💰 **IM:** {im} (**IM totalt:** {im_total})",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def entry_consolidated(self, d: Dict[str, Any]) -> str:
        """
        Consolidation of ENTRY 1 + ENTRY 2 (dual-limit).
        
        CLIENT SPEC: After both entries are filled, show consolidated position.
        """
        t = now_hms_stockholm()
        im_total = fmt_usdt(d["im_total"])
        
        lines = [
            "**📌 Sammanställning av ENTRY 1 + ENTRY 2**",
            "",
            f"📢 **Från kanal:** {d['source_name']}",
            f"📊 **Symbol:** {d['symbol']}",
            "",
            f"💥 **Genomsnittligt Entry:** {fmt_price(d['avg_entry'])}",
            f"💵 **Total kvantitet:** {fmt_quantity(d['qty_total'])}",
            f"💰 **IM totalt:** {im_total}",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def position_opened(self, d: Dict[str, Any]) -> str:
        """
        Position opened (after both entries filled and position confirmed).
        """
        t = now_hms_stockholm()
        im = fmt_usdt(d["im_confirmed"])
        lev = fmt_leverage(d["leverage"])
        
        lines = [
            "**✅ Position öppnad**",
            "",
            f"📊 **Symbol:** {d['symbol']}",
            f"📈 **Riktning:** {d['side']}",
            f"💥 **Entry:** {fmt_price(d['entry_price'])}",
            f"💵 **Kvantitet:** {fmt_quantity(d['qty'])}",
            f"⚡️ **Hävstång:** {lev}",
            f"💰 **IM:** {im}",
            f"📺 **Källa:** {d['source_name']}",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def tp_taken(self, d: Dict[str, Any]) -> str:
        """
        Take Profit hit (TP1, TP2, TP3, TP4).
        
        CLIENT SPEC: Must show profit in both % (including leverage) and USDT.
        """
        tp_no = d.get("tp_no", 1)
        t = now_hms_stockholm()
        pnl_usdt = fmt_usdt(d["pnl_usdt"])
        pnl_pct = fmt_percent(d["pnl_pct"])
        
        lines = [
            f"**💰 TP{tp_no} TRÄFFAD**",
            "",
            f"📢 **Från kanal:** {d['source_name']}",
            f"📊 **Symbol:** {d['symbol']}",
            f"📈 **Vinst:** {pnl_pct} | {pnl_usdt}",
            f"💵 **Stängd kvantitet:** {fmt_quantity(d['qty_closed'])}",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def trailing_activated(self, d: Dict[str, Any]) -> str:
        """
        Trailing Stop activated.
        
        CLIENT SPEC: Show profit in both % and USDT, trigger and distance.
        """
        t = now_hms_stockholm()
        pnl_usdt = fmt_usdt(d["pnl_usdt"])
        pnl_pct = fmt_percent(d["pnl_pct"])
        
        lines = [
            "**🔄 TRAILING STOP AKTIVERAD**",
            "",
            f"📢 **Från kanal:** {d['source_name']}",
            f"📊 **Symbol:** {d['symbol']}",
            f"📈 **Vinst:** {pnl_pct} | {pnl_usdt}",
            "",
            f"✅ **Aktivering:** +{d['trigger_pct']:.1f}%",
            f"📍 **Avstånd:** {d['trail_dist_pct']:.1f}% bakom högsta/lägsta pris",
            f"⛔ **SL uppdateras automatiskt**",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def breakeven_moved(self, d: Dict[str, Any]) -> str:
        """
        Breakeven - SL moved to entry + cost.
        
        CLIENT SPEC: After TP2, move SL to BE + 0.0015%.
        """
        t = now_hms_stockholm()
        
        lines = [
            "**✅ BREAKEVEN - SL flyttad till Entry + kostnad**",
            "",
            f"📢 **Från kanal:** {d['source_name']}",
            f"📊 **Symbol:** {d['symbol']}",
            f"💥 **Nytt SL:** {fmt_price(d['new_sl'])}",
            f"📊 **Entry:** {fmt_price(d['entry_price'])}",
            f"📈 **Kostnad:** +0.0015%",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def pyramid_step(self, d: Dict[str, Any]) -> str:
        """
        Pyramid step (levels 1-6).
        
        CLIENT SPEC: Add to position at specific profit levels.
        """
        level = d.get("level", 1)
        t = now_hms_stockholm()
        
        lines = [
            f"**📈 PYRAMID NIVÅ {level}**",
            "",
            f"📢 **Från kanal:** {d['source_name']}",
            f"📊 **Symbol:** {d['symbol']}",
            f"💥 **Entry:** {fmt_price(d['price'])}",
            f"💵 **Tillagd kvantitet:** {fmt_quantity(d['qty_added'])}",
            f"💰 **Ny total kvantitet:** {fmt_quantity(d['qty_total'])}",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def hedge_started(self, d: Dict[str, Any]) -> str:
        """
        Hedge started (-2% protection).
        """
        t = now_hms_stockholm()
        
        lines = [
            "**🛡️ HEDGE STARTAD**",
            "",
            f"📢 **Från kanal:** {d['source_name']}",
            f"📊 **Symbol:** {d['symbol']}",
            f"📉 **Trigger:** -2.0% från entry",
            f"💵 **Storlek:** 100% av original position",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def hedge_stopped(self, d: Dict[str, Any]) -> str:
        """
        Hedge stopped.
        """
        t = now_hms_stockholm()
        pnl_usdt = fmt_usdt(d["pnl_usdt"])
        pnl_pct = fmt_percent(d["pnl_pct"])
        
        lines = [
            "**🛡️ HEDGE STOPPAD**",
            "",
            f"📢 **Från kanal:** {d['source_name']}",
            f"📊 **Symbol:** {d['symbol']}",
            f"📈 **Resultat:** {pnl_pct} | {pnl_usdt}",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def reentry_started(self, d: Dict[str, Any]) -> str:
        """
        Re-entry started (attempt N of 3).
        """
        attempt = d.get("attempt", 1)
        t = now_hms_stockholm()
        
        lines = [
            f"**🔄 RE-ENTRY FÖRSÖK {attempt}/3**",
            "",
            f"📢 **Från kanal:** {d['source_name']}",
            f"📊 **Symbol:** {d['symbol']}",
            f"💥 **Entry:** {fmt_price(d['price'])}",
            f"💵 **Storlek:** {fmt_quantity(d['qty'])}",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def sl_hit(self, d: Dict[str, Any]) -> str:
        """
        Stop Loss hit.
        
        CLIENT SPEC: Show loss in both % and USDT.
        """
        t = now_hms_stockholm()
        pnl_usdt = fmt_usdt(d["pnl_usdt"])
        pnl_pct = fmt_percent(d["pnl_pct"])
        
        lines = [
            "**⛔ SL TRÄFFAD**",
            "",
            f"📢 **Från kanal:** {d['source_name']}",
            f"📊 **Symbol:** {d['symbol']}",
            f"📉 **Förlust:** {pnl_pct} | {pnl_usdt}",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def position_closed(self, d: Dict[str, Any]) -> str:
        """
        Position closed (final message).
        
        CLIENT SPEC: Show final P&L in both % and USDT.
        """
        t = now_hms_stockholm()
        pnl_usdt = fmt_usdt(d["pnl_usdt"])
        pnl_pct = fmt_percent(d["pnl_pct"])
        
        lines = [
            "**🏁 POSITION STÄNGD**",
            "",
            f"📢 **Från kanal:** {d['source_name']}",
            f"📊 **Symbol:** {d['symbol']}",
            f"📈 **Slutresultat:** {pnl_pct} | {pnl_usdt}",
            f"⏰ **Tid:** {t}",
            "",
            symbol_hashtags(d["symbol"]),
            f"🆔 {d['trade_id']}",
        ]
        return "\n".join(lines)
    
    def error_message(self, d: Dict[str, Any]) -> str:
        """
        Error message template.
        """
        t = now_hms_stockholm()
        error = d.get("error", "Unknown error")
        
        lines = [
            "**⚠️ FEL**",
            "",
            f"📊 **Symbol:** {d.get('symbol', 'N/A')}",
            f"❌ **Fel:** {error}",
            f"⏰ **Tid:** {t}",
        ]
        
        if d.get("trade_id"):
            lines.append("")
            lines.append(f"🆔 {d['trade_id']}")
        
        return "\n".join(lines)


class TemplateEngine:
    """
    Main template engine for Telegram messages.
    
    CLIENT SPEC: All Telegram output goes via TemplateEngine.render().
    This ensures consistent formatting and validation.
    """
    
    def __init__(self):
        self.registry = TemplateRegistry()
        self.guards = TemplateGuards()
    
    def render(self, key: str, data: Dict[str, Any]) -> str:
        """
        Render a template with data.
        
        Args:
            key: Template key (e.g., "ORDER_PLACED", "TP_TAKEN")
            data: Data dictionary with required fields
        
        Returns:
            Formatted message string
        
        Raises:
            AssertionError: If required fields are missing
            AttributeError: If template key doesn't exist
        """
        # Ensure trade_id exists
        data["trade_id"] = ensure_trade_id(data.get("trade_id"))
        
        # Validate required fields
        self.guards.check(key, data)
        
        # Get template method (convert key to method name)
        method_name = key.lower()
        
        if not hasattr(self.registry, method_name):
            system_logger.error(f"Unknown template key: {key}")
            return self.registry.error_message({
                "error": f"Unknown template: {key}",
                "symbol": data.get("symbol", "N/A")
            })
        
        # Render template
        template_method = getattr(self.registry, method_name)
        return template_method(data)


# Global template engine instance
_template_engine = None


def get_template_engine() -> TemplateEngine:
    """Get global template engine instance."""
    global _template_engine
    if _template_engine is None:
        _template_engine = TemplateEngine()
    return _template_engine


def render_template(key: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Render a template and return metadata for logging.
    
    CLIENT SPEC: This is the main entry point for rendering Telegram messages.
    All operational messages should use this function.
    
    Args:
        key: Template key (e.g., "ORDER_PLACED", "ENTRY_TAKEN")
        data: Data dictionary with required fields
    
    Returns:
        Dictionary with:
            - text: Formatted message text
            - template_name: Template key
            - trade_id: Trade ID from data
            - symbol: Symbol from data
            - hashtags: Generated hashtags
    
    Example:
        >>> rendered = render_template("ORDER_PLACED", {
        ...     "symbol": "BTCUSDT",
        ...     "side": "LONG",
        ...     "qty": "0.001",
        ...     "leverage": "10",
        ...     "source_name": "VIP Trading",
        ...     "order_id": "abc123",
        ...     "post_only": True,
        ...     "reduce_only": False,
        ...     "im_confirmed": "20.00"
        ... })
        >>> print(rendered["text"])
    """
    engine = get_template_engine()
    text = engine.render(key, data)
    
    return {
        "text": text,
        "template_name": key,
        "trade_id": data.get("trade_id", ""),
        "symbol": data.get("symbol", ""),
        "hashtags": symbol_hashtags(data.get("symbol", ""))
    }

