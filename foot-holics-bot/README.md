# 🤖 Foot Holics Match Manager Bot

A Telegram bot for easily adding new football matches to your Foot Holics website. This bot guides you through a step-by-step process and generates all necessary HTML, JSON, and code files.

## ✨ Features

- **Interactive Conversation Flow** - Step-by-step guidance for adding matches
- **Input Validation** - Ensures all data is properly formatted
- **Code Generation** - Automatically generates:
  - Complete HTML event pages
  - JSON entries for events.json
  - Homepage card HTML
- **Multi-User Support** - Handle multiple users simultaneously
- **Inline Keyboards** - Easy league selection with buttons
- **Auto-Suggestions** - Suggests file names based on team names
- **File Management** - Saves all generated code in organized folders

## 📋 Prerequisites

- Python 3.8 or higher
- A Telegram account
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))

## 🚀 Installation

### 1. Clone or Download

If this bot is in your website repository:
```bash
cd foot-holics/foot-holics-bot
```

### 2. Create Virtual Environment (Recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create Telegram Bot

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow the instructions to create your bot
4. Copy the bot token you receive

### 5. Configure Environment

```bash
# Copy the example file
cp .env.example .env

# Edit .env file and add your token
# Windows: notepad .env
# Linux/Mac: nano .env
```

Add your token:
```
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

## 🎮 Usage

### Start the Bot

```bash
python bot.py
```

You should see:
```
🤖 Foot Holics Match Manager Bot is running!
Press Ctrl+C to stop
```

### Use the Bot on Telegram

1. Open Telegram
2. Search for your bot by username
3. Send `/start` command
4. Follow the step-by-step instructions

### Conversation Flow

The bot will guide you through 7 steps:

#### Step 1: Match Name
```
📝 Please send match name: Home Team vs Away Team
Example: Chelsea vs Manchester United
```

#### Step 2: Date & Time
```
📅 Please send date & time: YYYY-MM-DD HH:MM
Example: 2025-11-05 20:00
```

#### Step 3: League Selection
Interactive buttons will appear:
- ⚽ Premier League
- ⚽ La Liga
- ⚽ Serie A
- ⚽ Bundesliga
- ⚽ Ligue 1
- 🏆 Champions League
- ⚽ Others (ISL, etc.)

#### Step 4: Stadium Name
```
🏟️ Please send the stadium name:
Example: Old Trafford or Santiago Bernabéu
```

#### Step 5: Match Preview
```
📰 Please send a match preview (1-2 paragraphs)
Include key details about the match, team form, key players, or rivalry context.
```

#### Step 6: Stream URLs
```
🎥 Please send stream URLs (one per line):
You can send 1-4 URLs. Each URL should be on a separate line.

Example:
https://example.com/stream1
https://example.com/stream2

Send 'skip' if you want to add URLs later.
```

#### Step 7: Image File Name
```
🖼️ Image file name:
Suggested: chelsea-manchester-united-poster.jpg

Press Enter to accept or type a custom name.
```

### Generated Output

After completing all steps, the bot will generate and send you:

1. **HTML Event File** - Complete match detail page
2. **JSON Entry** - Data for events.json
3. **Homepage Card** - Card HTML for index.html
4. **Instructions** - Step-by-step guide for implementation

All files are also saved in the `generated/` folder:
```
generated/
├── html_files/
│   └── 2025-11-05-chelsea-vs-manchester-united.html
├── json_entries/
│   └── 2025-11-05-chelsea-vs-manchester-united.json
└── cards/
    └── 2025-11-05-chelsea-vs-manchester-united-card.html
```

## 📁 Project Structure

```
foot-holics-bot/
├── bot.py                  # Main bot code
├── requirements.txt        # Python dependencies
├── .env                    # Your bot token (create this)
├── .env.example           # Template for .env
├── .gitignore             # Git ignore rules
├── README.md              # This file
├── templates/             # HTML templates (optional)
│   ├── event_template.html
│   └── card_template.html
└── generated/             # Generated code files
    ├── html_files/
    ├── json_entries/
    └── cards/
```

## 🔧 Configuration

### Custom Templates

You can create custom templates in the `templates/` folder:

**templates/event_template.html** - Full event page template
**templates/card_template.html** - Homepage card template

The bot will use these templates if they exist, otherwise it uses built-in templates.

### Available Placeholders

In templates, use these placeholders:
- `{{MATCH_NAME}}` - Full match name
- `{{HOME_TEAM}}` - Home team name
- `{{AWAY_TEAM}}` - Away team name
- `{{DATE}}` - Full date (e.g., November 05, 2025)
- `{{DATE_SHORT}}` - Short date (e.g., Nov 05, 2025)
- `{{TIME}}` - Match time (e.g., 20:00)
- `{{LEAGUE}}` - League name
- `{{LEAGUE_SLUG}}` - League slug (e.g., premier-league)
- `{{STADIUM}}` - Stadium name
- `{{PREVIEW}}` - Match preview text
- `{{IMAGE_FILE}}` - Image filename
- `{{STREAM_LINKS}}` - Generated stream links HTML
- `{{FILE_NAME}}` - Generated filename
- `{{SLUG}}` - URL slug
- `{{EXCERPT}}` - Short preview excerpt

## 🛠️ Commands

- `/start` - Start adding a new match
- `/cancel` - Cancel current operation

## 📝 Implementation Steps

After the bot generates code:

### 1. Create HTML File
```bash
# Copy the generated HTML
# Save as YYYY-MM-DD-team1-vs-team2.html in root directory
```

### 2. Update events.json
```bash
# Open data/events.json
# Add the JSON entry at the TOP of the array
# Make sure to add a comma after it
```

### 3. Update Homepage
```bash
# Open index.html
# Find the matches grid section (around line 123)
# Add the card HTML at the TOP of the matches
```

### 4. Add Match Image
```bash
# Upload match poster to assets/img/
# Recommended size: 1200x630px
# Format: JPG or PNG
```

### 5. Create Player Pages
```bash
# Navigate to p/ folder
# Copy 1-live.html to 2-live.html, 3-live.html, 4-live.html
# Update the iframe src URL in each file with your stream URLs
```

### 6. Push to GitHub
```bash
git add .
git commit -m "Add [Match Name] match"
git push
```

## 🐛 Troubleshooting

### Bot Not Starting

**Error:** `TELEGRAM_BOT_TOKEN not found`
**Solution:** Make sure you created `.env` file with your bot token

**Error:** `ModuleNotFoundError: No module named 'telegram'`
**Solution:** Install dependencies: `pip install -r requirements.txt`

### Bot Not Responding

**Issue:** Bot shows online but doesn't respond
**Solutions:**
- Check if bot is actually running (`python bot.py`)
- Verify bot token is correct in `.env`
- Try sending `/start` command again
- Restart the bot

### Invalid Input Errors

**Issue:** Bot says my input is invalid
**Solutions:**
- Match name must contain " vs "
- Date format must be exactly: YYYY-MM-DD HH:MM
- URLs must start with http:// or https://
- Preview must be at least 50 characters

### Code Not Generating

**Issue:** Bot stops before generating code
**Solutions:**
- Make sure you completed all 7 steps
- Check for error messages in terminal
- Try restarting with `/cancel` then `/start`

## 🔒 Security Notes

- **Never commit .env file** - It contains your bot token
- **Keep your bot token secret** - Anyone with it can control your bot
- **Use private bot** - Don't share your bot publicly unless needed
- **Regular updates** - Keep dependencies updated for security patches

## 📈 Future Enhancements

Possible features to add:
- [ ] Edit existing matches
- [ ] Delete matches
- [ ] Search matches
- [ ] Bulk import from CSV
- [ ] Image upload handling
- [ ] Direct GitHub integration
- [ ] Match status updates (upcoming → live → finished)
- [ ] Automated player page creation
- [ ] Schedule auto-posting

## 🤝 Contributing

Feel free to fork and improve this bot! Some ideas:
- Add more leagues
- Improve validation
- Add more customization options
- Create web interface
- Add database support

## 📄 License

This bot is part of the Foot Holics project. Use it freely for your website.

## 💬 Support

If you encounter issues:
1. Check this README
2. Look at error messages in terminal
3. Verify all prerequisites are met
4. Try restarting the bot

## 🎉 Credits

Built for **Foot Holics** - Your premium sports streaming aggregator.

---

**Happy Match Adding! ⚽🤖**
