/**
 * Vercel Serverless Function — Football News Proxy
 * Route: /api/news
 * Source: ESPN Soccer News (public, no key required)
 * Cache: 1 hour on CDN
 */
export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    return res.status(200).end();
  }

  res.setHeader('Access-Control-Allow-Origin', '*');

  try {
    const limit = Math.min(parseInt(req.query.limit) || 20, 40);

    const response = await fetch(
      `https://site.api.espn.com/apis/site/v2/sports/soccer/news?limit=${limit}`,
      {
        headers: {
          'User-Agent': 'Mozilla/5.0 (compatible; FootHolics/1.0)',
          'Accept': 'application/json',
        },
      }
    );

    if (!response.ok) {
      throw new Error(`ESPN API returned ${response.status}`);
    }

    const data = await response.json();

    // Normalize to a clean format
    const articles = (data.articles || []).map((a) => ({
      headline: a.headline || '',
      description: a.description || '',
      published: a.published || '',
      url: a.links?.web?.href || '',
      image: a.images?.[0]?.url || '',
      category: a.categories?.find((c) => c.type === 'league')?.description || 'Football',
    }));

    // Cache: 1 hour CDN, 2 hour stale-while-revalidate
    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=7200');
    return res.status(200).json({ articles, total: articles.length });
  } catch (err) {
    console.error('[news] fetch error:', err.message);
    return res.status(502).json({ error: 'Failed to fetch news', detail: err.message });
  }
}
