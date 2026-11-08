# Auto-trader (Angel One)

Places and manages the backtested weekly NIFTY iron condor in your Angel One account,
and publishes positions and P&L to the app's **Auto-trader** tab.

> **Real money, real risk.** The backtest edge is thin (≈ ₹1,300/lot/week before slippage
> surprises, worst losing run ≈ −₹42k per lot) and gaps can blow through any stop. Run
> **paper mode for at least 8–12 weeks** and compare it with the backtest before going live.
> This is software, not investment advice.

## What it does

| When (IST) | Action |
|---|---|
| Entry day (4 sessions before the Tuesday expiry), 15:10–15:24 | Runs the trade gate. Green: iron condor 1σ/1.75σ. Amber: wide 1.25σ/2σ at half size. Red: no trade. |
| Before ordering | Requires real credit (bids − asks) ≥ model credit at IV 0.90 × VIX; sizes so max loss ≤ `RISK_PCT` of `CAPITAL`, capped at `LOTS_MAX`; checks funds |
| Entry | Buys the wings first, then sells the shorts, using limit orders at bid/ask, re-priced up to 4 × 2 ticks. If any leg fails, the filled legs are reversed. |
| Every 20 s in market hours | Marks the position with live Angel quotes |
| Loss ≥ 1.5 × stop, any time | Exits immediately: buys back the shorts, then sells the wings |
| 15:15+ and loss ≥ 1 × credit | Exits (the backtested stop) |
| Expiry | Holds; cash settlement at the close is the target |
| Month's realised loss ≥ `MAX_MONTHLY_LOSS` | Pauses itself |

It only ever touches positions it opened (`managedBy: auto`). Your manual trades are ignored.
The app can **Enable**, **Pause** and **Exit everything now**. If the trader stops sending
heartbeats while a position is open, the Netlify monitor pushes an EXIT alert to your phone.

## 1. A server with a static IP (SEBI requirement)

Since April 2026, API orders must come from a static IP registered with your broker.
Netlify has no static IP, so the trader runs on a small Linux server:

- **Oracle Cloud Always Free** (₹0): an Ubuntu VM in the Mumbai region with a *reserved*
  public IP.
- **AWS Lightsail Mumbai** (about $5/month): attach a static IP.

Your home PC only works if your internet provider gives you a fixed IP.

```bash
sudo apt-get update && sudo apt-get install -y git
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash - && sudo apt-get install -y nodejs
git clone https://github.com/dheeru284/dheeru284.git && cd dheeru284 && git checkout claude/gracious-ritchie-o9zq1j
cd option-desk && npm install
```

## 2. Angel One SmartAPI

1. Go to <https://smartapi.angelbroking.com> → sign up / log in → **Create an App** (Trading API).
   Note the **API key**.
2. In the app settings, register this server's **static IP**.
3. Enable **TOTP** for your Angel One login. When the QR code is shown, also copy the
   **text secret** (base32). The trader generates the 6-digit codes itself.
4. Check with Angel One whether your account needs an algo / strategy registration for API
   orders. Rules for retail algos were changing through 2026; this trader places about 8
   orders a week, far below the per-second thresholds.

## 3. Configure and test

```bash
cp trader/.env.example trader/.env && nano trader/.env      # fill it in; keep MODE=paper
chmod 600 trader/.env
node trader/test-scenarios.mjs        # offline logic tests (sim market)
node trader/trader.mjs --check        # logs in to Angel, prints funds and NIFTY spot
node trader/trader.mjs --once         # one cycle; then look at the Auto-trader tab
```

## 4. Run it permanently

```bash
sudo cp trader/optiondesk-trader.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now optiondesk-trader
journalctl -u optiondesk-trader -f          # live log
```

Then open the app → **Auto-trader** → **Enable auto-trading**.

## 5. Going live (after paper results look right)

In `trader/.env` set `MODE=live`, `I_UNDERSTAND_LIVE_RISK=yes`, start with `LOTS_MAX=1`,
then `sudo systemctl restart optiondesk-trader`. The mode chip in the app turns **LIVE**.

To stop everything: press **Exit everything now** in the app (closes the position and
pauses), or run `sudo systemctl stop optiondesk-trader` and manage the position in Angel One.

## Known limits

- **Untested against Angel's servers.** The order code follows Angel's official SDK but has
  not been run against a real account; `--check`, `--once` and paper mode exist to catch
  problems before live use.
- **Model prices in sim mode.** Sim mode uses model prices. Paper and live modes use real
  Angel bid/ask quotes.
- **Gaps.** Stops cannot protect against overnight gaps; only the wings cap the loss.
- **Event calendar.** `site/events.json` lists the RBI, Budget and FOMC dates the gate uses.
  Add new dates there as they are announced.
