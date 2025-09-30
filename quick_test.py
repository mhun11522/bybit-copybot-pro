from app.signals.normalizer import parse_signal

# Test simple signal
result = parse_signal('BTCUSDT LONG lev=10 entries=60000,59800 sl=59000 tps=61000,62000,63000')
print('Simple signal result:', result)

# Test JUP signal
jup_signal = "✳ New FREE signal 💎 BUY #JUP/USD at #KRAKEN 📈 SPOT TRADE 🆔 #2882703 ⏱ 30-Sep-2025 09:03:46 UTC 🛒 Entry Zone: 0.41464960 - 0.43034368 💵 Current ask: 0.42692000 🎯 Target 1: 0.44423680 (4.06%) 🎯 Target 2: 0.45195520 (5.86%) 🎯 Target 3: 0.45967360 (7.67%) 🚫 Stop loss: 0.40993280 (3.98%)"
result2 = parse_signal(jup_signal)
print('JUP signal result:', result2)