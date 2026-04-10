/**
 * /api/match-live?id=FIXTURE_ID
 *
 * Server-side proxy for api-sports (api-football).
 * Returns: live score + game events + match statistics for a fixture.
 * Cached 5 minutes on Vercel edge — shared across ALL users.
 *
 * API cost: 2 calls per 5-min interval while match is live.
 * For a 2-hour match: ~48 calls total. Well within the free 100/day limit.
 */

const API_KEY  = 'b9c4d6e0be048bb79d8cf819e12775af';
const API_BASE = 'https://v3.football.api-sports.io';

async function apiFetch(path) {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: { 'x-apisports-key': API_KEY, 'Accept': 'application/json' },
    });
    if (!res.ok) throw new Error(`api-sports ${res.status} on ${path}`);
    return res.json();
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    if (req.method === 'OPTIONS') return res.status(200).end();

    const { id } = req.query;
    if (!id || isNaN(Number(id))) {
        return res.status(400).json({ error: 'valid fixture id required' });
    }

    try {
        // Fetch fixture, statistics, and lineups in parallel — 3 API calls
        const [fd, sd, ld] = await Promise.all([
            apiFetch(`/fixtures?id=${id}`),
            apiFetch(`/fixtures/statistics?fixture=${id}`),
            apiFetch(`/fixtures/lineups?fixture=${id}`),
        ]);

        const fixture = (fd.response || [])[0] || null;
        const stats   = sd.response || null;
        const lineups = ld.response || null;

        // Determine cache duration based on match status
        let cacheSec = 600; // default 10 min (live) — supports up to 3 simultaneous matches on free plan
        if (fixture) {
            const short = fixture.fixture.status.short;
            if (['NS', 'TBD'].includes(short)) {
                cacheSec = 1800; // 30 min — match hasn't started yet
            } else if (['FT', 'AET', 'PEN', 'AWD', 'WO'].includes(short)) {
                cacheSec = 86400; // 24 h — match is over, won't change
            }
        }

        res.setHeader('Cache-Control', `s-maxage=${cacheSec}, stale-while-revalidate=${Math.floor(cacheSec / 2)}`);
        return res.status(200).json({ fixture, stats, lineups });

    } catch (err) {
        console.error('[match-live]', err.message);
        res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=30');
        return res.status(500).json({ error: 'Failed to fetch live data' });
    }
}
