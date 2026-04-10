/**
 * /api/match-info?slug=SLUG
 *
 * Server-side proxy for api-sports (api-football).
 * Returns: fixture ID + head-to-head history for a given match slug.
 * Cached 24 hours on Vercel edge — only called ONCE per match per day.
 * API cost: 2 calls/day per match (fixture search + H2H).
 */

const API_KEY  = 'b9c4d6e0be048bb79d8cf819e12775af';
const API_BASE = 'https://v3.football.api-sports.io';

const LEAGUE_MAP = {
    'champions-league':  { id: 2,   season: 2025 },
    'europa-league':     { id: 3,   season: 2025 },
    'conference-league': { id: 848, season: 2025 },
    'premier-league':    { id: 39,  season: 2025 },
    'la-liga':           { id: 140, season: 2025 },
    'serie-a':           { id: 135, season: 2025 },
    'bundesliga':        { id: 78,  season: 2025 },
    'ligue-1':           { id: 61,  season: 2025 },
    'eredivisie':        { id: 88,  season: 2025 },
    'isl':               { id: 323, season: 2025 },
    'fa-cup':            { id: 45,  season: 2025 },
    'copa-del-rey':      { id: 143, season: 2025 },
    'carabao-cup':       { id: 48,  season: 2025 },
    'dfb-pokal':         { id: 81,  season: 2025 },
};

async function apiFetch(path) {
    const res = await fetch(`${API_BASE}${path}`, {
        headers: { 'x-apisports-key': API_KEY, 'Accept': 'application/json' },
    });
    if (!res.ok) throw new Error(`api-sports ${res.status} on ${path}`);
    return res.json();
}

function teamMatch(a, b) {
    const clean = s => s.toLowerCase()
        .replace(/^(fc|ac|as|afc|cf|rc|rcd|vf|sv|rb|sk|fk|cd|ud|sc|ss)\s/i, '')
        .trim();
    a = clean(a); b = clean(b);
    return a === b || a.includes(b) || b.includes(a) ||
           a.split(' ')[0] === b.split(' ')[0];
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    if (req.method === 'OPTIONS') return res.status(200).end();

    const { slug } = req.query;
    if (!slug) return res.status(400).json({ error: 'slug required' });

    try {
        // Load events.json to find the match
        const evRes = await fetch('https://www.footholics.in/data/events.json');
        if (!evRes.ok) throw new Error('events.json unavailable');
        const events = await evRes.json();
        const event  = events.find(e => e.slug === slug);

        if (!event) return res.status(404).json({ error: 'Match not found' });

        const league = LEAGUE_MAP[event.leagueSlug];
        if (!league) {
            // League not mapped — return empty but still cache for 6h
            res.setHeader('Cache-Control', 's-maxage=21600, stale-while-revalidate=3600');
            return res.status(200).json({ fixtureId: null, homeTeamId: null, awayTeamId: null, h2h: null });
        }

        // ── Find the fixture ─────────────────────────────────────────
        const fd = await apiFetch(
            `/fixtures?date=${event.date}&league=${league.id}&season=${league.season}`
        );
        const fixture = (fd.response || []).find(f =>
            teamMatch(f.teams.home.name, event.homeTeam) &&
            teamMatch(f.teams.away.name, event.awayTeam)
        );

        if (!fixture) {
            res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate=600');
            return res.status(200).json({ fixtureId: null, homeTeamId: null, awayTeamId: null, h2h: null });
        }

        const fixtureId  = fixture.fixture.id;
        const homeTeamId = fixture.teams.home.id;
        const awayTeamId = fixture.teams.away.id;

        // ── Fetch H2H ────────────────────────────────────────────────
        const hd = await apiFetch(
            `/fixtures/headtohead?h2h=${homeTeamId}-${awayTeamId}&last=10`
        );

        // Cache 24 hours — fixture ID and H2H never change for a match
        res.setHeader('Cache-Control', 's-maxage=86400, stale-while-revalidate=3600');
        return res.status(200).json({
            fixtureId,
            homeTeamId,
            awayTeamId,
            h2h: hd.response || null,
        });

    } catch (err) {
        console.error('[match-info]', err.message);
        // Short cache on error so it retries soon
        res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=30');
        return res.status(500).json({ error: 'Failed to fetch match info' });
    }
}
