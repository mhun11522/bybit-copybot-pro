from telethon import TelegramClient, events
from app.config import settings
from app.telegram.templates import signal_received
from app.signals.idempotency import is_new_signal
from app.signals.normalizer import parse_signal
from app.trade.fsm import TradeFSM

client = TelegramClient(
    settings.TELEGRAM_SESSION,
    settings.TELEGRAM_API_ID,
    settings.TELEGRAM_API_HASH
)

async def _allowed_by_name(event) -> tuple[bool, str]:
    """
    Enforce allow-list by channel ID and name mapping.
    Returns (allowed, resolved_name).
    """
    try:
        ent = await event.get_chat()
        name = getattr(ent, "title", "") or getattr(ent, "username", "") or str(event.chat_id)
        
        # Check if channel ID is in allowed list
        if settings.ALLOWED_CHANNEL_IDS and event.chat_id not in settings.ALLOWED_CHANNEL_IDS:
            return False, name
            
        # If we have a mapping, use the mapped name, otherwise use the resolved name
        if settings.CHANNEL_ID_NAME_MAP and event.chat_id in settings.CHANNEL_ID_NAME_MAP:
            mapped_name = settings.CHANNEL_ID_NAME_MAP[event.chat_id]
            return True, mapped_name
            
        # Fallback to name-based filtering if no ID mapping
        if settings.SRC_CHANNEL_NAMES:
            return (name in settings.SRC_CHANNEL_NAMES), name
            
        # If no filters configured, allow all
        return True, name
        
    except Exception:
        return False, "?"

@client.on(events.NewMessage)
async def _rx(event):
    print(f"📩 Received message from chat {event.chat_id}")
    
    allowed, chan_name = await _allowed_by_name(event)
    print(f"🔍 Channel check: allowed={allowed}, name='{chan_name}'")
    
    if not allowed:
        print(f"❌ Channel '{chan_name}' not in whitelist: {settings.SRC_CHANNEL_NAMES}")
        return

    text = (event.raw_text or "").strip()
    print(f"📝 Message text: '{text[:100]}...'")
    
    if not text:
        print("❌ Empty message, skipping")
        return

    # Parse signal first
    sig = parse_signal(text)
    print(f"🔍 Parsed signal: {sig}")
    
    if not sig:
        print("❌ Signal parsing failed, skipping")
        return

    # Check idempotency with parsed signal data (3h window, ±5% tolerance)
    if not await is_new_signal(event.chat_id, sig["symbol"], sig["direction"], sig["entries"]):
        print("❌ Duplicate signal detected (3h window, ±5% tolerance), skipping")
        return

    # Attach source channel *name* for templates
    sig["channel_name"] = chan_name
    sig["channel_id"] = int(event.chat_id)
    
    # Calculate leverage from SL distance (dynamic) or use hint, default to mode-based
    from decimal import Decimal
    from app.core.leverage import dynamic_leverage
    
    if sig.get("sl") and sig.get("entries"):
        # Use dynamic leverage based on SL distance
        entry = Decimal(sig["entries"][0])
        sl = Decimal(sig["sl"])
        lev = float(dynamic_leverage(entry, sl))
        
        # Calculate SL distance for logging
        dist_pct = float(abs((entry - sl) / entry) * Decimal("100"))
        print(f"🔧 Dynamic leverage calculation for {sig['symbol']}:")
        print(f"   Entry: {entry}, SL: {sl}")
        print(f"   SL distance: {dist_pct:.2f}%")
        print(f"   Calculated leverage: {lev:.2f}x")
        
        sig["leverage"] = lev
        
        # Assign mode based on calculated leverage
        if lev < 7.5:
            # Low leverage signals use SWING mode (6x)
            sig["leverage"] = 6.0
            sig["mode"] = "SWING"
            print(f"   Mode: SWING (leverage < 7.5)")
        else:
            # All calculated leverage >= 7.5 uses DYNAMIC mode (shows decimals)
            sig["mode"] = "DYNAMIC"
            print(f"   Mode: DYNAMIC (leverage >= 7.5)")
    elif sig.get("leverage_hint"):
        # Use channel's leverage hint
        lev = float(sig["leverage_hint"])
        sig["leverage"] = lev
        if lev == 6:
            sig["mode"] = "SWING"
        elif lev >= 10:
            sig["mode"] = "FAST"
        else:
            sig["mode"] = "DYNAMIC"
    else:
        # Default to FAST mode with 10x
        sig["leverage"] = 10.0
        sig["mode"] = "FAST"

    print(f"✅ Processing signal: {sig['symbol']} {sig['direction']} from {chan_name} • Leverage: {sig['leverage']:.2f}x • Mode: {sig['mode']}")

    # Send comprehensive signal received message to output channel
    try:
        from app.telegram.output import send_message
        from app.telegram import templates_v2
        from app.config.settings import IM_PER_ENTRY_USDT
        
        # Calculate IM (Initial Margin) - total IM for the trade
        im = float(IM_PER_ENTRY_USDT)  # Default: 20 USDT total (split across dual entries)
        
        # Choose template based on mode
        entry = sig.get("entries", ["?"])[0] if sig.get("entries") else "?"
        tps = sig.get("tps", [])
        sl = sig.get("sl", "?")
        direction = sig.get("direction", "LONG")
        lev = sig.get("leverage", 10.0)
        
        if sig["mode"] == "SWING":
            msg = templates_v2.signal_received_swing(sig['symbol'], chan_name, entry, tps, sl, im)
        elif sig["mode"] == "DYNAMIC":
            msg = templates_v2.signal_received_dynamic(sig['symbol'], chan_name, direction, entry, tps, sl, lev, im)
        else:  # FAST
            msg = templates_v2.signal_received_fast(sig['symbol'], chan_name, direction, entry, tps, sl, im)
        
        await send_message(msg)
    except Exception as e:
        print(f"⚠️  Could not send confirmation message: {e}")
        # Continue processing the signal even if we can't send confirmation

    # Start the trade FSM (ACK-gated internal steps will trigger messages)
    try:
        await TradeFSM(sig).run()
    except Exception as e:
        print(f"❌ Trade execution failed for {sig['symbol']}: {e}")
        # Error messages have already been sent by the FSM, just log here

async def start_telegram():
    print("🔌 Starting Telegram client...")
    print(f"📋 Whitelisted channels: {settings.SRC_CHANNEL_NAMES}")
    print(f"🔑 API ID: {settings.TELEGRAM_API_ID}")
    print(f"🔑 API Hash: {'*' * len(settings.TELEGRAM_API_HASH) if settings.TELEGRAM_API_HASH else 'NOT SET'}")
    
    try:
        print("🔄 Connecting to Telegram...")
        await client.start()
        print("✅ Telegram client started successfully!")
        print("📡 Listening for signals from whitelisted channels...")
        print("🎯 Bot is ready! Send test signals to your channels.")
        
        # Keep the bot running
        await client.run_until_disconnected()
        
    except Exception as e:
        print(f"❌ Telegram connection failed: {e}")
        print("💡 Troubleshooting:")
        print("   1. Check if .env file has correct TELEGRAM_API_ID and TELEGRAM_API_HASH")
        print("   2. Run 'python telegram_auth.py' for first-time authentication")
        print("   3. Make sure you have internet connection")
        print("   4. Check if Telegram API credentials are valid")
        
        # Don't raise the exception, just log it and continue
        print("🔄 Continuing without Telegram connection...")
        return