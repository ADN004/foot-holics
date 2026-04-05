/**
 * Vercel Serverless Function — Live Match Score
 * Route: /api/livescore?home=Barcelona&away=Atletico+Madrid&league=esp.1&date=2026-04-04
 *
 * Searches ESPN scoreboard for a specific match and returns live score data.
 * Source: ESPN Soccer API (public, no key required)
 * Cache: 30 seconds during live matches
 */

const ESPN_LEAGUES = [
  'eng.1',           // Premier League
  'esp.1',           // La Liga
  'ger.1',           // Bundesliga
  'ita.1',           // Serie A
  'fra.1',           // Ligue 1
  'UEFA.CHAMPIONS',  // Champions League
  'eng.2',           // Championship
  'usa.1',           // MLS
  'ind.1',           // Indian Super League
];

// Map Foot Holics league slugs → ESPN codes
const SLUG_TO_ESPN = {
  'premier-league':   ['eng.1'],
  'laliga':           ['esp.1'],
  'bundesliga':       ['ger.1'],
  'serie-a':          ['ita.1'],
  'ligue-1':          ['fra.1'],
  'champions-league': ['UEFA.CHAMPIONS'],
  'wc':               ['FIFA.WORLDQ.UEFA', 'FIFA.WORLD'],
  'nationals':        ['FIFA.WORLDQ.UEFA', 'UEFA.NATIONS.A'],
  'others':           ['usa.1', 'ind.1', 'eng.2', 'mex.1', 'arg.1'],
};

function fuzzyMatch(a, b) {
  if (!a || !b) return false;
  const norm = (s) => s.toLowerCase().replace(/[^a-z0-9\s]/g, '').replace(/\s+/g, ' ').trim();
  const na = norm(a);
  const nb = norm(b);
  return na.includes(nb) || nb.includes(na);
}

async function fetchScoreboard(league, dateStr) {
  // dateStr format: YYYYMMDD
  const url = `https://site.api.espn.com/apis/site/v2/sports/soccer/${league}/scoreboard?dates=${dateStr}&limit=50`;
  try {
    const res = await fetch(url, {
      headers: { 'User-Agent': 'Mozilla/5.0 (compatible; FootHolics/1.0)' },
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.events || [];
  } catch {
    return [];
  }
}

function parseGoalEvents(details, competitors) {
  if (!details || !details.length) return [];
  const events = [];

  details.forEach((d) => {
    const typeText = d.type?.text?.toLowerCase() || '';
    if (!typeText.includes('goal')) return;

    const scorer = d.athletesInvolved?.[0]?.displayName || '';
    const minute = d.clock?.displayValue || '';
    const teamId = d.team?.id;

    // Find which side this team is on
    let side = '';
    if (teamId && competitors) {
      const comp = competitors.find((c) => c.team?.id === teamId);
      if (comp) side = comp.homeAway === 'home' ? 'home' : 'away';
    }

    if (scorer) {
      events.push({ scorer, minute, side, type: typeText.includes('own') ? 'og' : 'goal' });
    }
  });

  return events;
}

export default async function handler(req, res) {
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    return res.status(200).end();
  }

  res.setHeader('Access-Control-Allow-Origin', '*');

  const { home, away, league, date } = req.query;

  if (!home || !away) {
    return res.status(400).json({ error: 'home and away params required' });
  }

  // Build date string for ESPN (YYYYMMDD from YYYY-MM-DD or today)
  let dateStr;
  if (date) {
    dateStr = date.replace(/-/g, '');
  } else {
    const d = new Date();
    const pad = (n) => String(n).padStart(2, '0');
    dateStr = `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
  }

  // Determine which leagues to search
  let leaguesToSearch;
  if (league && ESPN_LEAGUES.includes(league)) {
    leaguesToSearch = [league];
  } else if (league && SLUG_TO_ESPN[league]) {
    leaguesToSearch = SLUG_TO_ESPN[league];
  } else {
    leaguesToSearch = ESPN_LEAGUES;
  }

  // Also search adjacent days in case of timezone differences
  const dateObj = new Date(date || Date.now());
  const prevDate = new Date(dateObj);
  prevDate.setDate(prevDate.getDate() - 1);
  const nextDate = new Date(dateObj);
  nextDate.setDate(nextDate.getDate() + 1);
  const pad = (n) => String(n).padStart(2, '0');
  const prevDateStr = `${prevDate.getFullYear()}${pad(prevDate.getMonth() + 1)}${pad(prevDate.getDate())}`;
  const nextDateStr = `${nextDate.getFullYear()}${pad(nextDate.getMonth() + 1)}${pad(nextDate.getDate())}`;

  const allDates = [...new Set([prevDateStr, dateStr, nextDateStr])];

  // Fetch scoreboards in parallel
  const allFetches = [];
  for (const l of leaguesToSearch) {
    for (const d of allDates) {
      allFetches.push(fetchScoreboard(l, d));
    }
  }

  const results = await Promise.all(allFetches);
  const allEvents = results.flat();

  // Find the match
  let found = null;
  for (const ev of allEvents) {
    const comp = ev.competitions?.[0];
    if (!comp) continue;
    const homeComp = comp.competitors?.find((c) => c.homeAway === 'home');
    const awayComp = comp.competitors?.find((c) => c.homeAway === 'away');
    if (!homeComp || !awayComp) continue;

    const homeMatch = fuzzyMatch(home, homeComp.team?.displayName) || fuzzyMatch(home, homeComp.team?.shortDisplayName);
    const awayMatch = fuzzyMatch(away, awayComp.team?.displayName) || fuzzyMatch(away, awayComp.team?.shortDisplayName);

    if (homeMatch && awayMatch) {
      found = { ev, comp, homeComp, awayComp };
      break;
    }

    // Also try swapped (in case home/away was reversed in our data)
    const homeMatchSwap = fuzzyMatch(away, homeComp.team?.displayName) || fuzzyMatch(away, homeComp.team?.shortDisplayName);
    const awayMatchSwap = fuzzyMatch(home, awayComp.team?.displayName) || fuzzyMatch(home, awayComp.team?.shortDisplayName);
    if (homeMatchSwap && awayMatchSwap) {
      // Swap the sides back
      found = { ev, comp, homeComp: awayComp, awayComp: homeComp, swapped: true };
      break;
    }
  }

  if (!found) {
    // Match not found — return a "not found" state (page will show countdown/kickoff time)
    res.setHeader('Cache-Control', 's-maxage=300, stale-while-revalidate=600');
    return res.status(200).json({ found: false });
  }

  const { comp, homeComp, awayComp } = found;
  const status = comp.status?.type;
  const state = status?.state || 'pre';
  const isLive = state === 'in';
  const isCompleted = status?.completed || false;
  const description = status?.description || 'Scheduled';
  const detail = status?.shortDetail || status?.detail || description;
  const minute = isLive ? (status?.detail || '') : '';
  const period = comp.status?.period || 0;

  const homeScore = homeComp.score ?? null;
  const awayScore = awayComp.score ?? null;

  const goalEvents = parseGoalEvents(comp.details, comp.competitors);

  // Cache aggressively when live, more lax otherwise
  const cacheSeconds = isLive ? 30 : isCompleted ? 3600 : 120;
  res.setHeader('Cache-Control', `s-maxage=${cacheSeconds}, stale-while-revalidate=${cacheSeconds * 2}`);

  return res.status(200).json({
    found: true,
    state,        // 'pre' | 'in' | 'post'
    isLive,
    isCompleted,
    description,
    detail,
    minute,
    period,
    homeScore,
    awayScore,
    homeTeam: homeComp.team?.displayName || home,
    awayTeam: awayComp.team?.displayName || away,
    goalEvents,
    matchDate: found.ev.date,
  });
}
