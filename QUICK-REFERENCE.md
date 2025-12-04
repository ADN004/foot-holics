# Foot Holics - Quick Reference Guide

## 🚀 Quick Commands

### Start Bot
```powershell
cd foot-holics-bot
.\venv\Scripts\activate
python bot.py
```

### Add New Match
1. Run bot → Select option 1
2. Enter match details
3. Copy generated file to root
4. Update index.html with match card
5. `git add . && git commit -m "Add match" && git push`

### Delete Match
```powershell
# Delete file
del 2025-12-10-team-vs-team.html

# Remove card from index.html
# (Find and delete the match card block)

# Commit
git add . && git commit -m "Remove old match" && git push
```

---

## 📁 Important Paths

- **Match pages:** Root folder (`foot-holics/`)
- **Bot generated:** `foot-holics-bot/generated/html_files/`
- **Match cards:** `foot-holics-bot/generated/cards/`
- **Logos:** `assets/img/logos/`
- **Match posters:** `assets/img/matches/`
- **Templates:** `TEMPLATE-event.html`, `foot-holics-bot/bot.py`

---

## 📋 Folder Structure

```
foot-holics/
├── index.html                          # Homepage
├── 2025-XX-XX-team-vs-team.html       # Match pages
├── TEMPLATE-event.html                 # Template for new matches
├── BOT-USAGE-GUIDE.md                 # Full bot guide
├── assets/
│   ├── img/
│   │   ├── logos/
│   │   │   ├── site/                  # Site logos
│   │   │   ├── teams/                 # Team logos
│   │   │   │   ├── premier-league/
│   │   │   │   ├── la-liga/
│   │   │   │   └── ...
│   │   │   └── leagues/               # League logos
│   │   └── matches/                   # Match posters
└── foot-holics-bot/
    ├── bot.py                          # Bot script (has ads!)
    ├── generated/
    │   ├── html_files/                 # Generated pages
    │   └── cards/                      # Match cards
    └── venv/                           # Python environment
```

---

## ✅ After Adding/Deleting Matches

Always run:
```powershell
git add .
git commit -m "Your message"
git push
```

Vercel auto-deploys in 30-60 seconds!

---

## 🎯 Navigation Links Explained

The navigation links work as follows:
- **Home** → `index.html` (homepage)
- **Leagues** → Scrolls to leagues sidebar (same page)
- **Search** → Focuses search input (same page)
- **About** → Scrolls to footer about section (same page)

This is a **single-page design** - all links scroll to sections on the same page.

---

## 💰 Ads Status

✅ **All pages now have ads:**
- Index/Home ✅
- Match pages ✅
- Player pages ✅
- Legal pages ✅
- Bot-generated pages ✅
- Template ✅

**New matches automatically include ads!**

---

## 🔗 Important Links

- **Live Site:** https://foot-holics.vercel.app
- **GitHub:** https://github.com/ADN004/foot-holics
- **Vercel Dashboard:** https://vercel.com/dashboard
- **Adsterra Dashboard:** https://beta.publishers.adsterra.com
- **WhatsApp:** https://chat.whatsapp.com/KG7DBpC0BKv6bFtlzfOr2T
- **Telegram:** https://t.me/+XyKdBR9chQpjM2I9

---

## 📞 Need Help?

- Full bot guide: `BOT-USAGE-GUIDE.md`
- Bot docs: `foot-holics-bot/README.md`
- Quick start: `foot-holics-bot/QUICKSTART.md`

---

**Remember:** Every `git push` auto-deploys to Vercel! 🚀
