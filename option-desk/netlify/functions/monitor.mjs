// Scheduled every 2 minutes. Full checks during NSE hours; a news sweep every ~30 min otherwise.
import { runMonitor } from '../lib/monitor-core.mjs';

export default async () => {
  const r = await runMonitor({ siteUrl: process.env.URL });
  console.log(JSON.stringify({ ranAt: r.ranAt, open: r.marketOpen, alerts: r.alerts.map(a => `${a.level} ${a.title}`) }));
};

export const config = { schedule: '*/2 * * * *' };
