# Safety Checklist

Use this bot on testnet first.

Before live trading:

- Keep `BYBIT_TRADING_MODE=demo` until the full flow is tested.
- Create API keys without withdrawal permission.
- Start with the smallest possible quantity.
- Confirm that symbol, quantity, stop loss, and take profit are correct before pressing an order button.
- Recheck the top-bar trading mode before every order.
- Keep Bybit's web interface open as a backup way to close positions.
- Check local computer time synchronization if authenticated requests fail unexpectedly.

The EMA signal in this project is not financial advice. It is only a basic example indicator for a semi-automatic workflow.
