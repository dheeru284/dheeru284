// /api/position  GET → the open position being monitored
//                POST {legs, expiry, credit, lots, stopMult, spotAtEntry, ...} → start monitoring
//                DELETE → stop monitoring (trade closed)
import { getJSON, setJSON, del, authorised, json } from '../lib/store.mjs';

export default async (req) => {
  if (!authorised(req)) return json({ error: 'wrong or missing desk key' }, 401);
  if (req.method === 'GET') return json({ position: await getJSON('position', null) });
  if (req.method === 'DELETE') {
    const p = await getJSON('position', null);
    if (p) { const h = await getJSON('history', []); await setJSON('history', [{ ...p, closed: new Date().toISOString() }, ...h].slice(0, 200)); }
    await del('position');
    return json({ ok: true });
  }
  if (req.method === 'POST') {
    const b = await req.json();
    const okLeg = l => ['BUY', 'SELL'].includes(l.side) && ['C', 'P'].includes(l.type) && l.strike > 0 && l.premium >= 0;
    if (!Array.isArray(b.legs) || !b.legs.length || !b.legs.every(okLeg) || !/^\d{4}-\d{2}-\d{2}$/.test(b.expiry) || !(b.credit > 0))
      return json({ error: 'invalid position' }, 400);
    const pos = { id: Date.now(), opened: new Date().toISOString(), expiry: b.expiry, structure: b.structure || 'custom',
      legs: b.legs.map(l => ({ side: l.side, type: l.type, strike: +l.strike, premium: +l.premium, lots: +l.lots || 1 })),
      credit: +b.credit, lots: +b.lots || 1, stopMult: +b.stopMult || 1, spotAtEntry: +b.spotAtEntry, vixAtEntry: +b.vixAtEntry || null, ivMult: 0.95 };
    await setJSON('position', pos);
    return json({ ok: true, position: pos });
  }
  return json({ error: 'method not allowed' }, 405);
};

export const config = { path: '/api/position' };
