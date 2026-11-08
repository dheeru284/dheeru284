#!/usr/bin/env node
// Interactive setup on YOUR server:  node trader/setup.mjs
// Asks for the Angel One details (typed input hidden), checks the TOTP secret, tests the login,
// and writes trader/.env readable only by you. Nothing is sent anywhere except Angel One's login.
import fs from 'node:fs';
import readline from 'node:readline';
import { totp, Angel } from './angel.mjs';

const ENV = new URL('./.env', import.meta.url);
const old = fs.existsSync(ENV) ? Object.fromEntries(fs.readFileSync(ENV, 'utf8').split('\n').map(l => /^([A-Z0-9_]+)=(.*)$/.exec(l)).filter(Boolean).map(m => [m[1], m[2]])) : {};

function ask(q, { hidden = false, def = '' } = {}) {
  return new Promise(res => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stdout, terminal: true });
    const shown = def ? (hidden ? ' [keep current]' : ` [${def}]`) : '';
    if (hidden) rl._writeToOutput = s => { if (s.includes(q)) process.stdout.write(s); else process.stdout.write('*'.repeat(s.length ? 1 : 0)); };
    rl.question(`${q}${shown}: `, a => { rl.close(); if (hidden) process.stdout.write('\n'); res(a.trim() || def); });
  });
}

console.log('\nNIFTY Option Desk — auto-trader setup\nValues are saved only in trader/.env on this server.\n');
const myIp = await fetch('https://api.ipify.org', { signal: AbortSignal.timeout(5000) }).then(r => r.text()).catch(() => '');
if (myIp) console.log(`This server's public IP is ${myIp} — register it in your SmartAPI app.\n`);

const v = {};
v.ANGEL_API_KEY = await ask('Angel SmartAPI API key', { hidden: true, def: old.ANGEL_API_KEY });
v.ANGEL_CLIENT_CODE = await ask('Angel One client ID', { def: old.ANGEL_CLIENT_CODE });
v.ANGEL_PIN = await ask('Angel One login PIN (MPIN)', { hidden: true, def: old.ANGEL_PIN });
for (;;) {
  v.ANGEL_TOTP_SECRET = (await ask('TOTP secret (the text under the QR code, not the 6-digit code)', { hidden: true, def: old.ANGEL_TOTP_SECRET })).replace(/\s/g, '');
  try { const code = totp(v.ANGEL_TOTP_SECRET); console.log(`  → current code ${code}; it should match your authenticator app right now.`); break; }
  catch { console.log('  That is not a valid base32 secret (letters A–Z and digits 2–7). Try again.'); }
}
v.ANGEL_PUBLIC_IP = await ask('Static public IP registered with Angel', { def: old.ANGEL_PUBLIC_IP || myIp });
v.MODE = (await ask('Mode: sim / paper / live', { def: old.MODE || 'paper' })).toLowerCase();
v.I_UNDERSTAND_LIVE_RISK = v.MODE === 'live' ? ((await ask('LIVE places real orders. Type "yes" to confirm', { def: 'no' })) === 'yes' ? 'yes' : 'no') : 'no';
v.CAPITAL = await ask('Capital the sizing should assume (₹)', { def: old.CAPITAL || '1500000' });
v.RISK_PCT = await ask('Max loss per trade, % of capital', { def: old.RISK_PCT || '2' });
v.LOTS_MAX = await ask('Max lots per trade', { def: old.LOTS_MAX || '1' });
v.MAX_MONTHLY_LOSS = await ask('Pause after this monthly loss (₹)', { def: old.MAX_MONTHLY_LOSS || '20000' });
v.NETLIFY_SITE_ID = old.NETLIFY_SITE_ID || 'd6cd7c0a-3adc-4ded-a022-362ddee8ff89';
v.NETLIFY_AUTH_TOKEN = await ask('Netlify personal access token (so the app shows your trades)', { hidden: true, def: old.NETLIFY_AUTH_TOKEN });
v.NTFY_TOPIC = await ask('ntfy topic for phone alerts', { def: old.NTFY_TOPIC || '' });
Object.assign(v, { STOP_MULT: old.STOP_MULT || '1', HARD_STOP_MULT: old.HARD_STOP_MULT || '1.5', POLL_SECONDS: old.POLL_SECONDS || '20',
  ANGEL_LOCAL_IP: old.ANGEL_LOCAL_IP || '127.0.0.1', ANGEL_MAC: old.ANGEL_MAC || '00:00:00:00:00:00' });

if (v.MODE !== 'sim') {
  process.stdout.write('\nTesting Angel One login… ');
  try {
    const a = new Angel(v); await a.login(); const f = await a.funds();
    console.log(`OK. Available cash ₹${Number(f?.availablecash ?? 0).toLocaleString('en-IN')}.`);
    await a.logout();
  } catch (e) { console.log(`FAILED: ${e.message}\nCheck the values (and that this IP is registered), then run setup again. Saving anyway.`); }
}

fs.writeFileSync(ENV, Object.entries(v).map(([k, x]) => `${k}=${x}`).join('\n') + '\n', { mode: 0o600 });
fs.chmodSync(ENV, 0o600);
console.log(`\nSaved trader/.env (readable only by you). Mode: ${v.MODE.toUpperCase()}.\nNext: node trader/trader.mjs --once   then start the service (see trader/README.md).\n`);
