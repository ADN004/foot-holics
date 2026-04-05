/**
 * Vercel Serverless Function — Upcoming Fixtures Proxy
 * Route: /api/fixtures?league=eng.1  (omit league for all)
 * Source: ESPN Soccer Scoreboard API (public, no key required)
 * Cache: 1 hour on CDN
 *
 * Returns next 14 days of fixtures across major leagues.
 */

const LEAGUES = [
  { code: 'eng.1', name: 'Premier League', color: '#3d195b' },
  { code: 'esp.1', name: 'La Liga', color: '#ee8707' },
  { code: 'ger.1', name: 'Bundesliga', color: '#d20515' },
  { code: 'ita.1', name: 'Serie A', color: '#024494' },
  { code: 'fra.1', name: 'Ligue 1', color: '#002395' },
  { code: 'UEFA.CHAMPIONS', name: 'Champions League', color: '#00336a' },
];

function pad(n) { return String(n).padStart(2, '0'); }

function formatESPNDate(d) {
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
}

async function fetchLeagueFixtures(league, dateFrom, dateTo) {
  const url =
    `https://site.api.espn.com/apis/site/v2/sports/soccer/${league.code}/scoreboard` +
    `?dates=${dateFrom}-${dateTo}&limit=50`;

  try {
    const res = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; FootHolics/1.0)',
        'Accept': 'application/json',
      },
    });

    if (!res.ok) return [];

    const data = await res.json();
    const events = data.events || [];

    return events.map((ev) => {
      const comp = ev.competitions?.[0];
      const home = comp?.competitors?.find((c) => c.homeAway === 'home');
      const away = comp?.competitors?.find((c) => c.homeAway === 'away');
      const status = comp?.status?.type;

      return {
        id: ev.id,
        league: league.name,
        leagueCode: league.code,
        leagueColor: league.color,
        date: ev.date,
        homeTeam: home?.team?.displayName || '',
        homeLogo: home?.team?.logos?.[0]?.href || home?.team?.logo || '',
        homeScore: home?.score,
        awayTeam: away?.team?.displayName || '',
        awayLogo: away?.team?.logos?.[0]?.href || away?.team?.logo || '',
        awayScore: away?.score,
        statusState: status?.state || 'pre',
        statusDesc: status?.shortDetail || status?.description || 'Scheduled',
        completed: status?.completed || false,
        venue: comp?.venue?.fullName || '',
      };
    });
  } catch {
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

  const leagueFilter = req.query.league;
  const leagues = leagueFilter
    ? LEAGUES.filter((l) => l.code === leagueFilter)
    : LEAGUES;

  if (leagues.length === 0) {
    return res.status(400).json({ error: 'Invalid league code' });
  }

  const today = new Date();
  const end = new Date(today);
  end.setDate(end.getDate() + 14);

  const dateFrom = formatESPNDate(today);
  const dateTo = formatESPNDate(end);

  try {
    const results = await Promise.all(
      leagues.map((l) => fetchLeagueFixtures(l, dateFrom, dateTo))
    );

    const fixtures = results
      .flat()
      .sort((a, b) => new Date(a.date) - new Date(b.date));

    res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=7200');
    return res.status(200).json({ fixtures, dateFrom, dateTo });
  } catch (err) {
    console.error('[fixtures] fetch error:', err.message);
    return res.status(502).json({ error: 'Failed to fetch fixtures', detail: err.message });
  }
}
