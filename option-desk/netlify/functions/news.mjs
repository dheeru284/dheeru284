// GET /api/news → recent Indian-market headlines from public RSS feeds, each scored
// for sentiment and tagged with the macro factor it touches (crude, rupee, Fed, RBI ...).
import { fetchAll } from '../lib/news-core.mjs';

export default async () => {
  const { items, errors } = await fetchAll();
  items.sort((a, b) => b.date.localeCompare(a.date));
  const cutoff = Date.now() - 48 * 3600e3;
  const recent = items.filter(i => Date.parse(i.date) >= cutoff);
  const agg = recent.reduce((s, i) => s + i.sentiment, 0);
  const byTag = {};
  for (const i of recent) for (const t of i.tags) { byTag[t] ??= { n: 0, score: 0 }; byTag[t].n++; byTag[t].score += i.sentiment; }
  return new Response(JSON.stringify({ fetched: new Date().toISOString(), items: items.slice(0, 120), last48h: { n: recent.length, score: agg, byTag }, errors }), {
    headers: { 'content-type': 'application/json', 'cache-control': 'public, max-age=300', 'netlify-cdn-cache-control': 'public, s-maxage=600' },
  });
};

export const config = { path: '/api/news' };
