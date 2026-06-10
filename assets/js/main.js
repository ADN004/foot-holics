/**
 * FOOT HOLICS — Main JavaScript
 * Centralized modal management, mobile menu, search, theme, ads, cookie consent, bottom nav
 */

(function () {
  'use strict';

  // ============================================================
  // CENTRALIZED MODAL MANAGER
  // At most one modal/overlay is active at a time.
  // Handles body-scroll lock and cleanup callbacks.
  // ============================================================
  var ModalManager = (function () {
    var _activeId = null;
    var _onClose  = null;

    return {
      /**
       * Open a modal. If another is already open it is closed first.
       * @param {string}   id
       * @param {object}   [opts]
       * @param {boolean}  [opts.lockScroll=true]
       * @param {Function} [opts.onClose]  — called when this modal is closed
       * @returns {boolean} false if the same modal is already open (no-op)
       */
      open: function (id, opts) {
        opts = opts || {};
        if (_activeId === id) return false;        // already open — ignore
        if (_activeId !== null) this.close(_activeId); // close the current one first
        _activeId = id;
        _onClose  = opts.onClose || null;
        if (opts.lockScroll !== false) {
          document.body.style.overflow = 'hidden';
        }
        return true;
      },

      /**
       * Close the active modal (only if its id matches).
       * @returns {boolean} false if this id is not the active modal
       */
      close: function (id) {
        if (_activeId !== id) return false;
        _activeId = null;
        document.body.style.overflow = '';
        if (_onClose) {
          var cb = _onClose;
          _onClose = null;
          cb();
        }
        return true;
      },

      isOpen:   function (id) { return _activeId === id; },
      hasAny:   function ()   { return _activeId !== null; },
      closeAll: function ()   { if (_activeId) this.close(_activeId); }
    };
  }());

  // ============================================================
  // FOCUS TRAP UTILITY
  // Keeps Tab / Shift+Tab cycling inside an overlay element.
  // ============================================================
  function makeFocusTrap(container) {
    var SEL = [
      'a[href]:not([disabled])',
      'button:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])'
    ].join(',');

    function visible() {
      return Array.prototype.filter.call(
        container.querySelectorAll(SEL),
        function (el) { return el.offsetParent !== null; }
      );
    }

    function onKey(e) {
      if (e.key !== 'Tab') return;
      var els = visible();
      if (!els.length) { e.preventDefault(); return; }
      var first = els[0], last = els[els.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
      }
    }

    return {
      activate:   function () { container.addEventListener('keydown', onKey); },
      deactivate: function () { container.removeEventListener('keydown', onKey); },
      focusFirst: function () { var els = visible(); if (els.length) els[0].focus(); }
    };
  }

  // ============================================================
  // MOBILE MENU — body-level overlay
  // Appended to <body> so it lives in the root stacking context
  // and is unaffected by the sticky header's transform/overflow.
  // ============================================================
  var mobileMenuBtn = document.getElementById('mobileMenuBtn');
  var primaryNav    = document.getElementById('primaryNav');
  var ctaGroup      = document.getElementById('ctaGroup');
  var siteHeader    = document.querySelector('.site-header');

  var mobOverlay = document.createElement('div');
  mobOverlay.id  = 'mob-nav-overlay';
  var mobCtaBar  = document.createElement('div');
  mobCtaBar.id   = 'mob-cta-bar';

  // Build premium card-style nav items from the desktop primaryNav
  var NAV_ICON_MAP = {
    'home':      'fa-house',
    'matches':   'fa-futbol',
    'news':      'fa-newspaper',
    'articles':  'fa-pen-nib',
    'standings': 'fa-table-list',
    'fixtures':  'fa-calendar-days',
    'world cup': 'fa-trophy',
    'about':     'fa-circle-info',
    'contact':   'fa-envelope',
  };

  if (primaryNav) {
    primaryNav.querySelectorAll('a').forEach(function (link) {
      var text    = link.textContent.trim();
      var iconKey = text.toLowerCase();
      var icon    = NAV_ICON_MAP[iconKey] || 'fa-circle';
      var isWC    = link.classList.contains('nav-wc-link');

      var item   = document.createElement('a');
      item.href  = link.href;
      item.className = 'mob-nav-item'
        + (link.classList.contains('active') ? ' active'    : '')
        + (isWC                              ? ' mob-nav-wc' : '');
      item.innerHTML =
        '<div class="mob-nav-icon-box">' +
          '<i class="fa-solid ' + icon + '" aria-hidden="true"></i>' +
        '</div>' +
        '<span class="mob-nav-label">' + text + '</span>' +
        '<i class="fa-solid fa-chevron-right mob-nav-chevron" aria-hidden="true"></i>';

      item.addEventListener('click', closeMobileMenu);
      mobOverlay.appendChild(item);
    });
  }

  // Clone CTA buttons into bottom bar
  if (ctaGroup) {
    ctaGroup.querySelectorAll('a').forEach(function (btn) {
      mobCtaBar.appendChild(btn.cloneNode(true));
    });
  }

  document.body.appendChild(mobOverlay);
  document.body.appendChild(mobCtaBar);

  var _menuTrap = makeFocusTrap(mobOverlay);

  // DOM-only teardown — registered as ModalManager onClose callback
  function _closeMobileMenuDOM() {
    mobOverlay.classList.remove('is-open');
    mobCtaBar.classList.remove('is-open');
    siteHeader && siteHeader.classList.remove('menu-open');
    _menuTrap.deactivate();
    if (mobileMenuBtn) {
      mobileMenuBtn.innerHTML = '☰';
      mobileMenuBtn.setAttribute('aria-expanded', 'false');
      mobileMenuBtn.focus();   // return keyboard focus to the trigger
    }
  }

  function openMobileMenu() {
    if (!ModalManager.open('mobile-nav', { onClose: _closeMobileMenuDOM })) return;
    closeSearchDropdown();   // dismiss search dropdown if visible
    mobOverlay.classList.add('is-open');
    mobCtaBar.classList.add('is-open');
    siteHeader && siteHeader.classList.add('menu-open');
    if (mobileMenuBtn) {
      mobileMenuBtn.innerHTML = '✕';
      mobileMenuBtn.setAttribute('aria-expanded', 'true');
    }
    _menuTrap.activate();
    _menuTrap.focusFirst();
  }

  function closeMobileMenu() {
    // ModalManager.close triggers _closeMobileMenuDOM via onClose.
    // If the menu is not the active modal (edge-case: already closed by
    // another event), fall back to a direct DOM cleanup.
    if (!ModalManager.close('mobile-nav')) {
      _closeMobileMenuDOM();
    }
  }

  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      ModalManager.isOpen('mobile-nav') ? closeMobileMenu() : openMobileMenu();
    });
  }

  // Backdrop click — close if tap is outside the overlay / CTA bar / header
  document.addEventListener('click', function (e) {
    if (!ModalManager.isOpen('mobile-nav')) return;
    if (
      !e.target.closest('#mob-nav-overlay') &&
      !e.target.closest('#mob-cta-bar') &&
      !e.target.closest('.site-header')
    ) {
      closeMobileMenu();
    }
  });

  // ESC key closes the mobile menu
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && ModalManager.isOpen('mobile-nav')) {
      closeMobileMenu();
    }
  });

  // Resize: if the viewport grows past the mobile breakpoint, close and
  // release the scroll lock (which would otherwise freeze the page).
  window.addEventListener('resize', function () {
    if (ModalManager.isOpen('mobile-nav') && window.innerWidth > 1024) {
      closeMobileMenu();
    }
  });

  // Browser back button — close overlay instead of navigating away
  window.addEventListener('popstate', function () {
    if (ModalManager.isOpen('mobile-nav')) closeMobileMenu();
  });

  // ============================================================
  // STICKY HEADER
  // ============================================================
  window.addEventListener('scroll', function () {
    var st = window.pageYOffset || document.documentElement.scrollTop;
    siteHeader && siteHeader.classList.toggle('scrolled', st > 100);
  });

  // ============================================================
  // HERO SEARCH — Live Dropdown
  // ============================================================

  // Hoisted stub — replaced by initHeroSearch when elements exist.
  // openMobileMenu() calls this to dismiss an open dropdown.
  var closeSearchDropdown = function () {};

  (function initHeroSearch() {
    var heroSearch     = document.getElementById('heroSearch');
    var searchDropdown = document.getElementById('searchDropdown');
    var searchBtn      = document.querySelector('.search-btn');
    if (!heroSearch || !searchDropdown) return;

    // Expose to outer scope so mobile menu open can call it
    closeSearchDropdown = function () { searchDropdown.classList.remove('open'); };

    // ── Static page shortcuts ────────────────────────────────────────────────
    var STATIC_PAGES = [
      { title: 'Football News',     meta: 'Latest news from Premier League, La Liga, UCL & more',     url: 'news.html',      icon: '📰', badge: 'Page'  },
      { title: 'League Standings',  meta: 'Tables for Premier League, La Liga, Bundesliga, Serie A',  url: 'standings.html', icon: '📊', badge: 'Page'  },
      { title: 'Upcoming Fixtures', meta: 'Next 14 days of fixtures across all major leagues',         url: 'fixtures.html',  icon: '📅', badge: 'Page'  },
      { title: 'About Foot Holics', meta: 'Who we are and what we cover',                              url: 'about.html',     icon: 'ℹ️', badge: 'Page'  },
      { title: 'Contact Us',        meta: 'Get in touch with our editorial team',                      url: 'contact.html',   icon: '✉️', badge: 'Page'  },
      { title: 'Privacy Policy',    meta: 'How we handle your data and cookies',                       url: 'privacy.html',   icon: '🔒', badge: 'Legal' },
    ];

    var LEAGUE_SHORTCUTS = [
      { keywords: ['premier league','epl','pl','england'],         title: 'Premier League Standings',   url: 'standings.html?league=eng.1',          badge: 'Standings' },
      { keywords: ['la liga','laliga','spain','spanish'],          title: 'La Liga Standings',           url: 'standings.html?league=esp.1',          badge: 'Standings' },
      { keywords: ['bundesliga','germany','german'],               title: 'Bundesliga Standings',        url: 'standings.html?league=ger.1',          badge: 'Standings' },
      { keywords: ['serie a','italy','italian'],                   title: 'Serie A Standings',           url: 'standings.html?league=ita.1',          badge: 'Standings' },
      { keywords: ['ligue 1','france','french'],                   title: 'Ligue 1 Standings',           url: 'standings.html?league=fra.1',          badge: 'Standings' },
      { keywords: ['champions league','ucl','cl','europa'],        title: 'Champions League Standings',  url: 'standings.html?league=UEFA.CHAMPIONS', badge: 'Standings' },
      { keywords: ['fixture','schedule','upcoming','next match'],  title: 'Upcoming Fixtures',           url: 'fixtures.html',                        badge: 'Fixtures'  },
    ];

    // Build match index from DOM cards (runs once on load)
    var MATCH_INDEX = Array.from(document.querySelectorAll('.match-card')).map(function (card) {
      return {
        title:  (card.querySelector('.match-title')  || {}).textContent || '',
        league: (card.querySelector('.league-badge') || {}).textContent || '',
        date:   (card.querySelector('.match-meta')   || {}).textContent || '',
        url:    card.querySelector('.match-link') ? card.querySelector('.match-link').getAttribute('href') : '#',
      };
    });

    // ── News cache ─────────────────────────────────────────────────────────
    var _newsCache = null, _newsFetchPromise = null;
    function getNews() {
      if (_newsCache)        return Promise.resolve(_newsCache);
      if (_newsFetchPromise) return _newsFetchPromise;
      _newsFetchPromise = fetch('/api/news?limit=50')
        .then(function (r) { return r.ok ? r.json() : { articles: [] }; })
        .then(function (d) { _newsCache = d.articles || []; return _newsCache; })
        .catch(function () { return []; });
      return _newsFetchPromise;
    }
    setTimeout(getNews, 2000); // warm cache silently

    // ── Helpers ────────────────────────────────────────────────────────────
    function esc(s) {
      return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }
    function contains(text, q) { return (text || '').toLowerCase().indexOf(q) !== -1; }

    function thumbHtml(img, icon) {
      if (img) {
        return '<img class="search-result-thumb" src="' + esc(img) + '" alt="" loading="lazy" '
          + 'onerror="this.outerHTML=\'<div class=\\\'search-result-thumb-placeholder\\\'>' + icon + '</div>\'">';
      }
      return '<div class="search-result-thumb-placeholder">' + icon + '</div>';
    }

    function resultItem(url, thumbImg, icon, title, meta, badge, external) {
      var target = external ? ' target="_blank" rel="noopener noreferrer"' : '';
      return '<a href="' + esc(url) + '" class="search-result-item"' + target + ' role="option">'
        + thumbHtml(thumbImg, icon)
        + '<div class="search-result-info">'
          + '<div class="search-result-title">' + esc(title) + '</div>'
          + '<div class="search-result-meta">' + esc(meta) + '</div>'
        + '</div>'
        + '<span class="search-result-badge">' + esc(badge) + '</span>'
        + '</a>';
    }

    // ── Race-condition guard ─────────────────────────────────────────────
    // Each call to runSearch increments _token. Before writing results,
    // we verify the token still matches (no newer query started).
    var _searchToken = 0;

    async function runSearch(rawQuery) {
      var q     = rawQuery.trim().toLowerCase();
      var token = ++_searchToken;

      if (q.length < 2) { closeSearchDropdown(); return; }

      searchDropdown.innerHTML = '<div class="search-loading">Searching...</div>';
      searchDropdown.classList.add('open');

      var html = '';

      // 1. League shortcuts
      var leagueHits = LEAGUE_SHORTCUTS.filter(function (l) {
        return l.keywords.some(function (k) { return contains(k, q) || contains(q, k); });
      });
      if (leagueHits.length) {
        html += '<div class="search-result-group-label">Leagues</div>';
        html += leagueHits.map(function (l) {
          return resultItem(l.url, null, '🏆', l.title, 'View table & standings', l.badge, false);
        }).join('');
      }

      // 2. Static pages
      var pageHits = STATIC_PAGES.filter(function (p) {
        return contains(p.title, q) || contains(p.meta, q);
      });
      if (pageHits.length) {
        html += '<div class="search-result-group-label">Pages</div>';
        html += pageHits.map(function (p) {
          return resultItem(p.url, null, p.icon, p.title, p.meta, p.badge, false);
        }).join('');
      }

      // 3. DOM match cards
      var matchHits = MATCH_INDEX.filter(function (m) {
        return contains(m.title, q) || contains(m.league, q) || contains(m.date, q);
      }).slice(0, 4);
      if (matchHits.length) {
        html += '<div class="search-result-group-label">Matches</div>';
        html += matchHits.map(function (m) {
          return resultItem(m.url, null, '⚽', m.title, m.league, 'Match', false);
        }).join('');
      }

      // 4. News articles (async — guard against stale results)
      try {
        var articles = await getNews();
        if (token !== _searchToken) return;  // newer query is in flight
        var newsHits = articles.filter(function (a) {
          return contains(a.headline || '', q) || contains(a.category || '', q);
        }).slice(0, 5);
        if (newsHits.length) {
          html += '<div class="search-result-group-label">News</div>';
          html += newsHits.map(function (a) {
            return resultItem(a.url, a.image, '📰', a.headline, a.category || 'Football News', 'News', true);
          }).join('');
        }
      } catch (_) {}

      if (token !== _searchToken) return;  // discard stale result

      if (!html) {
        html = '<div class="search-empty">No results for "<strong>' + esc(rawQuery) + '</strong>".<br>'
          + 'Try <a href="news.html" style="color:var(--accent)">browsing all news</a> or '
          + '<a href="fixtures.html" style="color:var(--accent)">upcoming fixtures</a>.</div>';
      }

      searchDropdown.innerHTML = html;
      searchDropdown.classList.add('open');
    }

    // ── Listeners ──────────────────────────────────────────────────────────
    var _debounce;
    heroSearch.addEventListener('input', function () {
      clearTimeout(_debounce);
      var val = this.value;
      if (!val.trim()) { closeSearchDropdown(); return; }
      _debounce = setTimeout(function () { runSearch(val); }, 300);
    });

    heroSearch.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { closeSearchDropdown(); this.blur(); }
      if (e.key === 'Enter')  { e.preventDefault(); runSearch(this.value); }
    });

    if (searchBtn) {
      searchBtn.addEventListener('click', function () { runSearch(heroSearch.value); });
    }

    // Close when clicking outside the search box
    document.addEventListener('click', function (e) {
      if (!e.target.closest('#heroSearchBox')) closeSearchDropdown();
    });

    heroSearch.addEventListener('focus', function () {
      if (this.value.trim().length >= 2) runSearch(this.value);
    });
  }());  // end initHeroSearch

  // ============================================================
  // SMOOTH SCROLL for anchor links
  // ============================================================
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      var href = this.getAttribute('href');
      if (href !== '#' && href.length > 1) {
        e.preventDefault();
        var target = document.querySelector(href);
        if (target) {
          window.scrollTo({ top: target.offsetTop - 80, behavior: 'smooth' });
        }
      }
    });
  });

  // ============================================================
  // ANIMATE ON SCROLL (Fade In)
  // ============================================================
  var _scrollObserver = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add('animate-fade-in');
        _scrollObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

  document.querySelectorAll('.match-card, .glass-card').forEach(function (card) {
    _scrollObserver.observe(card);
  });

  // ============================================================
  // LIVE BADGE ANIMATION
  // Stored so intervals can be cleared if needed.
  // ============================================================
  var _liveBadgeTimers = [];
  document.querySelectorAll('.live-badge').forEach(function (badge) {
    _liveBadgeTimers.push(setInterval(function () {
      badge.style.transform = 'scale(1.05)';
      setTimeout(function () { badge.style.transform = 'scale(1)'; }, 300);
    }, 3000));
  });

  // ============================================================
  // COPY TO CLIPBOARD
  // ============================================================
  function copyToClipboard(text) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text)
        .then(function () { showNotification('Link copied to clipboard!'); })
        .catch(function () { _fallbackCopy(text); });
    } else {
      _fallbackCopy(text);
    }
  }

  function _fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0;';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try { document.execCommand('copy'); showNotification('Link copied to clipboard!'); }
    catch (err) { console.error('Copy failed:', err); }
    document.body.removeChild(ta);
  }

  // ============================================================
  // TOAST NOTIFICATION
  // ============================================================
  function showNotification(message, duration) {
    duration = duration || 3000;
    var prev = document.querySelector('.toast-notification');
    if (prev) prev.remove();

    var toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.textContent = message;
    toast.style.cssText = [
      'position:fixed', 'bottom:2rem', 'right:2rem',
      'background:var(--accent)', 'color:var(--bg)',
      'padding:1rem 1.5rem', 'border-radius:var(--radius-sm)',
      'box-shadow:var(--card-shadow)', 'font-weight:600',
      'z-index:10000', 'animation:slideInUp 0.3s ease-out'
    ].join(';');
    document.body.appendChild(toast);

    setTimeout(function () {
      toast.style.animation = 'slideOutDown 0.3s ease-out';
      setTimeout(function () { if (toast.parentNode) toast.remove(); }, 300);
    }, duration);
  }

  // ============================================================
  // IMAGE ERROR HANDLER
  // ============================================================
  document.querySelectorAll('img[loading="lazy"]').forEach(function (img) {
    img.addEventListener('error', function () {
      this.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="300"%3E%3Crect fill="%230f2a44" width="400" height="300"/%3E%3Ctext fill="%23B9C3CF" font-family="Arial" font-size="18" x="50%25" y="50%25" text-anchor="middle" dominant-baseline="middle"%3EImage Not Available%3C/text%3E%3C/svg%3E';
      this.alt = 'Image not available';
    });
  });

  // ============================================================
  // CONSOLE BRANDING
  // ============================================================
  console.log('%cFoot Holics', 'font-size:24px;font-weight:bold;color:#D4AF37;');
  console.log('%cLive. Passion. Football.', 'font-size:14px;color:#7DE3E3;');

  // ============================================================
  // REDUCED MOTION
  // ============================================================
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    document.documentElement.style.setProperty('scroll-behavior', 'auto');
  }

  // ============================================================
  // PLAYER PAGE — Countdown timer
  // ============================================================
  if (window.location.pathname.indexOf('/p/') !== -1) {
    var alertEl = document.querySelector('.player-alert');
    if (alertEl) {
      var _countdown = 20;
      var _cInterval = setInterval(function () {
        _countdown--;
        var p = alertEl.querySelector('p');
        if (!p) { clearInterval(_cInterval); return; }
        if (_countdown > 0) {
          p.innerHTML = '⏳ Please wait <strong>' + _countdown + ' seconds</strong> for the stream to load properly...';
        } else {
          p.innerHTML = '✅ Stream should be loaded! If not, try a different link or refresh.';
          alertEl.style.background = 'rgba(16,185,129,0.2)';
          alertEl.style.borderColor = 'rgba(16,185,129,0.5)';
          clearInterval(_cInterval);
        }
      }, 1000);
    }
  }

  // ============================================================
  // LEAGUE FILTER (Homepage sidebar)
  // Fixed: no longer relies on deprecated global `event` object.
  // ============================================================
  window.filterLeague = function (league) {
    var matchCards   = document.querySelectorAll('.match-card');
    var sidebarLinks = document.querySelectorAll('.sidebar-list a');

    sidebarLinks.forEach(function (link) { link.classList.remove('active'); });

    // Safely access the clicked element without the deprecated global event
    try {
      /* global event */
      if (typeof event !== 'undefined' && event && event.target) {
        var clicked = event.target.closest('a');
        if (clicked) clicked.classList.add('active');
      }
    } catch (_) {}

    matchCards.forEach(function (card) {
      if (league === 'all') {
        card.style.display = 'block';
        card.classList.add('animate-fade-in');
      } else {
        var badge = card.querySelector('.league-badge');
        if (badge) {
          var show = badge.className.indexOf(league) !== -1;
          card.style.display = show ? 'block' : 'none';
          if (show) card.classList.add('animate-fade-in');
        }
      }
    });

    var grid = document.getElementById('matchesGrid');
    if (grid) grid.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  window.scrollToTop = function () { window.scrollTo({ top: 0, behavior: 'smooth' }); };

  // ============================================================
  // INJECTED CSS KEYFRAMES
  // ============================================================
  var _kfStyle = document.createElement('style');
  _kfStyle.textContent = [
    '@keyframes slideInUp{from{transform:translateY(100%);opacity:0}to{transform:translateY(0);opacity:1}}',
    '@keyframes slideOutDown{from{transform:translateY(0);opacity:1}to{transform:translateY(100%);opacity:0}}'
  ].join('');
  document.head.appendChild(_kfStyle);

  // ============================================================
  // TELEGRAM POPUP
  // — shown once per session after 60 seconds idle
  // — will NOT open if any other modal is already active
  // — ESC handler is named and fully removed on close (no leak)
  // — coordinated with ModalManager for body-scroll lock
  // ============================================================
  var _tgPopupShown   = sessionStorage.getItem('telegramPopupShown');
  var _tgPopupPending = false;

  function createTelegramPopup() {
    // Never open over the mobile menu or any other active overlay
    if (ModalManager.hasAny()) return;

    var overlay = document.createElement('div');
    overlay.className = 'telegram-popup-overlay';
    overlay.id        = 'telegramPopupOverlay';
    overlay.innerHTML = [
      '<div class="telegram-popup">',
        '<button class="telegram-popup-close" id="telegramPopupClose" aria-label="Close popup">✕</button>',
        '<div class="telegram-popup-icon">',
          '<svg viewBox="0 0 24 24" fill="white" style="width:32px;height:32px;">',
            '<path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>',
          '</svg>',
        '</div>',
        '<h2 class="telegram-popup-title">Join Our Telegram Channel!</h2>',
        '<p class="telegram-popup-description">',
          'Get instant notifications for live matches, exclusive streaming links, and match highlights directly in Telegram.',
        '</p>',
        '<div class="telegram-popup-benefits"><ul>',
          '<li>Real-time match alerts</li>',
          '<li>Premium streaming links</li>',
          '<li>Exclusive match highlights</li>',
          '<li>Live score updates</li>',
          '<li>Community discussions</li>',
        '</ul></div>',
        '<div class="telegram-popup-cta">',
          '<a href="https://t.me/+XyKdBR9chQpjM2I9" target="_blank" rel="noopener noreferrer" class="telegram-popup-btn telegram-popup-btn-primary">',
            '<svg class="telegram-icon-svg" viewBox="0 0 24 24">',
              '<path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>',
            '</svg>',
            'Join Telegram Channel',
          '</a>',
          '<button class="telegram-popup-btn telegram-popup-btn-secondary" id="telegramPopupDismiss">Maybe Later</button>',
        '</div>',
      '</div>'
    ].join('');

    document.body.appendChild(overlay);

    var _popupTrap = makeFocusTrap(overlay);

    // Named ESC handler so it can be cleanly removed (no memory leak)
    function _popupEscHandler(e) {
      if (e.key === 'Escape' && ModalManager.isOpen('telegram-popup')) closePopup();
    }

    // All DOM teardown in one place — called via ModalManager onClose
    function _cleanupDOM() {
      overlay.classList.remove('show');
      sessionStorage.setItem('telegramPopupShown', 'true');
      _popupTrap.deactivate();
      document.removeEventListener('keydown', _popupEscHandler);
      setTimeout(function () { if (overlay.parentNode) overlay.remove(); }, 400);
    }

    function closePopup() {
      ModalManager.close('telegram-popup'); // triggers _cleanupDOM via onClose
    }

    overlay.querySelector('#telegramPopupClose').addEventListener('click', closePopup);
    overlay.querySelector('#telegramPopupDismiss').addEventListener('click', closePopup);
    overlay.addEventListener('click', function (e) { if (e.target === overlay) closePopup(); });
    document.addEventListener('keydown', _popupEscHandler);

    // Register with ModalManager — abort if another modal opened in the
    // narrow window between hasAny() check and here
    if (!ModalManager.open('telegram-popup', { lockScroll: true, onClose: _cleanupDOM })) {
      document.removeEventListener('keydown', _popupEscHandler);
      overlay.remove();
      return;
    }

    _popupTrap.activate();
    setTimeout(function () { overlay.classList.add('show'); }, 500);
  }

  setTimeout(function () {
    if (!_tgPopupPending && !_tgPopupShown) {
      _tgPopupPending = true;
      createTelegramPopup();
    }
  }, 60000);

  // ============================================================
  // DARK / LIGHT THEME TOGGLE
  // ============================================================
  var themeToggle = document.createElement('button');
  themeToggle.className = 'theme-toggle';
  themeToggle.setAttribute('aria-label', 'Toggle theme');
  document.body.appendChild(themeToggle);

  document.documentElement.setAttribute('data-theme', localStorage.getItem('theme') || 'dark');

  function _updateThemeIcon() {
    themeToggle.innerHTML = document.documentElement.getAttribute('data-theme') === 'dark' ? '🌙' : '☀️';
  }
  _updateThemeIcon();

  themeToggle.addEventListener('click', function () {
    var next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    _updateThemeIcon();
    showNotification('Switched to ' + next + ' mode', 2000);
  });

  // ============================================================
  // CLICKABLE MATCH CARDS (whole card acts as link)
  // ============================================================
  document.querySelectorAll('.match-card').forEach(function (card) {
    card.addEventListener('click', function (e) {
      // Let direct link clicks pass through naturally
      if (!e.target.closest('.match-link')) {
        var link = this.querySelector('.match-link');
        if (link) window.location.href = link.getAttribute('href');
      }
    });
  });

  // ============================================================
  // THREE.JS FLOATING PARTICLES (homepage desktop only)
  // ============================================================
  var _isHomepage = window.location.pathname.endsWith('index.html') ||
                    window.location.pathname === '/' ||
                    /\/$/.test(window.location.pathname);

  if (_isHomepage && window.innerWidth >= 768) {
    (function () {
      var s  = document.createElement('script');
      s.src  = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
      s.async = true;
      s.onload = function () {
        if (typeof THREE === 'undefined') return;

        var canvas   = document.createElement('canvas');
        canvas.id    = 'three-canvas';
        document.body.insertBefore(canvas, document.body.firstChild);

        var scene    = new THREE.Scene();
        var camera   = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
        var renderer = new THREE.WebGLRenderer({ canvas: canvas, alpha: true, antialias: true });
        renderer.setSize(window.innerWidth, window.innerHeight, false);
        renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        camera.position.z = 5;

        var geo  = new THREE.BufferGeometry();
        var pos  = new Float32Array(300);
        for (var i = 0; i < 300; i++) pos[i] = (Math.random() - 0.5) * 10;
        geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));

        var mat  = new THREE.PointsMaterial({ size: 0.02, color: 0xD4AF37, transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending });
        var mesh = new THREE.Points(geo, mat);
        scene.add(mesh);

        var mouseX = 0, mouseY = 0;
        document.addEventListener('mousemove', function (e) {
          mouseX = (e.clientX / window.innerWidth) * 2 - 1;
          mouseY = -(e.clientY / window.innerHeight) * 2 + 1;
        });

        (function animate() {
          requestAnimationFrame(animate);
          mesh.rotation.y += 0.001 + mouseX * 0.05;
          mesh.rotation.x  = mouseY * 0.1;
          renderer.render(scene, camera);
        }());

        window.addEventListener('resize', function () {
          camera.aspect = window.innerWidth / window.innerHeight;
          camera.updateProjectionMatrix();
          renderer.setSize(window.innerWidth, window.innerHeight, false);
        });
      };
      document.head.appendChild(s);
    }());
  }

  // One-time cleanup: purge click-count state left behind by the removed
  // ad-interstitial system from returning visitors' browsers.
  localStorage.removeItem('footholics_ad_clicks');

  // ============================================================
  // COOKIE CONSENT BANNER
  // ============================================================
  (function initCookieConsent() {
    if (localStorage.getItem('cookieConsent')) return;

    var banner = document.createElement('div');
    banner.className = 'cookie-banner';
    banner.setAttribute('role', 'dialog');
    banner.setAttribute('aria-label', 'Cookie consent');
    banner.innerHTML = [
      '<div class="cookie-banner-text">',
        '<strong>We use cookies.</strong> We and our partners use cookies and similar technologies to ',
        'analyse traffic, personalise content and serve targeted advertisements (including via Google AdSense). ',
        'By clicking <strong>Accept</strong> you consent to our use of cookies as described in our ',
        '<a href="privacy.html">Privacy Policy</a>.',
      '</div>',
      '<div class="cookie-banner-actions">',
        '<button class="cookie-btn-decline" id="cookieDecline">Decline</button>',
        '<button class="cookie-btn-accept" id="cookieAccept">Accept All</button>',
      '</div>'
    ].join('');
    document.body.appendChild(banner);

    requestAnimationFrame(function () {
      setTimeout(function () { banner.classList.add('visible'); }, 600);
    });

    function dismiss(choice) {
      localStorage.setItem('cookieConsent', choice);
      banner.classList.remove('visible');
      setTimeout(function () { if (banner.parentNode) banner.remove(); }, 400);
    }

    document.getElementById('cookieAccept').addEventListener('click', function () { dismiss('accepted'); });
    document.getElementById('cookieDecline').addEventListener('click', function () { dismiss('declined'); });
  }());

  // ============================================================
  // MOBILE BOTTOM NAVIGATION
  // ============================================================
  (function () {
    var p          = window.location.pathname;
    var inArticles = /\/articles\//.test(p);
    var base       = inArticles ? '../' : '';

    function isActive(key) {
      if (key === 'home')      return p === '/' || (p.indexOf('index.html') !== -1 && !inArticles);
      if (key === 'articles')  return inArticles;
      if (key === 'wc')        return p.indexOf('world-cup-2026') !== -1;
      if (key === 'fixtures')  return p.indexOf('fixtures') !== -1;
      if (key === 'standings') return p.indexOf('standings') !== -1;
      return false;
    }

    var items = [
      { href: base + 'index.html',          icon: 'fa-house',         label: 'Home',      key: 'home'      },
      { href: base + 'articles/index.html', icon: 'fa-newspaper',     label: 'Articles',  key: 'articles'  },
      { href: base + 'world-cup-2026.html', icon: 'fa-trophy',        label: 'World Cup', key: 'wc',       wc: true },
      { href: base + 'fixtures.html',       icon: 'fa-calendar-days', label: 'Fixtures',  key: 'fixtures'  },
      { href: base + 'standings.html',      icon: 'fa-table-list',    label: 'Standings', key: 'standings' },
    ];

    var nav = document.createElement('nav');
    nav.id  = 'bottom-nav';
    nav.setAttribute('aria-label', 'Site navigation');

    items.forEach(function (item) {
      var active = isActive(item.key);
      var a = document.createElement('a');
      a.href = item.href;
      a.className = 'bottom-nav-item'
        + (item.wc ? ' bottom-nav-wc' : '')
        + (active   ? ' active'        : '');
      if (active) a.setAttribute('aria-current', 'page');
      a.innerHTML = '<i class="fa-solid ' + item.icon + ' bottom-nav-icon" aria-hidden="true"></i>'
                  + '<span>' + item.label + '</span>';
      nav.appendChild(a);
    });

    document.body.appendChild(nav);
  }());

}());
