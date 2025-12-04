# 🚀 Quick Start Guide - Foot Holics Bot

## Installation (5 minutes)

### 1. Get Your Bot Token
```
1. Open Telegram → Search @BotFather
2. Send: /newbot
3. Follow instructions
4. Copy your bot token
```

### 2. Setup Bot
```bash
cd foot-holics/foot-holics-bot

# Install dependencies
pip install -r requirements.txt

# Create .env file
# On Windows:
copy .env.example .env

# On Mac/Linux:
cp .env.example .env

# Edit .env and paste your bot token
notepad .env  # or nano .env
```

### 3. Run Bot
```bash
python bot.py
```

You'll see: `🤖 Foot Holics Match Manager Bot is running!`

## Usage (2 minutes per match)

### On Telegram:
1. Search your bot
2. Send `/start`
3. Answer 7 questions:
   - Match name (e.g., "Chelsea vs Arsenal")
   - Date & time (e.g., "2025-11-05 20:00")
   - League (click button)
   - Stadium (e.g., "Stamford Bridge")
   - Preview (1-2 paragraphs)
   - Stream URLs (1-4 links, one per line)
   - Image name (press Enter for auto-suggestion)

4. Receive 3 code blocks:
   - HTML file
   - JSON entry
   - Homepage card

## Implementation (3 minutes)

### 1. Create Match Page
```bash
# Create new file: YYYY-MM-DD-team1-vs-team2.html
# Paste HTML code from bot
```

### 2. Update Data
```bash
# Open data/events.json
# Add JSON entry at TOP of array
# Add comma after it
```

### 3. Update Homepage
```bash
# Open index.html
# Find matches grid (line ~123)
# Paste card HTML at TOP
```

### 4. Add Image
```bash
# Upload poster to assets/img/
# Name it exactly as specified by bot
```

### 5. Update Player Pages
```bash
# Edit p/2-live.html, p/3-live.html, p/4-live.html
# Change iframe src to your stream URLs
```

### 6. Push Changes
```bash
git add .
git commit -m "Add [Match Name]"
git push
```

## Done! ✅

Your match is now live on Foot Holics!

---

## Common Issues

**Bot not responding?**
- Check if bot is running: `python bot.py`
- Verify token in .env file
- Send `/start` again

**Invalid format error?**
- Match: Must contain " vs "
- Date: Must be YYYY-MM-DD HH:MM
- URLs: Must start with http:// or https://

**Need help?**
See full [README.md](README.md) for detailed instructions.
