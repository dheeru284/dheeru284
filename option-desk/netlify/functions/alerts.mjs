// /api/alerts  GET → recent alerts and monitor status
//              POST {action:"test"} → send a test push   ·   POST {action:"run"} → run the monitor now
import { getJSON, authorised, json } from '../lib/store.mjs';
import { push } from '../lib/notify.mjs';
import { runMonitor } from '../lib/monitor-core.mjs';

export default async (req) => {
  if (!authorised(req)) return json({ error: 'wrong or missing desk key' }, 401);
  if (req.method === 'GET') {
    const [alerts, state] = await Promise.all([getJSON('alerts', []), getJSON('state', {})]);
    return json({ alerts: alerts.slice(0, 60), lastRun: state.lastRun || null,
      channels: { ntfy: !!process.env.NTFY_TOPIC, telegram: !!(process.env.TELEGRAM_BOT_TOKEN && process.env.TELEGRAM_CHAT_ID) } });
  }
  if (req.method === 'POST') {
    const b = await req.json().catch(() => ({}));
    if (b.action === 'test') return json(await push({ level: 'TEST', title: 'Option Desk alerts are working', body: 'You will get EXIT, WARN and TARGET alerts here while a trade is open, plus market-moving news.' }));
    if (b.action === 'run') return json(await runMonitor({ force: true, siteUrl: process.env.URL }));
  }
  return json({ error: 'bad request' }, 400);
};

export const config = { path: '/api/alerts' };
