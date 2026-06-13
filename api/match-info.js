/**
 * /api/match-info?slug=SLUG
 *
 * ESPN-based match info: resolves a match to its ESPN event id and returns
 * head-to-head history. ESPN's hidden site API is KEYLESS and has no daily
 * quota (same source as standings.js), so this removes the api-football limit.
 *
 * The response is reshaped into the api-football-style shape the live detail
 * page already renders, so detail.html needs no H2H changes:
 *   { fixtureId, espnLeague, h2h: [ { fixture:{date}, teams:{home,away}, goals:{home,away}, league:{name} } ] }
 *
 * `espnLeague` is the ESPN league slug of the resolved event — match-live needs
 * it to build the per-league summary URL.
 *
 * Cached 24h on Vercel edge (H2H barely changes), shared across all visitors.
 */

const ESPN_BASE = 'https://site.api.espn.com/apis/site/v2/sports/soccer';

// bot leagueSlug → ESPN league slug candidates (tried in order until the fixture
// is found). World Cup / international matches span several ESPN competitions,
// so we list the likely ones.
const ESPN_LEAGUES = {
    'premier-league':   ['eng.1'],
    'laliga':           ['esp.1'],
    'la-liga':          ['esp.1'],
    'serie-a':          ['ita.1'],
    'bundesliga':       ['ger.1'],
    'ligue-1':          ['fra.1'],
    'champions-league': ['uefa.champions'],
    'europa-league':    ['uefa.europa'],
    'conference-league':['uefa.europa.conf'],
    'wc':               ['fifa.world', 'fifa.friendly', 'fifa.worldq.conmebol',
                         'fifa.worldq.uefa', 'fifa.worldq.concacaf', 'fifa.worldq.afc',
                         'fifa.worldq.caf'],
    'nationals':        ['fifa.friendly', 'fifa.world', 'uefa.nations'],
};

// Best-effort sweep for unmapped leagues ("others" etc.).
const FALLBACK_SLUGS = ['eng.1', 'esp.1', 'ita.1', 'ger.1', 'fra.1',
    'uefa.champions', 'fifa.world', 'fifa.friendly', 'usa.1'];

function teamMatch(a, b) {
    const clean = s => String(s || '').toLowerCase()
        .replace(/^(fc|ac|as|afc|cf|rc|rcd|vf|sv|rb|sk|fk|cd|ud|sc|ss)\s/i, '')
        .trim();
    a = clean(a); b = clean(b);
    if (!a || !b) return false;
    return a === b || a.includes(b) || b.includes(a) ||
           a.split(' ')[0] === b.split(' ')[0];
}

function espnDate(isoDate) {
    return String(isoDate || '').replace(/-/g, ''); // "2026-06-13" → "20260613"
}

function prevEspnDate(isoDate) {
    const d = new Date(isoDate + 'T12:00:00Z');
    d.setUTCDate(d.getUTCDate() - 1);
    return d.toISOString().slice(0, 10).replace(/-/g, '');
}

async function getJson(url) {
    const r = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error(`espn ${r.status} on ${url}`);
    return r.json();
}

// Scan candidate ESPN leagues on a date for the fixture; return { id, slug } or null.
async function findEvent(slugs, date, home, away) {
    for (const slug of slugs) {
        let data;
        try {
            data = await getJson(`${ESPN_BASE}/${slug}/scoreboard?dates=${date}`);
        } catch {
            continue; // unknown slug / no events that day
        }
        for (const ev of (data.events || [])) {
            const comp = ev.competitions && ev.competitions[0];
            const competitors = (comp && comp.competitors) || [];
            const h = competitors.find(c => c.homeAway === 'home');
            const a = competitors.find(c => c.homeAway === 'away');
            if (!h || !a) continue;
            const hn = h.team && h.team.displayName;
            const an = a.team && a.team.displayName;
            // accept either orientation (operator may have entered teams reversed)
            if ((teamMatch(hn, home) && teamMatch(an, away)) ||
                (teamMatch(hn, away) && teamMatch(an, home))) {
                return { id: ev.id, slug };
            }
        }
    }
    return null;
}

// Reshape ESPN headToHeadGames → the api-football-like array detail.html renders.
function reshapeH2H(summary, fallbackPersp) {
    const block = summary && Array.isArray(summary.headToHeadGames)
        ? summary.headToHeadGames[0] : null;
    if (!block || !Array.isArray(block.events)) return null;

    const persp = (block.team && block.team.displayName) || fallbackPersp;
    const toInt = v =>
        (v === '' || v == null || isNaN(parseInt(v, 10))) ? null : parseInt(v, 10);

    return block.events.map(e => {
        const homeIsPersp = e.atVs === 'vs'; // "vs" = perspective team was home
        const opp = (e.opponent && e.opponent.displayName) || '';
        return {
            fixture: { date: e.gameDate },
            teams: {
                home: { name: homeIsPersp ? persp : opp },
                away: { name: homeIsPersp ? opp : persp },
            },
            goals: { home: toInt(e.homeTeamScore), away: toInt(e.awayTeamScore) },
            league: { name: e.leagueName || e.competitionName || '' },
        };
    });
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    if (req.method === 'OPTIONS') return res.status(200).end();

    const { slug } = req.query;
    if (!slug) return res.status(400).json({ error: 'slug required' });

    const empty = (cacheSec) => {
        res.setHeader('Cache-Control', `s-maxage=${cacheSec}, stale-while-revalidate=600`);
        return res.status(200).json({ fixtureId: null, espnLeague: null, h2h: null });
    };

    try {
        const evRes = await fetch('https://footholics.in/data/events.json');
        if (!evRes.ok) throw new Error('events.json unavailable');
        const events = await evRes.json();
        const event = events.find(e => e.slug === slug);
        if (!event) return res.status(404).json({ error: 'Match not found' });

        const candidates = ESPN_LEAGUES[event.leagueSlug] || FALLBACK_SLUGS;

        // Try the stored (IST) date, then the previous day — events.json holds IST
        // dates, and ESPN buckets by its own day, so a late-night IST match can sit
        // on the previous ESPN date.
        let found = await findEvent(candidates, espnDate(event.date),
            event.homeTeam, event.awayTeam);
        if (!found) {
            found = await findEvent(candidates, prevEspnDate(event.date),
                event.homeTeam, event.awayTeam);
        }
        if (!found) return empty(3600); // not on ESPN (date/teams/coverage) — retry in 1h

        const summary = await getJson(
            `${ESPN_BASE}/${found.slug}/summary?event=${found.id}`
        );
        const h2h = reshapeH2H(summary, event.homeTeam);

        // Event id + H2H are stable for a match → cache 24h.
        res.setHeader('Cache-Control', 's-maxage=86400, stale-while-revalidate=3600');
        return res.status(200).json({
            fixtureId: found.id,
            espnLeague: found.slug,
            h2h,
        });
    } catch (err) {
        console.error('[match-info]', err.message);
        res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=30');
        return res.status(500).json({ error: 'Failed to fetch match info' });
    }
}
