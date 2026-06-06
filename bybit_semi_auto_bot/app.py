from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, TypeVar

from .config import Settings, load_settings
from .exchange import BybitClient, MarketSnapshot, PositionSnapshot
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
        self.position: PositionSnapshot | None = None
        self.signal: Signal | None = None

        self.symbol_var = tk.StringVar(value=settings.symbol)
        self.qty_var = tk.StringVar(value=str(settings.default_qty))
        self.stop_loss_var = tk.StringVar(value="")
        self.take_profit_var = tk.StringVar(value="")
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

        mode = "TESTNET" if self.settings.testnet else "LIVE"
        ttk.Label(top, text=f"Mode: {mode}").grid(row=0, column=2, sticky="e", padx=(0, 16))
        ttk.Button(top, text="Refresh", command=self.refresh_all).grid(row=0, column=3, sticky="e")

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

        ttk.Label(right, text="Stop loss").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self.stop_loss_var).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Label(right, text="Take profit").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(right, textvariable=self.take_profit_var).grid(row=2, column=1, sticky="ew", pady=4)

        ttk.Button(right, text="Open Long", command=lambda: self.confirm_order("Buy")).grid(
            row=3, column=0, columnspan=2, sticky="ew", pady=(16, 6)
        )
        ttk.Button(right, text="Open Short", command=lambda: self.confirm_order("Sell")).grid(
            row=4, column=0, columnspan=2, sticky="ew", pady=6
        )
        ttk.Button(right, text="Close Position", command=self.confirm_close_position).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=6
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
        self.signal = signal
        self.position = position

        mark = f", mark {market.mark_price:.2f}" if market.mark_price else ""
        self.market_var.set(f"{market.symbol}: last {market.last_price:.2f}{mark}")
        self.signal_var.set(
            f"{signal.label}\nFast EMA: {signal.fast_ema:.2f} | Slow EMA: {signal.slow_ema:.2f}"
            if signal
            else "No signal"
        )
        self.position_var.set(_format_position(position))
        self.balance_var.set(f"USDT wallet balance: {balance:.2f}" if balance is not None else "USDT wallet balance: API key needed")
        self.status_var.set("Ready")

    def confirm_order(self, side: str) -> None:
        symbol = self.symbol_var.get().strip().upper()
        qty = _parse_float(self.qty_var.get(), "Quantity")
        stop_loss = _parse_optional_float(self.stop_loss_var.get(), "Stop loss")
        take_profit = _parse_optional_float(self.take_profit_var.get(), "Take profit")
        if qty is None or stop_loss is False or take_profit is False:
            return

        direction = "LONG" if side == "Buy" else "SHORT"
        confirmed = messagebox.askyesno(
            "Confirm order",
            f"Open {direction} market order?\n\nSymbol: {symbol}\nQty: {qty}\nStop loss: {stop_loss or '-'}\nTake profit: {take_profit or '-'}",
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


def main() -> None:
    settings = load_settings()
    app = TradingApp(settings)
    app.mainloop()
