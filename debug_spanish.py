#!/usr/bin/env python3

import re

# Test the Spanish signal step by step
signal = """Moneda #H/USDT
 
 Entrada 0.095997
 Objetivo 🎯
 0.092000
  0.088000
  0.084000
  0.080000"""

print("Original signal:")
print(repr(signal))
print()

# Clean and normalize
original_text = signal.strip()
t = " ".join(original_text.split())
print("Normalized text:")
print(repr(t))
print()

# Test symbol regex
SYM_RE = r"([A-Z0-9]{1,}USDT|#[A-Z0-9]{1,}\/USDT|#[A-Z0-9]{1,}\/USD|[A-Z0-9]{1,}\/USDT|#([A-Z0-9]{1,})USDT|([A-Z0-9]{1,})USDT\.P|#([A-Z0-9]{1,})ETHUSDT|([A-Z0-9]{1,})ETHUSDT)"
m_sym = re.search(SYM_RE, t, re.I)
print(f"Symbol match: {m_sym}")
if m_sym:
    print(f"Symbol groups: {m_sym.groups()}")

# Test direction regex
LONG_RE = r"(LONG|LÅNG|BUY|🟢|💎\s*BUY|🔴\s*Long|Opening\s+LONG|Position:\s*LONG|Long\s+Set-Up)"
SHORT_RE = r"(SHORT|SELL|🔴|💎\s*SELL|Opening\s+SHORT|Position:\s*SHORT|Short\s+Set-Up|premium\s+signals\s+short)"

m_long = re.search(LONG_RE, t, re.I)
m_short = re.search(SHORT_RE, t, re.I)
print(f"Long match: {m_long}")
print(f"Short match: {m_short}")

# Test entry regex
m_ent = re.search(r"Entrada\s*([0-9\.,\s\-]+)", t, re.I)
print(f"Entry match: {m_ent}")
if m_ent:
    print(f"Entry groups: {m_ent.groups()}")

# Test target regex
m_tps = re.search(r"Objetivo\s*🎯\s*([0-9\.,\s\-]+)", t, re.I)
print(f"Target match: {m_tps}")
if m_tps:
    print(f"Target groups: {m_tps.groups()}")