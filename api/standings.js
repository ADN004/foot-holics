/**
 * Vercel Serverless Function — League Standings Proxy
 * Route: /api/standings?league=eng.1
 * Source: ESPN Soccer API (public, no key required)
 * Cache: 6 hours on CDN
 *
 * Supported league codes:
 *   eng.1       → Premier League
 *   esp.1       → La Liga
 *   ger.1       → Bundesliga
 *   ita.1       → Serie A
 *   fra.1       → Ligue 1
 *   UEFA.CHAMPIONS → Champions League (group stage)
 */
const ALLOWED_LEAGUES = new Set(['eng.1', 'esp.1', 'ger.1', 'ita.1', 'fra.1', 'UEFA.CHAMPIONS']);

export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    return res.status(200).end();
  }

  res.setHeader('Access-Control-Allow-Origin', '*');

  const league = req.query.league || 'eng.1';

  if (!ALLOWED_LEAGUES.has(league)) {
    return res.status(400).json({ error: 'Invalid league code' });
  }

  try {
    const response = await fetch(
      `https://site.api.espn.com/apis/v2/sports/soccer/${league}/standings`,
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

    // Find the "overall" standings child
    const child = data.children?.find(
      (c) => c.name?.toLowerCase().includes('overall') || c.abbreviation === 'ovr'
    ) || data.children?.[0];

    const entries = child?.standings?.entries || [];

    const getStat = (stats, name) => {
      const s = stats.find((x) => x.name === name);
      return s ? (s.displayValue || String(s.value)) : '-';
    };

    const rows = entries.map((entry, idx) => ({
      position: idx + 1,
      team: entry.team?.displayName || '',
      abbreviation: entry.team?.abbreviation || '',
      logo: entry.team?.logos?.[0]?.href || '',
      gp: getStat(entry.stats, 'gamesPlayed'),
      w: getStat(entry.stats, 'wins'),
      d: getStat(entry.stats, 'ties'),
      l: getStat(entry.stats, 'losses'),
      gf: getStat(entry.stats, 'pointsFor'),
      ga: getStat(entry.stats, 'pointsAgainst'),
      gd: getStat(entry.stats, 'pointDifferential'),
      pts: getStat(entry.stats, 'points'),
      form: getStat(entry.stats, 'streak'),
    }));

    // Cache: 6 hours CDN, 12 hours stale-while-revalidate
    res.setHeader('Cache-Control', 's-maxage=21600, stale-while-revalidate=43200');
    return res.status(200).json({
      league,
      season: data.season?.displayName || '',
      name: data.name || '',
      rows,
    });
  } catch (err) {
    console.error('[standings] fetch error:', err.message);
    return res.status(502).json({ error: 'Failed to fetch standings', detail: err.message });
  }
}
