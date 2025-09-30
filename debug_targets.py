#!/usr/bin/env python3

import re
from decimal import Decimal

# Test the target parsing
signal = """Moneda #H/USDT
 
 Entrada 0.095997
 Objetivo 🎯
 0.092000
  0.088000
  0.084000
  0.080000"""

original_text = signal.strip()
t = " ".join(original_text.split())

print("Normalized text:")
print(repr(t))
print()

# Test the target regex
m_tps = re.search(r"Objetivo\s*🎯\s*([0-9\.,\s\-]+)", t, re.I)
print(f"Target match: {m_tps}")
if m_tps:
    target_text = m_tps.group(1).strip()
    print(f"Target text: {repr(target_text)}")
    tps = [x.strip() for x in target_text.split() if x.strip() and re.match(r'^[0-9]+(?:\.[0-9]+)?$', x.strip())]
    print(f"Parsed targets: {tps}")
    
    # Test decimal conversion
    for tp in tps:
        try:
            val = Decimal(tp)
            print(f"  {tp} -> {val}")
        except Exception as e:
            print(f"  {tp} -> ERROR: {e}")