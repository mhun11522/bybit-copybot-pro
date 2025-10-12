# Client Explanation - IM and Leverage Issues

## Problem Summary

Your bot was placing orders with:
- **Wrong IM**: 149.80 USDT and 213.65 USDT instead of 20 USDT
- **Wrong Leverage**: 10.00x and 7.50x instead of 6.00x (SWING)

## What Went Wrong

### Issue 1: IM Calculation
The bot was calculating Initial Margin as **2% of your wallet balance** instead of using a fixed 20 USDT.

**Example**:
- Your wallet: 7,490 USDT
- Bot calculated: 7,490 × 0.02 = **149.80 USDT** ❌
- Should be: **20 USDT** ✅

This means you were risking **7-10x more money per trade** than intended!

### Issue 2: Leverage Mode
The bot was defaulting to **DYNAMIC mode (7.5x minimum)** when signals didn't have mode keywords, instead of defaulting to **SWING (6.00x)**.

---

## What Was Fixed

### Fix 1: IM Calculation ✅
Changed the bot to always use **fixed 20 USDT per trade**, regardless of wallet size.

**File**: `app/core/position_calculator.py`

### Fix 2: Leverage Default ✅  
Changed default mode from DYNAMIC to **SWING (6.00x)** when no mode keyword is detected.

**File**: `app/signals/strict_parser.py`

---

## What Happens Now

### Before Fix:
```
Order: ETHUSDT LONG
IM: 149.80 USDT ❌
Leverage: 10.00x ❌
Risk: TOO HIGH
```

### After Fix:
```
Order: ETHUSDT LONG
IM: 20.00 USDT ✅
Leverage: 6.00x (SWING) ✅
Risk: Controlled
```

---

## Next Steps

1. **Bot needs restart** to apply these fixes
2. Test with next signal to verify correct values
3. Monitor next 3-5 trades to confirm everything works

---

## Trade Types (Reminder)

| Type | Leverage | IM per Trade |
|------|----------|--------------|
| SWING (default) | x6.00 | 20 USDT |
| DYNAMIC | x7.50-x25.00 | 20 USDT |
| FAST | x10.00 | 20 USDT |

---

**Status**: ✅ FIXED  
**Priority**: CRITICAL  
**Action Required**: Restart bot

The issues have been identified and fixed. Your bot will now use correct IM (20 USDT) and leverage (6.00x SWING by default) for all trades.

