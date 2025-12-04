# Foot Holics Bot - Complete Usage Guide

## 📋 Table of Contents
1. [Quick Start](#quick-start)
2. [How to Use the Bot](#how-to-use-the-bot)
3. [Adding New Matches with Ads](#adding-new-matches)
4. [Deleting Unwanted Matches](#deleting-matches)
5. [Adding Logos](#adding-logos)
6. [Publishing Changes](#publishing-changes)

---

## 🚀 Quick Start

### Prerequisites
- Python installed
- Virtual environment already set up in `foot-holics-bot/venv/`

### Activate the Bot

**Windows:**
```powershell
cd foot-holics-bot
.\venv\Scripts\activate
python -m foot_holics_bot
```

**Linux/Mac:**
```bash
cd foot-holics-bot
source venv/bin/activate
python -m foot_holics_bot
```

---

## 🎮 How to Use the Bot

### Starting the Bot

1. **Navigate to bot directory:**
   ```powershell
   cd c:\Users\adity\sports\foot-holics\foot-holics-bot
   ```

2. **Activate virtual environment:**
   ```powershell
   .\venv\Scripts\activate
   ```

3. **Run the bot:**
   ```powershell
   python bot.py
   ```

   (Or if it's a module:)
   ```powershell
   python -m foot_holics_bot
   ```

### Bot Commands

When the bot starts, you'll see a menu:

```
Foot Holics Bot - Menu:
1. Generate new match page
2. Update existing match
3. Delete match
4. Generate match card
5. Exit
```

---

## ➕ Adding New Matches with Ads

### Method 1: Interactive Bot

1. **Start the bot** (as shown above)

2. **Select Option 1:** "Generate new match page"

3. **Provide match details:**
   ```
   Enter home team: Manchester United
   Enter away team: Liverpool
   Enter date (YYYY-MM-DD): 2025-12-10
   Enter time (HH:MM GMT): 15:00
   Enter league: Premier League
   Enter stadium: Old Trafford
   ```

4. **Bot generates:**
   - Full match HTML page with **ads included** ✅
   - Match card for homepage
   - Saves to correct locations

5. **Files created:**
   - `2025-12-10-manchester-united-vs-liverpool.html` (with popunder + social bar ads)
   - Match card in `foot-holics-bot/generated/cards/`

### Method 2: Manual Creation

1. **Copy the template:**
   ```powershell
   cp TEMPLATE-event.html 2025-12-10-your-match.html
   ```

2. **Edit the new file:**
   - Update team names
   - Update date/time
   - Update stadium
   - **Ads are already in template!** ✅

---

## 🎨 Adding Logos & Images

### Folder Structure

```
foot-holics/
├── assets/
│   ├── img/
│   │   ├── logos/              ← Create this folder
│   │   │   ├── site/           ← Site logos
│   │   │   │   ├── logo.png           (Main logo)
│   │   │   │   ├── logo-white.png     (White version)
│   │   │   │   ├── favicon.png        (Already exists)
│   │   │   │   └── og-image.jpg       (Social media)
│   │   │   │
│   │   │   ├── teams/          ← Team logos
│   │   │   │   ├── premier-league/
│   │   │   │   │   ├── manchester-united.png
│   │   │   │   │   ├── liverpool.png
│   │   │   │   │   └── ...
│   │   │   │   ├── la-liga/
│   │   │   │   ├── serie-a/
│   │   │   │   ├── bundesliga/
│   │   │   │   └── champions-league/
│   │   │   │
│   │   │   └── leagues/        ← League logos
│   │   │       ├── premier-league.png
│   │   │       ├── la-liga.png
│   │   │       └── ...
│   │   │
│   │   └── matches/            ← Match posters (existing)
│   │       ├── real-betis-atletico-madrid.jpg
│   │       └── ...
```

### Creating Logo Folders

```powershell
cd c:\Users\adity\sports\foot-holics\assets\img
mkdir logos
cd logos
mkdir site
mkdir teams
mkdir leagues
cd teams
mkdir premier-league la-liga serie-a bundesliga champions-league
```

### Adding Logos

**1. Site Logo (Header):**
   - Create: `assets/img/logos/site/logo.png` (200x60px recommended)
   - Update in `index.html` line 44-46:
   ```html
   <a href="index.html" class="logo">
       <img src="assets/img/logos/site/logo.png" alt="Foot Holics" style="height: 40px;">
       <span>Foot Holics</span>
   </a>
   ```

**2. Team Logos (Match Pages):**
   - Add to: `assets/img/logos/teams/premier-league/manchester-united.png`
   - Reference in match HTML:
   ```html
   <img src="assets/img/logos/teams/premier-league/manchester-united.png"
        alt="Manchester United"
        style="height: 60px;">
   ```

**3. Match Posters:**
   - Add to: `assets/img/matches/your-match.jpg` (1200x630px recommended)
   - Reference in match card:
   ```html
   <img src="assets/img/matches/your-match.jpg"
        alt="Team A vs Team B"
        class="match-poster">
   ```

### Where to Find Logos

**Free Logo Sources:**
- Team logos: Wikipedia (public domain)
- League logos: Official websites (use carefully, respect copyright)
- Or use text-only design (current setup)

---

## 🗑️ Deleting Unwanted Matches

### Method 1: Using Bot

1. **Start bot** and select **Option 3:** "Delete match"

2. **Enter match filename:**
   ```
   Enter match file to delete: 2025-10-26-brentford-vs-liverpool.html
   ```

3. **Bot removes:**
   - Match HTML file
   - Match card
   - Entry from `data/events.json`

### Method 2: Manual Deletion

1. **Delete HTML file:**
   ```powershell
   del 2025-10-26-brentford-vs-liverpool.html
   ```

2. **Delete match card (if exists):**
   ```powershell
   del foot-holics-bot/generated/cards/2025-10-26-brentford-vs-liverpool-card.html
   ```

3. **Remove from index.html:**
   - Open `index.html`
   - Find the match card (search for match name)
   - Delete the entire `<article class="glass-card match-card">` block

4. **Remove from events.json (optional):**
   - Open `data/events.json`
   - Remove the match entry

---

## ✅ Bot-Generated Pages Already Include Ads!

### Ads Automatically Added:

When you generate a new match using the bot, it includes:
- ✅ **Popunder ad** (triggers on click)
- ✅ **Social Bar ad** (sticky bottom)
- ✅ **Ad placeholder slots** for future expansion

### Template Already Has Ads:

The `TEMPLATE-event.html` includes:
```html
<!-- Adsterra Ad Scripts -->
<script type="text/javascript" src="//pl28190353..."></script>
<script type="text/javascript" src="//pl28190484..."></script>
```

**So YES - all new matches automatically have ads!** ✅

---

## 📤 Publishing Changes

### After Adding/Deleting Matches:

1. **Check what changed:**
   ```powershell
   git status
   ```

2. **Stage changes:**
   ```powershell
   git add .
   ```

3. **Commit:**
   ```powershell
   git commit -m "Add: Manchester United vs Liverpool match"
   ```

   Or for deletions:
   ```powershell
   git commit -m "Remove: Old Brentford vs Liverpool match"
   ```

4. **Push to GitHub:**
   ```powershell
   git push
   ```

5. **Vercel auto-deploys!** (30-60 seconds)
   - Check: https://vercel.com/dashboard
   - Live: https://foot-holics.vercel.app

---

## 🤖 Bot Code Location

### Main Bot Files:

```
foot-holics-bot/
├── bot.py                  ← Main bot script
├── requirements.txt        ← Dependencies
├── .env.example           ← Environment variables template
├── README.md              ← Bot documentation
├── generated/             ← Generated files
│   ├── html_files/        ← Full match pages
│   └── cards/             ← Match cards for homepage
└── venv/                  ← Virtual environment
```

---

## 🔧 Common Bot Commands

### Generate Match:
```python
# In bot menu:
1 → Enter match details → Bot generates HTML + Card
```

### Update Existing Match:
```python
# In bot menu:
2 → Enter filename → Update details
```

### Delete Match:
```python
# In bot menu:
3 → Enter filename → Confirms deletion
```

---

## 📝 Quick Workflow Example

### Adding Today's Match:

1. **Start bot:**
   ```powershell
   cd foot-holics-bot
   .\venv\Scripts\activate
   python bot.py
   ```

2. **Select 1** (Generate new match)

3. **Enter details:**
   ```
   Home: Arsenal
   Away: Chelsea
   Date: 2025-12-15
   Time: 17:30
   League: Premier League
   Stadium: Emirates Stadium
   ```

4. **Bot generates file** with ads included ✅

5. **Copy to root:**
   ```powershell
   copy foot-holics-bot\generated\html_files\2025-12-15-arsenal-vs-chelsea.html .
   ```

6. **Add match card to index.html** (copy from generated cards folder)

7. **Commit and push:**
   ```powershell
   git add .
   git commit -m "Add: Arsenal vs Chelsea - Dec 15"
   git push
   ```

8. **Live in 60 seconds!** 🚀

---

## 🎯 Pro Tips

1. **Ads are automatic** - Don't worry, all bot-generated pages have ads!

2. **Delete old matches weekly** - Keep site fresh and relevant

3. **Add matches 1-2 hours before game** - Best for traffic

4. **Use consistent naming:** `YYYY-MM-DD-team-vs-team.html`

5. **Update index.html** - Add new match cards prominently

6. **Check Adsterra daily** - Monitor which matches earn most

---

## ❓ Troubleshooting

### Bot won't start:
```powershell
# Reinstall dependencies
cd foot-holics-bot
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Ads not showing on new matches:
- Check TEMPLATE-event.html has ad codes
- Verify bot copies template correctly
- Manually add ad scripts if needed

### Match not appearing on homepage:
- Generate match card using bot Option 4
- Copy card HTML to index.html
- Commit and push

---

## 📞 Need Help?

- Bot issues: Check `foot-holics-bot/README.md`
- Ads not working: Check Adsterra dashboard
- Deployment: Check Vercel logs

---

**Happy Match Adding! ⚽💰**
