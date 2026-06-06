from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from dataclasses import replace
from typing import Callable, Literal, TypeVar

from .config import Settings, load_settings
from .exchange import BybitClient, MarketSnapshot, PositionSnapshot
from .risk import RiskPrices, calculate_risk_prices, format_price
from .strategy import Signal, ema_signal


T = TypeVar("T")


class TradingApp(tk.Tk):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.title("Bybit Futures Semi-Auto Bot")
        self.geometry("820x560")
        self.minsize(760, 520)

        self.settings = settings
        self.client = BybitClient(settings)
        self.market: MarketSnapshot | None = None
        self.position: PositionSnapshot | None = None
        self.signal: Signal | None = None

        self.symbol_var = tk.StringVar(value=settings.symbol)
        self.mode_var = tk.StringVar(value=_mode_label(settings.trading_mode))
        self.qty_var = tk.StringVar(value=str(settings.default_qty))
        self.stop_loss_var = tk.StringVar(value="")
        self.take_profit_var = tk.StringVar(value="")
        self.auto_risk_var = tk.BooleanVar(value=True)
        self.stop_percent_var = tk.StringVar(value="1")
        self.risk_mode_var = tk.StringVar(value="Risk/reward")
        self.reward_risk_var = tk.StringVar(value="3")
        self.take_profit_percent_var = tk.StringVar(value="3")
        self.status_var = tk.StringVar(value="Ready")
        self.market_var = tk.StringVar(value="-")
        self.balance_var = tk.StringVar(value="-")
        self.position_var = tk.StringVar(value="No active position")
        self.signal_var = tk.StringVar(value="No signal loaded")

        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=12)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Symbol").grid(row=0, column=0, sticky="w")
        ttk.Entry(top, textvariable=self.symbol_var, width=14).grid(row=0, column=1, sticky="w", padx=(8, 20))

        ttk.Label(top, text="Trading").grid(row=0, column=2, sticky="e", padx=(0, 8))
        mode_box = ttk.Combobox(
            top,
            textvariable=self.mode_var,
            values=("Demo", "Live"),
            state="readonly",
            width=8,
        )
        mode_box.grid(row=0, column=3, sticky="e", padx=(0, 16))
        mode_box.bind("<<ComboboxSelected>>", lambda _event: self.change_trading_mode())
        ttk.Button(top, text="Refresh", command=self.refresh_all).grid(row=0, column=4, sticky="e")

        body = ttk.Frame(self, padding=(12, 0, 12, 12))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(body, text="Market", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)

        ttk.Label(left, textvariable=self.market_var, font=("Segoe UI", 14)).grid(row=0, column=0, sticky="w")
        ttk.Separator(left).grid(row=1, column=0, sticky="ew", pady=12)
        ttk.Label(left, text="EMA signal").grid(row=2, column=0, sticky="w")
        ttk.Label(left, textvariable=self.signal_var, wraplength=460, font=("Segoe UI", 12)).grid(
            row=3, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Separator(left).grid(row=4, column=0, sticky="ew", pady=12)
        ttk.Label(left, text="Position").grid(row=5, column=0, sticky="w")
        ttk.Label(left, textvariable=self.position_var, wraplength=460, font=("Segoe UI", 12)).grid(
            row=6, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Separator(left).grid(row=7, column=0, sticky="ew", pady=12)
        ttk.Label(left, textvariable=self.balance_var).grid(row=8, column=0, sticky="w")

        right = ttk.LabelFrame(body, text="Manual Order", padding=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.columnconfigure(1, weight=1)

        ttk.Label(right, text="Quantity").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self.qty_var).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Checkbutton(right, text="Auto SL/TP", variable=self.auto_risk_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(8, 4)
        )

        ttk.Label(right, text="Stop %").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self.stop_percent_var).grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Label(right, text="Target mode").grid(row=3, column=0, sticky="w", pady=4)
        ttk.Combobox(
            right,
            textvariable=self.risk_mode_var,
            values=("Risk/reward", "Profit percent"),
            state="readonly",
        ).grid(row=3, column=1, sticky="ew", pady=4)

        ttk.Label(right, text="RR").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self.reward_risk_var).grid(row=4, column=1, sticky="ew", pady=4)

        ttk.Label(right, text="Profit %").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self.take_profit_percent_var).grid(row=5, column=1, sticky="ew", pady=4)

        ttk.Button(right, text="Calc Long SL/TP", command=lambda: self.calculate_and_fill_risk("Buy")).grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=(12, 4)
        )
        ttk.Button(right, text="Calc Short SL/TP", command=lambda: self.calculate_and_fill_risk("Sell")).grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=4
        )

        ttk.Separator(right).grid(row=8, column=0, columnspan=2, sticky="ew", pady=10)

        ttk.Label(right, text="Stop loss").grid(row=9, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self.stop_loss_var).grid(row=9, column=1, sticky="ew", pady=4)

        ttk.Label(right, text="Take profit").grid(row=10, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self.take_profit_var).grid(row=10, column=1, sticky="ew", pady=4)

        ttk.Button(right, text="Open Long", command=lambda: self.confirm_order("Buy")).grid(
            row=11, column=0, columnspan=2, sticky="ew", pady=(16, 6)
        )
        ttk.Button(right, text="Open Short", command=lambda: self.confirm_order("Sell")).grid(
            row=12, column=0, columnspan=2, sticky="ew", pady=6
        )
        ttk.Button(right, text="Close Position", command=self.confirm_close_position).grid(
            row=13, column=0, columnspan=2, sticky="ew", pady=6
        )

        status = ttk.Frame(self, padding=(12, 0, 12, 12))
        status.grid(row=2, column=0, sticky="ew")
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

    def refresh_all(self) -> None:
        symbol = self.symbol_var.get().strip().upper()

        def work() -> tuple[MarketSnapshot, Signal | None, PositionSnapshot | None, float | None]:
            market = self.client.get_market_snapshot(symbol)
            candles = self.client.get_klines(symbol, self.settings.interval)
            signal = ema_signal(candles)
            position = self.client.get_position(symbol)
            balance = self.client.get_wallet_balance()
            return market, signal, position, balance

        self._run_background("Refreshing data...", work, self._apply_refresh_result)

    def _apply_refresh_result(self, result: tuple[MarketSnapshot, Signal | None, PositionSnapshot | None, float | None]) -> None:
        market, signal, position, balance = result
        self.market = market
        self.signal = signal
        self.position = position

        mark = f", mark {market.mark_price:.2f}" if market.mark_price else ""
        self.market_var.set(f"{market.symbol}: last {market.last_price:.2f}{mark} | {_mode_label(self.settings.trading_mode)}")
        self.signal_var.set(
            f"{signal.label}\nFast EMA: {signal.fast_ema:.2f} | Slow EMA: {signal.slow_ema:.2f}"
            if signal
            else "No signal"
        )
        self.position_var.set(_format_position(position))
        self.balance_var.set(f"USDT wallet balance: {balance:.2f}" if balance is not None else "USDT wallet balance: API key needed")
        self.status_var.set("Ready")

    def change_trading_mode(self) -> None:
        new_mode = _mode_value(self.mode_var.get())
        if new_mode == self.settings.trading_mode:
            return
        if new_mode == "live":
            confirmed = messagebox.askyesno(
                "Switch to live trading",
                "Switch to LIVE trading?\n\nOrders will be sent to the real Bybit account if API keys are live keys.",
            )
            if not confirmed:
                self.mode_var.set(_mode_label(self.settings.trading_mode))
                return

        self.settings = replace(self.settings, trading_mode=new_mode)
        self.client = BybitClient(self.settings)
        self.status_var.set(f"Switched to {_mode_label(new_mode)}")
        self.refresh_all()

    def calculate_and_fill_risk(self, side: Literal["Buy", "Sell"]) -> RiskPrices | None:
        try:
            prices = self._calculate_risk(side)
        except ValueError as exc:
            messagebox.showerror("Risk settings", str(exc))
            return None

        self.stop_loss_var.set(format_price(prices.stop_loss))
        self.take_profit_var.set(format_price(prices.take_profit))
        direction = "LONG" if side == "Buy" else "SHORT"
        self.status_var.set(
            f"{direction} risk: SL {prices.stop_percent:g}%, TP {prices.take_profit_percent:g}%"
        )
        return prices

    def confirm_order(self, side: Literal["Buy", "Sell"]) -> None:
        symbol = self.symbol_var.get().strip().upper()
        qty = _parse_float(self.qty_var.get(), "Quantity")
        risk_prices = None
        if self.auto_risk_var.get():
            risk_prices = self.calculate_and_fill_risk(side)
            if risk_prices is None:
                return

        stop_loss = _parse_optional_float(self.stop_loss_var.get(), "Stop loss")
        take_profit = _parse_optional_float(self.take_profit_var.get(), "Take profit")
        if qty is None or stop_loss is False or take_profit is False:
            return

        direction = "LONG" if side == "Buy" else "SHORT"
        mode = _mode_label(self.settings.trading_mode)
        entry_line = f"\nReference entry: {risk_prices.entry_price:.2f}" if risk_prices else ""
        confirmed = messagebox.askyesno(
            "Confirm order",
            f"Open {direction} market order on {mode}?\n\n"
            f"Symbol: {symbol}\nQty: {qty}{entry_line}\n"
            f"Stop loss: {stop_loss or '-'}\nTake profit: {take_profit or '-'}",
        )
        if not confirmed:
            return

        def work() -> dict:
            return self.client.place_market_order(symbol, side, qty, stop_loss, take_profit)

        self._run_background("Placing order...", work, lambda result: self._order_done(result, "Order placed"))

    def confirm_close_position(self) -> None:
        if not self.position:
            messagebox.showinfo("No position", "There is no active position to close.")
            return

        confirmed = messagebox.askyesno(
            "Confirm close",
            f"Close current {self.position.side} position?\n\nSymbol: {self.position.symbol}\nSize: {self.position.size}",
        )
        if not confirmed:
            return

        def work() -> dict:
            if not self.position:
                raise RuntimeError("Position disappeared before close request")
            return self.client.close_position_market(self.position)

        self._run_background("Closing position...", work, lambda result: self._order_done(result, "Close order placed"))

    def _calculate_risk(self, side: Literal["Buy", "Sell"]) -> RiskPrices:
        if not self.market:
            raise ValueError("Refresh market data before calculating SL/TP.")

        stop_percent = _require_float(self.stop_percent_var.get(), "Stop %")
        if self.risk_mode_var.get() == "Risk/reward":
            reward_risk = _require_float(self.reward_risk_var.get(), "RR")
            return calculate_risk_prices(
                side=side,
                entry_price=self.market.last_price,
                stop_percent=stop_percent,
                reward_risk=reward_risk,
            )

        take_profit_percent = _require_float(self.take_profit_percent_var.get(), "Profit %")
        return calculate_risk_prices(
            side=side,
            entry_price=self.market.last_price,
            stop_percent=stop_percent,
            take_profit_percent=take_profit_percent,
        )

    def _order_done(self, result: dict, message: str) -> None:
        order_id = result.get("result", {}).get("orderId", "-")
        self.status_var.set(f"{message}. Order ID: {order_id}")
        self.refresh_all()

    def _run_background(self, status: str, func: Callable[[], T], on_success: Callable[[T], None]) -> None:
        self.status_var.set(status)

        def runner() -> None:
            try:
                result = func()
            except Exception as exc:
                self.after(0, lambda: self._show_error(exc))
                return
            self.after(0, lambda: on_success(result))

        threading.Thread(target=runner, daemon=True).start()

    def _show_error(self, exc: Exception) -> None:
        self.status_var.set("Error")
        messagebox.showerror("Bybit bot error", str(exc))


def _format_position(position: PositionSnapshot | None) -> str:
    if not position:
        return "No active position"
    return (
        f"{position.side} {position.size:g} {position.symbol}\n"
        f"Average: {position.avg_price:.2f} | Unrealised PnL: {position.unrealised_pnl:.4f}"
    )


def _parse_float(value: str, label: str) -> float | None:
    try:
        parsed = float(value)
    except ValueError:
        messagebox.showerror("Invalid value", f"{label} must be a number.")
        return None
    if parsed <= 0:
        messagebox.showerror("Invalid value", f"{label} must be greater than zero.")
        return None
    return parsed


def _parse_optional_float(value: str, label: str) -> float | None | bool:
    if not value.strip():
        return None
    return _parse_float(value, label) or False


def _require_float(value: str, label: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be a number.") from exc
    if parsed <= 0:
        raise ValueError(f"{label} must be greater than zero.")
    return parsed


def _mode_label(mode: str) -> str:
    return "Live" if mode == "live" else "Demo"


def _mode_value(label: str) -> str:
    return "live" if label.lower() == "live" else "demo"


def main() -> None:
    settings = load_settings()
    app = TradingApp(settings)
    app.mainloop()
