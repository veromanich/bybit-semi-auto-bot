from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys

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
    _load_env_file()
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


def save_env_values(values: dict[str, str]) -> Path:
    env_path = get_env_path()
    existing = _read_env_values(env_path)
    existing.update(values)
    env_path.write_text(_format_env_values(existing), encoding="utf-8")
    for key, value in values.items():
        os.environ[key] = value
    return env_path


def get_env_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / ".env"
    return Path.cwd() / ".env"


def _load_env_file() -> None:
    load_dotenv(get_env_path())


def _read_env_values(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _format_env_values(values: dict[str, str]) -> str:
    ordered_keys = (
        "BYBIT_API_KEY",
        "BYBIT_API_SECRET",
        "BYBIT_TRADING_MODE",
        "BYBIT_CATEGORY",
        "BOT_SYMBOL",
        "BOT_INTERVAL",
        "BOT_DEFAULT_QTY",
        "BOT_RECV_WINDOW",
    )
    lines = [f"{key}={values[key]}" for key in ordered_keys if key in values]
    lines.extend(f"{key}={value}" for key, value in values.items() if key not in ordered_keys)
    return "\n".join(lines) + "\n"
