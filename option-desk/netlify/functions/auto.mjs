// /api/auto  GET → auto-trader status, open position, closed trades, P&L summary, activity log
//            POST {action:"enable"|"pause"|"flatten"} → control the trader (it acts on its next cycle)
import { getJSON, setJSON, authorised, json } from '../lib/store.mjs';

const istDate = iso => new Date(Date.parse(iso) + 5.5 * 3600e3).toISOString().slice(0, 10);

export default async (req) => {
  if (!authorised(req)) return json({ error: 'wrong or missing desk key' }, 401);
  if (req.method === 'POST') {
    const { action } = await req.json().catch(() => ({}));
    const c = await getJSON('auto-control', { enabled: false });
    if (action === 'enable') Object.assign(c, { enabled: true, disabledReason: null });
    else if (action === 'pause') c.enabled = false;
    else if (action === 'flatten') Object.assign(c, { flatten: true, enabled: false });
    else return json({ error: 'unknown action' }, 400);
    c.updated = new Date().toISOString();
    await setJSON('auto-control', c);
    return json({ ok: true, control: c });
  }
  const [control, status, position, trades, log] = await Promise.all([
    getJSON('auto-control', { enabled: false }), getJSON('auto-status', null), getJSON('position', null),
    getJSON('auto-trades', []), getJSON('auto-log', [])]);
  const today = istDate(new Date().toISOString());
  const sum = f => trades.filter(f).reduce((a, t) => a + t.pnl, 0);
  const weekAgo = istDate(new Date(Date.now() - 7 * 864e5).toISOString());
  const summary = {
    trades: trades.length, wins: trades.filter(t => t.pnl > 0).length, total: sum(() => true),
    month: sum(t => istDate(t.closed).slice(0, 7) === today.slice(0, 7)), week: sum(t => istDate(t.closed) > weekAgo),
    best: trades.length ? Math.max(...trades.map(t => t.pnl)) : 0, worst: trades.length ? Math.min(...trades.map(t => t.pnl)) : 0,
    open: position?.managedBy === 'auto' ? position.last?.pnl ?? 0 : 0,
  };
  const online = status?.beat && Date.now() - Date.parse(status.beat) < 5 * 60e3;
  return json({ control, status, online, position: position?.managedBy === 'auto' ? position : null, trades: trades.slice(0, 200), log: log.slice(0, 60), summary });
};

export const config = { path: '/api/auto' };
