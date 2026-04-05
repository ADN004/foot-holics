/**
 * Foot Holics — Live Score Widget
 * Reads data attributes from #liveScoreWidget and fetches live score from /api/livescore
 * Polls every 30 seconds during the 2-hour match window.
 */
(function () {
    'use strict';

    var widget = document.getElementById('liveScoreWidget');
    if (!widget) return;

    var homeTeam   = widget.dataset.home   || '';
    var awayTeam   = widget.dataset.away   || '';
    var leagueSlug = widget.dataset.league || '';
    var matchDate  = widget.dataset.date   || '';   // ISO: "2026-04-04T19:00:00Z"
    var homeLogo   = widget.dataset.homeLogo || '';
    var awayLogo   = widget.dataset.awayLogo || '';

    var dateOnly = matchDate ? matchDate.slice(0, 10) : '';

    var SLUG_MAP = {
        'premier-league':   'eng.1',
        'laliga':           'esp.1',
        'bundesliga':       'ger.1',
        'serie-a':          'ita.1',
        'ligue-1':          'fra.1',
        'champions-league': 'UEFA.CHAMPIONS',
    };
    var espnLeague = SLUG_MAP[leagueSlug] || leagueSlug || '';

    var apiUrl = '/api/livescore?home=' + encodeURIComponent(homeTeam)
               + '&away=' + encodeURIComponent(awayTeam)
               + (espnLeague ? '&league=' + encodeURIComponent(espnLeague) : '')
               + (dateOnly  ? '&date='   + encodeURIComponent(dateOnly)   : '');

    var kickoffTime = matchDate ? new Date(matchDate) : null;
    var countdownInterval = null;
    var pollInterval = null;

    function esc(s) {
        if (!s) return '';
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    function logoImg(src, name) {
        if (!src || src === '#') return '';
        return '<img src="' + esc(src) + '" alt="' + esc(name) + '" class="ls-team-logo" loading="lazy" onerror="this.style.display=\'none\'">';
    }

    function pad(n) { return n < 10 ? '0' + String(n) : String(n); }

    function formatCountdown(ms) {
        if (ms <= 0) return '00:00:00';
        var s = Math.floor(ms / 1000);
        var h = Math.floor(s / 3600);
        var m = Math.floor((s % 3600) / 60);
        var sec = s % 60;
        return pad(h) + ':' + pad(m) + ':' + pad(sec);
    }

    function goalHtml(events, side) {
        return events
            .filter(function (e) { return e.side === side; })
            .map(function (e) {
                return '<span class="ls-goal-event">'
                    + '<span class="scorer">&#9917; ' + esc(e.scorer) + '</span> '
                    + '<span class="minute">' + esc(e.minute) + '</span>'
                    + '</span>';
            })
            .join('');
    }

    function setWidget(html) {
        widget.innerHTML = html;
    }

    function renderUpcoming() {
        if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }

        var timeStr = kickoffTime
            ? kickoffTime.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC'
            : '';

        setWidget(
            '<div class="ls-status-bar upcoming-status"><span>&#9200;</span> <span>UPCOMING</span></div>'
            + '<div class="ls-scoreboard">'
                + '<div class="ls-team-col">' + logoImg(homeLogo, homeTeam) + '<span class="ls-team-name">' + esc(homeTeam) + '</span></div>'
                + '<div class="ls-score-col">'
                    + '<div class="ls-countdown" id="lsCountdown">--:--:--</div>'
                    + (timeStr ? '<div class="ls-kickoff-time">Kick off ' + esc(timeStr) + '</div>' : '')
                + '</div>'
                + '<div class="ls-team-col">' + logoImg(awayLogo, awayTeam) + '<span class="ls-team-name">' + esc(awayTeam) + '</span></div>'
            + '</div>'
            + '<p class="ls-powered">Live data via ESPN</p>'
        );

        var cdEl = document.getElementById('lsCountdown');
        if (cdEl && kickoffTime) {
            function tick() {
                var remaining = kickoffTime.getTime() - Date.now();
                cdEl.textContent = remaining > 0 ? formatCountdown(remaining) : '00:00:00';
            }
            tick();
            countdownInterval = setInterval(tick, 1000);
        }
    }

    function renderLive(data) {
        if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
        widget.classList.add('is-live');
        widget.classList.remove('is-finished');

        var hg = goalHtml(data.goalEvents || [], 'home');
        var ag = goalHtml(data.goalEvents || [], 'away');
        var eventsBlock = (hg || ag)
            ? '<div class="ls-events"><div class="ls-events-side home">' + hg + '</div><div class="ls-events-side away">' + ag + '</div></div>'
            : '';

        setWidget(
            '<div class="ls-status-bar live-status">'
                + '<span style="width:8px;height:8px;background:#ef4444;border-radius:50%;display:inline-block;animation:blink 1.5s infinite;"></span>'
                + ' <span>LIVE &bull; ' + esc(data.minute || data.detail || '') + '</span>'
            + '</div>'
            + '<div class="ls-scoreboard">'
                + '<div class="ls-team-col">' + logoImg(homeLogo, homeTeam) + '<span class="ls-team-name">' + esc(data.homeTeam || homeTeam) + '</span></div>'
                + '<div class="ls-score-col"><div class="ls-score-display">'
                    + '<span class="ls-score">' + esc(data.homeScore !== null && data.homeScore !== undefined ? String(data.homeScore) : '-') + '</span>'
                    + '<span class="ls-score-sep">:</span>'
                    + '<span class="ls-score">' + esc(data.awayScore !== null && data.awayScore !== undefined ? String(data.awayScore) : '-') + '</span>'
                + '</div></div>'
                + '<div class="ls-team-col">' + logoImg(awayLogo, awayTeam) + '<span class="ls-team-name">' + esc(data.awayTeam || awayTeam) + '</span></div>'
            + '</div>'
            + eventsBlock
            + '<p class="ls-powered">Live data via ESPN &bull; updates every 30s</p>'
        );
    }

    function renderFinished(data) {
        if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
        if (pollInterval)      { clearInterval(pollInterval);      pollInterval = null; }
        widget.classList.remove('is-live');
        widget.classList.add('is-finished');

        var hg = goalHtml(data.goalEvents || [], 'home');
        var ag = goalHtml(data.goalEvents || [], 'away');
        var eventsBlock = (hg || ag)
            ? '<div class="ls-events"><div class="ls-events-side home">' + hg + '</div><div class="ls-events-side away">' + ag + '</div></div>'
            : '';

        setWidget(
            '<div class="ls-status-bar finished-status"><span>&#10003;</span> <span>FULL TIME</span></div>'
            + '<div class="ls-scoreboard">'
                + '<div class="ls-team-col">' + logoImg(homeLogo, homeTeam) + '<span class="ls-team-name">' + esc(data.homeTeam || homeTeam) + '</span></div>'
                + '<div class="ls-score-col"><div class="ls-score-display">'
                    + '<span class="ls-score">' + esc(data.homeScore !== null && data.homeScore !== undefined ? String(data.homeScore) : '-') + '</span>'
                    + '<span class="ls-score-sep">:</span>'
                    + '<span class="ls-score">' + esc(data.awayScore !== null && data.awayScore !== undefined ? String(data.awayScore) : '-') + '</span>'
                + '</div></div>'
                + '<div class="ls-team-col">' + logoImg(awayLogo, awayTeam) + '<span class="ls-team-name">' + esc(data.awayTeam || awayTeam) + '</span></div>'
            + '</div>'
            + eventsBlock
            + '<p class="ls-powered">Final score via ESPN</p>'
        );
    }

    async function fetchScore() {
        try {
            var res = await fetch(apiUrl);
            if (!res.ok) throw new Error('API error');
            var data = await res.json();
            if (!data.found) {
                renderUpcoming();
                return;
            }
            if (data.isCompleted || data.state === 'post') {
                renderFinished(data);
            } else if (data.isLive || data.state === 'in') {
                renderLive(data);
            } else {
                renderUpcoming();
            }
        } catch {
            renderUpcoming();
        }
    }

    // Initial load
    fetchScore();

    // Poll during 2-hour match window
    if (kickoffTime) {
        var windowStart = kickoffTime.getTime() - 5  * 60 * 1000;   // 5 min early
        var windowEnd   = kickoffTime.getTime() + 130 * 60 * 1000;  // 130 min after kickoff
        var now = Date.now();
        if (now >= windowStart && now <= windowEnd) {
            pollInterval = setInterval(fetchScore, 30000);
        }
    }
})();
