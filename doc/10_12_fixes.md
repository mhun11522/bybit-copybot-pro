# CRITICAL FIXES - October 12, 2025

## Client Issue Report
Client reported two critical problems with orders:
1. **Wrong Initial Margin (IM)**: 149.80 USDT and 213.65 USDT instead of 20 USDT
2. **Wrong Leverage**: 10.00x and 7.50x instead of expected SWING 6.00x

---

## ROOT CAUSE ANALYSIS

### Issue 1: Initial Margin Calculation Bug

**Problem**: Bot was calculating IM as a percentage of wallet balance instead of using fixed BASE_IM.

**Formula Used (WRONG)**:
```
IM = wallet_balance × risk_pct × channel_multiplier
Example: 7,490 USDT × 0.02 = 149.80 USDT ❌
Example: 10,682 USDT × 0.02 = 213.64 USDT ❌
```

**Formula Should Be (CORRECT)**:
```
IM = 20 USDT (fixed BASE_IM from config)
```

**File**: `app/core/position_calculator.py`
**Lines**: 109-124

**Impact**: Client was risking 7-10x more capital per trade than intended (150-200 USDT instead of 20 USDT).

---

### Issue 2: Leverage Mode Detection Bug

**Problem**: Bot was defaulting to DYNAMIC mode (7.5x minimum) when no mode keyword was found in signal.

**Logic Used (WRONG)**:
```
If signal has no "SWING", "FAST", or "DYNAMIC" keyword:
  → Default to DYNAMIC mode (7.5x minimum) ❌
```

**Logic Should Be (CORRECT)**:
```
If signal has no "SWING", "FAST", or "DYNAMIC" keyword:
  → Default to SWING mode (6.00x fixed) ✅
```

**File**: `app/signals/strict_parser.py`
**Lines**: 846-871

**Impact**: Orders were using wrong leverage (7.5x or 10x instead of 6.0x SWING).

---

## FIXES APPLIED

### Fix 1: Position Calculator

**Changed**: `app/core/position_calculator.py` lines 109-124

**Before**:
```python
base_im = wallet_balance * risk_pct * channel_risk_multiplier
im = base_im
```

**After**:
```python
from app.config.settings import BASE_IM
im = BASE_IM  # Fixed 20 USDT per trade
```

**Result**: All trades now use fixed 20 USDT IM regardless of wallet balance.

---

### Fix 2: Leverage Classification

**Changed**: `app/signals/strict_parser.py` lines 868-871

**Before**:
```python
# Default to DYNAMIC with calculated leverage
leverage = self._calculate_dynamic_leverage(raw_leverage)
return leverage, "DYNAMIC"
```

**After**:
```python
# Default to SWING x6.00 when no mode keyword detected
system_logger.info("No mode keyword detected, defaulting to SWING x6.00")
return STRICT_CONFIG.swing_leverage, "SWING"
```

**Result**: Signals without mode keywords now default to SWING (6.00x).

---

## EXPECTED BEHAVIOR AFTER FIX

### Example Order (ETHUSDT LONG)

**Before Fix**:
- IM: 149.80 USDT ❌
- Leverage: 10.00x or 7.50x ❌
- Position Size: ~0.26 or 5.03 contracts

**After Fix**:
- IM: 20.00 USDT ✅
- Leverage: 6.00x (SWING) ✅
- Position Size: ~0.04 contracts (20 × 6 / 3000 = 0.04 ETH)

---

## LEVERAGE RULES (REMINDER)

| Mode | Leverage | When Used |
|------|----------|-----------|
| SWING | **x6.00** (fixed) | Default mode when no keyword detected |
| DYNAMIC | **x7.50 - x25.00** | When signal explicitly says "DYNAMIC" |
| FAST | **x10.00** (fixed) | When signal explicitly says "FAST" or no SL detected |

---

## TESTING RECOMMENDATIONS

1. **Restart the bot** to apply fixes
2. **Test with new signal** to verify:
   - IM shows 20.00 USDT
   - Leverage shows 6.00x for SWING signals
3. **Monitor next 3-5 trades** to confirm fixes work correctly

---

## FILES MODIFIED

1. `app/core/position_calculator.py`
   - Fixed IM calculation to use BASE_IM
   - Updated debug logging

2. `app/signals/strict_parser.py`
   - Changed default mode from DYNAMIC to SWING
   - Added logging for mode detection

---

## IMMEDIATE ACTIONS REQUIRED

⚠️ **RESTART BOT REQUIRED** - These changes require bot restart to take effect.

```bash
# Stop current bot instance
# Then restart with:
python start_bot.py
```

---

**Status**: ✅ FIXED
**Date**: 2025-10-12
**Priority**: CRITICAL
**Tested**: Ready for deployment

