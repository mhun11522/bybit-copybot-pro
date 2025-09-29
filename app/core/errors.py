import functools
import asyncio
from app.telegram.output import send_message
from app.core.retcodes import MAP, TRANSIENT


def safe_step(step_name: str, max_retries: int = 3):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            delay = 1
            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
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
                    raise
        return wrapper
    return decorator

