/**
 * /api/match-info?slug=SLUG
 *
 * ESPN-based, KEYLESS, no daily quota. Resolves a match to its ESPN event id and
 * returns head-to-head history, reshaped into the api-football-style shape the
 * live detail page already renders:
 *   { fixtureId, espnLeague, h2h: [ { fixture:{date}, teams:{home,away}, goals:{home,away}, league:{name} } ] }
 *
 * H2H is oriented to the operator's home/away team names so the record counts
 * and labels are correct even when ESPN names them differently.
 *
 * `espnLeague` is the resolved ESPN league slug — match-live needs it for the
 * per-league summary/scoreboard URLs.
 */

import {
    ESPN_BASE, ESPN_LEAGUES, FALLBACK_SLUGS,
    getJson, espnDate, prevEspnDate, findEvent, teamMatch,
} from '../lib/espn.js';

// Reshape ESPN headToHeadGames → api-football-like H2H, oriented to ev teams.
function reshapeH2H(summary, evHome, evAway) {
    const block = summary && Array.isArray(summary.headToHeadGames)
        ? summary.headToHeadGames[0] : null;
    if (!block || !Array.isArray(block.events)) return null;

    const persp = (block.team && block.team.displayName) || evHome;
    const perspIsHome = teamMatch(persp, evHome); // orient meetings to ev.homeTeam
    const toInt = v =>
        (v === '' || v == null || isNaN(parseInt(v, 10))) ? null : parseInt(v, 10);

    return block.events.map(e => {
        // perspective team's goals vs opponent's goals in that past meeting
        const perspGoals = e.atVs === 'vs' ? toInt(e.homeTeamScore) : toInt(e.awayTeamScore);
        const oppGoals   = e.atVs === 'vs' ? toInt(e.awayTeamScore) : toInt(e.homeTeamScore);
        return {
            fixture: { date: e.gameDate },
            teams: { home: { name: evHome }, away: { name: evAway } },
            goals: {
                home: perspIsHome ? perspGoals : oppGoals,
                away: perspIsHome ? oppGoals : perspGoals,
            },
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
        // events.json stores IST dates; ESPN buckets by its own day, so also try
        // the previous day for late-night/early-morning IST kickoffs.
        const dates = [espnDate(event.date), prevEspnDate(event.date)];

        const found = await findEvent(candidates, dates, event.homeTeam, event.awayTeam);
        if (!found) return empty(3600); // not on ESPN (date/teams/coverage) — retry in 1h

        const summary = await getJson(
            `${ESPN_BASE}/${found.slug}/summary?event=${found.id}`
        );
        const h2h = reshapeH2H(summary, event.homeTeam, event.awayTeam);

        res.setHeader('Cache-Control', 's-maxage=86400, stale-while-revalidate=3600');
        return res.status(200).json({ fixtureId: found.id, espnLeague: found.slug, h2h });
    } catch (err) {
        console.error('[match-info]', err.message);
        res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=30');
        return res.status(500).json({ error: 'Failed to fetch match info' });
    }
}
