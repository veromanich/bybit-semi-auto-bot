# Bybit Futures Semi-Auto Bot

Desktop Python app for semi-automatic Bybit USDT perpetual futures trading.

The bot does not enter trades by itself. It shows market data, account state, and a simple EMA signal; every order must be confirmed by the user in the desktop interface.

## Safety Defaults

- Demo trading is enabled by default.
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

## Trading Mode

The app has a `Trading` selector in the top bar:

- `Demo` uses Bybit demo trading through pybit's `demo=True` mode.
- `Live` sends requests to the real Bybit account.

You can also set the startup mode in `.env`:

```env
BYBIT_TRADING_MODE=demo
```

Use `live` only after testing the full flow.

## Risk Tools

The order panel can calculate stop loss and take profit automatically before you confirm a trade.

- `Stop %` is the distance from the current market price to stop loss.
- `Risk/reward` mode uses `RR`. Example: stop `1%` and RR `3` means take profit is `3%` away.
- `Profit percent` mode uses the direct `Profit %` value instead of RR.
- Long and short calculations are mirrored automatically.

Example for a long at 100 USDT:

- Stop `%`: `1`
- RR: `3`
- Stop loss: `99`
- Take profit: `103`

## API Key Permissions

For demo or live use, create a Bybit API key with trading permissions. Do not enable withdrawal permissions.

## First Version

This first version supports:

- USDT perpetual futures through Bybit V5 unified trading API.
- Market data refresh.
- Wallet balance display.
- Current position display.
- EMA signal preview.
- Demo/live selector.
- Automatic stop loss and take profit calculation by risk/reward or profit percent.
- Manual long/short market orders.
- Optional stop loss and take profit attached to orders.
- Manual market close for the current position.
