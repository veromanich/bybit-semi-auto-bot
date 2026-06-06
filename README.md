# Bybit Futures Semi-Auto Bot

Desktop Python app for semi-automatic Bybit USDT perpetual futures trading.

The bot does not enter trades by itself. It shows market data, account state, and a simple EMA signal; every order must be confirmed by the user in the desktop interface.

## Safety Defaults

- Testnet is enabled by default.
- API keys are loaded from `.env`.
- Orders use explicit quantity, stop loss, and take profit fields.
- The strategy is advisory only.

Trading futures is risky. Test thoroughly on Bybit testnet or demo before using real funds.

## Setup

1. Install Python 3.11 or newer.
2. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and fill in your Bybit API keys.

```powershell
Copy-Item .env.example .env
```

5. Start the app:

```powershell
python -m bybit_semi_auto_bot
```

## API Key Permissions

For testnet or demo use, create a Bybit API key with trading permissions. Do not enable withdrawal permissions.

## First Version

This first version supports:

- USDT perpetual futures through Bybit V5 unified trading API.
- Market data refresh.
- Wallet balance display.
- Current position display.
- EMA signal preview.
- Manual long/short market orders.
- Optional stop loss and take profit attached to orders.
- Manual market close for the current position.

