from decimal import getcontext, ROUND_DOWN, ROUND_HALF_UP

# Set a high precision for all Decimal arithmetic globally
getcontext().prec = 28

# Export commonly used rounding modes
ROUND_QTY = ROUND_DOWN
ROUND_PRICE = ROUND_HALF_UP

