// Shared RSS fetching and headline scoring for /api/news and the live monitor.
export const FEEDS = [
  ['Economic Times', 'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms'],
  ['Moneycontrol', 'https://www.moneycontrol.com/rss/marketreports.xml'],
  ['Livemint', 'https://www.livemint.com/rss/markets'],
  ['Business Standard', 'https://www.business-standard.com/rss/markets-106.rss'],
  ['Google News', 'https://news.google.com/rss/search?q=Nifty+OR+Sensex+OR+%22stock+market%22+India&hl=en-IN&gl=IN&ceid=IN:en'],
  ['Google News (macro)', 'https://news.google.com/rss/search?q=RBI+OR+Fed+OR+%22crude+oil%22+OR+rupee+OR+FII&hl=en-IN&gl=IN&ceid=IN:en'],
];

// Direction words describe a price move; their meaning flips when the subject is something
// that hurts India when it rises (crude, US yields, the dollar, inflation).
const UP = ['rally', 'surge', 'soar', 'jump', 'gain', 'rise', 'rises', 'record high', 'rebound', 'recover', 'higher', 'climb',
  'advance', 'reclaim', 'breakout', 'spike', 'up '];
const DOWN = ['crash', 'plunge', 'slump', 'tumble', 'fall', 'drop', 'decline', 'sell-off', 'selloff', 'slip', 'lower', 'shed',
  'crack', 'eases', 'easing', 'cools', 'down '];
const GOOD = ['bull', 'upgrade', 'beat', 'inflow', 'buying', 'rate cut', 'cuts rate', 'ceasefire', 'deal', 'strong', 'outperform',
  'boost', 'positive', 'optimism', 'record profit'];
const BAD = ['bear', 'downgrade', 'miss', 'outflow', 'selling', 'war', 'attack', 'tension', 'sanction', 'tariff', 'hike', 'recession',
  'slowdown', 'weak', 'fear', 'panic', 'volatil', 'loss', 'default', 'crisis', 'warning', 'probe', 'ban', 'escalat'];
const INVERSE = /(crude|oil|brent|wti|yield|inflation|dollar|dxy|vix|usd\/inr)/;
const has = (t, w) => t.includes(w);
const TAGS = {
  Crude: ['crude', 'oil', 'brent', 'opec', 'wti'], Rupee: ['rupee', 'inr', 'forex', 'usd/inr', 'dollar'],
  Fed: ['fed', 'fomc', 'powell', 'federal reserve', 'treasury', 'us yield', 'bond yield'],
  RBI: ['rbi', 'repo', 'mpc', 'malhotra', 'monetary policy'], 'FII/DII': ['fii', 'fpi', 'dii', 'foreign investor', 'foreign fund'],
  Geopolitics: ['war', 'israel', 'iran', 'russia', 'ukraine', 'china', 'pakistan', 'missile', 'sanction', 'tariff', 'trump'],
  Inflation: ['inflation', 'cpi', 'wpi'], Earnings: ['q1', 'q2', 'q3', 'q4', 'results', 'earnings', 'profit', 'quarter'],
  Gold: ['gold', 'silver'], 'US markets': ['wall street', 'dow', 'nasdaq', 's&p', 'us stocks'],
  Derivatives: ['expiry', 'option', 'f&o', 'vix', 'open interest', 'sebi'],
};

const decode = s => s.replace(/<!\[CDATA\[(.*?)\]\]>/gs, '$1').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;|&apos;/g, "'")
  .replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/<[^>]+>/g, '').trim();
const pick = (item, tag) => { const m = item.match(new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`, 'i')); return m ? decode(m[1]) : ''; };

export function score(title) {
  const t = ` ${title.toLowerCase()} `;
  let s = 0;
  for (const clause of t.split(/[;:|,]| as | after | amid | on (?=[a-z]+ (?:tension|war|fear|hope))/)) {
    const c = ` ${clause} `;
    let dir = UP.filter(w => has(c, w)).length - DOWN.filter(w => has(c, w)).length;
    if (INVERSE.test(c) && !/(nifty|sensex|stocks|shares|market|index)/.test(c)) dir = -dir;
    s += dir + GOOD.filter(w => has(c, w)).length - BAD.filter(w => has(c, w)).length;
  }
  const tags = Object.entries(TAGS).filter(([, ws]) => ws.some(w => new RegExp(`\\b${w.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&')}`, 'i').test(t))).map(([k]) => k);
  return { sentiment: Math.max(-3, Math.min(3, s)), tags };
}

export async function feed([source, url]) {
  const r = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0 (OptionDesk news)' }, signal: AbortSignal.timeout(8000) });
  if (!r.ok) throw new Error(`${source} HTTP ${r.status}`);
  const xml = await r.text();
  return [...xml.matchAll(/<item[\s>][\s\S]*?<\/item>/gi)].slice(0, 30).map(m => {
    const it = m[0];
    const title = pick(it, 'title');
    return { source, title, link: pick(it, 'link'), date: new Date(pick(it, 'pubDate') || Date.now()).toISOString(), ...score(title) };
  });
}


// All feeds, de-duplicated, newest first.
export async function fetchAll() {
  const res = await Promise.allSettled(FEEDS.map(feed));
  const seen = new Set(), items = [], errors = [];
  res.forEach((r, i) => {
    if (r.status !== 'fulfilled') return errors.push(`${FEEDS[i][0]}: ${r.reason}`);
    for (const it of r.value) {
      const k = key(it.title);
      if (!it.title || seen.has(k)) continue;
      seen.add(k); items.push({ ...it, key: k });
    }
  });
  items.sort((a, b) => b.date.localeCompare(a.date));
  return { items, errors };
}
export const key = t => t.toLowerCase().replace(/[^a-z0-9]/g, '').slice(0, 60);

// Headlines that historically move Indian markets fast.
export const HIGH_IMPACT = /\b(war|attack|missile|strike[sd]? on|terror|emergency|sanction|tariff|rate hike|hikes rate|rate cut|cuts rate|repo|rbi|fed|fomc|powell|crash|circuit|halt|default|earthquake|ceasefire|budget|election result|exit poll|resign|sebi|ban|lockdown|nuclear|opec|downgrade)\b/i;
