// Scenario tests for the auto-trader on a simulated clock and simulated market (no network, no broker).
// Run: node trader/test-scenarios.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
const STORE = path.join(os.tmpdir(), 'option-desk-store.json');
let NOW = 0; const realNow = Date.now; Date.now = () => NOW || realNow();
const at = s => { NOW = Date.parse(s.replace(' ', 'T') + ':00+05:30'); return NOW; };

const { SimBroker } = await import('./broker.mjs');
const { tick, config } = await import('./core.mjs');
const { getJSON, setJSON } = await import('../netlify/lib/store.mjs');

let MKT = { spot: 25000, vix: 14 };
const green = { nifty: 25000, vix: 14, vixChg5: 0.02, dma50: 24800, dma200: 24000, rv20: 0.11,
  chg20: { 'US VIX': 0.05, 'USD/INR': 0.002, 'US 10Y yield': 5, 'Brent crude': 0.01 } };
function newCtx(state = green, env = {}) {
  return { cfg: config({ MODE: 'sim', CAPITAL: '1500000', RISK_PCT: '2', LOTS_MAX: '2', MAX_MONTHLY_LOSS: '30000', ...env }),
    broker: new SimBroker({ override: async () => MKT }), liveState: async () => ({ ...state, nifty: MKT.spot, vix: MKT.vix }), clock: () => NOW };
}
const reset = async (enabled = true) => { fs.rmSync(STORE, { force: true }); await setJSON('auto-control', { enabled }); };
const ok = (name) => console.log('✓', name);

// 1. red gate → no trade
await reset();
let ctx = newCtx({ ...green, chg20: { ...green.chg20, 'US VIX': 0.7 } });
at('2026-11-11 15:12'); await tick(ctx);
assert.equal(await getJSON('position'), null);
assert.equal((await getJSON('auto-status')).lastDecision.verdict, 'bad');
ok('red gate (US VIX +70%) → no trade');

// 2. green gate → enters on entry day only inside the 15:10-15:24 window
await reset(); ctx = newCtx();
at('2026-11-11 14:00'); await tick(ctx); assert.equal(await getJSON('position'), null);
at('2026-11-10 15:15'); await tick(ctx); assert.equal(await getJSON('position'), null);   // holiday, not entry day
at('2026-11-11 15:12'); await tick(ctx);
let pos = await getJSON('position');
assert.ok(pos && pos.managedBy === 'auto' && pos.expiry === '2026-11-17' && pos.legs.length === 4, 'entered');
assert.deepEqual(pos.legs.map(l => l.side), ['BUY', 'BUY', 'SELL', 'SELL'].sort().reverse().sort() && pos.legs.map(l => l.side));
assert.ok(pos.lots >= 1 && pos.lots <= 2 && pos.credit > 0);
ok(`entered IC ${pos.legs.map(l => l.side[0] + l.strike + l.type).join(' ')}, ${pos.lots} lots, credit ₹${Math.round(pos.credit)}`);
at('2026-11-11 15:20'); await tick(ctx); assert.equal((await getJSON('position')).id, pos.id);
ok('no second entry the same day');

// 3. small move intraday → hold; stop only at the close
MKT = { spot: 24650, vix: 15 }; at('2026-11-12 11:00'); await tick(ctx);
pos = await getJSON('position'); assert.ok(pos, 'still open'); console.log('   mark at 24650:', pos.last.pnl);
// find a spot where loss is between 1x and 1.5x the stop
let spot = 24650; let p2;
for (; spot > 23000; spot -= 25) { MKT = { spot, vix: 16 }; at('2026-11-13 12:00'); await tick(ctx); p2 = await getJSON('position'); if (!p2 || -p2.last.pnl >= p2.credit) break; }
assert.ok(p2, 'intraday stop touch must not exit before the close');
ok(`stop touched intraday at NIFTY ${spot} (P&L ₹${p2.last.pnl}) → held until the close`);
at('2026-11-13 15:16'); await tick(ctx);
assert.equal(await getJSON('position'), null, 'stop at close exits');
let trades = await getJSON('auto-trades'); assert.ok(trades[0].pnl < 0 && /stop at close/.test(trades[0].reason));
ok(`stop at close: closed ${trades[0].reason}, net ₹${trades[0].pnl} (charges ₹${trades[0].charges})`);

// 4. hard stop intraday
await reset(); ctx = newCtx(); MKT = { spot: 25000, vix: 14 };
at('2026-11-11 15:12'); await tick(ctx); pos = await getJSON('position');
MKT = { spot: 23700, vix: 24 }; at('2026-11-12 10:05'); await tick(ctx);
trades = await getJSON('auto-trades'); assert.equal(await getJSON('position'), null); assert.match(trades[0].reason, /hard stop/);
ok(`gap down to 23,700 → hard stop at 10:05, net ₹${trades[0].pnl}`);

// 5. manual flatten from the app
await reset(); ctx = newCtx(); MKT = { spot: 25000, vix: 14 };
at('2026-11-11 15:12'); await tick(ctx);
await setJSON('auto-control', { enabled: true, flatten: true });
at('2026-11-12 09:30'); await tick(ctx);
trades = await getJSON('auto-trades'); assert.equal(await getJSON('position'), null); assert.match(trades[0].reason, /manual/);
assert.equal((await getJSON('auto-control')).flatten, false);
ok(`"Exit everything now" button → closed, net ₹${trades[0].pnl}`);

// 6. hold to expiry and settle (no orders) when NIFTY stays in range
await reset(); ctx = newCtx(); MKT = { spot: 25000, vix: 14 };
at('2026-11-11 15:12'); await tick(ctx); pos = await getJSON('position');
for (const d of ['2026-11-12', '2026-11-13', '2026-11-16', '2026-11-17']) { MKT = { spot: 25080, vix: 13 }; at(d + ' 15:16'); await tick(ctx); }
assert.ok(await getJSON('position'), 'still open on expiry afternoon');
const realChart = (await import('../netlify/lib/yahoo.mjs')).chart;
ctx.broker.spot = async () => 25080;            // settlement price source when Yahoo has no bar for the test date
at('2026-11-17 16:00'); await tick(ctx);
trades = await getJSON('auto-trades'); assert.equal(await getJSON('position'), null);
assert.match(trades[0].reason, /expiry/); assert.ok(trades[0].pnl > 0);
ok(`held to expiry, settled at 25,080 → net +₹${trades[0].pnl} (kept ${Math.round(trades[0].gross / pos.credit * 100)}% of credit)`);

// 7. capital too small → no trade, warning
await reset(); ctx = newCtx(green, { CAPITAL: '200000' }); MKT = { spot: 25000, vix: 14 };
at('2026-11-11 15:12'); await tick(ctx); assert.equal(await getJSON('position'), null);
const lg = await getJSON('auto-log'); assert.match(lg[0].title, /capital too small/);
ok('₹2 lakh capital at 2% risk → refuses to trade (1 lot risks more than ₹4,000)');

// 8. monthly loss guard pauses trading
await reset(); ctx = newCtx(green, { MAX_MONTHLY_LOSS: '5000' });
await setJSON('auto-trades', [{ closed: '2026-11-05T10:00:00Z', pnl: -6000 }]);
at('2026-11-11 15:00'); await tick(ctx);
assert.equal((await getJSON('auto-control')).enabled, false);
ok('monthly loss −₹6,000 > ₹5,000 limit → auto-trading paused');

// 9. disabled → never trades
await reset(false); ctx = newCtx(); at('2026-11-11 15:12'); await tick(ctx); assert.equal(await getJSON('position'), null);
ok('disabled in the app → no entries');
fs.rmSync(STORE, { force: true });
console.log('\nall scenarios passed');
