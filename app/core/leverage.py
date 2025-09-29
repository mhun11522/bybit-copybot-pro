from dataclasses import dataclass


@dataclass
class LeveragePolicy:
    mode: str  # SWING | DYNAMIC | FAST


def enforce_leverage(mode: str, requested: int) -> int:
    mode = (mode or "").upper()
    if mode == "SWING":
        return 6
    if mode == "FAST":
        return 10
    # DYNAMIC: must be >= 8 (no 6–7.5)
    if requested < 8:
        return 8
    return requested

