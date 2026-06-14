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


@dataclass(frozen=True)
class InstrumentRules:
    symbol: str
    min_order_qty: str
    qty_step: str
    min_notional_value: str | None
    tick_size: str


@dataclass(frozen=True)
class OpenOrder:
    order_id: str
    symbol: str
    side: str
    order_type: str
    price: str
    qty: str
    trigger_price: str
    status: str
    created_time: str


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    order_type: str
    qty: float
    price: float | None = None
    trigger_price: float | None = None
    trigger_direction: int | None = None
    trigger_by: str | None = None
    time_in_force: str | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


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

    def get_instrument_rules(self, symbol: str) -> InstrumentRules:
        response = self.session.get_instruments_info(category=self.settings.category, symbol=symbol)
        item = _first_result_item(response, "list")
        lot_size = item.get("lotSizeFilter", {})
        price_filter = item.get("priceFilter", {})
        return InstrumentRules(
            symbol=item["symbol"],
            min_order_qty=str(lot_size.get("minOrderQty", "0")),
            qty_step=str(lot_size.get("qtyStep", "0")),
            min_notional_value=(
                str(lot_size["minNotionalValue"]) if lot_size.get("minNotionalValue") not in {None, ""} else None
            ),
            tick_size=str(price_filter.get("tickSize", "0")),
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

    def get_open_orders(self, symbol: str) -> list[OpenOrder]:
        if not self._has_credentials:
            return []
        response = self.session.get_open_orders(category=self.settings.category, symbol=symbol)
        rows = response.get("result", {}).get("list", [])
        return [
            OpenOrder(
                order_id=str(item.get("orderId", "")),
                symbol=str(item.get("symbol", "")),
                side=str(item.get("side", "")),
                order_type=str(item.get("orderType", "")),
                price=str(item.get("price", "")),
                qty=str(item.get("qty", "")),
                trigger_price=str(item.get("triggerPrice", "")),
                status=str(item.get("orderStatus", "")),
                created_time=str(item.get("createdTime", "")),
            )
            for item in rows
        ]

    def cancel_order(self, symbol: str, order_id: str) -> dict[str, Any]:
        return self.session.cancel_order(
            category=self.settings.category,
            symbol=symbol,
            orderId=order_id,
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

    def place_order(self, request: OrderRequest) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "category": self.settings.category,
            "symbol": request.symbol,
            "side": request.side,
            "orderType": request.order_type,
            "qty": _format_decimal(request.qty),
            "positionIdx": 0,
        }
        if request.price is not None:
            payload["price"] = _format_decimal(request.price)
        if request.time_in_force:
            payload["timeInForce"] = request.time_in_force
        if request.trigger_price is not None:
            payload["triggerPrice"] = _format_decimal(request.trigger_price)
        if request.trigger_direction is not None:
            payload["triggerDirection"] = request.trigger_direction
        if request.trigger_by:
            payload["triggerBy"] = request.trigger_by
        if request.stop_loss:
            payload["stopLoss"] = _format_decimal(request.stop_loss)
        if request.take_profit:
            payload["takeProfit"] = _format_decimal(request.take_profit)
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
