/**
 * Shared helpers for ESPN's keyless soccer site API.
 * Imported by the /api endpoints (match-info, match-live, …).
 */

export const ESPN_BASE = 'https://site.api.espn.com/apis/site/v2/sports/soccer';

// bot leagueSlug → ESPN league slug candidates (tried in order until the fixture
// is found). International matches span several ESPN competitions.
export const ESPN_LEAGUES = {
    'premier-league':    ['eng.1'],
    'laliga':            ['esp.1'],
    'la-liga':           ['esp.1'],
    'serie-a':           ['ita.1'],
    'bundesliga':        ['ger.1'],
    'ligue-1':           ['fra.1'],
    'champions-league':  ['uefa.champions'],
    'europa-league':     ['uefa.europa'],
    'conference-league': ['uefa.europa.conf'],
    'wc':                ['fifa.world', 'fifa.friendly', 'fifa.worldq.conmebol',
                          'fifa.worldq.uefa', 'fifa.worldq.concacaf', 'fifa.worldq.afc',
                          'fifa.worldq.caf'],
    'nationals':         ['fifa.friendly', 'fifa.world', 'uefa.nations'],
};

// Best-effort sweep for unmapped leagues ("others" etc.).
export const FALLBACK_SLUGS = ['eng.1', 'esp.1', 'ita.1', 'ger.1', 'fra.1',
    'uefa.champions', 'fifa.world', 'fifa.friendly', 'usa.1', 'mex.1', 'bra.1'];

// ── Team-name canonicalisation + fuzzy matching ─────────────────────────
// Maps the operator's wording (and common variants/typos) onto a canonical form
// so "USA"↔"United States", "Bosnia and Herzegovina"↔"Bosnia-Herzegovina",
// "Czecia"↔"Czechia" all match ESPN's naming.
const ALIASES = {
    'usa': 'united states', 'us': 'united states', 'united states of america': 'united states',
    'bosnia and herzegovina': 'bosnia herzegovina', 'bosnia': 'bosnia herzegovina',
    'czech republic': 'czechia', 'czecia': 'czechia',
    'korea republic': 'south korea', 'korea dpr': 'north korea',
    "cote d ivoire": 'cote divoire', 'ivory coast': 'cote divoire',
    'china pr': 'china', 'uae': 'united arab emirates',
    'dr congo': 'congo dr', 'democratic republic of the congo': 'congo dr',
    'cape verde islands': 'cape verde',
    'man city': 'manchester city', 'man utd': 'manchester united', 'man united': 'manchester united',
    'spurs': 'tottenham hotspur', 'tottenham': 'tottenham hotspur',
    'wolves': 'wolverhampton wanderers', 'psg': 'paris saint germain',
    'inter': 'internazionale', 'inter milan': 'internazionale',
    'atletico': 'atletico madrid', 'barca': 'barcelona',
    'bayern': 'bayern munich', 'bayern munchen': 'bayern munich',
    'dortmund': 'borussia dortmund',
};

function stripAccents(s) {
    return s.normalize('NFD').replace(/[̀-ͯ]/g, '');
}

export function normTeam(s) {
    return stripAccents(String(s || '')).toLowerCase()
        .replace(/&/g, ' and ')
        .replace(/[^a-z0-9 ]/g, ' ')   // drop hyphens/dots/apostrophes/punctuation
        .replace(/\b(fc|afc|cf|ac|as|rc|rcd|sc|ss|sv|sk|fk|cd|ud)\b/g, ' ') // club prefixes
        .replace(/\s+/g, ' ').trim();
}

export function canonTeam(s) {
    const n = normTeam(s);
    return ALIASES[n] || n;
}

// Levenshtein with an early-out — used only for typo tolerance on short names.
function lev(a, b) {
    if (Math.abs(a.length - b.length) > 3) return 99;
    const dp = Array.from({ length: a.length + 1 }, (_, i) => {
        const row = new Array(b.length + 1).fill(0);
        row[0] = i;
        return row;
    });
    for (let j = 0; j <= b.length; j++) dp[0][j] = j;
    for (let i = 1; i <= a.length; i++)
        for (let j = 1; j <= b.length; j++)
            dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1,
                dp[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    return dp[a.length][b.length];
}

export function teamMatch(a, b) {
    a = canonTeam(a); b = canonTeam(b);
    if (!a || !b) return false;
    if (a === b) return true;
    if (a.includes(b) || b.includes(a)) return true;
    // significant shared token ("bosnia herzegovina" vs "herzegovina")
    const ta = a.split(' ').filter(t => t.length >= 4);
    const sb = new Set(b.split(' ').filter(t => t.length >= 4));
    if (ta.some(t => sb.has(t))) return true;
    // typo tolerance for single-word names ("czecia" vs "czechia")
    if (!a.includes(' ') && !b.includes(' ') &&
        Math.max(a.length, b.length) >= 5 && lev(a, b) <= 2) return true;
    return false;
}

export function espnDate(iso) { return String(iso || '').replace(/-/g, ''); }

export function prevEspnDate(iso) {
    const d = new Date(iso + 'T12:00:00Z');
    d.setUTCDate(d.getUTCDate() - 1);
    return d.toISOString().slice(0, 10).replace(/-/g, '');
}

export async function getJson(url) {
    const r = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!r.ok) throw new Error(`espn ${r.status} on ${url}`);
    return r.json();
}

// Find the ESPN event for a match by scanning candidate leagues across given dates.
// Returns { id, slug, event } (event = raw scoreboard event) or null.
export async function findEvent(slugs, dates, home, away) {
    for (const date of dates) {
        for (const slug of slugs) {
            let data;
            try { data = await getJson(`${ESPN_BASE}/${slug}/scoreboard?dates=${date}`); }
            catch { continue; }
            for (const ev of (data.events || [])) {
                const comp = ev.competitions && ev.competitions[0];
                const cs = (comp && comp.competitors) || [];
                const h = cs.find(c => c.homeAway === 'home');
                const a = cs.find(c => c.homeAway === 'away');
                if (!h || !a) continue;
                const hn = h.team && h.team.displayName;
                const an = a.team && a.team.displayName;
                if ((teamMatch(hn, home) && teamMatch(an, away)) ||
                    (teamMatch(hn, away) && teamMatch(an, home))) {
                    return { id: ev.id, slug, event: ev };
                }
            }
        }
    }
    return null;
}
