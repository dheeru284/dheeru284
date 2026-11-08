// Small JSON key-value store: Netlify Blobs in production, a local file when run outside Netlify
// (local testing). Keys used: "position", "alerts", "state".
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

let blobs = null;
async function store() {
  if (blobs !== null) return blobs;
  try {
    const { getStore } = await import('@netlify/blobs');
    const s = getStore({ name: 'option-desk', consistency: 'strong' });
    await s.get('__probe');          // throws outside a Netlify runtime
    blobs = s;
  } catch {
    blobs = false;
  }
  return blobs;
}

const LOCAL = path.join(os.tmpdir(), 'option-desk-store.json');
const readLocal = () => { try { return JSON.parse(fs.readFileSync(LOCAL, 'utf8')); } catch { return {}; } };

export async function getJSON(key, fallback = null) {
  const s = await store();
  if (s) { const v = await s.get(key, { type: 'json' }); return v ?? fallback; }
  return readLocal()[key] ?? fallback;
}

export async function setJSON(key, value) {
  const s = await store();
  if (s) return s.setJSON(key, value);
  const all = readLocal(); all[key] = value; fs.writeFileSync(LOCAL, JSON.stringify(all));
}

export async function del(key) {
  const s = await store();
  if (s) return s.delete(key);
  const all = readLocal(); delete all[key]; fs.writeFileSync(LOCAL, JSON.stringify(all));
}

// Shared-secret check for every write and for reading the position/alerts.
export function authorised(req) {
  const want = process.env.ALERT_KEY;
  if (!want) return true;                // no key configured: site protection is the only guard
  const got = req.headers.get('x-desk-key') || new URL(req.url).searchParams.get('key');
  return got === want;
}

export const json = (obj, status = 200) => new Response(JSON.stringify(obj), {
  status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
});
