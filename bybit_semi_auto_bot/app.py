from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_UP, ROUND_UP
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Callable, Literal, TypeVar

try:
    import customtkinter as ctk
except ModuleNotFoundError as exc:  # pragma: no cover - shown only before dependencies are installed.
    raise SystemExit("Установите зависимости: pip install -r requirements.txt") from exc

from .config import Settings, load_settings
from .exchange import BybitClient, InstrumentRules, MarketSnapshot, OpenOrder, OrderRequest, PositionSnapshot
from .risk import PositionSize, RiskPrices, calculate_position_size, calculate_risk_prices, format_price
from .strategy import Signal, ema_signal


T = TypeVar("T")
OrderSide = Literal["Buy", "Sell"]

ORDER_KINDS = ("Рынок", "Лимит", "Стоп", "Стоп-лимит")
ORDER_KIND_API = {
    "Рынок": ("Market", False),
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


class TradingApp(ctk.CTk):
    def __init__(self, settings: Settings) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        super().__init__()

        self.title("Bybit полуавтоматический бот")
        self.geometry("1180x820+20+20")
        self.minsize(1040, 740)

        self.settings = settings
        self.client = BybitClient(settings)
        self.market: MarketSnapshot | None = None
        self.position: PositionSnapshot | None = None
        self.signal: Signal | None = None
        self.wallet_balance: float | None = None
        self.instrument_rules: InstrumentRules | None = None
        self.open_orders: list[OpenOrder] = []

        self.symbol_var = tk.StringVar(value=settings.symbol)
        self.mode_var = tk.StringVar(value=_mode_label(settings.trading_mode))
        self.side_var = tk.StringVar(value="Buy")

        self.order_kind_var = tk.StringVar(value="Рынок")
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
        self.error_log: list[tuple[str, str]] = []

        self.order_fields_frame: ctk.CTkFrame | None = None
        self.orders_frame: ctk.CTkScrollableFrame | None = None
        self.errors_box: ctk.CTkTextbox | None = None
        self.buy_side_button: ctk.CTkButton | None = None
        self.sell_side_button: ctk.CTkButton | None = None
        self.calculate_risk_button: ctk.CTkButton | None = None
        self.demo_test_button: ctk.CTkButton | None = None
        self.reward_risk_widgets: tuple[ctk.CTkLabel, ctk.CTkBaseClass] | None = None
        self.take_profit_percent_widgets: tuple[ctk.CTkLabel, ctk.CTkBaseClass] | None = None

        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self, fg_color="#0f1014")
        top.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        top.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(top, text="Символ").grid(row=0, column=0, padx=(12, 8), pady=10)
        symbol_entry = ctk.CTkEntry(top, textvariable=self.symbol_var, width=130)
        symbol_entry.grid(row=0, column=1, pady=10)
        symbol_entry.bind("<Return>", lambda _event: self.refresh_all())
        symbol_entry.bind("<FocusOut>", lambda _event: self._clear_symbol_state_if_needed())

        ctk.CTkLabel(top, text="Режим").grid(row=0, column=3, padx=(8, 8), pady=10)
        ctk.CTkOptionMenu(top, variable=self.mode_var, values=["Демо", "Реальный"], command=lambda _v: self.change_trading_mode()).grid(
            row=0, column=4, padx=(0, 12), pady=10
        )
        ctk.CTkButton(top, text="Обновить", width=110, command=self.refresh_all).grid(row=0, column=5, padx=(0, 12), pady=10)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        body.grid_columnconfigure(0, weight=0, minsize=300)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        left = ctk.CTkFrame(body, fg_color="#111217", corner_radius=10, width=300)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.grid_propagate(False)
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(7, weight=1)

        ctk.CTkLabel(left, text="Рынок", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))
        ctk.CTkLabel(left, textvariable=self.market_var, font=ctk.CTkFont(size=16)).grid(row=1, column=0, sticky="w", padx=16)
        ctk.CTkLabel(left, textvariable=self.balance_var, text_color="#a5a8b0").grid(row=2, column=0, sticky="w", padx=16, pady=(8, 0))
        ctk.CTkLabel(left, textvariable=self.rules_var, text_color="#a5a8b0", wraplength=260, justify="left").grid(
            row=3, column=0, sticky="w", padx=16, pady=(8, 0)
        )
        ctk.CTkLabel(left, text="EMA сигнал", font=ctk.CTkFont(size=14, weight="bold")).grid(row=4, column=0, sticky="w", padx=16, pady=(18, 4))
        ctk.CTkLabel(left, textvariable=self.signal_var, justify="left", wraplength=260).grid(row=5, column=0, sticky="w", padx=16)
        ctk.CTkLabel(left, text="Позиция", font=ctk.CTkFont(size=14, weight="bold")).grid(row=6, column=0, sticky="w", padx=16, pady=(18, 4))
        ctk.CTkLabel(left, textvariable=self.position_var, justify="left", wraplength=260).grid(row=7, column=0, sticky="nw", padx=16)

        ctk.CTkLabel(left, text="Открытые заявки", font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=8, column=0, sticky="w", padx=16, pady=(18, 6)
        )
        self.orders_frame = ctk.CTkScrollableFrame(left, fg_color="#171920", height=160)
        self.orders_frame.grid(row=9, column=0, sticky="ew", padx=16, pady=(0, 16))
        self.orders_frame.grid_columnconfigure(0, weight=1)

        right = ctk.CTkFrame(body, fg_color="#14161c", corner_radius=10)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(2, weight=1)

        self._build_ticket(right)

        bottom = ctk.CTkFrame(self, fg_color="#0f1014")
        bottom.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        bottom.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(bottom, textvariable=self.status_var, anchor="w").grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        ctk.CTkLabel(bottom, textvariable=self.error_count_var, text_color="#a5a8b0").grid(row=0, column=1, padx=12, pady=8)

    def _build_ticket(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkLabel(parent, text="Заявка", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, sticky="w", padx=16, pady=(14, 8)
        )

        side_bar = ctk.CTkFrame(parent, fg_color="transparent")
        side_bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 12))
        side_bar.grid_columnconfigure(0, weight=1)
        side_bar.grid_columnconfigure(1, weight=1)
        self.sell_side_button = ctk.CTkButton(side_bar, text="Продать", fg_color="#303136", hover_color="#3b3c42", command=lambda: self._set_side("Sell"))
        self.sell_side_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.buy_side_button = ctk.CTkButton(side_bar, text="Купить", command=lambda: self._set_side("Buy"))
        self.buy_side_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        ticket = ctk.CTkScrollableFrame(parent, fg_color="#14161c")
        ticket.grid(row=2, column=0, sticky="nsew", padx=10)
        ticket.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        self._build_order_section(ticket, 0)
        self._build_risk_section(ticket, 1)
        self._build_exit_section(ticket, 2)
        self._build_settings_section(ticket, 3)

        summary = ctk.CTkFrame(parent, fg_color="#171920")
        summary.grid(row=3, column=0, sticky="ew", padx=16, pady=(8, 0))
        summary.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(summary, textvariable=self.order_value_var, anchor="w").grid(row=0, column=0, sticky="ew", padx=12, pady=(8, 2))
        ctk.CTkLabel(summary, textvariable=self.order_risk_var, anchor="w").grid(row=1, column=0, sticky="ew", padx=12, pady=(2, 8))

        self.submit_button = ctk.CTkButton(parent, text="Купить", height=46, command=self.confirm_selected_order)
        self.submit_button.grid(row=4, column=0, sticky="ew", padx=16, pady=(12, 8))
        self._set_side("Buy")
        ctk.CTkButton(parent, text="Закрыть позицию", fg_color="#303136", hover_color="#3b3c42", command=self.confirm_close_position).grid(
            row=5, column=0, sticky="ew", padx=16, pady=(0, 16)
        )

    def _section(self, parent: ctk.CTkFrame, title: str, row: int) -> ctk.CTkFrame:
        section = ctk.CTkFrame(parent, fg_color="#171920", corner_radius=8)
        section.grid(row=row, column=0, sticky="ew", padx=6, pady=6)
        section.grid_columnconfigure(0, weight=0, minsize=92)
        section.grid_columnconfigure(1, weight=1)
        section.grid_columnconfigure(2, weight=0, minsize=92)
        section.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(section, text=title, font=ctk.CTkFont(size=14, weight="bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=10, pady=(10, 4)
        )
        return section

    def _build_order_section(self, parent: ctk.CTkFrame, row: int) -> None:
        frame = self._section(parent, "Параметры заявки", row)
        self._field(
            frame,
            "Тип заявки",
            ctk.CTkOptionMenu(frame, variable=self.order_kind_var, values=list(ORDER_KINDS), command=self._set_order_kind),
            1,
        )
        self._field(frame, "Количество", ctk.CTkEntry(frame, textvariable=self.qty_var), 1, pair=1)
        self.order_fields_frame = ctk.CTkFrame(frame, fg_color="transparent", height=1)
        self.order_fields_frame.grid(row=2, column=0, columnspan=4, sticky="ew", padx=0, pady=0)
        self.order_fields_frame.grid_propagate(True)
        self.order_fields_frame.grid_columnconfigure(0, weight=0, minsize=92)
        self.order_fields_frame.grid_columnconfigure(1, weight=1)
        self.order_fields_frame.grid_columnconfigure(2, weight=0, minsize=92)
        self.order_fields_frame.grid_columnconfigure(3, weight=1)
        self._rebuild_order_fields()

    def _build_risk_section(self, parent: ctk.CTkFrame, row: int) -> None:
        frame = self._section(parent, "Риск и расчет", row)
        ctk.CTkCheckBox(frame, text="Авто количество", variable=self.auto_qty_var).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 6)
        )
        ctk.CTkCheckBox(frame, text="Авто SL/TP", variable=self.auto_risk_var).grid(
            row=1, column=2, columnspan=2, sticky="w", padx=10, pady=(10, 6)
        )
        self._field(frame, "Риск, % баланса", ctk.CTkEntry(frame, textvariable=self.risk_percent_var), 2)
        self._field(frame, "Стоп, %", ctk.CTkEntry(frame, textvariable=self.stop_percent_var), 2, pair=1)
        self._field(
            frame,
            "Цель",
            ctk.CTkOptionMenu(frame, variable=self.risk_mode_var, values=["Риск/прибыль", "Процент профита"], command=lambda _value: self._sync_risk_target_fields()),
            3,
        )
        self.reward_risk_widgets = self._field(frame, "RR", ctk.CTkEntry(frame, textvariable=self.reward_risk_var), 3, pair=1)
        self.take_profit_percent_widgets = self._field(frame, "Профит, %", ctk.CTkEntry(frame, textvariable=self.take_profit_percent_var), 3, pair=1)
        self.calculate_risk_button = ctk.CTkButton(frame, text="Рассчитать SL/TP для покупки", command=self.calculate_selected_order)
        self.calculate_risk_button.grid(
            row=4, column=0, columnspan=4, sticky="ew", padx=10, pady=(14, 10)
        )
        self._sync_risk_target_fields()

    def _build_exit_section(self, parent: ctk.CTkFrame, row: int) -> None:
        frame = self._section(parent, "Уровни выхода", row)
        self._field(frame, "Стоп-лосс", ctk.CTkEntry(frame, textvariable=self.stop_loss_var), 1)
        self._field(frame, "Тейк-профит", ctk.CTkEntry(frame, textvariable=self.take_profit_var), 1, pair=1)
        ctk.CTkButton(frame, text="Очистить SL/TP", fg_color="#303136", hover_color="#3b3c42", command=self._clear_protection).grid(
            row=2, column=0, columnspan=4, sticky="ew", padx=10, pady=(12, 10)
        )

    def _build_settings_section(self, parent: ctk.CTkFrame, row: int) -> None:
        frame = self._section(parent, "Дополнительные настройки", row)
        self._field(frame, "Плечо", ctk.CTkEntry(frame, textvariable=self.leverage_var), 1)
        self._field(frame, "Маржа", ctk.CTkOptionMenu(frame, variable=self.margin_mode_var, values=["Кросс", "Изолированная"]), 1, pair=1)
        ctk.CTkCheckBox(frame, text="Применять перед заявкой", variable=self.apply_settings_before_order_var).grid(
            row=2, column=0, columnspan=4, sticky="w", padx=10, pady=(12, 4)
        )
        ctk.CTkButton(frame, text="Применить маржу/плечо", command=self.confirm_apply_trade_settings).grid(
            row=3, column=0, columnspan=4, sticky="ew", padx=10, pady=(12, 10)
        )
        self.demo_test_button = ctk.CTkButton(
            frame,
            text="Тест demo API",
            fg_color="#303136",
            hover_color="#3b3c42",
            command=self.confirm_demo_api_test,
        )
        self.demo_test_button.grid(row=4, column=0, columnspan=4, sticky="ew", padx=10, pady=(0, 10))
        self._sync_mode_controls()

    def _build_errors_tab(self, frame: ctk.CTkFrame) -> None:
        self.errors_box = ctk.CTkTextbox(frame, height=260, wrap="word")
        self.errors_box.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        frame.grid_rowconfigure(0, weight=1)
        ctk.CTkButton(frame, text="Очистить ошибки", fg_color="#303136", hover_color="#3b3c42", command=self._clear_errors).grid(
            row=1, column=0, sticky="ew", padx=8, pady=(0, 8)
        )

    def _field(self, frame: ctk.CTkFrame, label: str, widget: ctk.CTkBaseClass, row: int, pair: int = 0) -> tuple[ctk.CTkLabel, ctk.CTkBaseClass]:
        frame.grid_columnconfigure(0, weight=0, minsize=92)
        frame.grid_columnconfigure(1, weight=1)
        frame.grid_columnconfigure(2, weight=0, minsize=92)
        frame.grid_columnconfigure(3, weight=1)
        label_column = 0 if pair == 0 else 2
        field_column = label_column + 1
        label_widget = ctk.CTkLabel(frame, text=label, text_color="#a5a8b0", anchor="w")
        label_widget.grid(
            row=row, column=label_column, sticky="w", padx=(8, 6), pady=5
        )
        widget.grid(row=row, column=field_column, sticky="ew", padx=(0, 8), pady=5)
        return label_widget, widget

    def _rebuild_order_fields(self) -> None:
        if self.order_fields_frame is None:
            return
        for child in self.order_fields_frame.winfo_children():
            child.destroy()
        self.order_fields_frame.configure(height=1)

        order_type, is_conditional = ORDER_KIND_API[self.order_kind_var.get()]
        row = 0
        if order_type == "Limit":
            self._field(self.order_fields_frame, "Цена", ctk.CTkEntry(self.order_fields_frame, textvariable=self.limit_price_var), row)
            self._field(
                self.order_fields_frame,
                "Время действия",
                ctk.CTkOptionMenu(self.order_fields_frame, variable=self.time_in_force_var, values=list(TIME_IN_FORCE)),
                row,
                pair=1,
            )
            row += 1
            ctk.CTkButton(self.order_fields_frame, text="Взять рыночную цену", fg_color="#303136", hover_color="#3b3c42", command=self._fill_limit_from_market).grid(
                row=row, column=0, columnspan=4, sticky="ew", padx=10, pady=(4, 10)
            )
            row += 1
        else:
            self.time_in_force_var.set("IOC")

        if is_conditional:
            self.order_fields_frame.configure(height=1)
            self._field(self.order_fields_frame, "Стоп-цена", ctk.CTkEntry(self.order_fields_frame, textvariable=self.trigger_price_var), row)
            self._field(
                self.order_fields_frame,
                "Условие",
                ctk.CTkOptionMenu(self.order_fields_frame, variable=self.trigger_direction_var, values=list(TRIGGER_DIRECTIONS)),
                row,
                pair=1,
            )
            row += 1
            self._field(
                self.order_fields_frame,
                "Источник цены",
                ctk.CTkOptionMenu(self.order_fields_frame, variable=self.trigger_by_var, values=list(TRIGGER_BY)),
                row,
            )

    def _set_order_kind(self, value: str) -> None:
        self.order_kind_var.set(value)
        self._rebuild_order_fields()

    def _sync_risk_target_fields(self) -> None:
        show_reward_risk = self.risk_mode_var.get() == "Риск/прибыль"
        for widgets, visible in (
            (self.reward_risk_widgets, show_reward_risk),
            (self.take_profit_percent_widgets, not show_reward_risk),
        ):
            if widgets is None:
                continue
            for widget in widgets:
                if visible:
                    widget.grid()
                else:
                    widget.grid_remove()

    def _sync_mode_controls(self) -> None:
        if self.demo_test_button is None:
            return
        if self.settings.is_demo:
            self.demo_test_button.grid()
        else:
            self.demo_test_button.grid_remove()

    def refresh_all(self) -> None:
        symbol = self.symbol_var.get().strip().upper()
        self.symbol_var.set(symbol)

        def work() -> tuple[MarketSnapshot, InstrumentRules, Signal | None, PositionSnapshot | None, float | None, list[OpenOrder]]:
            market = self.client.get_market_snapshot(symbol)
            rules = self.client.get_instrument_rules(symbol)
            candles = self.client.get_klines(symbol, self.settings.interval)
            signal = ema_signal(candles)
            position = self.client.get_position(symbol)
            balance = self.client.get_wallet_balance()
            orders = self.client.get_open_orders(symbol)
            return market, rules, signal, position, balance, orders

        self._run_background("Обновляю данные...", work, self._apply_refresh_result)

    def _apply_refresh_result(
        self,
        result: tuple[MarketSnapshot, InstrumentRules, Signal | None, PositionSnapshot | None, float | None, list[OpenOrder]],
    ) -> None:
        market, rules, signal, position, balance, orders = result
        self.market = market
        self.instrument_rules = rules
        self.signal = signal
        self.position = position
        self.wallet_balance = balance
        self.open_orders = orders

        mark = f", mark {market.mark_price:.2f}" if market.mark_price else ""
        self.market_var.set(f"{market.symbol}: last {market.last_price:.2f}{mark} | {_mode_label(self.settings.trading_mode)}")
        self.signal_var.set(f"{signal.label}\nFast EMA: {signal.fast_ema:.2f} | Slow EMA: {signal.slow_ema:.2f}" if signal else "Нет сигнала")
        self.position_var.set(_format_position(position))
        self.balance_var.set(f"USDT баланс: {balance:.2f}" if balance is not None else "USDT баланс: нужны API ключи")
        self.rules_var.set(_format_rules(rules))
        self._render_open_orders()
        self.status_var.set("Готово")

    def _render_open_orders(self) -> None:
        if self.orders_frame is None:
            return
        for child in self.orders_frame.winfo_children():
            child.destroy()

        if not self.open_orders:
            ctk.CTkLabel(self.orders_frame, text="Открытых заявок нет", text_color="#a5a8b0").grid(row=0, column=0, sticky="w", padx=8, pady=8)
            return

        for row, order in enumerate(self.open_orders):
            item = ctk.CTkFrame(self.orders_frame, fg_color="#20232b")
            item.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
            item.grid_columnconfigure(0, weight=1)
            trigger = f" | стоп {order.trigger_price}" if order.trigger_price else ""
            text = f"{order.side} {order.qty} {order.symbol} {order.order_type} @ {order.price or '-'}{trigger} | {order.status}"
            ctk.CTkLabel(item, text=text, anchor="w", justify="left").grid(row=0, column=0, sticky="ew", padx=8, pady=8)
            ctk.CTkButton(item, text="Отменить", width=90, fg_color="#303136", hover_color="#3b3c42", command=lambda selected=order: self.confirm_cancel_order(selected)).grid(
                row=0, column=1, padx=8, pady=8
            )

    def confirm_cancel_order(self, order: OpenOrder) -> None:
        confirmed = messagebox.askyesno("Отменить заявку", f"Отменить заявку?\n\n{order.symbol}\nID: {order.order_id}")
        if not confirmed:
            return

        def work() -> dict:
            return self.client.cancel_order(order.symbol, order.order_id)

        self._run_background("Отменяю заявку...", work, lambda _result: self._cancel_done(order))

    def _cancel_done(self, order: OpenOrder) -> None:
        self.status_var.set(f"Заявка отменена: {order.order_id}")
        self.refresh_all()

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
        self._sync_mode_controls()
        self.status_var.set(f"Режим: {_mode_label(new_mode)}")
        self.refresh_all()

    def calculate_selected_order(self) -> RiskPrices | None:
        return self.calculate_and_fill_order(self._selected_side())

    def calculate_and_fill_risk(self, side: OrderSide) -> RiskPrices | None:
        try:
            prices = self._calculate_risk(side)
        except ValueError as exc:
            messagebox.showerror("Настройки риска", str(exc))
            return None

        self.stop_loss_var.set(format_price(prices.stop_loss))
        self.take_profit_var.set(format_price(prices.take_profit))
        direction = "покупки" if side == "Buy" else "продажи"
        self.status_var.set(f"Риск для {direction}: SL {prices.stop_percent:g}%, TP {prices.take_profit_percent:g}%")
        return prices

    def calculate_and_fill_order(self, side: OrderSide) -> RiskPrices | None:
        prices = self.calculate_and_fill_risk(side)
        if prices is None:
            return None

        if self.auto_qty_var.get():
            try:
                size = self._calculate_position_size(prices)
            except ValueError as exc:
                messagebox.showerror("Размер позиции", str(exc))
                return None

            quantity = size.quantity
            if self.instrument_rules:
                quantity = _round_decimal_str(str(quantity), self.instrument_rules.qty_step, ROUND_FLOOR)
            self.qty_var.set(format_price(quantity))
            self.order_risk_var.set(f"Риск: {size.risk_amount:.2f} USDT")
            self.order_value_var.set(f"Сумма сделки: {size.position_value:.2f} USDT")
            self.status_var.set(f"Риск {size.risk_amount:.2f} USDT | Кол-во {format_price(quantity)} | Маржа ~{size.estimated_margin:.2f} USDT")

        return prices

    def confirm_selected_order(self) -> None:
        self.confirm_order(self._selected_side())

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
        entry_line = f"\nРасчетный вход: {risk_prices.entry_price:.2f}" if risk_prices else ""
        confirmed = messagebox.askyesno(
            "Подтвердите заявку",
            f"Открыть {direction}: {self.order_kind_var.get()} ({_mode_label(self.settings.trading_mode)})?\n\n"
            f"Символ: {symbol}\nКоличество: {request.qty}{entry_line}\n"
            f"Цена: {request.price or '-'}\nСтоп-цена: {request.trigger_price or '-'}\n"
            f"Стоп-лосс: {request.stop_loss or '-'}\nТейк-профит: {request.take_profit or '-'}",
        )
        if not confirmed:
            return

        apply_settings = self.apply_settings_before_order_var.get()
        margin_mode = _margin_mode_value(self.margin_mode_var.get())
        leverage = None
        if apply_settings:
            leverage = _parse_float(self.leverage_var.get(), "Плечо")
            if leverage is None:
                return

        def work() -> dict:
            if apply_settings and leverage is not None:
                self._apply_trade_settings_api(symbol, margin_mode, leverage)
            return self.client.place_order(request)

        self._run_background("Отправляю заявку...", work, lambda result: self._order_done(result, "Заявка отправлена"))

    def confirm_demo_api_test(self) -> None:
        if not self.settings.is_demo:
            messagebox.showinfo("Только demo", "Тест API доступен только в demo-режиме.")
            return
        if not self.settings.api_key or not self.settings.api_secret:
            messagebox.showerror("Нет demo API ключей", "Добавьте BYBIT_API_KEY и BYBIT_API_SECRET в .env.")
            return
        symbol = self.symbol_var.get().strip().upper()
        confirmed = messagebox.askyesno(
            "Тест demo API",
            "Проверить Market, Limit, Stop и Stop-limit на demo API?\n\n"
            f"Символ: {symbol}\n"
            "Market-заявка будет сразу закрыта, остальные заявки будут сразу отменены.",
        )
        if not confirmed:
            return

        self._run_background("Проверяю demo API...", lambda: self._run_demo_api_test(symbol), self._demo_api_test_done)

    def _run_demo_api_test(self, symbol: str) -> list[str]:
        market = self.client.get_market_snapshot(symbol)
        rules = self.client.get_instrument_rules(symbol)
        last = Decimal(str(market.last_price))
        tick = _to_decimal(rules.tick_size)
        qty_step = _to_decimal(rules.qty_step)
        qty = _demo_test_quantity(last, rules)
        limit_buy_price = _round_decimal_str(str(last * Decimal("0.80")), rules.tick_size, ROUND_DOWN)
        trigger_buy_price = _round_decimal_str(str(last * Decimal("1.20")), rules.tick_size, ROUND_UP)
        stop_limit_price = _round_decimal_str(str(last * Decimal("1.19")), rules.tick_size, ROUND_UP)
        if tick <= 0 or qty_step <= 0:
            raise ValueError(f"{symbol}: неверные правила инструмента для demo-теста.")

        messages = [
            f"{symbol}: last {_format_decimal(last)}, qty {_format_decimal(qty)}",
            f"Правила: мин. {rules.min_order_qty}, шаг {rules.qty_step}, тик {rules.tick_size}",
        ]
        cancel_ids: list[tuple[str, str]] = []

        def remember(label: str, response: dict) -> str:
            order_id = str(response.get("result", {}).get("orderId", ""))
            messages.append(f"OK {label}: {order_id or '-'}")
            return order_id

        try:
            remember(
                "Market Buy",
                self.client.place_order(
                    OrderRequest(symbol=symbol, side="Buy", order_type="Market", qty=float(qty), time_in_force="IOC")
                ),
            )
            position = self.client.get_position(symbol)
            if position:
                remember("Close market position", self.client.close_position_market(position))
            else:
                messages.append("Market Buy не оставил открытой позиции.")

            cancel_ids.append(
                (
                    "Limit Buy",
                    remember(
                        "Limit Buy",
                        self.client.place_order(
                            OrderRequest(
                                symbol=symbol,
                                side="Buy",
                                order_type="Limit",
                                qty=float(qty),
                                price=float(limit_buy_price),
                                time_in_force="GTC",
                            )
                        ),
                    ),
                )
            )
            cancel_ids.append(
                (
                    "Stop Market Buy",
                    remember(
                        "Stop Market Buy",
                        self.client.place_order(
                            OrderRequest(
                                symbol=symbol,
                                side="Buy",
                                order_type="Market",
                                qty=float(qty),
                                trigger_price=float(trigger_buy_price),
                                trigger_direction=1,
                                trigger_by="LastPrice",
                                time_in_force="IOC",
                            )
                        ),
                    ),
                )
            )
            cancel_ids.append(
                (
                    "Stop Limit Buy",
                    remember(
                        "Stop Limit Buy",
                        self.client.place_order(
                            OrderRequest(
                                symbol=symbol,
                                side="Buy",
                                order_type="Limit",
                                qty=float(qty),
                                price=float(stop_limit_price),
                                trigger_price=float(trigger_buy_price),
                                trigger_direction=1,
                                trigger_by="LastPrice",
                                time_in_force="GTC",
                            )
                        ),
                    ),
                )
            )
        finally:
            for label, order_id in cancel_ids:
                if not order_id:
                    continue
                try:
                    remember(f"Cancel {label}", self.client.cancel_order(symbol, order_id))
                except Exception as exc:
                    messages.append(f"WARN Cancel {label}: {exc}")
            position = self.client.get_position(symbol)
            if position:
                try:
                    remember("Cleanup close position", self.client.close_position_market(position))
                except Exception as exc:
                    messages.append(f"WARN Cleanup close position: {exc}")

        open_orders = self.client.get_open_orders(symbol)
        position = self.client.get_position(symbol)
        messages.append(f"Осталось открытых заявок: {len(open_orders)}")
        messages.append(f"Осталась позиция: {position.size if position else 0}")
        return messages

    def _demo_api_test_done(self, messages: list[str]) -> None:
        self.status_var.set("Demo API тест завершен")
        for message in messages:
            self._log_error(f"Demo test: {message}")
        messagebox.showinfo("Demo API тест", "\n".join(messages[-8:]))
        self.refresh_all()

    def confirm_apply_trade_settings(self) -> None:
        symbol = self.symbol_var.get().strip().upper()
        leverage = _parse_float(self.leverage_var.get(), "Плечо")
        if leverage is None:
            return

        margin_mode = _margin_mode_value(self.margin_mode_var.get())
        confirmed = messagebox.askyesno(
            "Применить настройки",
            f"Применить маржу/плечо ({_mode_label(self.settings.trading_mode)})?\n\n"
            f"Символ: {symbol}\nМаржа: {self.margin_mode_var.get()}\nПлечо: {leverage}x",
        )
        if not confirmed:
            return

        def work() -> dict:
            return self._apply_trade_settings_api(symbol, margin_mode, leverage)

        self._run_background("Применяю маржу/плечо...", work, lambda result: self._settings_done(symbol, margin_mode, leverage, result))

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
        qty = _parse_float(self.qty_var.get(), "Количество")
        stop_loss = _parse_optional_float(self.stop_loss_var.get(), "Стоп-лосс")
        take_profit = _parse_optional_float(self.take_profit_var.get(), "Тейк-профит")
        if qty is None or stop_loss is False or take_profit is False:
            return None
        qty = self._normalize_quantity(qty)
        if qty is None:
            return None

        order_type, is_conditional = ORDER_KIND_API[self.order_kind_var.get()]
        price = None
        trigger_price = None
        trigger_direction = None
        trigger_by = None

        if order_type == "Limit":
            price = _parse_float(self.limit_price_var.get(), "Цена")
            if price is None:
                return None
            price = self._normalize_price(price, "Цена")
            if price is None:
                return None
            self.limit_price_var.set(format_price(price))

        if is_conditional:
            trigger_price = _parse_float(self.trigger_price_var.get(), "Стоп-цена")
            if trigger_price is None:
                return None
            trigger_price = self._normalize_price(trigger_price, "Стоп-цена")
            if trigger_price is None:
                return None
            self.trigger_price_var.set(format_price(trigger_price))
            try:
                trigger_direction = self._resolve_trigger_direction(trigger_price)
            except ValueError as exc:
                messagebox.showerror("Условие стоп-заявки", str(exc))
                return None
            trigger_by = TRIGGER_BY_API[self.trigger_by_var.get()]

        time_in_force = TIME_IN_FORCE_API[self.time_in_force_var.get()]
        if order_type == "Market":
            time_in_force = "IOC"

        reference_price = price or (self.market.last_price if self.market else None)
        if reference_price is not None and not self._validate_min_notional(qty, reference_price):
            return None

        normalized_stop_loss = self._normalize_optional_price(stop_loss, "Стоп-лосс")
        normalized_take_profit = self._normalize_optional_price(take_profit, "Тейк-профит")

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
            raise ValueError(f"Обновите данные рынка для {symbol} перед расчетом SL/TP.")

        stop_percent = _require_float(self.stop_percent_var.get(), "Стоп, %")
        if self.risk_mode_var.get() == "Риск/прибыль":
            reward_risk = _require_float(self.reward_risk_var.get(), "RR")
            return calculate_risk_prices(side, self.market.last_price, stop_percent, reward_risk=reward_risk)

        take_profit_percent = _require_float(self.take_profit_percent_var.get(), "Профит, %")
        return calculate_risk_prices(side, self.market.last_price, stop_percent, take_profit_percent=take_profit_percent)

    def _calculate_position_size(self, prices: RiskPrices) -> PositionSize:
        if self.wallet_balance is None:
            raise ValueError("Баланс не загружен. Добавьте API ключи и обновите данные.")

        return calculate_position_size(
            entry_price=prices.entry_price,
            stop_loss=prices.stop_loss,
            balance=self.wallet_balance,
            risk_percent=_require_float(self.risk_percent_var.get(), "Риск, % баланса"),
            leverage=_require_float(self.leverage_var.get(), "Плечо"),
        )

    def _resolve_trigger_direction(self, trigger_price: float) -> int:
        direction = self.trigger_direction_var.get()
        if direction == "Цена растет":
            return 1
        if direction == "Цена падает":
            return 2
        if not self.market:
            raise ValueError("Для автоматического условия нужны рыночные данные.")
        return 1 if trigger_price > self.market.last_price else 2

    def _settings_done(self, symbol: str, margin_mode: str, leverage: float, result: dict) -> None:
        label = "Изолированная" if margin_mode == "isolated" else "Кросс"
        warnings = [
            f"Margin warning: {result['margin_warning']}" if result.get("margin_warning") else "",
            f"Leverage warning: {result['leverage_warning']}" if result.get("leverage_warning") else "",
        ]
        warnings = [warning for warning in warnings if warning]
        self.status_var.set(f"{symbol}: маржа {label}, плечо {leverage:g}x применено")
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

    def _set_side(self, side: OrderSide) -> None:
        self.side_var.set(side)
        is_buy = side == "Buy"
        self.submit_button.configure(text="Купить" if is_buy else "Продать")
        self.submit_button.configure(fg_color="#2458ff" if is_buy else "#303136", hover_color="#3768ff" if is_buy else "#3b3c42")
        if self.buy_side_button is not None and self.sell_side_button is not None:
            self.buy_side_button.configure(fg_color="#2458ff" if is_buy else "#303136", hover_color="#3768ff" if is_buy else "#3b3c42")
            self.sell_side_button.configure(fg_color="#303136" if is_buy else "#d24b4b", hover_color="#3b3c42" if is_buy else "#e05d5d")
        if self.calculate_risk_button is not None:
            side_text = "покупки" if is_buy else "продажи"
            self.calculate_risk_button.configure(text=f"Рассчитать SL/TP для {side_text}")

    def _selected_side(self) -> OrderSide:
        return "Buy" if self.side_var.get() == "Buy" else "Sell"

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
        self.open_orders = []
        self.market_var.set("-")
        self.position_var.set("Нет открытой позиции")
        self.signal_var.set("Сигнал не загружен")
        self.balance_var.set("-")
        self.rules_var.set("Правила инструмента: не загружены")
        self._render_open_orders()

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
            message = f"Минимальное количество для {self.instrument_rules.symbol}: {min_text}"
            messagebox.showerror("Количество слишком маленькое", message)
            self._log_error(message)
            return None
        if rounded != qty:
            self.qty_var.set(format_price(rounded))
            self.status_var.set(f"Количество округлено к шагу {self.instrument_rules.qty_step}: {format_price(rounded)}")
        return rounded

    def _normalize_price(self, value: float, label: str) -> float | None:
        if not self.instrument_rules:
            return value
        rounded = _round_decimal_str(str(value), self.instrument_rules.tick_size, ROUND_HALF_UP)
        if rounded <= 0:
            messagebox.showerror("Неверная цена", f"{label} должна быть больше нуля.")
            return None
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
            f"{self.instrument_rules.symbol}: сумма заявки ниже минимума. "
            f"Сейчас {_format_decimal(notional)} USDT, минимум {_format_decimal(min_notional)} USDT."
        )
        messagebox.showerror("Сумма слишком маленькая", message)
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
        self.status_var.set("Ошибка")
        self._log_error(message)
        messagebox.showerror("Ошибка Bybit бота", message)

    def _log_error(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.error_log.append((timestamp, message))
        self.error_log = self.error_log[-100:]
        if self.errors_box is not None:
            self.errors_box.configure(state="normal")
            self.errors_box.delete("1.0", "end")
            self.errors_box.insert("end", "\n".join(f"{time} | {' '.join(text.split())}" for time, text in self.error_log))
            self.errors_box.configure(state="disabled")
        self.error_count_var.set(f"Ошибки: {len(self.error_log)}")

    def _clear_errors(self) -> None:
        self.error_log.clear()
        if self.errors_box is not None:
            self.errors_box.configure(state="normal")
            self.errors_box.delete("1.0", "end")
            self.errors_box.configure(state="disabled")
        self.error_count_var.set("Ошибки: 0")


def _format_position(position: PositionSnapshot | None) -> str:
    if not position:
        return "Нет открытой позиции"
    side = "Покупка" if position.side == "Buy" else "Продажа"
    return f"{side} {position.size:g} {position.symbol}\nСредняя: {position.avg_price:.2f} | Нереализ. PnL: {position.unrealised_pnl:.4f}"


def _format_rules(rules: InstrumentRules) -> str:
    min_notional = f" | мин. сумма {rules.min_notional_value} USDT" if rules.min_notional_value else ""
    return f"Мин. кол-во {rules.min_order_qty} | шаг {rules.qty_step} | тик {rules.tick_size}{min_notional}"


def _parse_float(value: str, label: str) -> float | None:
    try:
        parsed = float(value)
    except ValueError:
        messagebox.showerror("Неверное значение", f"{label}: нужно число.")
        return None
    if parsed <= 0:
        messagebox.showerror("Неверное значение", f"{label}: значение должно быть больше нуля.")
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
        raise ValueError(f"{label}: нужно число.") from exc
    if parsed <= 0:
        raise ValueError(f"{label}: значение должно быть больше нуля.")
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


def _demo_test_quantity(last_price: Decimal, rules: InstrumentRules) -> Decimal:
    min_qty = _to_decimal(rules.min_order_qty)
    qty = min_qty
    min_notional = _to_decimal(rules.min_notional_value or "0")
    if min_notional > 0:
        notional_qty = min_notional / last_price * Decimal("1.05")
        rounded_notional_qty = Decimal(str(_round_decimal_str(str(notional_qty), rules.qty_step, ROUND_CEILING)))
        qty = max(qty, rounded_notional_qty)
    return Decimal(str(_round_decimal_str(str(qty), rules.qty_step, ROUND_CEILING)))


def main() -> None:
    settings = load_settings()
    app = TradingApp(settings)
    app.mainloop()
