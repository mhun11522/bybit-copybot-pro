from decimal import Decimal, getcontext
from app.config.settings import LEV_MIN, LEV_MAX

getcontext().prec = 28

def dynamic_leverage(entry: Decimal, sl: Decimal) -> Decimal:
    """
    Client spec (Sept 17): leverage derived from SL distance.
    Conservative safe default: lev = clamp( 100 / sl_distance_pct, [LEV_MIN, LEV_MAX] )
    
    More conservative approach: cap at 12x for very tight SL distances
    """
    dist_pct = abs((entry - sl) / entry) * Decimal("100")
    if dist_pct <= 0:
        return Decimal(str(LEV_MIN))
    
    # Calculate base leverage
    lev = Decimal("100") / dist_pct
    
    # Apply conservative caps for very tight SL distances
    if dist_pct < 2.0:  # Less than 2% SL distance
        lev = Decimal("12")  # Cap at 12x for tight SL
    elif dist_pct < 3.0:  # Less than 3% SL distance  
        lev = Decimal("10")  # Cap at 10x for very tight SL
    elif dist_pct < 5.0:  # Less than 5% SL distance
        lev = Decimal("8")   # Cap at 8x for tight SL
    
    # Apply min/max bounds
    if lev < Decimal(str(LEV_MIN)): lev = Decimal(str(LEV_MIN))
    if lev > Decimal(str(LEV_MAX)): lev = Decimal(str(LEV_MAX))
    
    # round to 2 decimals
    return lev.quantize(Decimal("0.01"))
