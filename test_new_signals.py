#!/usr/bin/env python3

from app.signals.normalizer import parse_signal

# Test KP3R/USD signal
kp3r_signal = """✳️ New FREE signal

💎 BUY #KP3R/USD at #KRAKEN

📈 SPOT TRADE
🆔 #2887172
⏱️ 30-Sep-2025 18:12:24 UTC

🛒 Entry Zone: 4.30315000 - 4.46602000
💵 Current ask: 4.42000000
🎯 Target 1: 4.61020000 (4.30%)
🎯 Target 2: 4.69030000 (6.12%)
🎯 Target 3: 4.77040000 (7.93%)
🚫 Stop loss: 4.25420000 (3.75%)
💰 Volume #KP3R: 658.939130
💰 Volume #USD: 2861.291616

⏳ SHORT/MID TERM (up to 2 weeks)
⚠️ Risk:  - Invest up to 5% of your portfolio
☯️ R/R ratio: 1.6"""

print("=== Testing KP3R/USD Signal ===")
print("Input:", repr(kp3r_signal))
result = parse_signal(kp3r_signal)
print("Result:", result)
print()

# Test H/USDT signal
h_signal = """Moneda #H/usdt

 
 Entrada 0.095997

 
 Objetivo 🎯 

 0.092000 
  0.088000 
  0.084000 
  0.080000 
  0.076042

 
 Stop-Loss: 0.099409"""

print("=== Testing H/USDT Signal ===")
print("Input:", repr(h_signal))
result = parse_signal(h_signal)
print("Result:", result)
print()

# Test LIVE/USDT signal
live_signal = """✳ New FREE signal
💎 BUY #LIVE/USDT at #BITGET
📈 SPOT TRADE
🆔 #2887219
⏱ 30-Sep-2025 18:14:20 UTC"""

print("=== Testing LIVE/USDT Signal ===")
print("Input:", repr(live_signal))
result = parse_signal(live_signal)
print("Result:", result)