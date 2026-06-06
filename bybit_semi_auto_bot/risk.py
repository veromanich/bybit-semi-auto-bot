from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskPrices:
    entry_price: float
    stop_loss: float
    take_profit: float
    stop_percent: float
    take_profit_percent: float


@dataclass(frozen=True)
class PositionSize:
    quantity: float
    risk_amount: float
    position_value: float
    estimated_margin: float


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


def calculate_position_size(
    entry_price: float,
    stop_loss: float,
    balance: float,
    risk_percent: float,
    leverage: float = 1,
) -> PositionSize:
    if entry_price <= 0:
        raise ValueError("Entry price must be greater than zero.")
    if balance <= 0:
        raise ValueError("Wallet balance must be greater than zero.")
    if risk_percent <= 0:
        raise ValueError("Risk percent must be greater than zero.")
    if leverage <= 0:
        raise ValueError("Leverage must be greater than zero.")

    stop_distance = abs(entry_price - stop_loss)
    if stop_distance <= 0:
        raise ValueError("Stop loss must be different from entry price.")

    risk_amount = balance * risk_percent / 100
    quantity = risk_amount / stop_distance
    position_value = quantity * entry_price
    estimated_margin = position_value / leverage

    return PositionSize(
        quantity=quantity,
        risk_amount=risk_amount,
        position_value=position_value,
        estimated_margin=estimated_margin,
    )


def format_price(value: float) -> str:
    text = f"{value:.8f}".rstrip("0").rstrip(".")
    return text if text else "0"
