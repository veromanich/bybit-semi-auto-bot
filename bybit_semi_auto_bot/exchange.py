from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from pybit.unified_trading import HTTP

from .config import Settings


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    last_price: float
    mark_price: float | None
    index_price: float | None


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    side: str
    size: float
    avg_price: float
    unrealised_pnl: float


class BybitClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.session = HTTP(
            testnet=False,
            demo=settings.is_demo,
            api_key=settings.api_key or None,
            api_secret=settings.api_secret or None,
            recv_window=settings.recv_window,
        )

    def get_market_snapshot(self, symbol: str) -> MarketSnapshot:
        response = self.session.get_tickers(category=self.settings.category, symbol=symbol)
        item = _first_result_item(response, "list")
        return MarketSnapshot(
            symbol=item["symbol"],
            last_price=_to_float(item.get("lastPrice")),
            mark_price=_optional_float(item.get("markPrice")),
            index_price=_optional_float(item.get("indexPrice")),
        )

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> list[dict[str, float]]:
        response = self.session.get_kline(
            category=self.settings.category,
            symbol=symbol,
            interval=interval,
            limit=limit,
        )
        rows = response.get("result", {}).get("list", [])
        candles = [
            {
                "timestamp": float(row[0]),
                "open": _to_float(row[1]),
                "high": _to_float(row[2]),
                "low": _to_float(row[3]),
                "close": _to_float(row[4]),
                "volume": _to_float(row[5]),
            }
            for row in rows
        ]
        candles.sort(key=lambda row: row["timestamp"])
        return candles

    def get_wallet_balance(self) -> float | None:
        if not self._has_credentials:
            return None
        response = self.session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
        account = _first_result_item(response, "list")
        coins = account.get("coin", [])
        usdt = next((coin for coin in coins if coin.get("coin") == "USDT"), None)
        if not usdt:
            return None
        return _optional_float(usdt.get("walletBalance"))

    def get_position(self, symbol: str) -> PositionSnapshot | None:
        if not self._has_credentials:
            return None
        response = self.session.get_positions(category=self.settings.category, symbol=symbol)
        positions = response.get("result", {}).get("list", [])
        active = next((item for item in positions if _to_float(item.get("size", "0")) > 0), None)
        if not active:
            return None
        return PositionSnapshot(
            symbol=active["symbol"],
            side=active.get("side", ""),
            size=_to_float(active.get("size")),
            avg_price=_to_float(active.get("avgPrice")),
            unrealised_pnl=_to_float(active.get("unrealisedPnl")),
        )

    def place_market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "category": self.settings.category,
            "symbol": symbol,
            "side": side,
            "orderType": "Market",
            "qty": _format_decimal(qty),
        }
        if stop_loss:
            payload["stopLoss"] = _format_decimal(stop_loss)
        if take_profit:
            payload["takeProfit"] = _format_decimal(take_profit)
        return self.session.place_order(**payload)

    def set_leverage(self, symbol: str, leverage: float) -> dict[str, Any]:
        leverage_text = _format_decimal(leverage)
        return self.session.set_leverage(
            category=self.settings.category,
            symbol=symbol,
            buyLeverage=leverage_text,
            sellLeverage=leverage_text,
        )

    def switch_margin_mode(self, symbol: str, margin_mode: str, leverage: float) -> dict[str, Any]:
        leverage_text = _format_decimal(leverage)
        trade_mode = 1 if margin_mode == "isolated" else 0
        return self.session.switch_margin_mode(
            category=self.settings.category,
            symbol=symbol,
            tradeMode=trade_mode,
            buyLeverage=leverage_text,
            sellLeverage=leverage_text,
        )

    def close_position_market(self, position: PositionSnapshot) -> dict[str, Any]:
        close_side = "Sell" if position.side == "Buy" else "Buy"
        return self.session.place_order(
            category=self.settings.category,
            symbol=position.symbol,
            side=close_side,
            orderType="Market",
            qty=_format_decimal(position.size),
            reduceOnly=True,
        )

    @property
    def _has_credentials(self) -> bool:
        return bool(self.settings.api_key and self.settings.api_secret)


def _first_result_item(response: dict[str, Any], key: str) -> dict[str, Any]:
    rows = response.get("result", {}).get(key, [])
    if not rows:
        raise RuntimeError(f"Bybit returned an empty result for {key}")
    return rows[0]


def _to_float(value: Any) -> float:
    if value in {None, ""}:
        return 0.0
    return float(value)


def _optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def _format_decimal(value: float) -> str:
    try:
        decimal = Decimal(str(value)).normalize()
    except InvalidOperation as exc:
        raise ValueError(f"Invalid decimal value: {value}") from exc
    return format(decimal, "f")
