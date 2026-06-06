from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskPrices:
    entry_price: float
    stop_loss: float
    take_profit: float
    stop_percent: float
    take_profit_percent: float


def calculate_risk_prices(
    side: str,
    entry_price: float,
    stop_percent: float,
    reward_risk: float | None = None,
    take_profit_percent: float | None = None,
) -> RiskPrices:
    if entry_price <= 0:
        raise ValueError("Entry price must be greater than zero.")
    if stop_percent <= 0:
        raise ValueError("Stop percent must be greater than zero.")
    if reward_risk is None and take_profit_percent is None:
        raise ValueError("Reward/risk or take profit percent is required.")

    resolved_take_profit_percent = (
        stop_percent * reward_risk if reward_risk is not None else take_profit_percent
    )
    if resolved_take_profit_percent is None or resolved_take_profit_percent <= 0:
        raise ValueError("Take profit percent must be greater than zero.")

    if side == "Buy":
        stop_loss = entry_price * (1 - stop_percent / 100)
        take_profit = entry_price * (1 + resolved_take_profit_percent / 100)
    elif side == "Sell":
        stop_loss = entry_price * (1 + stop_percent / 100)
        take_profit = entry_price * (1 - resolved_take_profit_percent / 100)
    else:
        raise ValueError(f"Unsupported order side: {side}")

    return RiskPrices(
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        stop_percent=stop_percent,
        take_profit_percent=resolved_take_profit_percent,
    )


def format_price(value: float) -> str:
    text = f"{value:.8f}".rstrip("0").rstrip(".")
    return text if text else "0"
