/**
 * Vercel Serverless Function — Football News Proxy
 * Route: /api/news?limit=20
 * Sources: BBC Sport Football RSS (primary) + Sky Sports RSS (secondary)
 *          Fetched and parsed directly — no third-party intermediary
 * Cache: 1 hour CDN
 */

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
  return html
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/<[^>]+>/g, '')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ')
    .trim();
}

function getTagContent(xml, tag) {
  // Handle CDATA and plain text
  const re = new RegExp(`<${tag}[^>]*>(?:<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>|([\\s\\S]*?))<\\/${tag}>`, 'i');
  const m = xml.match(re);
  if (!m) return '';
  return (m[1] !== undefined ? m[1] : m[2] || '').trim();
}

function getAttr(xml, tag, attr) {
  const re = new RegExp(`<${tag}[^>]*\\s${attr}="([^"]*)"`, 'i');
  const m = xml.match(re);
  return m ? m[1] : '';
}

function parseRSS(xml, limit) {
  const items = [];
  // Split on <item> tags
  const itemRegex = /<item[\s>]([\s\S]*?)<\/item>/gi;
  let match;
  while ((match = itemRegex.exec(xml)) !== null && items.length < limit) {
    const block = match[1];
    const title = stripHtml(getTagContent(block, 'title'));
    const link = getTagContent(block, 'link') || getAttr(block, 'link', 'href');
    const pubDate = getTagContent(block, 'pubDate');
    const description = stripHtml(getTagContent(block, 'description'));

    // Try to extract image from media:thumbnail, media:content, or enclosure
    let image = getAttr(block, 'media:thumbnail', 'url')
             || getAttr(block, 'media:content', 'url')
             || getAttr(block, 'enclosure', 'url')
             || '';

    // Try to extract from description img tag if no image found
    if (!image) {
      const imgMatch = block.match(/<img[^>]+src="([^"]+)"/i);
      if (imgMatch) image = imgMatch[1];
    }

    if (title && link) {
      items.push({ title, link, pubDate, description, image });
    }
  }
  return items;
}

const RSS_FEEDS = [
  'https://feeds.bbci.co.uk/sport/football/rss.xml',
  'https://www.skysports.com/rss/12040',
  'https://www.football365.com/feed',
];

export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    return res.status(200).end();
  }

  res.setHeader('Access-Control-Allow-Origin', '*');

  const limit = Math.min(parseInt(req.query.limit) || 20, 40);

  let items = [];

  for (const feedUrl of RSS_FEEDS) {
    try {
      const response = await fetch(feedUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
          'Accept': 'application/rss+xml, application/xml, text/xml, */*',
          'Accept-Language': 'en-US,en;q=0.9',
        },
        redirect: 'follow',
      });

      if (!response.ok) {
        console.warn(`[news] ${feedUrl} responded ${response.status}`);
        continue;
      }

      const xml = await response.text();
      const parsed = parseRSS(xml, limit);

      if (parsed.length > 0) {
        items = parsed;
        console.log(`[news] loaded ${items.length} articles from ${feedUrl}`);
        break;
      }
    } catch (err) {
      console.warn('[news] feed error:', feedUrl, err.message);
    }
  }

  if (!items.length) {
    return res.status(502).json({ error: 'All news feeds unavailable. Try again later.' });
  }

  const articles = items.map((item) => ({
    headline: item.title,
    description: item.description
      ? item.description.slice(0, 200) + (item.description.length > 200 ? '...' : '')
      : '',
    published: item.pubDate || '',
    url: item.link || '',
    image: item.image || '',
    category: detectCategory(item.title, item.description),
  })).filter((a) => a.headline && a.url);

  res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=7200');
  return res.status(200).json({ articles, total: articles.length });
}
