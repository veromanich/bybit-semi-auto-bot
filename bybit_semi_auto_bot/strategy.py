from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    label: str
    direction: str
    fast_ema: float
    slow_ema: float
    last_close: float


def ema_signal(candles: list[dict[str, float]], fast_period: int = 9, slow_period: int = 21) -> Signal:
    if len(candles) < slow_period + 2:
        raise ValueError(f"Need at least {slow_period + 2} candles for EMA signal")

    closes = [candle["close"] for candle in candles]
    fast = _ema(closes, fast_period)
    slow = _ema(closes, slow_period)

    previous_fast = fast[-2]
    previous_slow = slow[-2]
    current_fast = fast[-1]
    current_slow = slow[-1]

    if previous_fast <= previous_slow and current_fast > current_slow:
        label = "LONG setup: fast EMA crossed above slow EMA"
        direction = "Buy"
    elif previous_fast >= previous_slow and current_fast < current_slow:
        label = "SHORT setup: fast EMA crossed below slow EMA"
        direction = "Sell"
    elif current_fast > current_slow:
        label = "Trend bias: LONG"
        direction = "Buy"
    elif current_fast < current_slow:
        label = "Trend bias: SHORT"
        direction = "Sell"
    else:
        label = "No clear EMA bias"
        direction = "Neutral"

    return Signal(
        label=label,
        direction=direction,
        fast_ema=current_fast,
        slow_ema=current_slow,
        last_close=closes[-1],
    )


def _ema(values: list[float], period: int) -> list[float]:
    multiplier = 2 / (period + 1)
    result = [sum(values[:period]) / period]
    for price in values[period:]:
        result.append((price - result[-1]) * multiplier + result[-1])
    padding = [result[0]] * (period - 1)
    return padding + result

