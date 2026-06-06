from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_secret: str
    trading_mode: str
    category: str
    symbol: str
    interval: str
    default_qty: float
    recv_window: int

    @property
    def is_demo(self) -> bool:
        return self.trading_mode == "demo"

    @property
    def is_live(self) -> bool:
        return self.trading_mode == "live"


def _bool_from_env(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_settings() -> Settings:
    load_dotenv()
    legacy_testnet = _bool_from_env(os.getenv("BYBIT_TESTNET"), True)
    default_mode = "demo" if legacy_testnet else "live"
    trading_mode = os.getenv("BYBIT_TRADING_MODE", default_mode).strip().lower()
    if trading_mode not in {"demo", "live"}:
        trading_mode = "demo"

    return Settings(
        api_key=os.getenv("BYBIT_API_KEY", "").strip(),
        api_secret=os.getenv("BYBIT_API_SECRET", "").strip(),
        trading_mode=trading_mode,
        category=os.getenv("BYBIT_CATEGORY", "linear").strip(),
        symbol=os.getenv("BOT_SYMBOL", "BTCUSDT").strip().upper(),
        interval=os.getenv("BOT_INTERVAL", "15").strip(),
        default_qty=float(os.getenv("BOT_DEFAULT_QTY", "0.001")),
        recv_window=int(os.getenv("BOT_RECV_WINDOW", "5000")),
    )
