/**
 * /api/match-schedule?tab=yesterday|today|tomorrow
 *
 * ESPN-based, KEYLESS, no daily quota. Returns worldwide fixtures for a day,
 * grouped by competition with major leagues first — same response shape the
 * homepage + match centre already render:
 *   { tab, date, total, leagues: [ { league, matches:[normMatch] } ] }
 *
 * Source: ESPN all/scoreboard (one call, all competitions).
 */

import { ESPN_BASE, getJson, espnDate } from '../lib/espn.js';

// Keyword priority for sorting competitions (lower index = shown first).
const LEAGUE_PRIORITY = [
    'world cup', 'champions league', 'europa league', 'conference league',
    'nations league', 'euro', 'copa america', 'african cup', 'asian cup',
    'premier league', 'laliga', 'la liga', 'serie a', 'bundesliga', 'ligue 1',
    'champions', 'fa cup', 'efl cup', 'carabao', 'copa del rey', 'coppa italia',
    'dfb pokal', 'eredivisie', 'primeira liga', 'super lig',
    'mls', 'liga mx', 'brasileir', 'libertadores',
];

function istNow() { return new Date(Date.now() + 5.5 * 3600_000); }

function tabToDate(tab) {
    const d = istNow();
    if (tab === 'yesterday') d.setDate(d.getDate() - 1);
    if (tab === 'tomorrow')  d.setDate(d.getDate() + 1);
    return d.toISOString().slice(0, 10); // YYYY-MM-DD
}

// "2025-26-english-premier-league" / "2026-fifa-world-cup" → "English Premier League"
function leagueNameFromSlug(slug) {
    return String(slug || '')
        .replace(/^\d{4}(-\d{2})?-/, '')          // drop leading season year(s)
        .replace(/-/g, ' ')
        .replace(/\b\w/g, c => c.toUpperCase())
        .replace(/\bFifa\b/, 'FIFA').replace(/\bUefa\b/, 'UEFA')
        .replace(/\bMls\b/, 'MLS').replace(/\bEfl\b/, 'EFL')
        .trim() || 'Football';
}

function leagueIdFromUid(uid) {
    const m = /l:(\d+)/.exec(uid || '');
    return m ? Number(m[1]) : 0;
}

function shortStatus(state) {
    if (state === 'pre') return 'NS';
    if (state === 'post') return 'FT';
    return '1H'; // live
}

function priorityRank(name) {
    const n = name.toLowerCase();
    for (let i = 0; i < LEAGUE_PRIORITY.length; i++)
        if (n.includes(LEAGUE_PRIORITY[i])) return i;
    return 999;
}

function normMatch(ev) {
    const comp = (ev.competitions && ev.competitions[0]) || {};
    const cs = comp.competitors || [];
    const h = cs.find(c => c.homeAway === 'home') || cs[0] || {};
    const a = cs.find(c => c.homeAway === 'away') || cs[1] || {};
    const st = ev.status || comp.status || {};
    const toInt = v => (v == null || v === '' || isNaN(parseInt(v, 10))) ? null : parseInt(v, 10);
    const side = c => ({
        id: c.team ? c.team.id : null,
        name: c.team ? c.team.displayName : '',
        logo: c.team ? c.team.logo : '',
        winner: c.winner === true,
    });
    const slug = (ev.season && ev.season.slug) || '';
    return {
        id: ev.id,
        date: ev.date,
        timestamp: ev.date ? Math.floor(Date.parse(ev.date) / 1000) : 0,
        status: {
            long: (st.type && st.type.description) || '',
            short: shortStatus(st.type && st.type.state),
            elapsed: parseInt(st.displayClock, 10) || null,
        },
        venue: comp.venue ? { name: comp.venue.fullName, city: null } : null,
        league: {
            id: leagueIdFromUid(ev.uid),
            name: leagueNameFromSlug(slug),
            country: '',
            logo: '',  // ESPN's multi-league scoreboard omits per-league logos
            flag: '',
            season: '',
            round: '',
        },
        home: side(h),
        away: side(a),
        goals: { home: toInt(h.score), away: toInt(a.score) },
        score: { halftime: { home: null, away: null }, fulltime: { home: toInt(h.score), away: toInt(a.score) } },
    };
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    if (req.method === 'OPTIONS') return res.status(200).end();

    const tab = req.query.tab || 'today';
    if (!['yesterday', 'today', 'tomorrow'].includes(tab)) {
        return res.status(400).json({ error: 'tab must be yesterday|today|tomorrow' });
    }

    const date = tabToDate(tab);

    try {
        const data = await getJson(`${ESPN_BASE}/all/scoreboard?dates=${espnDate(date)}`);
        const matches = (data.events || []).map(normMatch);

        // Group by competition (ESPN league id from the uid).
        const leagueMap = {};
        for (const m of matches) {
            const key = m.league.id || m.league.name;
            if (!leagueMap[key]) leagueMap[key] = { league: m.league, matches: [] };
            leagueMap[key].matches.push(m);
        }

        const leagues = Object.values(leagueMap).sort((a, b) => {
            const ra = priorityRank(a.league.name), rb = priorityRank(b.league.name);
            if (ra !== rb) return ra - rb;
            return a.league.name.localeCompare(b.league.name);
        });
        leagues.forEach(g => g.matches.sort((a, b) => a.timestamp - b.timestamp));

        const cacheSec = tab === 'yesterday' ? 86400 : tab === 'tomorrow' ? 7200 : 1800;
        res.setHeader('Cache-Control', `s-maxage=${cacheSec}, stale-while-revalidate=${Math.floor(cacheSec / 2)}`);
        return res.status(200).json({ tab, date, total: matches.length, leagues });
    } catch (err) {
        console.error('[match-schedule]', err.message);
        res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=30');
        return res.status(500).json({ error: 'Failed to fetch schedule' });
    }
}
