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

The order panel is split into tabs:

- `Order`: order type, quantity, limit price, time in force, conditional trigger.
- `Risk`: automatic quantity and automatic SL/TP calculation.
- `Protection`: manual stop loss and take profit fields.
- `Margin`: leverage and cross/isolated margin controls.
- `Errors`: latest API/application errors.

Bybit V5 futures support `Market` and `Limit` as the base `orderType`. Conditional orders are created by adding `triggerPrice`, so the app exposes:

- `Market`
- `Limit`
- `Conditional Market`
- `Conditional Limit`

For limit orders, fill `Limit price`. For conditional orders, fill `Trigger price`; `Trigger direction` can be automatic or set manually.

The app hides fields that are not used by the selected order type:

- `Market`: quantity only.
- `Limit`: quantity, limit price, time in force.
- `Conditional Market`: quantity, trigger price, trigger direction, trigger price source.
- `Conditional Limit`: quantity, limit price, time in force, trigger price, trigger direction, trigger price source.

The risk tab can calculate stop loss and take profit automatically before you confirm a trade.

- `Stop %` is the distance from the current market price to stop loss.
- `Risk/reward` mode uses `RR`. Example: stop `1%` and RR `3` means take profit is `3%` away.
- `Profit percent` mode uses the direct `Profit %` value instead of RR.
- Long and short calculations are mirrored automatically.
- `Auto quantity` calculates position size from wallet balance and `Risk % balance`.
- `Leverage` is used to estimate required margin for the calculated position.

Position size formula:

```text
risk_amount = wallet_balance * risk_percent / 100
quantity = risk_amount / abs(entry_price - stop_loss)
estimated_margin = quantity * entry_price / leverage
```

Example for a long at 100 USDT:

- Stop `%`: `1`
- RR: `3`
- Stop loss: `99`
- Take profit: `103`

If wallet balance is 1000 USDT and risk is 1%, the risk amount is 10 USDT. With a 1 USDT stop distance, quantity is 10 contracts/coins before exchange lot-size rounding.

## Margin And Leverage

The `Margin` tab includes:

- `Leverage`
- `Margin`: `Cross` or `Isolated`
- `Apply Margin/Leverage`
- `Apply before order`

Apply these settings before opening a position, or enable `Apply before order` so the app attempts to apply them immediately before sending the order. `Apply before order` is off by default so margin/leverage warnings do not block ordinary order entry unexpectedly. Bybit may reject changing margin mode if the symbol, account mode, open orders, or current position state does not allow it. The app records those responses in the `Errors` tab.

## Error Log

The `Errors` tab stores the latest API/application errors during the session. If an order is rejected by Bybit, copy the newest line from this tab when debugging.

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
- Automatic position size calculation from wallet risk percent.
- Margin mode and leverage controls.
- Manual long/short market orders.
- Optional stop loss and take profit attached to orders.
- Manual market close for the current position.
