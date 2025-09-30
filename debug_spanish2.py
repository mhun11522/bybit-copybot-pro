#!/usr/bin/env python3

import sys
sys.path.append('.')

from app.signals.normalizer import parse_signal

# Test the Spanish signal
signal = """Moneda #H/USDT
 
 Entrada 0.095997
 Objetivo 🎯
 0.092000
  0.088000
  0.084000
  0.080000"""

print("Testing Spanish signal:")
print(repr(signal))
print()

result = parse_signal(signal)
print(f"Result: {result}")

# Let's also test with a direction added
signal_with_direction = """SHORT Moneda #H/USDT
 
 Entrada 0.095997
 Objetivo 🎯
 0.092000
  0.088000
  0.084000
  0.080000"""

print("\nTesting with SHORT direction:")
result2 = parse_signal(signal_with_direction)
print(f"Result: {result2}")