/**
 * /api/match-detail?id=FIXTURE_ID
 *
 * Returns full match data in one shot:
 *   fixture · events · lineups · statistics · H2H · per-team recent form
 *
 * Source: api-football.com v3
 * API calls: 1 (fixture) + 4 parallel (events/lineups/stats/h2h) + 2 form (non-live)
 * Cache: finished → 24 h | live → 5 min | upcoming → 30 min
 */

// Set in Vercel → Settings → Environment Variables (never hardcode — public repo).
const API_KEY  = process.env.API_FOOTBALL_KEY;
const API_BASE = 'https://v3.football.api-sports.io';

const FINISHED  = new Set(['FT', 'AET', 'PEN', 'AWD', 'WO']);
const LIVE_SET  = new Set(['1H', 'HT', '2H', 'ET', 'BT', 'P', 'INT', 'LIVE']);

async function apiFetch(path) {
    const r = await fetch(`${API_BASE}${path}`, {
        headers: { 'x-apisports-key': API_KEY, Accept: 'application/json' },
    });
    if (!r.ok) throw new Error(`api-sports ${r.status} on ${path}`);
    return r.json();
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
        // Step 1 — get fixture to resolve team IDs and status
        const fd = await apiFetch(`/fixtures?id=${id}`);
        const fixture = (fd.response || [])[0];
        if (!fixture) {
            res.setHeader('Cache-Control', 's-maxage=60');
            return res.status(404).json({ error: 'Match not found' });
        }

        const homeId   = fixture.teams.home.id;
        const awayId   = fixture.teams.away.id;
        const short    = fixture.fixture.status.short;
        const isFinished = FINISHED.has(short);
        const isLive     = LIVE_SET.has(short);

        // Step 2 — parallel fetch; skip form calls during live to save quota
        const empty = Promise.resolve({ response: [] });
        const [evd, ld, sd, h2hd, hfd, afd] = await Promise.all([
            apiFetch(`/fixtures/events?fixture=${id}`),
            apiFetch(`/fixtures/lineups?fixture=${id}`),
            apiFetch(`/fixtures/statistics?fixture=${id}`),
            apiFetch(`/fixtures/headtohead?h2h=${homeId}-${awayId}&last=10`),
            isLive ? empty : apiFetch(`/fixtures?team=${homeId}&last=5`),
            isLive ? empty : apiFetch(`/fixtures?team=${awayId}&last=5`),
        ]);

        const cacheSec = isFinished ? 86400 : isLive ? 900 : 1800;
        res.setHeader('Cache-Control', `s-maxage=${cacheSec}, stale-while-revalidate=${Math.floor(cacheSec / 2)}`);

        return res.status(200).json({
            fixture,
            events:    evd.response || [],
            lineups:   ld.response  || [],
            stats:     sd.response  || [],
            h2h:       h2hd.response || [],
            homeForm: (hfd.response || []).filter(f => f.fixture.id !== Number(id)).slice(0, 5),
            awayForm: (afd.response || []).filter(f => f.fixture.id !== Number(id)).slice(0, 5),
        });

    } catch (err) {
        console.error('[match-detail]', err.message);
        res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=30');
        return res.status(500).json({ error: 'Failed to fetch match detail' });
    }
}
