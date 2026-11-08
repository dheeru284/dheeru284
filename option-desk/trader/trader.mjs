#!/usr/bin/env node
// Auto-trader process. Run on a server with a static IP registered in your Angel SmartAPI app:
//   node trader/trader.mjs            (reads trader/.env)
//   node trader/trader.mjs --once     (one cycle, for testing)
//   node trader/trader.mjs --check    (log in, print funds and the next decision; no orders)
import fs from 'node:fs';
import { makeBroker } from './broker.mjs';
import { config, tick, log } from './core.mjs';

const envFile = new URL('./.env', import.meta.url);
if (fs.existsSync(envFile)) {
  for (const line of fs.readFileSync(envFile, 'utf8').split('\n')) {
    const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/.exec(line);
    if (m && !(m[1] in process.env)) process.env[m[1]] = m[2].replace(/^["']|["']$/g, '');
  }
}

const cfg = config();
const broker = makeBroker(process.env);
const ctx = { cfg, broker };
const arg = process.argv[2];

if (cfg.mode === 'live' && process.env.I_UNDERSTAND_LIVE_RISK !== 'yes') {
  console.error('MODE=live needs I_UNDERSTAND_LIVE_RISK=yes in trader/.env. Real orders will be placed.');
  process.exit(1);
}

if (arg === '--check') {
  if (broker.login) { await broker.login(); console.log('Angel login OK. Funds:', JSON.stringify(await broker.funds())); }
  console.log('Spot:', await broker.spot(), 'Config:', cfg);
  process.exit(0);
}

let stopping = false;
process.on('SIGTERM', () => { stopping = true; });
process.on('SIGINT', () => { stopping = true; });

let lastErr = 0;
do {
  try {
    const { t } = await tick(ctx);
    const market = t.min >= 9 * 60 + 10 && t.min <= 15 * 60 + 40;
    if (arg === '--once') break;
    await new Promise(r => setTimeout(r, (market ? Number(process.env.POLL_SECONDS || 20) : 120) * 1000));
  } catch (e) {
    console.error(e);
    if (Date.now() - lastErr > 15 * 60e3) { lastErr = Date.now(); await log({ ...ctx, now: Date.now() }, 'ERROR', 'Auto-trader error', e.message).catch(() => {}); }
    if (arg === '--once') break;
    await new Promise(r => setTimeout(r, 30000));
  }
} while (!stopping);
console.log('trader stopped');
if (broker.angel) await broker.angel.logout();
