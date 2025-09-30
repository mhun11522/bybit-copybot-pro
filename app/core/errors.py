import functools, asyncio, time, traceback
from app.telegram.output import send_message
from app.core.retcodes import MAP, TRANSIENT

_BREAKER = {"open": False, "until": 0.0, "fail_count": 0}
_PAUSE_S = 120
_MAX_FAILS = 3

def _extract_retcode(exc: Exception):
    s = str(exc)
    for tok in s.replace(",", " ").replace(":", " ").split():
        if tok.isdigit():
            try: return int(tok)
            except: pass
    return None

def safe_step(step_name: str):
    def deco(fn):
        @functools.wraps(fn)
        async def wrap(*a, **kw):
            if _BREAKER["open"] and time.time() < _BREAKER["until"]:
                await send_message("⛔ Paus aktiverad / Trading paused (circuit breaker)")
                raise RuntimeError("Circuit breaker open")
            try:
                return await fn(*a, **kw)
            except Exception as e:
                code = _extract_retcode(e)
                await send_message(MAP.get(code, f"❌ Okänt fel / Unknown error in {step_name}"))
                if code in TRANSIENT:
                    delay = 1.0
                    for _ in range(2):
                        await asyncio.sleep(delay)
                        try: return await fn(*a, **kw)
                        except Exception: delay *= 2
                _BREAKER["fail_count"] += 1
                if _BREAKER["fail_count"] >= _MAX_FAILS:
                    _BREAKER["open"] = True
                    _BREAKER["until"] = time.time() + _PAUSE_S
                    _BREAKER["fail_count"] = 0
                    await send_message("⛔ Trading pausad i 2 min / Trading paused for 2 minutes")
                traceback.print_exc()
                raise
        return wrap
    return deco

def breaker_reset():
    if _BREAKER["open"] and time.time() >= _BREAKER["until"]:
        _BREAKER["open"] = False
    if _BREAKER["fail_count"] > 0:
        _BREAKER["fail_count"] -= 1