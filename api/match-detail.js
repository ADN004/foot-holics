/**
 * /api/match-detail?id=ESPN_EVENT_ID
 *
 * ESPN-based, KEYLESS, no daily quota. Returns full match data in one summary
 * call, reshaped into the api-football-style shape the match centre renders:
 *   { fixture, events, lineups, stats, h2h, homeForm, awayForm }
 *
 * ESPN resolves the summary by event id regardless of the league in the path,
 * so a single fixed slug works for every competition.
 *
 * Verified from ESPN: boxscore (stats), headToHeadGames (h2h), lastFiveGames
 * (form), header (score/status). Lineups (rosters) and the goal-by-goal events
 * are best-effort — ESPN's coverage of those varies by competition.
 */

import { ESPN_BASE, getJson, teamMatch } from '../lib/espn.js';

const SLUG = 'eng.1'; // any valid soccer slug — summary resolves by event id

const toInt = v => (v == null || v === '' || isNaN(parseInt(v, 10))) ? null : parseInt(v, 10);
const num = v => { const n = parseFloat(String(v == null ? '' : v).replace('%', '')); return isNaN(n) ? 0 : n; };

function shortStatus(state) {
    if (state === 'pre') return 'NS';
    if (state === 'post') return 'FT';
    return '1H'; // live
}

function teamLogo(team) {
    if (!team) return '';
    if (team.logo) return team.logo;
    return (team.logos && team.logos[0] && team.logos[0].href) || '';
}

// ── Fixture header (score / status / teams / venue) ─────────────────────
function reshapeFixture(summary) {
    const header = summary.header || {};
    const hc = (header.competitions && header.competitions[0]) || {};
    const comps = hc.competitors || [];
    const h = comps.find(c => c.homeAway === 'home') || comps[0] || {};
    const a = comps.find(c => c.homeAway === 'away') || comps[1] || {};
    const st = hc.status || {};
    const state = st.type && st.type.state;
    const gh = toInt(h.score), ga = toInt(a.score);
    const venueObj = (summary.gameInfo && summary.gameInfo.venue) || hc.venue || null;
    const team = c => ({
        id: c.team ? String(c.team.id) : null,
        name: c.team ? c.team.displayName : '',
        logo: teamLogo(c.team),
    });
    return {
        fixture: {
            id: header.id || null,
            date: hc.date || null,
            status: { short: shortStatus(state), elapsed: parseInt(st.displayClock, 10) || null },
            venue: venueObj ? { name: venueObj.fullName || venueObj.name || '' } : null,
        },
        league: { name: (header.league && header.league.name) || '' },
        teams: { home: team(h), away: team(a) },
        goals: { home: gh, away: ga },
        score: { halftime: { home: null, away: null }, fulltime: { home: gh, away: ga } },
    };
}

// ── Team statistics ─────────────────────────────────────────────────────
function reshapeStats(summary) {
    const teams = (summary.boxscore && summary.boxscore.teams) || [];
    if (!teams.length) return [];
    const raw = (t, name) => {
        const s = (t.statistics || []).find(x => x.name === name);
        return s ? s.displayValue : null;
    };
    return teams.map(t => {
        const total = num(raw(t, 'totalShots')), on = num(raw(t, 'shotsOnTarget'));
        const poss = raw(t, 'possessionPct');
        return {
            team: { id: t.team ? String(t.team.id) : null, name: t.team ? t.team.displayName : '' },
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

// ── Convert an ESPN per-team "events" block (h2h / lastFive) → meetings list ──
function reshapeMeetings(block) {
    if (!block || !Array.isArray(block.events)) return [];
    const persp = (block.team && block.team.displayName) || '';
    return block.events.map(e => {
        const homeIsPersp = e.atVs === 'vs';
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

// ── Lineups (ESPN rosters — formation + starting XI) ────────────────────
function reshapeLineups(summary) {
    const rosters = (summary.rosters || []).slice()
        .sort((a, b) => (a.homeAway === 'home' ? -1 : 1)); // home first (match.html expects [home, away])
    return rosters.map(r => {
        const startXI = (r.roster || []).filter(p => p.starter).map(p => {
            const ath = p.athlete || {};
            return {
                player: {
                    id: ath.id ? String(ath.id) : null,
                    name: ath.displayName || ath.shortName || '',
                    number: p.jersey || ath.jersey || null,
                    pos: (p.position && (p.position.abbreviation || p.position.name)) || null,
                },
            };
        });
        return {
            team: { id: r.team ? String(r.team.id) : null, name: r.team ? r.team.displayName : '' },
            formation: r.formation || '',
            startXI,
        };
    });
}

// ── Goal/card/sub events (ESPN keyEvents — minute + type only; ESPN does not
// attach player/team to these, so those fields stay blank). ───────────────
function reshapeEvents(summary) {
    const ke = summary.keyEvents || [];
    if (!Array.isArray(ke)) return [];
    const out = [];
    for (const e of ke) {
        const kind = (e.type && (e.type.type || '')).toLowerCase();
        const text = (e.type && e.type.text) || '';
        let type = null;
        if (e.scoringPlay || /goal/.test(kind)) type = 'Goal';
        else if (/card|yellow|red/.test(kind)) type = 'Card';
        else if (/sub/.test(kind)) type = 'subst';
        else continue; // skip kickoff / end-of-half / VAR / etc.
        const clock = (e.clock && e.clock.displayValue) || '';
        out.push({
            time: { elapsed: parseInt(clock, 10) || 0, extra: null },
            team: { id: null },
            type,
            detail: text,
            player: { name: '' },  // ESPN keyEvents carry no player name
            assist: { name: '' },
        });
    }
    return out;
}

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    if (req.method === 'OPTIONS') return res.status(200).end();

    const { id } = req.query;
    if (!id) return res.status(400).json({ error: 'event id required' });

    try {
        const summary = await getJson(`${ESPN_BASE}/${SLUG}/summary?event=${id}`);

        const fixture = reshapeFixture(summary);
        const stats   = reshapeStats(summary);
        const lineups = reshapeLineups(summary);
        const events  = reshapeEvents(summary);
        const h2h     = reshapeMeetings(summary.headToHeadGames && summary.headToHeadGames[0]);

        // Recent form: match each lastFiveGames block to home/away by name.
        const lf = summary.lastFiveGames || [];
        const homeName = fixture.teams.home.name, awayName = fixture.teams.away.name;
        const homeBlock = lf.find(b => b.team && teamMatch(b.team.displayName, homeName)) || lf[0];
        const awayBlock = lf.find(b => b.team && teamMatch(b.team.displayName, awayName)) || lf[1];
        const homeForm = reshapeMeetings(homeBlock);
        const awayForm = reshapeMeetings(awayBlock);

        const short = fixture.fixture.status.short;
        const cacheSec = short === 'FT' ? 86400 : short === 'NS' ? 1800 : 900;
        res.setHeader('Cache-Control', `s-maxage=${cacheSec}, stale-while-revalidate=${Math.floor(cacheSec / 2)}`);
        return res.status(200).json({ fixture, events, lineups, stats, h2h, homeForm, awayForm });
    } catch (err) {
        console.error('[match-detail]', err.message);
        res.setHeader('Cache-Control', 's-maxage=60, stale-while-revalidate=30');
        return res.status(500).json({ error: 'Failed to fetch match detail' });
    }
}
