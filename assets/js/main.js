/**
 * FOOT HOLICS - Main JavaScript
 * Handles interactions, search, mobile menu, and dynamic content
 */

(function() {
  'use strict';

  // ========================================
  // Mobile Menu Toggle
  // ========================================
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');
  const primaryNav = document.getElementById('primaryNav');
  const ctaGroup = document.getElementById('ctaGroup');

  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', function() {
      primaryNav?.classList.toggle('mobile-open');
      ctaGroup?.classList.toggle('mobile-open');

      // Toggle icon
      if (primaryNav?.classList.contains('mobile-open')) {
        mobileMenuBtn.innerHTML = '✕';
      } else {
        mobileMenuBtn.innerHTML = '☰';
      }
    });
  }

  // Close mobile menu when clicking outside
  document.addEventListener('click', function(e) {
    if (primaryNav?.classList.contains('mobile-open')) {
      if (!e.target.closest('.header-inner')) {
        primaryNav.classList.remove('mobile-open');
        ctaGroup?.classList.remove('mobile-open');
        if (mobileMenuBtn) mobileMenuBtn.innerHTML = '☰';
      }
    }
  });

  // ========================================
  // Sticky Header on Scroll
  // ========================================
  const siteHeader = document.querySelector('.site-header');
  let lastScrollTop = 0;

  window.addEventListener('scroll', function() {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;

    if (scrollTop > 100) {
      siteHeader?.classList.add('scrolled');
    } else {
      siteHeader?.classList.remove('scrolled');
    }

    lastScrollTop = scrollTop;
  });

  // ========================================
  // Hero Search Functionality
  // ========================================
  const heroSearch = document.getElementById('heroSearch');
  const searchBtn = document.querySelector('.search-btn');

  function performSearch(query) {
    query = query.trim().toLowerCase();

    if (query.length === 0) {
      // Show all matches if search is empty
      document.querySelectorAll('.match-card').forEach(card => {
        card.style.display = 'block';
      });
      return;
    }

    const matchCards = document.querySelectorAll('.match-card');
    let foundCount = 0;

    matchCards.forEach(card => {
      const title = card.querySelector('.match-title')?.textContent.toLowerCase() || '';
      const excerpt = card.querySelector('.match-excerpt')?.textContent.toLowerCase() || '';
      const league = card.querySelector('.league-badge')?.textContent.toLowerCase() || '';
      const stadium = card.querySelector('.match-meta')?.textContent.toLowerCase() || '';

      const searchText = `${title} ${excerpt} ${league} ${stadium}`;

      if (searchText.includes(query)) {
        card.style.display = 'block';
        card.classList.add('animate-fade-in');
        foundCount++;
      } else {
        card.style.display = 'none';
      }
    });

    // Show notification with results
    if (foundCount === 0) {
      showNotification(`No matches found for "${query}". Try different keywords.`, 3000);
    } else {
      showNotification(`Found ${foundCount} match${foundCount !== 1 ? 'es' : ''} for "${query}"`, 2000);
    }

    // Scroll to matches grid
    const matchesGrid = document.getElementById('matchesGrid');
    if (matchesGrid) {
      matchesGrid.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  if (heroSearch) {
    heroSearch.addEventListener('keypress', function(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        performSearch(this.value);
      }
    });

    // Real-time search as user types (debounced)
    let searchTimeout;
    heroSearch.addEventListener('input', function() {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        if (this.value.length >= 3 || this.value.length === 0) {
          performSearch(this.value);
        }
      }, 500);
    });
  }

  if (searchBtn) {
    searchBtn.addEventListener('click', function() {
      if (heroSearch) {
        performSearch(heroSearch.value);
      }
    });
  }

  // ========================================
  // Smooth Scroll for Anchor Links
  // ========================================
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      if (href !== '#' && href.length > 1) {
        e.preventDefault();
        const target = document.querySelector(href);
        if (target) {
          const offsetTop = target.offsetTop - 80; // Account for sticky header
          window.scrollTo({
            top: offsetTop,
            behavior: 'smooth'
          });
        }
      }
    });
  });

  // ========================================
  // Animate on Scroll (Fade In)
  // ========================================
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };

  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('animate-fade-in');
        observer.unobserve(entry.target);
      }
    });
  }, observerOptions);

  // Observe match cards for animation
  document.querySelectorAll('.match-card, .glass-card').forEach(card => {
    observer.observe(card);
  });

  // ========================================
  // Live Badge Animation Enhancement
  // ========================================
  const liveBadges = document.querySelectorAll('.live-badge');
  liveBadges.forEach(badge => {
    // Add extra visual feedback
    setInterval(() => {
      badge.style.transform = 'scale(1.05)';
      setTimeout(() => {
        badge.style.transform = 'scale(1)';
      }, 300);
    }, 3000);
  });

  // ========================================
  // Copy to Clipboard (for share links)
  // ========================================
  function copyToClipboard(text) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(() => {
        showNotification('Link copied to clipboard!');
      }).catch(() => {
        fallbackCopyTextToClipboard(text);
      });
    } else {
      fallbackCopyTextToClipboard(text);
    }
  }

  function fallbackCopyTextToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.top = '0';
    textArea.style.left = '0';
    textArea.style.opacity = '0';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand('copy');
      showNotification('Link copied to clipboard!');
    } catch (err) {
      console.error('Fallback copy failed:', err);
    }
    document.body.removeChild(textArea);
  }

  // ========================================
  // Notification Toast
  // ========================================
  function showNotification(message, duration = 3000) {
    // Remove existing notification if any
    const existing = document.querySelector('.toast-notification');
    if (existing) {
      existing.remove();
    }

    const toast = document.createElement('div');
    toast.className = 'toast-notification';
    toast.textContent = message;
    toast.style.cssText = `
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      background: var(--accent);
      color: var(--bg);
      padding: 1rem 1.5rem;
      border-radius: var(--radius-sm);
      box-shadow: var(--card-shadow);
      font-weight: 600;
      z-index: 10000;
      animation: slideInUp 0.3s ease-out;
    `;

    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.animation = 'slideOutDown 0.3s ease-out';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  // ========================================
  // Image Lazy Load Error Handler
  // ========================================
  document.querySelectorAll('img[loading="lazy"]').forEach(img => {
    img.addEventListener('error', function() {
      // Replace with placeholder if image fails to load
      this.src = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="400" height="300"%3E%3Crect fill="%230f2a44" width="400" height="300"/%3E%3Ctext fill="%23B9C3CF" font-family="Arial" font-size="18" x="50%25" y="50%25" text-anchor="middle" dominant-baseline="middle"%3EImage Not Available%3C/text%3E%3C/svg%3E';
      this.alt = 'Image not available';
    });
  });

  // ========================================
  // Console Welcome Message
  // ========================================
  console.log('%cFoot Holics', 'font-size: 24px; font-weight: bold; color: #D4AF37;');
  console.log('%cLive. Passion. Football.', 'font-size: 14px; color: #7DE3E3;');

  // ========================================
  // Prefers Reduced Motion Check
  // ========================================
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReducedMotion) {
    document.documentElement.style.setProperty('scroll-behavior', 'auto');
  }

  // ========================================
  // Player Page: Countdown Timer
  // ========================================
  if (window.location.pathname.includes('/p/')) {
    const alert = document.querySelector('.player-alert');
    if (alert) {
      let countdown = 20;
      const originalText = alert.textContent;

      const countdownInterval = setInterval(() => {
        countdown--;
        if (countdown > 0) {
          alert.querySelector('p').innerHTML = `⏳ Please wait <strong>${countdown} seconds</strong> for the stream to load properly...`;
        } else {
          alert.querySelector('p').innerHTML = '✅ Stream should be loaded! If not, try a different link or refresh.';
          alert.style.background = 'rgba(16, 185, 129, 0.2)';
          alert.style.borderColor = 'rgba(16, 185, 129, 0.5)';
          clearInterval(countdownInterval);
        }
      }, 1000);
    }
  }

  // ========================================
  // League Filter Functionality (Homepage)
  // ========================================
  window.filterLeague = function(league) {
    const matchCards = document.querySelectorAll('.match-card');
    const sidebarLinks = document.querySelectorAll('.sidebar-list a');

    // Update active state in sidebar
    sidebarLinks.forEach(link => {
      link.classList.remove('active');
    });
    event.target.closest('a').classList.add('active');

    // Filter cards
    matchCards.forEach(card => {
      if (league === 'all') {
        card.style.display = 'block';
        card.classList.add('animate-fade-in');
      } else {
        const badge = card.querySelector('.league-badge');
        if (badge) {
          const badgeClass = badge.className;
          if (badgeClass.includes(league)) {
            card.style.display = 'block';
            card.classList.add('animate-fade-in');
          } else {
            card.style.display = 'none';
          }
        }
      }
    });

    // Scroll to matches
    const matchesGrid = document.getElementById('matchesGrid');
    if (matchesGrid) {
      matchesGrid.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  // ========================================
  // Scroll to Top Helper
  // ========================================
  window.scrollToTop = function() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  // ========================================
  // Add CSS Animations Dynamically
  // ========================================
  const style = document.createElement('style');
  style.textContent = `
    @keyframes slideInUp {
      from {
        transform: translateY(100%);
        opacity: 0;
      }
      to {
        transform: translateY(0);
        opacity: 1;
      }
    }

    @keyframes slideOutDown {
      from {
        transform: translateY(0);
        opacity: 1;
      }
      to {
        transform: translateY(100%);
        opacity: 0;
      }
    }

    @media (max-width: 768px) {
      .primary-nav.mobile-open {
        display: flex !important;
      }

      .cta-group.mobile-open {
        display: flex !important;
      }
    }
  `;
  document.head.appendChild(style);

  // ========================================
  // TELEGRAM POPUP FUNCTIONALITY
  // ========================================

  // Check if popup was already shown in this session
  const popupShown = sessionStorage.getItem('telegramPopupShown');
  let popupTriggered = false;

  function createTelegramPopup() {
    // Create popup HTML
    const popupHTML = `
      <div class="telegram-popup-overlay" id="telegramPopupOverlay">
        <div class="telegram-popup">
          <button class="telegram-popup-close" id="telegramPopupClose" aria-label="Close popup">✕</button>

          <div class="telegram-popup-icon">
            <svg viewBox="0 0 24 24" fill="white" style="width: 32px; height: 32px;">
              <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
            </svg>
          </div>

          <h2 class="telegram-popup-title">Join Our Telegram Channel!</h2>

          <p class="telegram-popup-description">
            Get instant notifications for live matches, exclusive streaming links, and match highlights directly in Telegram.
          </p>

          <div class="telegram-popup-benefits">
            <ul>
              <li>Real-time match alerts</li>
              <li>Premium streaming links</li>
              <li>Exclusive match highlights</li>
              <li>Live score updates</li>
              <li>Community discussions</li>
            </ul>
          </div>

          <div class="telegram-popup-cta">
            <a href="https://t.me/+XyKdBR9chQpjM2I9" target="_blank" rel="noopener noreferrer" class="telegram-popup-btn telegram-popup-btn-primary">
              <svg class="telegram-icon-svg" viewBox="0 0 24 24">
                <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
              </svg>
              Join Telegram Channel
            </a>
            <button class="telegram-popup-btn telegram-popup-btn-secondary" id="telegramPopupDismiss">
              Maybe Later
            </button>
          </div>
        </div>
      </div>
    `;

    // Insert popup into page
    document.body.insertAdjacentHTML('beforeend', popupHTML);

    // Get popup elements
    const overlay = document.getElementById('telegramPopupOverlay');
    const closeBtn = document.getElementById('telegramPopupClose');
    const dismissBtn = document.getElementById('telegramPopupDismiss');

    // Function to close popup
    function closePopup() {
      overlay.classList.remove('show');
      sessionStorage.setItem('telegramPopupShown', 'true');
      setTimeout(() => {
        overlay.remove();
      }, 400);
    }

    // Close button click
    closeBtn.addEventListener('click', closePopup);

    // Dismiss button click
    dismissBtn.addEventListener('click', closePopup);

    // Close when clicking outside
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) {
        closePopup();
      }
    });

    // Close on Escape key
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && overlay.classList.contains('show')) {
        closePopup();
      }
    });

    // Show popup after a short delay
    setTimeout(() => {
      overlay.classList.add('show');
    }, 500);
  }

  // Trigger popup on scroll (after scrolling 400px)
  function checkScrollForPopup() {
    if (!popupTriggered && !popupShown) {
      const scrollPosition = window.pageYOffset || document.documentElement.scrollTop;

      if (scrollPosition > 400) {
        popupTriggered = true;
        createTelegramPopup();

        // Remove scroll listener after popup is shown
        window.removeEventListener('scroll', checkScrollForPopup);
      }
    }
  }

  // Also show popup after 10 seconds if user hasn't scrolled
  setTimeout(() => {
    if (!popupTriggered && !popupShown) {
      popupTriggered = true;
      createTelegramPopup();
    }
  }, 10000);

  // Add scroll listener
  window.addEventListener('scroll', checkScrollForPopup);

  // ========================================
  // SPLASH SCREEN
  // ========================================

  // Show splash only on first visit of session
  const splashShown = sessionStorage.getItem('splashShown');

  if (!splashShown) {
    // Create splash screen
    const splash = document.createElement('div');
    splash.className = 'splash-screen';
    splash.innerHTML = `
      <div class="splash-logo">
        <img src="assets/img/logos/site/logo.png" alt="Foot Holics Logo" class="splash-logo-icon">
        <div class="splash-logo-text">Foot Holics</div>
        <div class="splash-logo-tagline">Live. Passion. Football.</div>
      </div>
    `;

    document.body.appendChild(splash);

    // Mark as shown and remove after animation
    sessionStorage.setItem('splashShown', 'true');

    setTimeout(() => {
      splash.remove();
    }, 2600);
  }

  // ========================================
  // DARK / LIGHT THEME TOGGLE
  // ========================================

  // Create theme toggle button
  const themeToggle = document.createElement('button');
  themeToggle.className = 'theme-toggle';
  themeToggle.setAttribute('aria-label', 'Toggle theme');
  themeToggle.innerHTML = '🌙';

  document.body.appendChild(themeToggle);

  // Check for saved theme preference or default to dark
  const currentTheme = localStorage.getItem('theme') || 'dark';
  document.documentElement.setAttribute('data-theme', currentTheme);

  // Update button icon based on theme
  function updateThemeIcon() {
    const theme = document.documentElement.getAttribute('data-theme');
    themeToggle.innerHTML = theme === 'dark' ? '🌙' : '☀️';
  }

  updateThemeIcon();

  // Toggle theme
  themeToggle.addEventListener('click', function() {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon();

    // Show notification
    showNotification(`Switched to ${newTheme} mode`, 2000);
  });

  // ========================================
  // CLICKABLE MATCH CARDS
  // ========================================

  document.querySelectorAll('.match-card').forEach(card => {
    card.addEventListener('click', function(e) {
      // Don't trigger if clicking the button directly
      if (!e.target.closest('.match-link')) {
        const link = this.querySelector('.match-link');
        if (link) {
          window.location.href = link.getAttribute('href');
        }
      }
    });
  });

  // ========================================
  // THREE.JS SUBTLE BACKGROUND EFFECTS
  // ========================================

  // Only load Three.js if on homepage and screen is large enough
  if (window.location.pathname.endsWith('index.html') || window.location.pathname === '/' || window.location.pathname.endsWith('/')) {
    if (window.innerWidth >= 768) {
      loadThreeJS();
    }
  }

  function loadThreeJS() {
    // Dynamically load Three.js from CDN
    const script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
    script.async = true;
    script.onload = initThreeJS;
    document.head.appendChild(script);
  }

  function initThreeJS() {
    if (typeof THREE === 'undefined') return;

    // Create canvas
    const canvas = document.createElement('canvas');
    canvas.id = 'three-canvas';
    document.body.insertBefore(canvas, document.body.firstChild);

    // Scene setup
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, window.innerWidth / window.innerHeight, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });

    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    camera.position.z = 5;

    // Create floating particles
    const particlesGeometry = new THREE.BufferGeometry();
    const particlesCount = 100;
    const posArray = new Float32Array(particlesCount * 3);

    for (let i = 0; i < particlesCount * 3; i++) {
      posArray[i] = (Math.random() - 0.5) * 10;
    }

    particlesGeometry.setAttribute('position', new THREE.BufferAttribute(posArray, 3));

    const particlesMaterial = new THREE.PointsMaterial({
      size: 0.02,
      color: 0xD4AF37,
      transparent: true,
      opacity: 0.6,
      blending: THREE.AdditiveBlending
    });

    const particlesMesh = new THREE.Points(particlesGeometry, particlesMaterial);
    scene.add(particlesMesh);

    // Animation
    let mouseX = 0;
    let mouseY = 0;

    document.addEventListener('mousemove', (e) => {
      mouseX = (e.clientX / window.innerWidth) * 2 - 1;
      mouseY = -(e.clientY / window.innerHeight) * 2 + 1;
    });

    function animate() {
      requestAnimationFrame(animate);

      // Rotate particles slowly
      particlesMesh.rotation.y += 0.001;
      particlesMesh.rotation.x = mouseY * 0.1;
      particlesMesh.rotation.y += mouseX * 0.05;

      renderer.render(scene, camera);
    }

    animate();

    // Handle resize
    window.addEventListener('resize', () => {
      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    });
  }

  // ========================================
  // AD MANAGEMENT SYSTEM
  // ========================================

  /**
   * Interstitial Ad System for Adsterra
   * First click = Show ad, Second click = Go to destination
   * Uses localStorage to track click states
   */

  const AdManager = {
    // Configuration
    config: {
      clickDelay: 500, // ms to wait before action
      storageKey: 'footholics_ad_clicks',
      sessionKey: 'footholics_session_ads'
    },

    // Initialize ad system
    init: function() {
      this.attachListeners();
      this.initializeAdSlots();
    },

    // Get click count for a specific link
    getClickCount: function(href) {
      const clicks = JSON.parse(localStorage.getItem(this.config.storageKey) || '{}');
      return clicks[href] || 0;
    },

    // Increment click count
    incrementClickCount: function(href) {
      const clicks = JSON.parse(localStorage.getItem(this.config.storageKey) || '{}');
      clicks[href] = (clicks[href] || 0) + 1;
      localStorage.setItem(this.config.storageKey, JSON.stringify(clicks));
    },

    // Reset click count (called after successful navigation)
    resetClickCount: function(href) {
      const clicks = JSON.parse(localStorage.getItem(this.config.storageKey) || '{}');
      clicks[href] = 0;
      localStorage.setItem(this.config.storageKey, JSON.stringify(clicks));
    },

    // Handle link clicks with interstitial ad logic
    handleAdClick: function(e, link) {
      const href = link.getAttribute('href');
      const isExternal = link.getAttribute('target') === '_blank';

      // Skip ad logic for internal navigation links
      if (href.startsWith('#') || href === 'index.html') {
        return; // Allow normal navigation
      }

      const clickCount = this.getClickCount(href);

      if (clickCount === 0) {
        // First click - show ad
        e.preventDefault();
        this.showInterstitialAd();
        this.incrementClickCount(href);

        // Visual feedback
        this.showAdNotification('Please wait... Ad loading');

      } else {
        // Second click - allow navigation
        this.resetClickCount(href);
        this.showAdNotification('Redirecting...');
        // Allow default navigation
      }
    },

    // Attach event listeners to all links
    attachListeners: function() {
      // Match cards and watch live buttons
      const matchLinks = document.querySelectorAll('.match-link, .btn-primary, .btn-secondary');

      matchLinks.forEach(link => {
        const href = link.getAttribute('href');
        if (href && !href.startsWith('#') && !href.includes('mailto:')) {
          link.addEventListener('click', (e) => {
            this.handleAdClick(e, link);
          });
        }
      });
    },

    // Show interstitial ad (integrate with Adsterra)
    showInterstitialAd: function() {
      // This triggers Adsterra interstitial ad
      // The actual ad script should be loaded in HTML
      // This is a placeholder for the ad display logic

      // Trigger ad slot
      const adSlot = document.getElementById('interstitial-ad-slot');
      if (adSlot && typeof window.adsterraInters !== 'undefined') {
        // Trigger Adsterra interstitial
        window.adsterraInters.show();
      }

      console.log('[Ad Manager] Interstitial ad triggered');
    },

    // Show notification to user
    showAdNotification: function(message) {
      const notification = document.createElement('div');
      notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 12px 20px;
        border-radius: 8px;
        z-index: 10000;
        font-size: 14px;
        backdrop-filter: blur(10px);
      `;
      notification.textContent = message;
      document.body.appendChild(notification);

      setTimeout(() => {
        notification.remove();
      }, 2000);
    },

    // Initialize ad slots for Adsterra scripts
    initializeAdSlots: function() {
      // Ad slots are already in HTML
      // This function can be used to dynamically load ads
      console.log('[Ad Manager] Ad slots initialized');
    }
  };

  // Initialize ad system when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => AdManager.init());
  } else {
    AdManager.init();
  }

  // ========================================
  // GLOBAL AD CLICK HANDLER
  // ========================================

  /**
   * Global handler for onclick ads on links
   * First click shows ad, second click allows navigation
   */
  window.handleAdClick = function(linkElement) {
    const href = linkElement.getAttribute('href');
    const clickKey = 'ad_click_' + href.replace(/[^a-z0-9]/gi, '_');
    const clicked = sessionStorage.getItem(clickKey);

    if (!clicked) {
      // First click - show ad and prevent navigation
      sessionStorage.setItem(clickKey, 'true');
      showNotification('Please click again to continue...', 2000);
      return false; // Prevent navigation
    } else {
      // Second click - allow navigation
      showNotification('Redirecting...', 1000);
      return true; // Allow navigation
    }
  };

})();
