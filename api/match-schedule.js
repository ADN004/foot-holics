/**
 * /api/match-schedule?tab=yesterday|today|tomorrow
 *
 * Returns all worldwide football fixtures for a given day,
 * grouped by league with major leagues sorted first.
 *
 * Source: api-football.com v3
 * Cache:  yesterday → 24 h | tomorrow → 2 h | today → 30 min
 */

const API_KEY  = 'b9c4d6e0be048bb79d8cf819e12775af';
const API_BASE = 'https://v3.football.api-sports.io';

// Lower index = higher priority in sort
const PRIORITY_IDS = [
    1, 2, 3, 4, 5, 6,           // World Cup, UCL, Europa, Conference, etc.
    13, 39, 61, 78, 88, 94,     // PL, Ligue 1, Bundesliga, Eredivisie, PL2
    135, 140, 143, 203,          // Serie A, La Liga, Copa del Rey, Süper Lig
    253, 307, 332, 848,          // MLS, Saudi Pro, Argentine Liga, Conference
];

function istNow() {
    return new Date(Date.now() + 5.5 * 3600_000);
}

function tabToDate(tab) {
    const d = istNow();
    if (tab === 'yesterday') d.setDate(d.getDate() - 1);
    if (tab === 'tomorrow')  d.setDate(d.getDate() + 1);
    return d.toISOString().slice(0, 10); // YYYY-MM-DD
}

function normMatch(f) {
    return {
        id:        f.fixture.id,
        date:      f.fixture.date,
        timestamp: f.fixture.timestamp,
        status: {
            long:    f.fixture.status.long,
            short:   f.fixture.status.short,
            elapsed: f.fixture.status.elapsed,
        },
        venue: f.fixture.venue
            ? { name: f.fixture.venue.name, city: f.fixture.venue.city }
            : null,
        league: {
            id:      f.league.id,
            name:    f.league.name,
            country: f.league.country,
            logo:    f.league.logo,
            flag:    f.league.flag,
            season:  f.league.season,
            round:   f.league.round,
        },
        home: {
            id:     f.teams.home.id,
            name:   f.teams.home.name,
            logo:   f.teams.home.logo,
            winner: f.teams.home.winner,
        },
        away: {
            id:     f.teams.away.id,
            name:   f.teams.away.name,
            logo:   f.teams.away.logo,
            winner: f.teams.away.winner,
        },
        goals: f.goals,
        score: f.score,
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
        const r = await fetch(
            `${API_BASE}/fixtures?date=${date}&timezone=Asia%2FKolkata`,
            { headers: { 'x-apisports-key': API_KEY, Accept: 'application/json' } }
        );
        if (!r.ok) throw new Error(`api-sports ${r.status}`);
        const data = await r.json();

        const matches = (data.response || []).map(normMatch);

        // Group by league
        const leagueMap = {};
        for (const m of matches) {
            const key = m.league.id;
            if (!leagueMap[key]) leagueMap[key] = { league: m.league, matches: [] };
            leagueMap[key].matches.push(m);
        }

        // Sort leagues: priority list first, then country → name
        const leagues = Object.values(leagueMap).sort((a, b) => {
            const pa = PRIORITY_IDS.indexOf(a.league.id);
            const pb = PRIORITY_IDS.indexOf(b.league.id);
            if (pa !== -1 && pb !== -1) return pa - pb;
            if (pa !== -1) return -1;
            if (pb !== -1) return 1;
            const cc = a.league.country.localeCompare(b.league.country);
            return cc !== 0 ? cc : a.league.name.localeCompare(b.league.name);
        });

        // Sort matches within each league by kick-off
        leagues.forEach(g => g.matches.sort((a, b) => a.timestamp - b.timestamp));

        const cacheSec = tab === 'yesterday' ? 86400 : tab === 'tomorrow' ? 7200 : 1800;
        res.setHeader('Cache-Control', `s-maxage=${cacheSec}, stale-while-revalidate=${cacheSec / 2}`);
        return res.status(200).json({ tab, date, total: matches.length, leagues });

    } catch (err) {
        console.error('[match-schedule]', err.message);
        res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=30');
        return res.status(500).json({ error: 'Failed to fetch schedule' });
    }
}
