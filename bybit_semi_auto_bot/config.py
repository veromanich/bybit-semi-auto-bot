from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    api_key: str
    api_secret: str
    testnet: bool
    category: str
    symbol: str
    interval: str
    default_qty: float
    recv_window: int


def _bool_from_env(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_settings() -> Settings:
    load_dotenv()

    return Settings(
        api_key=os.getenv("BYBIT_API_KEY", "").strip(),
        api_secret=os.getenv("BYBIT_API_SECRET", "").strip(),
        testnet=_bool_from_env(os.getenv("BYBIT_TESTNET"), True),
        category=os.getenv("BYBIT_CATEGORY", "linear").strip(),
        symbol=os.getenv("BOT_SYMBOL", "BTCUSDT").strip().upper(),
        interval=os.getenv("BOT_INTERVAL", "15").strip(),
        default_qty=float(os.getenv("BOT_DEFAULT_QTY", "0.001")),
        recv_window=int(os.getenv("BOT_RECV_WINDOW", "5000")),
    )

