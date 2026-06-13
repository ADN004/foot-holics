/**
 * /api/match-live?id=EVENT_ID&league=ESPN_SLUG&date=YYYY-MM-DD
 *
 * ESPN-based, KEYLESS, no daily quota. Returns live score + status (from the
 * scoreboard) and match statistics (from the summary boxscore), reshaped into
 * the api-football-style shape the live detail page already renders:
 *   { fixture: {...}, stats: [ { team:{name}, statistics:[{type,value}] } ] }
 *
 * `id`/`league` come from /api/match-info; `date` is the match's IST date.
 * Finished matches are cached ~permanently (their stats never change).
 */

import { ESPN_BASE, FALLBACK_SLUGS, getJson, espnDate, prevEspnDate } from '../lib/espn.js';

// ESPN status state → the short code the frontend branches on (NS / FT / live).
function shortStatus(state) {
    if (state === 'pre') return 'NS';
    if (state === 'post') return 'FT';
    return '1H'; // 'in' → any non-NS/FT code makes the frontend show LIVE + minute
}

// Map ESPN boxscore team stats → the {team, statistics:[{type,value}]} shape.
function reshapeStats(summary) {
    const teams = (summary && summary.boxscore && summary.boxscore.teams) || [];
    if (!teams.length) return null;
    const num = v => {
        const n = parseFloat(String(v == null ? '' : v).replace('%', ''));
        return isNaN(n) ? 0 : n;
    };
    const raw = (t, name) => {
        const s = (t.statistics || []).find(x => x.name === name);
        return s ? s.displayValue : null;
    };
    return teams.map(t => {
        const total = num(raw(t, 'totalShots'));
        const on = num(raw(t, 'shotsOnTarget'));
        const poss = raw(t, 'possessionPct');
        return {
            team: { name: t.team && t.team.displayName },
            statistics: [
                { type: 'Ball Possession', value: (poss != null ? poss : 0) + '%' },
                { type: 'Total Shots',     value: total },
                { type: 'Shots on Goal',   value: on },
                { type: 'Shots off Goal',  value: Math.max(0, total - on) },
                { type: 'Corner Kicks',    value: num(raw(t, 'wonCorners')) },
                { type: 'Fouls',           value: num(raw(t, 'foulsCommitted')) },
                { type: 'Yellow Cards',    value: num(raw(t, 'yellowCards')) },
                { type: 'Red Cards',       value: num(raw(t, 'redCards')) },
                { type: 'Offsides',        value: num(raw(t, 'offsides')) },
            ],
        };
    });
}

// Reshape a raw ESPN scoreboard event → api-football-like fixture (score/status/events).
function reshapeFixture(scEvent) {
    const comp = (scEvent.competitions && scEvent.competitions[0]) || {};
    const cs = comp.competitors || [];
    const h = cs.find(c => c.homeAway === 'home') || cs[0] || {};
    const a = cs.find(c => c.homeAway === 'away') || cs[1] || {};
    const st = comp.status || scEvent.status || {};
    const state = st.type && st.type.state;
    const elapsed = parseInt(st.displayClock, 10);
    const toScore = v => (v == null || v === '' || isNaN(parseInt(v, 10))) ? null : parseInt(v, 10);
    const gh = toScore(h.score), ga = toScore(a.score);

    // Best-effort goal/card events from the scoreboard competition "details".
    const events = (comp.details || []).map(d => {
        const text = (d.type && d.type.text) || '';
        const type = /goal/i.test(text) ? 'Goal' : /card/i.test(text) ? 'Card' : text;
        const ath = (d.athletesInvolved && d.athletesInvolved[0]) || null;
        return {
            time: { elapsed: d.clock ? parseInt(d.clock.displayValue, 10) || 0 : 0, extra: null },
            team: { id: d.team ? String(d.team.id) : null },
            type,
            detail: text,
            player: { name: ath ? ath.displayName : '' },
            assist: { name: '' },
        };
    });

    return {
        fixture: { status: { short: shortStatus(state), elapsed: isNaN(elapsed) ? null : elapsed } },
        goals: { home: gh, away: ga },
        score: { halftime: { home: null, away: null }, fulltime: { home: gh, away: ga } },
        events,
        teams: {
            home: { id: String(h.id || (h.team && h.team.id) || '') },
            away: { id: String(a.id || (a.team && a.team.id) || '') },
        },
    };
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    if (req.method === 'OPTIONS') return res.status(200).end();

    const { id, league, date } = req.query;
    if (!id) return res.status(400).json({ error: 'event id required' });

    try {
        const slugs = league ? [league] : FALLBACK_SLUGS;
        const dates = date ? [espnDate(date), prevEspnDate(date)] : [espnDate(new Date().toISOString().slice(0, 10))];

        // 1) Locate the scoreboard event (score + status).
        let scEvent = null;
        for (const d of dates) {
            for (const slug of slugs) {
                let data;
                try { data = await getJson(`${ESPN_BASE}/${slug}/scoreboard?dates=${d}`); }
                catch { continue; }
                const e = (data.events || []).find(x => String(x.id) === String(id));
                if (e) { scEvent = e; break; }
            }
            if (scEvent) break;
        }

        // 2) Stats from the summary boxscore (needs the league slug).
        let stats = null;
        if (league) {
            try {
                const summary = await getJson(`${ESPN_BASE}/${league}/summary?event=${id}`);
                stats = reshapeStats(summary);
            } catch { /* stats unavailable — fixture/score still returned */ }
        }

        const fixture = scEvent ? reshapeFixture(scEvent) : null;

        // Cache by status: live=10min, upcoming=30min, finished=~permanent.
        const short = fixture && fixture.fixture.status.short;
        const cacheSec = short === 'FT' ? 2592000 : short === 'NS' ? 1800 : 600;
        res.setHeader('Cache-Control', `s-maxage=${cacheSec}, stale-while-revalidate=${Math.floor(cacheSec / 2)}`);
        return res.status(200).json({ fixture, stats });
    } catch (err) {
        console.error('[match-live]', err.message);
        res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=30');
        return res.status(500).json({ error: 'Failed to fetch live data' });
    }
}
