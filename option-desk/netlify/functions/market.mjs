// GET /api/market → one year of daily closes for NIFTY and every macro factor the
// research found relevant, plus the latest live quote. Source: Yahoo Finance chart API.
import { fetchMany } from '../lib/yahoo.mjs';

export default async () => new Response(JSON.stringify(await fetchMany()), {
  headers: {
    'content-type': 'application/json',
    'cache-control': 'public, max-age=120',
    'netlify-cdn-cache-control': 'public, s-maxage=300, stale-while-revalidate=600',
  },
});

export const config = { path: '/api/market' };
