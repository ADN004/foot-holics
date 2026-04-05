/**
 * Vercel Serverless Function — Football News Proxy
 * Route: /api/news?limit=25
 *
 * Primary:  ESPN league-specific news endpoints (includes images, covers all leagues)
 * Fallback: BBC Sport + The Guardian RSS if ESPN fails
 * Cache: 1 hour CDN
 */

// ── Category keyword map ──────────────────────────────────────────────────────
const CATEGORY_KEYWORDS = {
  'Premier League':   ['premier league', 'epl', 'man city', 'manchester city', 'arsenal',
                       'liverpool', 'chelsea', 'tottenham', 'spurs', 'manchester united',
                       'man united', 'aston villa', 'newcastle', 'west ham', 'brighton',
                       'fulham', 'everton', 'brentford', 'fa cup'],
  'Champions League': ['champions league', 'ucl', 'europa league', 'uel', 'conference league',
                       'uecl', 'uefa'],
  'La Liga':          ['la liga', 'laliga', 'real madrid', 'barcelona', 'atletico', 'sevilla',
                       'villarreal', 'real sociedad', 'betis', 'athletic bilbao'],
  'Bundesliga':       ['bundesliga', 'bayern', 'dortmund', 'rb leipzig', 'leverkusen',
                       'frankfurt', 'wolfsburg', 'gladbach', 'hertha', 'stuttga'],
  'Serie A':          ['serie a', 'inter milan', 'ac milan', 'juventus', 'napoli', 'roma',
                       'lazio', 'fiorentina', 'atalanta', 'torino', 'calcio'],
  'Ligue 1':          ['ligue 1', 'psg', 'paris saint-germain', 'marseille', 'lyon', 'monaco',
                       'nice', 'lens', 'lille'],
};

function detectCategory(title, description) {
  const text = ((title || '') + ' ' + (description || '')).toLowerCase();
  for (const [cat, words] of Object.entries(CATEGORY_KEYWORDS)) {
    if (words.some((w) => text.includes(w))) return cat;
  }
  return 'Football';
}

// ── ESPN ─────────────────────────────────────────────────────────────────────
const ESPN_LEAGUES = [
  { id: 'eng.1',        cat: 'Premier League'   },
  { id: 'esp.1',        cat: 'La Liga'          },
  { id: 'ger.1',        cat: 'Bundesliga'        },
  { id: 'ita.1',        cat: 'Serie A'           },
  { id: 'fra.1',        cat: 'Ligue 1'           },
  { id: 'UEFA.CHAMPIONS', cat: 'Champions League' },
];

async function fetchESPNLeagueNews(leagueId, limit) {
  const url = `https://site.api.espn.com/apis/site/v2/sports/soccer/${leagueId}/news?limit=${limit}`;
  const res = await fetch(url, {
    headers: { 'User-Agent': 'Mozilla/5.0 (compatible; FootHolics/1.0)' },
  });
  if (!res.ok) throw new Error(`ESPN ${leagueId} → ${res.status}`);
  const data = await res.json();
  return (data.articles || []).map((a) => {
    const image = (a.images && a.images[0]) ? a.images[0].url : '';
    const desc = a.description || a.story || '';
    return {
      headline: a.headline || '',
      description: desc.slice(0, 220) + (desc.length > 220 ? '...' : ''),
      published: a.published || '',
      url: a.links?.web?.href || a.links?.mobile?.href || '',
      image,
      category: detectCategory(a.headline, desc),
    };
  }).filter((a) => a.headline && a.url);
}

// ── RSS fallback ──────────────────────────────────────────────────────────────
function stripHtml(html) {
  if (!html) return '';
  return html
    .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

function xmlAttr(block, tag, attr) {
  const re = new RegExp(`<${tag}[^>]*\\s${attr}="([^"]*)"`, 'i');
  const m = block.match(re);
  return m ? m[1] : '';
}

function xmlTag(block, tag) {
  const re = new RegExp(
    `<${tag}(?:\\s[^>]*)?>(?:<!\\[CDATA\\[([\\s\\S]*?)\\]\\]>|([\\s\\S]*?))<\\/${tag}>`, 'i'
  );
  const m = block.match(re);
  if (!m) return '';
  return (m[1] !== undefined ? m[1] : m[2] || '').trim();
}

function parseRSS(xml) {
  const items = [];
  const itemRe = /<item[\s>]([\s\S]*?)<\/item>/gi;
  let m;
  while ((m = itemRe.exec(xml)) !== null) {
    const b = m[1];
    const title = stripHtml(xmlTag(b, 'title'));
    const link  = xmlTag(b, 'link') || xmlAttr(b, 'link', 'href');
    const pubDate = xmlTag(b, 'pubDate');
    const description = stripHtml(xmlTag(b, 'description'));

    // Try various image locations
    let image = xmlAttr(b, 'media:thumbnail', 'url')
             || xmlAttr(b, 'media:content', 'url')
             || xmlAttr(b, 'enclosure', 'url')
             || '';

    // Try og:image or any https img src in the block
    if (!image) {
      const ig = b.match(/src="(https?:\/\/[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"/i);
      if (ig) image = ig[1];
    }

    if (title && link) items.push({ title, link, pubDate, description, image });
  }
  return items;
}

const RSS_FEEDS = [
  'https://feeds.bbci.co.uk/sport/football/rss.xml',
  'https://www.theguardian.com/football/rss',
];

async function fetchRSSFeed(url) {
  try {
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*',
      },
    });
    if (!res.ok) { console.warn(`[news] RSS ${url} → ${res.status}`); return []; }
    const xml = await res.text();
    return parseRSS(xml);
  } catch (e) {
    console.warn(`[news] RSS ${url} error:`, e.message);
    return [];
  }
}

// ── Handler ───────────────────────────────────────────────────────────────────
export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    return res.status(200).end();
  }
  res.setHeader('Access-Control-Allow-Origin', '*');

  const limit = Math.min(parseInt(req.query.limit) || 25, 50);
  const perLeague = Math.ceil(limit / ESPN_LEAGUES.length) + 2; // a few extra per league

  // ── Step 1: Try ESPN (all leagues in parallel) ────────────────────────────
  const espnResults = await Promise.allSettled(
    ESPN_LEAGUES.map((l) => fetchESPNLeagueNews(l.id, perLeague))
  );

  let articles = espnResults.flatMap((r) => r.status === 'fulfilled' ? r.value : []);

  // ── Step 2: If ESPN gives nothing, fall back to RSS ───────────────────────
  if (!articles.length) {
    console.warn('[news] ESPN returned nothing — falling back to RSS');
    const rssResults = await Promise.allSettled(RSS_FEEDS.map(fetchRSSFeed));
    const rssItems = rssResults.flatMap((r) => r.status === 'fulfilled' ? r.value : []);

    if (!rssItems.length) {
      return res.status(502).json({ error: 'All news feeds unavailable. Try again later.' });
    }

    articles = rssItems.map((item) => ({
      headline: item.title,
      description: item.description
        ? item.description.slice(0, 220) + (item.description.length > 220 ? '...' : '')
        : '',
      published: item.pubDate || '',
      url: item.link || '',
      image: item.image || '',
      category: detectCategory(item.title, item.description),
    })).filter((a) => a.headline && a.url);
  }

  // ── Deduplicate by headline ───────────────────────────────────────────────
  const seen = new Set();
  const unique = articles.filter((a) => {
    const key = a.headline.toLowerCase().replace(/\s+/g, ' ').trim();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  // ── Sort newest first ─────────────────────────────────────────────────────
  unique.sort((a, b) => {
    const da = a.published ? new Date(a.published).getTime() : 0;
    const db = b.published ? new Date(b.published).getTime() : 0;
    return db - da;
  });

  const result = unique.slice(0, limit);

  res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=7200');
  return res.status(200).json({ articles: result, total: result.length });
}
