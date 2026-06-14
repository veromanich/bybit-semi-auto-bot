from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Literal, TypeVar

from .config import Settings, load_settings
from .exchange import BybitClient, InstrumentRules, MarketSnapshot, OrderRequest, PositionSnapshot
from .risk import PositionSize, RiskPrices, calculate_position_size, calculate_risk_prices, format_price
from .strategy import Signal, ema_signal


T = TypeVar("T")
OrderSide = Literal["Buy", "Sell"]


ORDER_KINDS = ("Рыночная", "Лимит", "Стоп", "Стоп-лимит")
ORDER_KIND_API = {
    "Рыночная": ("Market", False),
    "Лимит": ("Limit", False),
    "Стоп": ("Market", True),
    "Стоп-лимит": ("Limit", True),
}
TIME_IN_FORCE = ("Годен до отмены", "IOC", "FOK", "PostOnly", "RPI")
TIME_IN_FORCE_API = {"Годен до отмены": "GTC", "IOC": "IOC", "FOK": "FOK", "PostOnly": "PostOnly", "RPI": "RPI"}
TRIGGER_DIRECTIONS = ("Авто", "Цена растет", "Цена падает")
TRIGGER_BY = ("Последняя цена", "Цена маркировки", "Индексная цена")
TRIGGER_BY_API = {
    "Последняя цена": "LastPrice",
    "Цена маркировки": "MarkPrice",
    "Индексная цена": "IndexPrice",
}


class TradingApp(tk.Tk):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.title("Bybit полуавтоматический бот")
        self.geometry("1040x760")
        self.minsize(960, 720)
        self.configure(bg="#0f0f10")

        self.settings = settings
        self.client = BybitClient(settings)
        self.market: MarketSnapshot | None = None
        self.position: PositionSnapshot | None = None
        self.signal: Signal | None = None
        self.wallet_balance: float | None = None
        self.instrument_rules: InstrumentRules | None = None

        self.symbol_var = tk.StringVar(value=settings.symbol)
        self.mode_var = tk.StringVar(value=_mode_label(settings.trading_mode))

        self.side_var = tk.StringVar(value="Buy")
        self.order_kind_var = tk.StringVar(value="Рыночная")
        self.qty_var = tk.StringVar(value=str(settings.default_qty))
        self.limit_price_var = tk.StringVar(value="")
        self.time_in_force_var = tk.StringVar(value="Годен до отмены")
        self.trigger_price_var = tk.StringVar(value="")
        self.trigger_direction_var = tk.StringVar(value="Авто")
        self.trigger_by_var = tk.StringVar(value="Последняя цена")

        self.auto_qty_var = tk.BooleanVar(value=False)
        self.risk_percent_var = tk.StringVar(value="1")
        self.leverage_var = tk.StringVar(value="1")
        self.margin_mode_var = tk.StringVar(value="Кросс")
        self.apply_settings_before_order_var = tk.BooleanVar(value=False)

        self.auto_risk_var = tk.BooleanVar(value=False)
        self.stop_percent_var = tk.StringVar(value="1")
        self.risk_mode_var = tk.StringVar(value="Риск/прибыль")
        self.reward_risk_var = tk.StringVar(value="3")
        self.take_profit_percent_var = tk.StringVar(value="3")
        self.stop_loss_var = tk.StringVar(value="")
        self.take_profit_var = tk.StringVar(value="")

        self.status_var = tk.StringVar(value="Готово")
        self.market_var = tk.StringVar(value="-")
        self.balance_var = tk.StringVar(value="-")
        self.position_var = tk.StringVar(value="Нет открытой позиции")
        self.signal_var = tk.StringVar(value="Сигнал не загружен")
        self.rules_var = tk.StringVar(value="Правила инструмента: не загружены")
        self.order_value_var = tk.StringVar(value="Сумма сделки: -")
        self.order_risk_var = tk.StringVar(value="Риск: -")
        self.error_count_var = tk.StringVar(value="Ошибки: 0")
        self.order_field_rows: dict[str, list[tk.Widget]] = {}
        self.error_log: list[tuple[str, str]] = []
        self.error_list: tk.Listbox | None = None

        self._configure_theme()
        self._build_ui()
        self.refresh_all()

    def _configure_theme(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", background="#0f0f10", foreground="#e6e6e6", fieldbackground="#18191c")
        style.configure("TFrame", background="#0f0f10")
        style.configure("Ticket.TFrame", background="#141518")
        style.configure("TLabel", background="#0f0f10", foreground="#d8d8d8")
        style.configure("TLabelframe", background="#0f0f10", foreground="#d8d8d8", bordercolor="#2b2d33")
        style.configure("TLabelframe.Label", background="#0f0f10", foreground="#ffffff", font=("Segoe UI", 10, "bold"))
        style.configure("Muted.TLabel", background="#0f0f10", foreground="#8c8f98")
        style.configure("Ticket.TLabel", background="#141518", foreground="#d8d8d8")
        style.configure("Header.TLabel", background="#0f0f10", foreground="#ffffff", font=("Segoe UI", 13, "bold"))
        style.configure("Section.TLabel", background="#141518", foreground="#ffffff", font=("Segoe UI", 10, "bold"))
        style.configure("TEntry", fieldbackground="#111215", foreground="#ffffff", insertcolor="#ffffff", bordercolor="#34363c")
        style.configure("TCombobox", fieldbackground="#111215", foreground="#ffffff", bordercolor="#34363c")
        style.configure("TCheckbutton", background="#141518", foreground="#d8d8d8")
        style.configure("TNotebook", background="#141518", borderwidth=0)
        style.configure("TNotebook.Tab", background="#141518", foreground="#a5a8b0", padding=(10, 6))
        style.map("TNotebook.Tab", background=[("selected", "#1f2024")], foreground=[("selected", "#ffffff")])
        style.configure("Buy.TButton", background="#2458ff", foreground="#ffffff", font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Buy.TButton", background=[("active", "#3768ff")])
        style.configure("Sell.TButton", background="#303136", foreground="#ffffff", font=("Segoe UI", 10, "bold"), padding=8)
        style.map("Sell.TButton", background=[("active", "#3b3c42")])
        style.configure("Primary.TButton", background="#2458ff", foreground="#ffffff", font=("Segoe UI", 11, "bold"), padding=10)
        style.map("Primary.TButton", background=[("active", "#3768ff")])

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        top = ttk.Frame(self, padding=12)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Символ").grid(row=0, column=0, sticky="w")
        symbol_entry = ttk.Entry(top, textvariable=self.symbol_var, width=14)
        symbol_entry.grid(row=0, column=1, sticky="w", padx=(8, 20))
        symbol_entry.bind("<Return>", lambda _event: self.refresh_all())
        symbol_entry.bind("<FocusOut>", lambda _event: self._clear_symbol_state_if_needed())

        ttk.Label(top, text="Режим").grid(row=0, column=2, sticky="e", padx=(0, 8))
        mode_box = ttk.Combobox(
            top,
            textvariable=self.mode_var,
            values=("Демо", "Реальный"),
            state="readonly",
            width=8,
        )
        mode_box.grid(row=0, column=3, sticky="e", padx=(0, 16))
        mode_box.bind("<<ComboboxSelected>>", lambda _event: self.change_trading_mode())
        ttk.Button(top, text="Обновить", command=self.refresh_all).grid(row=0, column=4, sticky="e")

        body = ttk.Frame(self, padding=(12, 0, 12, 12))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(body, text="Рынок", padding=12)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.columnconfigure(0, weight=1)

        ttk.Label(left, textvariable=self.market_var, font=("Segoe UI", 14)).grid(row=0, column=0, sticky="w")
        ttk.Separator(left).grid(row=1, column=0, sticky="ew", pady=12)
        ttk.Label(left, text="EMA сигнал").grid(row=2, column=0, sticky="w")
        ttk.Label(left, textvariable=self.signal_var, wraplength=520, font=("Segoe UI", 12)).grid(
            row=3, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Separator(left).grid(row=4, column=0, sticky="ew", pady=12)
        ttk.Label(left, text="Позиция").grid(row=5, column=0, sticky="w")
        ttk.Label(left, textvariable=self.position_var, wraplength=520, font=("Segoe UI", 12)).grid(
            row=6, column=0, sticky="w", pady=(4, 0)
        )
        ttk.Separator(left).grid(row=7, column=0, sticky="ew", pady=12)
        ttk.Label(left, textvariable=self.balance_var).grid(row=8, column=0, sticky="w")
        ttk.Label(left, textvariable=self.rules_var, wraplength=520).grid(row=9, column=0, sticky="w", pady=(8, 0))

        right = ttk.LabelFrame(body, text="Заявка", padding=10)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        side_bar = ttk.Frame(right, style="Ticket.TFrame")
        side_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        side_bar.columnconfigure((0, 1), weight=1)
        self.sell_button = ttk.Button(side_bar, text="Продать", style="Sell.TButton", command=lambda: self._set_side("Sell"))
        self.sell_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.buy_button = ttk.Button(side_bar, text="Купить", style="Buy.TButton", command=lambda: self._set_side("Buy"))
        self.buy_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        notebook = ttk.Notebook(right)
        notebook.grid(row=1, column=0, sticky="nsew")

        self._build_order_tab(notebook)
        self._build_risk_tab(notebook)
        self._build_protection_tab(notebook)
        self._build_margin_tab(notebook)
        self._build_errors_tab(notebook)

        actions = ttk.Frame(right, padding=(0, 10, 0, 0))
        actions.grid(row=2, column=0, sticky="ew")
        actions.columnconfigure((0, 1), weight=1)
        self.submit_button = ttk.Button(actions, text="Купить", style="Primary.TButton", command=self.confirm_selected_order)
        self.submit_button.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Button(actions, text="Закрыть позицию", command=self.confirm_close_position).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0)
        )

        status = ttk.Frame(self, padding=(12, 0, 12, 12))
        status.grid(row=2, column=0, sticky="ew")
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Label(status, textvariable=self.error_count_var).grid(row=0, column=1, sticky="e")
        self._set_side(self.side_var.get())

    def _build_order_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Заявка")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Тип заявки").grid(row=0, column=0, sticky="w", pady=4)
        order_box = ttk.Combobox(frame, textvariable=self.order_kind_var, values=ORDER_KINDS, state="readonly")
        order_box.grid(row=0, column=1, sticky="ew", pady=4)
        order_box.bind("<<ComboboxSelected>>", lambda _event: self._order_type_changed())

        ttk.Label(frame, text="Количество").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.qty_var).grid(row=1, column=1, sticky="ew", pady=4)

        limit_label = ttk.Label(frame, text="Цена")
        limit_entry = ttk.Entry(frame, textvariable=self.limit_price_var)
        self._grid_order_row("limit_price", limit_label, limit_entry, row=2)

        tif_label = ttk.Label(frame, text="Время действия")
        tif_box = ttk.Combobox(frame, textvariable=self.time_in_force_var, values=TIME_IN_FORCE, state="readonly")
        self._grid_order_row("time_in_force", tif_label, tif_box, row=3)

        trigger_price_label = ttk.Label(frame, text="Стоп-цена")
        trigger_price_entry = ttk.Entry(frame, textvariable=self.trigger_price_var)
        self._grid_order_row("trigger_price", trigger_price_label, trigger_price_entry, row=4)

        trigger_direction_label = ttk.Label(frame, text="Условие")
        trigger_direction_box = ttk.Combobox(
            frame,
            textvariable=self.trigger_direction_var,
            values=TRIGGER_DIRECTIONS,
            state="readonly",
        )
        self._grid_order_row("trigger_direction", trigger_direction_label, trigger_direction_box, row=5)

        trigger_by_label = ttk.Label(frame, text="Источник цены")
        trigger_by_box = ttk.Combobox(frame, textvariable=self.trigger_by_var, values=TRIGGER_BY, state="readonly")
        self._grid_order_row("trigger_by", trigger_by_label, trigger_by_box, row=6)

        fill_limit_button = ttk.Button(frame, text="Взять рыночную цену", command=self._fill_limit_from_market)
        fill_limit_button.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(12, 4))
        self.order_field_rows["fill_limit"] = [fill_limit_button]
        self._order_type_changed()

    def _grid_order_row(self, key: str, label: tk.Widget, field: tk.Widget, row: int) -> None:
        label.grid(row=row, column=0, sticky="w", pady=4)
        field.grid(row=row, column=1, sticky="ew", pady=4)
        self.order_field_rows[key] = [label, field]

    def _build_errors_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Ошибки")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        list_frame = ttk.Frame(frame)
        list_frame.grid(row=0, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.error_list = tk.Listbox(list_frame, height=12)
        self.error_list.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.error_list.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.error_list.configure(yscrollcommand=scrollbar.set)

        ttk.Button(frame, text="Очистить ошибки", command=self._clear_errors).grid(
            row=1, column=0, sticky="ew", pady=(10, 0)
        )

    def _build_risk_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Риск")
        frame.columnconfigure(1, weight=1)

        ttk.Checkbutton(frame, text="Авто количество", variable=self.auto_qty_var).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        ttk.Label(frame, text="Риск, % баланса").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.risk_percent_var).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Separator(frame).grid(row=2, column=0, columnspan=2, sticky="ew", pady=10)

        ttk.Checkbutton(frame, text="Авто SL/TP", variable=self.auto_risk_var).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )
        ttk.Label(frame, text="Стоп, %").grid(row=4, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.stop_percent_var).grid(row=4, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Цель").grid(row=5, column=0, sticky="w", pady=4)
        ttk.Combobox(
            frame,
            textvariable=self.risk_mode_var,
            values=("Риск/прибыль", "Процент профита"),
            state="readonly",
        ).grid(row=5, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="RR").grid(row=6, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.reward_risk_var).grid(row=6, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Профит, %").grid(row=7, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.take_profit_percent_var).grid(row=7, column=1, sticky="ew", pady=4)

        ttk.Button(frame, text="Рассчитать для покупки", command=lambda: self.calculate_and_fill_order("Buy")).grid(
            row=8, column=0, columnspan=2, sticky="ew", pady=(12, 4)
        )
        ttk.Button(frame, text="Рассчитать для продажи", command=lambda: self.calculate_and_fill_order("Sell")).grid(
            row=9, column=0, columnspan=2, sticky="ew", pady=4
        )
        ttk.Label(frame, textvariable=self.order_risk_var).grid(row=10, column=0, columnspan=2, sticky="w", pady=(12, 0))
        ttk.Label(frame, textvariable=self.order_value_var).grid(row=11, column=0, columnspan=2, sticky="w", pady=(4, 0))

    def _build_protection_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Выход")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Стоп-лосс").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.stop_loss_var).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Тейк-профит").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.take_profit_var).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Button(frame, text="Очистить SL/TP", command=self._clear_protection).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(12, 4)
        )

    def _build_margin_tab(self, notebook: ttk.Notebook) -> None:
        frame = ttk.Frame(notebook, padding=12)
        notebook.add(frame, text="Настройки")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Плечо").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=self.leverage_var).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(frame, text="Маржа").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Combobox(
            frame,
            textvariable=self.margin_mode_var,
            values=("Кросс", "Изолированная"),
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=4)

        ttk.Button(frame, text="Применить маржу/плечо", command=self.confirm_apply_trade_settings).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(12, 4)
        )
        ttk.Checkbutton(
            frame,
            text="Применять перед заявкой",
            variable=self.apply_settings_before_order_var,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def refresh_all(self) -> None:
        symbol = self.symbol_var.get().strip().upper()
        self.symbol_var.set(symbol)

        def work() -> tuple[MarketSnapshot, InstrumentRules, Signal | None, PositionSnapshot | None, float | None]:
            market = self.client.get_market_snapshot(symbol)
            rules = self.client.get_instrument_rules(symbol)
            candles = self.client.get_klines(symbol, self.settings.interval)
            signal = ema_signal(candles)
            position = self.client.get_position(symbol)
            balance = self.client.get_wallet_balance()
            return market, rules, signal, position, balance

        self._run_background("Refreshing data...", work, self._apply_refresh_result)

    def _apply_refresh_result(
        self,
        result: tuple[MarketSnapshot, InstrumentRules, Signal | None, PositionSnapshot | None, float | None],
    ) -> None:
        market, rules, signal, position, balance = result
        self.market = market
        self.instrument_rules = rules
        self.signal = signal
        self.position = position
        self.wallet_balance = balance

        mark = f", mark {market.mark_price:.2f}" if market.mark_price else ""
        self.market_var.set(f"{market.symbol}: last {market.last_price:.2f}{mark} | {_mode_label(self.settings.trading_mode)}")
        self.signal_var.set(
            f"{signal.label}\nFast EMA: {signal.fast_ema:.2f} | Slow EMA: {signal.slow_ema:.2f}"
            if signal
            else "No signal"
        )
        self.position_var.set(_format_position(position))
        self.balance_var.set(f"USDT wallet balance: {balance:.2f}" if balance is not None else "USDT wallet balance: API key needed")
        self.rules_var.set(_format_rules(rules))
        self.status_var.set("Ready")

    def change_trading_mode(self) -> None:
        new_mode = _mode_value(self.mode_var.get())
        if new_mode == self.settings.trading_mode:
            return
        if new_mode == "live":
            confirmed = messagebox.askyesno(
                "Переключение на реальный режим",
                "Переключиться на РЕАЛЬНУЮ торговлю?\n\nЗаявки будут отправляться на настоящий аккаунт Bybit, если ключи реальные.",
            )
            if not confirmed:
                self.mode_var.set(_mode_label(self.settings.trading_mode))
                return

        self.settings = replace(self.settings, trading_mode=new_mode)
        self.client = BybitClient(self.settings)
        self._clear_loaded_market_state()
        self.status_var.set(f"Switched to {_mode_label(new_mode)}")
        self.refresh_all()

    def calculate_and_fill_risk(self, side: OrderSide) -> RiskPrices | None:
        try:
            prices = self._calculate_risk(side)
        except ValueError as exc:
            messagebox.showerror("Risk settings", str(exc))
            return None

        self.stop_loss_var.set(format_price(prices.stop_loss))
        self.take_profit_var.set(format_price(prices.take_profit))
        direction = "покупки" if side == "Buy" else "продажи"
        self.status_var.set(
            f"Риск для {direction}: SL {prices.stop_percent:g}%, TP {prices.take_profit_percent:g}%"
        )
        return prices

    def calculate_and_fill_order(self, side: OrderSide) -> RiskPrices | None:
        prices = self.calculate_and_fill_risk(side)
        if prices is None:
            return None

        if self.auto_qty_var.get():
            try:
                size = self._calculate_position_size(prices)
            except ValueError as exc:
                messagebox.showerror("Position size", str(exc))
                return None

            quantity = size.quantity
            if self.instrument_rules:
                quantity = _round_decimal_str(str(quantity), self.instrument_rules.qty_step, ROUND_FLOOR)
            self.qty_var.set(format_price(quantity))
            self.status_var.set(
                f"Риск {size.risk_amount:.2f} USDT | Кол-во {format_price(quantity)} | "
                f"Маржа ~{size.estimated_margin:.2f} USDT"
            )
            self.order_risk_var.set(f"Риск: {size.risk_amount:.2f} USDT")
            self.order_value_var.set(f"Сумма сделки: {size.position_value:.2f} USDT")

        return prices

    def confirm_order(self, side: OrderSide) -> None:
        symbol = self.symbol_var.get().strip().upper()
        self.symbol_var.set(symbol)
        if not self._has_fresh_market(symbol):
            messagebox.showinfo("Обновите символ", f"Данные рынка для {symbol} ещё не загружены. Сейчас обновлю.")
            self.refresh_all()
            return

        risk_prices = None
        if self.auto_risk_var.get():
            risk_prices = self.calculate_and_fill_order(side)
            if risk_prices is None:
                return

        request = self._build_order_request(symbol, side)
        if request is None:
            return

        direction = "покупку" if side == "Buy" else "продажу"
        mode = _mode_label(self.settings.trading_mode)
        entry_line = f"\nReference entry: {risk_prices.entry_price:.2f}" if risk_prices else ""
        confirmed = messagebox.askyesno(
            "Подтвердите заявку",
            f"Открыть {direction}: {self.order_kind_var.get()} ({mode})?\n\n"
            f"Символ: {symbol}\nКоличество: {request.qty}{entry_line}\n"
            f"Цена: {request.price or '-'}\nСтоп-цена: {request.trigger_price or '-'}\n"
            f"Стоп-лосс: {request.stop_loss or '-'}\nТейк-профит: {request.take_profit or '-'}\n"
            f"Маржа: {self.margin_mode_var.get()} | Плечо: {self.leverage_var.get().strip()}x",
        )
        if not confirmed:
            return

        apply_settings = self.apply_settings_before_order_var.get()
        margin_mode = _margin_mode_value(self.margin_mode_var.get())
        leverage = None
        if apply_settings:
            leverage = _parse_float(self.leverage_var.get(), "Leverage")
            if leverage is None:
                return

        def work() -> dict:
            if apply_settings and leverage is not None:
                self._apply_trade_settings_api(symbol, margin_mode, leverage)
            return self.client.place_order(request)

        self._run_background("Отправляю заявку...", work, lambda result: self._order_done(result, "Заявка отправлена"))

    def confirm_apply_trade_settings(self) -> None:
        symbol = self.symbol_var.get().strip().upper()
        self.symbol_var.set(symbol)
        leverage = _parse_float(self.leverage_var.get(), "Leverage")
        if leverage is None:
            return

        margin_mode = _margin_mode_value(self.margin_mode_var.get())
        mode = _mode_label(self.settings.trading_mode)
        confirmed = messagebox.askyesno(
            "Применить настройки",
            f"Применить маржу/плечо ({mode})?\n\n"
            f"Символ: {symbol}\nМаржа: {self.margin_mode_var.get()}\nПлечо: {leverage}x",
        )
        if not confirmed:
            return

        def work() -> dict:
            return self._apply_trade_settings_api(symbol, margin_mode, leverage)

        self._run_background(
            "Применяю маржу/плечо...",
            work,
            lambda result: self._settings_done(symbol, margin_mode, leverage, result),
        )

    def confirm_close_position(self) -> None:
        if not self.position:
            messagebox.showinfo("Нет позиции", "Нет открытой позиции для закрытия.")
            return

        confirmed = messagebox.askyesno(
            "Закрыть позицию",
            f"Закрыть текущую позицию {self.position.side}?\n\nСимвол: {self.position.symbol}\nРазмер: {self.position.size}",
        )
        if not confirmed:
            return

        def work() -> dict:
            if not self.position:
                raise RuntimeError("Position disappeared before close request")
            return self.client.close_position_market(self.position)

        self._run_background("Закрываю позицию...", work, lambda result: self._order_done(result, "Заявка на закрытие отправлена"))

    def _build_order_request(self, symbol: str, side: OrderSide) -> OrderRequest | None:
        qty = _parse_float(self.qty_var.get(), "Quantity")
        stop_loss = _parse_optional_float(self.stop_loss_var.get(), "Stop loss")
        take_profit = _parse_optional_float(self.take_profit_var.get(), "Take profit")
        if qty is None or stop_loss is False or take_profit is False:
            return None
        qty = self._normalize_quantity(qty)
        if qty is None:
            return None

        order_kind = self.order_kind_var.get()
        order_type, is_conditional = ORDER_KIND_API[order_kind]
        price = None
        trigger_price = None
        trigger_direction = None
        trigger_by = None

        if order_type == "Limit":
            price = _parse_float(self.limit_price_var.get(), "Limit price")
            if price is None:
                return None
            price = self._normalize_price(price, "Limit price")
            if price is None:
                return None
            self.limit_price_var.set(format_price(price))

        if is_conditional:
            trigger_price = _parse_float(self.trigger_price_var.get(), "Trigger price")
            if trigger_price is None:
                return None
            trigger_price = self._normalize_price(trigger_price, "Trigger price")
            if trigger_price is None:
                return None
            self.trigger_price_var.set(format_price(trigger_price))
            try:
                trigger_direction = self._resolve_trigger_direction(trigger_price)
            except ValueError as exc:
                messagebox.showerror("Trigger settings", str(exc))
                return None
            trigger_by = TRIGGER_BY_API[self.trigger_by_var.get()]

        time_in_force = TIME_IN_FORCE_API[self.time_in_force_var.get()]
        if order_type == "Market":
            time_in_force = "IOC"

        reference_price = price or (self.market.last_price if self.market else None)
        if reference_price is not None and not self._validate_min_notional(qty, reference_price):
            return None

        normalized_stop_loss = self._normalize_optional_price(stop_loss, "Stop loss")
        normalized_take_profit = self._normalize_optional_price(take_profit, "Take profit")
        if normalized_stop_loss is not None:
            self.stop_loss_var.set(format_price(normalized_stop_loss))
        if normalized_take_profit is not None:
            self.take_profit_var.set(format_price(normalized_take_profit))

        return OrderRequest(
            symbol=symbol,
            side=side,
            order_type=order_type,
            qty=qty,
            price=price,
            trigger_price=trigger_price,
            trigger_direction=trigger_direction,
            trigger_by=trigger_by,
            time_in_force=time_in_force,
            stop_loss=normalized_stop_loss,
            take_profit=normalized_take_profit,
        )

    def _calculate_risk(self, side: OrderSide) -> RiskPrices:
        symbol = self.symbol_var.get().strip().upper()
        if not self._has_fresh_market(symbol):
            raise ValueError(f"Refresh market data for {symbol} before calculating SL/TP.")

        stop_percent = _require_float(self.stop_percent_var.get(), "Stop %")
        if self.risk_mode_var.get() == "Риск/прибыль":
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

    def _calculate_position_size(self, prices: RiskPrices) -> PositionSize:
        if self.wallet_balance is None:
            raise ValueError("Wallet balance is not loaded. Add API keys and refresh data.")

        risk_percent = _require_float(self.risk_percent_var.get(), "Risk % balance")
        leverage = _require_float(self.leverage_var.get(), "Leverage")
        return calculate_position_size(
            entry_price=prices.entry_price,
            stop_loss=prices.stop_loss,
            balance=self.wallet_balance,
            risk_percent=risk_percent,
            leverage=leverage,
        )

    def _resolve_trigger_direction(self, trigger_price: float) -> int:
        direction = self.trigger_direction_var.get()
        if direction == "Цена растет":
            return 1
        if direction == "Цена падает":
            return 2
        if not self.market:
            raise ValueError("Market data is required for automatic trigger direction.")
        return 1 if trigger_price > self.market.last_price else 2

    def _settings_done(self, symbol: str, margin_mode: str, leverage: float, result: dict) -> None:
        label = "Изолированная" if margin_mode == "isolated" else "Кросс"
        warnings = [
            f"Margin warning: {result['margin_warning']}" if result.get("margin_warning") else "",
            f"Leverage warning: {result['leverage_warning']}" if result.get("leverage_warning") else "",
        ]
        warnings = [warning for warning in warnings if warning]
        suffix = f" | {' | '.join(warnings)}" if warnings else ""
        self.status_var.set(f"{symbol}: маржа {label}, плечо {leverage:g}x применено{suffix}")
        for warning in warnings:
            self._log_error(warning)
        self.refresh_all()

    def _apply_trade_settings_api(self, symbol: str, margin_mode: str, leverage: float) -> dict:
        results: dict[str, object] = {}
        try:
            results["margin"] = self.client.switch_margin_mode(symbol, margin_mode, leverage)
        except Exception as exc:
            results["margin_warning"] = str(exc)
        try:
            results["leverage"] = self.client.set_leverage(symbol, leverage)
        except Exception as exc:
            results["leverage_warning"] = str(exc)
        return results

    def _order_done(self, result: dict, message: str) -> None:
        order_id = result.get("result", {}).get("orderId", "-")
        self.status_var.set(f"{message}. ID: {order_id}")
        self.refresh_all()

    def _fill_limit_from_market(self) -> None:
        symbol = self.symbol_var.get().strip().upper()
        if not self._has_fresh_market(symbol):
            messagebox.showinfo("Обновите символ", f"Сначала обновите данные рынка для {symbol}.")
            return
        self.limit_price_var.set(format_price(self.market.last_price))

    def _order_type_changed(self) -> None:
        order_kind = self.order_kind_var.get()
        order_type, is_conditional = ORDER_KIND_API[order_kind]
        show_limit = order_type == "Limit"
        show_conditional = is_conditional

        self._set_order_rows_visible(["limit_price", "fill_limit"], show_limit)
        self._set_order_rows_visible(["time_in_force"], show_limit)
        self._set_order_rows_visible(["trigger_price", "trigger_direction", "trigger_by"], show_conditional)

        if order_kind == "Рыночная":
            self.time_in_force_var.set("IOC")
        elif self.time_in_force_var.get() == "IOC":
            self.time_in_force_var.set("Годен до отмены")

    def confirm_selected_order(self) -> None:
        self.confirm_order("Buy" if self.side_var.get() == "Buy" else "Sell")

    def _set_side(self, side: OrderSide) -> None:
        self.side_var.set(side)
        is_buy = side == "Buy"
        self.submit_button.configure(text="Купить" if is_buy else "Продать")
        self.submit_button.configure(style="Primary.TButton" if is_buy else "Sell.TButton")

    def _set_order_rows_visible(self, keys: list[str], visible: bool) -> None:
        for key in keys:
            for widget in self.order_field_rows.get(key, []):
                if visible:
                    widget.grid()
                else:
                    widget.grid_remove()

    def _clear_protection(self) -> None:
        self.stop_loss_var.set("")
        self.take_profit_var.set("")

    def _clear_symbol_state_if_needed(self) -> None:
        symbol = self.symbol_var.get().strip().upper()
        self.symbol_var.set(symbol)
        if self.market and self.market.symbol != symbol:
            self._clear_loaded_market_state()
            self.status_var.set(f"{symbol} выбран. Нажмите Обновить или Enter, чтобы загрузить рынок.")

    def _clear_loaded_market_state(self) -> None:
        self.market = None
        self.instrument_rules = None
        self.position = None
        self.signal = None
        self.wallet_balance = None
        self.market_var.set("-")
        self.position_var.set("Нет открытой позиции")
        self.signal_var.set("Сигнал не загружен")
        self.balance_var.set("-")
        self.rules_var.set("Правила инструмента: не загружены")

    def _has_fresh_market(self, symbol: str) -> bool:
        return bool(self.market and self.market.symbol == symbol and self.instrument_rules and self.instrument_rules.symbol == symbol)

    def _normalize_quantity(self, qty: float) -> float | None:
        if not self.instrument_rules:
            return qty

        rounded = _round_decimal_str(str(qty), self.instrument_rules.qty_step, ROUND_FLOOR)
        min_qty = _to_decimal(self.instrument_rules.min_order_qty)
        if Decimal(str(rounded)) < min_qty:
            min_text = _format_decimal(min_qty)
            self.qty_var.set(min_text)
            messagebox.showerror(
                "Quantity too small",
                f"Minimum quantity for {self.instrument_rules.symbol} is {min_text}.",
            )
            self._log_error(f"{self.instrument_rules.symbol} quantity below minimum. Minimum qty: {min_text}")
            return None

        if rounded != qty:
            self.qty_var.set(format_price(rounded))
            self.status_var.set(f"Quantity rounded to step {self.instrument_rules.qty_step}: {format_price(rounded)}")
        return rounded

    def _normalize_price(self, value: float, label: str) -> float | None:
        if not self.instrument_rules:
            return value
        rounded = _round_decimal_str(str(value), self.instrument_rules.tick_size, ROUND_HALF_UP)
        if rounded <= 0:
            messagebox.showerror("Invalid price", f"{label} must be greater than zero.")
            return None
        if rounded != value:
            self.status_var.set(f"{label} rounded to tick {self.instrument_rules.tick_size}: {format_price(rounded)}")
        return rounded

    def _normalize_optional_price(self, value: float | None | bool, label: str) -> float | None:
        if value is None or value is False:
            return None
        return self._normalize_price(float(value), label)

    def _validate_min_notional(self, qty: float, reference_price: float) -> bool:
        if not self.instrument_rules or not self.instrument_rules.min_notional_value:
            return True

        notional = Decimal(str(qty)) * Decimal(str(reference_price))
        min_notional = _to_decimal(self.instrument_rules.min_notional_value)
        if notional >= min_notional:
            return True

        message = (
            f"{self.instrument_rules.symbol} order value is below minimum. "
            f"Current: {_format_decimal(notional)} USDT, minimum: {_format_decimal(min_notional)} USDT."
        )
        messagebox.showerror("Order value too small", message)
        self._log_error(message)
        return False

    def _run_background(self, status: str, func: Callable[[], T], on_success: Callable[[T], None]) -> None:
        self.status_var.set(status)

        def runner() -> None:
            try:
                result = func()
            except Exception as exc:
                self.after(0, lambda exc=exc: self._show_error(exc))
                return
            self.after(0, lambda: on_success(result))

        threading.Thread(target=runner, daemon=True).start()

    def _show_error(self, exc: Exception) -> None:
        message = str(exc)
        self.status_var.set("Error")
        self._log_error(message)
        messagebox.showerror("Bybit bot error", message)

    def _log_error(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.error_log.append((timestamp, message))
        if len(self.error_log) > 100:
            self.error_log = self.error_log[-100:]

        if self.error_list is not None:
            self.error_list.delete(0, tk.END)
            for item_time, item_message in self.error_log:
                one_line = " ".join(item_message.split())
                self.error_list.insert(tk.END, f"{item_time} | {one_line}")
            self.error_list.yview_moveto(1)
        self.error_count_var.set(f"Errors: {len(self.error_log)}")

    def _clear_errors(self) -> None:
        self.error_log.clear()
        if self.error_list is not None:
            self.error_list.delete(0, tk.END)
        self.error_count_var.set("Errors: 0")


def _format_position(position: PositionSnapshot | None) -> str:
    if not position:
        return "Нет открытой позиции"
    side = "Покупка" if position.side == "Buy" else "Продажа"
    return (
        f"{side} {position.size:g} {position.symbol}\n"
        f"Средняя: {position.avg_price:.2f} | Нереализ. PnL: {position.unrealised_pnl:.4f}"
    )


def _format_rules(rules: InstrumentRules) -> str:
    min_notional = f" | мин. сумма {rules.min_notional_value} USDT" if rules.min_notional_value else ""
    return (
        f"Правила инструмента: мин. кол-во {rules.min_order_qty} | шаг {rules.qty_step} | "
        f"тик {rules.tick_size}{min_notional}"
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
    return "Реальный" if mode == "live" else "Демо"


def _mode_value(label: str) -> str:
    return "live" if label.lower() in {"live", "реальный"} else "demo"


def _margin_mode_value(label: str) -> str:
    return "isolated" if label.lower() in {"isolated", "изолированная"} else "cross"


def _round_decimal_str(value: str, step: str, rounding: str) -> float:
    decimal_value = _to_decimal(value)
    decimal_step = _to_decimal(step)
    if decimal_step <= 0:
        return float(decimal_value)
    rounded = (decimal_value / decimal_step).to_integral_value(rounding=rounding) * decimal_step
    return float(rounded)


def _to_decimal(value: str | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def main() -> None:
    settings = load_settings()
    app = TradingApp(settings)
    app.mainloop()
