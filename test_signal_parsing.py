#!/usr/bin/env python3

import sys
sys.path.append('.')

from app.signals.normalizer import parse_signal

# Test signals from the logs
test_signals = [
    # Spanish signal
    """Moneda #H/USDT
 
 Entrada 0.095997
 Objetivo 🎯
 0.092000
  0.088000
  0.084000
  0.080000""",
    
    # English signal  
    """New premium signals short
Coin #H/USDT
 Entry 0.095997
 Target 🎯
 0.092000
  0.088000""",
    
    # Complex symbol
    """Coin: #NEIROETHUSDT
Long Set-Up
Leverage: 5-10x"""
]

for i, signal in enumerate(test_signals, 1):
    print(f"\n=== Test Signal {i} ===")
    print(f"Input: {signal[:100]}...")
    result = parse_signal(signal)
    print(f"Result: {result}")