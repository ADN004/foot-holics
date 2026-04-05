/**
 * Vercel Serverless Function — Football News Proxy
 * Route: /api/news?limit=20
 * Sources: BBC Sport Football RSS (primary) + Sky Sports RSS (secondary)
 *          Converted to JSON via rss2json.com (free, no key needed)
 * Cache: 1 hour CDN
 */

// Keyword map for auto-categorising articles
const CATEGORY_KEYWORDS = {
  'Premier League': ['premier league', 'epl', 'man city', 'manchester city', 'arsenal', 'liverpool',
                     'chelsea', 'tottenham', 'spurs', 'manchester united', 'man united', 'aston villa',
                     'newcastle', 'west ham', 'brighton', 'fulham'],
  'La Liga':        ['la liga', 'laliga', 'real madrid', 'barcelona', 'atletico madrid',
                     'atletico de madrid', 'sevilla', 'villarreal', 'real sociedad'],
  'Champions League': ['champions league', 'ucl', 'europa league', 'conference league'],
  'Bundesliga':     ['bundesliga', 'bayern', 'borussia', 'dortmund', 'rb leipzig', 'leverkusen'],
  'Serie A':        ['serie a', 'inter milan', 'ac milan', 'juventus', 'napoli', 'roma', 'lazio'],
};

function detectCategory(title, description) {
  const text = ((title || '') + ' ' + (description || '')).toLowerCase();
  for (const [cat, words] of Object.entries(CATEGORY_KEYWORDS)) {
    if (words.some((w) => text.includes(w))) return cat;
  }
  return 'Football';
}

function stripHtml(html) {
  if (!html) return '';
  return html.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&lt;/g, '<')
             .replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").trim();
}

async function fetchRSS(rssUrl, limit) {
  const url = `https://api.rss2json.com/v1/api.json?rss_url=${encodeURIComponent(rssUrl)}&count=${limit}`;
  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; FootHolics/1.0)' },
  });
  if (!res.ok) throw new Error(`rss2json returned ${res.status}`);
  const data = await res.json();
  if (data.status !== 'ok') throw new Error('rss2json error: ' + data.message);
  return data.items || [];
}

export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    return res.status(200).end();
  }

  res.setHeader('Access-Control-Allow-Origin', '*');

  const limit = Math.min(parseInt(req.query.limit) || 20, 40);

  // Try BBC Sport Football RSS first, fall back to Sky Sports
  const RSS_FEEDS = [
    'https://feeds.bbci.co.uk/sport/football/rss.xml',
    'https://www.skysports.com/rss/12040',
  ];

  let items = [];

  for (const feed of RSS_FEEDS) {
    try {
      items = await fetchRSS(feed, limit);
      if (items.length > 0) break;
    } catch (err) {
      console.warn('[news] feed failed:', feed, err.message);
    }
  }

  if (!items.length) {
    return res.status(502).json({ error: 'All news feeds unavailable. Try again later.' });
  }

  const articles = items.map((item) => {
    const desc = stripHtml(item.description || item.content || '');
    const image = item.thumbnail
      || item.enclosure?.link
      || (item.content?.match(/src="([^"]+\.(jpg|jpeg|png|webp)[^"]*)"/i)?.[1] || '');

    return {
      headline: stripHtml(item.title || ''),
      description: desc.slice(0, 200) + (desc.length > 200 ? '...' : ''),
      published: item.pubDate || '',
      url: item.link || '',
      image: image || '',
      category: detectCategory(item.title, item.description),
    };
  }).filter((a) => a.headline && a.url);

  res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=7200');
  return res.status(200).json({ articles, total: articles.length });
}
