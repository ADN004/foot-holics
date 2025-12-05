# Foot Holics

**Live Football Streaming Aggregator**

A modern, responsive sports streaming aggregator website featuring a glassmorphism design, comprehensive match listings, and automated match management through a Telegram bot.

![Foot Holics](assets/img/og-image.jpg)

---

## What is Foot Holics?

Foot Holics is a static website that aggregates football match streaming links from various sources. It provides:

- **Match Listings** - Organized by league and date
- **Live Stream Links** - Multiple streaming options for each match
- **Match Details** - Team information, stadium, broadcast channels
- **Search Functionality** - Find matches quickly
- **Responsive Design** - Works on desktop, tablet, and mobile

---

## Features

### Website Features
- Premium glassmorphism UI design
- Fully responsive layout (mobile-first)
- SEO optimized with meta tags and structured data
- Client-side search functionality
- Multiple league support (Premier League, La Liga, Serie A, Bundesliga, Champions League, etc.)
- Live streaming player pages with multiple links
- Legal disclaimers and DMCA-compliant structure

### Telegram Bot Features
- **Add New Match** - Automatically generates HTML, JSON, and card files
- **Update Match** - Edit match details (teams, date, time, stadium, preview)
- **Delete Match** - Removes match from all files automatically
- **List Matches** - View all created matches
- **Generate Card** - Extract and generate match card HTML
- **Match Stats** - View statistics about your matches

---

## Project Structure

```
foot-holics/
├── index.html                    # Homepage with match cards
├── 2025-*-*.html                # Individual match pages
├── search.html                   # Search and filtering page
├── p/                           # Player/streaming pages
│   ├── 1-live.html
│   ├── 2-live.html
│   └── ...
├── assets/
│   ├── css/
│   │   └── main.css            # Main stylesheet
│   ├── js/
│   │   └── main.js             # Main JavaScript
│   └── img/                    # Images, posters, logos
├── data/
│   └── events.json             # Match data for search/filters
├── foot-holics-bot/            # Telegram bot for managing matches
│   ├── bot.py                  # Main bot code
│   ├── generated/              # Generated files
│   │   ├── html_files/
│   │   ├── json_entries/
│   │   └── cards/
│   ├── .env                    # Bot token (create this)
│   ├── requirements.txt        # Python dependencies
│   └── README files           # Bot documentation
├── sitemap.xml                 # SEO sitemap
├── robots.txt                  # Search engine instructions
└── README.md                   # This file
```

---

## Getting Started

### Running the Website Locally

**Option 1: Python HTTP Server**
```bash
cd foot-holics
python -m http.server 8000
# Open http://localhost:8000 in your browser
```

**Option 2: VS Code Live Server**
1. Install the "Live Server" extension in VS Code
2. Right-click on `index.html`
3. Select "Open with Live Server"

### Setting Up the Telegram Bot

1. **Navigate to bot directory:**
   ```bash
   cd foot-holics-bot
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv

   # Activate (Windows)
   .\venv\Scripts\activate

   # Activate (Mac/Linux)
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create `.env` file:**
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ```
   Get your bot token from [@BotFather](https://t.me/BotFather) on Telegram.

5. **Run the bot:**
   ```bash
   python bot.py
   ```

6. **Use the bot in Telegram:**
   - Find your bot in Telegram
   - Type `/start` to see the menu
   - Use buttons to add/update/delete matches

---

## Managing Matches

### Using the Telegram Bot (Recommended)

The Telegram bot provides a fully automated workflow:

**Add a New Match:**
1. Click **➕ Add New Match** in the bot
2. Enter match details (teams, date, time, league, stadium, preview)
3. Bot automatically:
   - Generates HTML match page
   - Adds entry to `data/events.json`
   - Adds card to `index.html`
4. You just need to:
   - Upload match poster image to `assets/img/`
   - Git commit and push

**Update a Match:**
1. Click **✏️ Update Match**
2. Select the match to edit
3. Choose which fields to update
4. Bot automatically updates:
   - Match HTML file
   - `data/events.json` entry
   - `index.html` card
5. Git commit and push

**Delete a Match:**
1. Click **🗑️ Delete Match**
2. Select and confirm deletion
3. Bot automatically removes from:
   - Project root (HTML file)
   - `data/events.json`
   - `index.html`
4. Git commit and push

### Manual Match Management

If you prefer to manage matches manually:

1. **Create new match HTML file** - Copy structure from existing match file
2. **Add entry to `data/events.json`** - Follow existing JSON structure
3. **Add card to `index.html`** - Copy card structure and update details
4. **Upload poster image** - Add to `assets/img/`
5. **Update sitemap.xml** - Add new page URL

---

## Design System

### Colors
```css
--bg: #071428              /* Deep Navy background */
--panel: #0f2a44           /* Midnight Blue panels */
--accent: #D4AF37          /* Gold accent */
--accent-2: #7DE3E3        /* Soft Cyan accent */
--text: #F5F7FA            /* Light text */
--muted: #B9C3CF           /* Muted text */
--glass: rgba(255,255,255,0.06)  /* Glass effect */
```

### Typography
- **Body:** Inter (Google Fonts)
- **Headings:** Playfair Display (Google Fonts)
- **Weights:** 400, 500, 600, 700

### Components
- Glassmorphism cards with backdrop-filter
- Smooth hover effects and micro-interactions
- Animated live badges with pulsing dots
- Gradient buttons and glass panels

---

## Customization

### Changing Site Colors

Edit CSS variables in `assets/css/main.css`:
```css
:root {
  --accent: #YOUR_COLOR;     /* Primary accent color */
  --accent-2: #YOUR_COLOR;   /* Secondary accent color */
}
```

### Adding New Leagues

1. Add badge style in `assets/css/main.css`:
```css
.league-badge.your-league {
  background: linear-gradient(135deg, #COLOR1, #COLOR2);
}
```

2. Add sidebar link in HTML files
3. Update bot's LEAGUES dictionary in `bot.py`

### Changing Telegram Popup Link

Edit `assets/js/main.js` around line 434:
```javascript
<a href="https://t.me/YOUR_CHANNEL" ...>
```

---

## Deployment

This is a static website that can be deployed to:
- **Vercel** (recommended) - Automatic deployments from GitHub
- **GitHub Pages** - Free static hosting
- **Netlify** - Free with custom domains
- Any static hosting service

Since you're using Vercel with GitHub integration, any `git push` will automatically deploy your site.

**Note:** Private repos work fine with Vercel if you signed up using GitHub OAuth.

---

## SEO & Performance

### Included Optimizations
- Meta tags and Open Graph for social sharing
- JSON-LD structured data for search engines
- Sitemap.xml for search engine crawling
- Lazy loading images for faster page loads
- Mobile-first responsive design
- Semantic HTML5 markup

### Adding Google Analytics (Optional)

Add before `</head>` in HTML files:
```html
<script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-XXXXXXXXXX');
</script>
```

---

## Legal & Disclaimers

### Content Policy

Foot Holics does NOT host any streaming content. All links shown are from third-party public sources. The site acts solely as a link aggregator.

### DMCA Compliance

- Copyright holders should contact the actual hosting platforms directly
- All trademarks and team names are property of their respective owners
- Comprehensive legal disclaimers included on every page

---

## Troubleshooting

### Bot Won't Start
```bash
cd foot-holics-bot
.\venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

### Images Not Loading
- Check file paths are correct (relative to root)
- Verify images exist in `assets/img/`
- File names are case-sensitive on Linux servers

### Mobile Menu Not Working
- Ensure `main.js` is loaded properly
- Check browser Console for JavaScript errors
- Verify viewport meta tag is present

---

## Support & Contributing

For issues, questions, or suggestions:
- Check the bot documentation in `foot-holics-bot/` folder
- Review existing match files for examples
- Test locally before deploying

---

## Tech Stack

- **Frontend:** HTML5, CSS3, JavaScript (Vanilla)
- **Design:** Glassmorphism, CSS Grid, Flexbox
- **Fonts:** Google Fonts (Inter, Playfair Display)
- **Icons:** Inline SVG (Feather Icons style)
- **Bot:** Python, python-telegram-bot library
- **Hosting:** Vercel (or any static hosting)

---

**Enjoy building your football streaming aggregator! ⚽**

*Built with passion for football fans worldwide.*
