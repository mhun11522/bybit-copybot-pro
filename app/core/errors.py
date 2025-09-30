import functools
import asyncio
from app.telegram.output import send_message
from app.core.retcodes import MAP, TRANSIENT
import time

# Simple in-memory circuit breaker per step
_FAIL_COUNTS: dict[str, int] = {}
_BREAKER_UNTIL: dict[str, float] = {}


def safe_step(step_name: str, max_retries: int = 3, breaker_threshold: int = 3, breaker_cooldown_sec: int = 120):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Check breaker
            now = time.time()
            unblock_ts = _BREAKER_UNTIL.get(step_name)
            if unblock_ts and now < unblock_ts:
                try:
                    await send_message(f"⛔ Pausad steg • {step_name}\n⛔ Circuit breaker open • {step_name}")
                except Exception:
                    pass
                raise RuntimeError(f"circuit_breaker_open {step_name}")
            delay = 1
            for attempt in range(1, max_retries + 1):
                try:
                    result = await func(*args, **kwargs)
                    # Reset failure count on success
                    _FAIL_COUNTS.pop(step_name, None)
                    return result
                except Exception as e:
                    # Try to extract numeric code from exception text
                    code = None
                    for token in str(e).split():
                        if token.isdigit():
                            code = int(token)
                            break
                    human = MAP.get(code, f"❌ Okänt fel / Unknown error in {step_name}")
                    try:
                        await send_message(f"{human} (försök {attempt})")
                    except Exception:
                        pass
                    if code in TRANSIENT and attempt < max_retries:
                        await asyncio.sleep(delay)
                        delay *= 2
                        continue
                    # Hard failure reached; update breaker counts
                    _FAIL_COUNTS[step_name] = _FAIL_COUNTS.get(step_name, 0) + 1
                    if _FAIL_COUNTS[step_name] >= breaker_threshold:
                        _BREAKER_UNTIL[step_name] = time.time() + breaker_cooldown_sec
                        try:
                            await send_message(
                                f"⛔ Avbrott aktiverat • {step_name}\n⛔ Circuit breaker tripped • {step_name}"
                            )
                        except Exception:
                            pass
                    raise
        return wrapper
    return decorator

