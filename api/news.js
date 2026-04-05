/**
 * Vercel Serverless Function — Football News Proxy
 * Route: /api/news?limit=25
 * Sources: Multiple RSS feeds fetched in parallel, combined & deduplicated
 * Cache: 1 hour CDN
 */

const CATEGORY_KEYWORDS = {
  'Premier League': ['premier league', 'epl', 'man city', 'manchester city', 'arsenal', 'liverpool',
                     'chelsea', 'tottenham', 'spurs', 'manchester united', 'man united', 'aston villa',
                     'newcastle', 'west ham', 'brighton', 'fulham', 'everton', 'brentford'],
  'Champions League': ['champions league', 'ucl', 'europa league', 'uel', 'conference league',
                       'uecl', 'uefa', 'champions'],
  'La Liga':        ['la liga', 'laliga', 'real madrid', 'barcelona', 'atletico madrid',
                     'atletico de madrid', 'sevilla', 'villarreal', 'real sociedad', 'betis'],
  'Bundesliga':     ['bundesliga', 'bayern munich', 'borussia dortmund', 'rb leipzig',
                     'bayer leverkusen', 'frankfurt', 'wolfsburg', 'gladbach'],
  'Serie A':        ['serie a', 'inter milan', 'ac milan', 'juventus', 'napoli', 'roma',
                     'lazio', 'fiorentina', 'atalanta', 'torino', 'calcio'],
  'Ligue 1':        ['ligue 1', 'psg', 'paris saint-germain', 'marseille', 'lyon', 'monaco',
                     'nice', 'lens', 'lille'],
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
  return html
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function getTagContent(block, tag) {
  const re = new RegExp(
    `<${tag}(?:\\s[^>]*)?>(?:<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>|([\\s\\S]*?))<\\/${tag}>`,
    'i'
  );
  const m = block.match(re);
  if (!m) return '';
  return (m[1] !== undefined ? m[1] : m[2] || '').trim();
}

function getAttr(block, tag, attr) {
  const re = new RegExp(`<${tag}[^>]*\\s${attr}="([^"]*)"`, 'i');
  const m = block.match(re);
  return m ? m[1] : '';
}

function parseRSS(xml) {
  const items = [];
  const itemRegex = /<item[\s>]([\s\S]*?)<\/item>/gi;
  let match;
  while ((match = itemRegex.exec(xml)) !== null) {
    const block = match[1];
    const title = stripHtml(getTagContent(block, 'title'));
    const link = getTagContent(block, 'link') || getAttr(block, 'link', 'href');
    const pubDate = getTagContent(block, 'pubDate');
    const description = stripHtml(getTagContent(block, 'description'));

    let image = getAttr(block, 'media:thumbnail', 'url')
             || getAttr(block, 'media:content', 'url')
             || getAttr(block, 'enclosure', 'url')
             || '';

    if (!image) {
      // Try to grab image URL from within description/content
      const imgMatch = block.match(/src="(https?:\/\/[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"/i);
      if (imgMatch) image = imgMatch[1];
    }

    if (title && link) {
      items.push({ title, link, pubDate, description, image });
    }
  }
  return items;
}

// All feeds fetched in PARALLEL and combined
const RSS_FEEDS = [
  'https://feeds.bbci.co.uk/sport/football/rss.xml',           // BBC Sport Football
  'https://www.theguardian.com/football/rss',                   // The Guardian Football
  'https://www.skysports.com/rss/12040',                        // Sky Sports Football
];

async function fetchFeed(feedUrl) {
  try {
    const response = await fetch(feedUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
      },
      redirect: 'follow',
    });
    if (!response.ok) {
      console.warn(`[news] ${feedUrl} → ${response.status}`);
      return [];
    }
    const xml = await response.text();
    const items = parseRSS(xml);
    console.log(`[news] ${feedUrl} → ${items.length} items`);
    return items;
  } catch (err) {
    console.warn(`[news] ${feedUrl} failed:`, err.message);
    return [];
  }
}

export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    return res.status(200).end();
  }

  res.setHeader('Access-Control-Allow-Origin', '*');

  const limit = Math.min(parseInt(req.query.limit) || 25, 50);

  // Fetch all feeds in parallel
  const results = await Promise.allSettled(RSS_FEEDS.map(fetchFeed));
  const allItems = results.flatMap((r) => (r.status === 'fulfilled' ? r.value : []));

  if (!allItems.length) {
    return res.status(502).json({ error: 'All news feeds unavailable. Try again later.' });
  }

  // Deduplicate by headline (normalised)
  const seen = new Set();
  const unique = allItems.filter((item) => {
    const key = item.title.toLowerCase().replace(/\s+/g, ' ').trim();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  // Sort newest first
  unique.sort((a, b) => {
    const da = a.pubDate ? new Date(a.pubDate).getTime() : 0;
    const db = b.pubDate ? new Date(b.pubDate).getTime() : 0;
    return db - da;
  });

  const articles = unique.slice(0, limit).map((item) => ({
    headline: item.title,
    description: item.description
      ? item.description.slice(0, 220) + (item.description.length > 220 ? '...' : '')
      : '',
    published: item.pubDate || '',
    url: item.link || '',
    image: item.image || '',
    category: detectCategory(item.title, item.description),
  })).filter((a) => a.headline && a.url);

  res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=7200');
  return res.status(200).json({ articles, total: articles.length });
}
