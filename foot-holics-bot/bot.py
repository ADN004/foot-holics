#!/usr/bin/env python3
"""
Foot Holics Match Manager Bot
A Telegram bot for easily adding new football matches to the Foot Holics website.
"""

import os
import json
import re
from datetime import datetime
from typing import Dict, Any
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# Load environment variables
load_dotenv()

# Conversation states
(
    MATCH_NAME,
    DATE_TIME,
    LEAGUE,
    STADIUM,
    PREVIEW,
    STREAM_URLS,
    IMAGE_NAME,
    CONFIRM,
) = range(8)

# League data with emojis and colors
LEAGUES = {
    "Premier League": {
        "emoji": "⚽",
        "slug": "premier-league",
        "color": "#37003C",
    },
    "La Liga": {
        "emoji": "⚽",
        "slug": "laliga",
        "color": "#FF6B00",
    },
    "Serie A": {
        "emoji": "⚽",
        "slug": "serie-a",
        "color": "#024494",
    },
    "Bundesliga": {
        "emoji": "⚽",
        "slug": "bundesliga",
        "color": "#D3010C",
    },
    "Ligue 1": {
        "emoji": "⚽",
        "slug": "ligue-1",
        "color": "#002395",
    },
    "Champions League": {
        "emoji": "🏆",
        "slug": "champions-league",
        "color": "#00285E",
    },
    "Others": {
        "emoji": "⚽",
        "slug": "others",
        "color": "#8B5CF6",
    },
}


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def generate_event_id() -> str:
    """Generate unique event ID based on timestamp."""
    return f"event-{int(datetime.now().timestamp())}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask for match name."""
    user = update.effective_user

    welcome_message = f"""
🤖 **Welcome to Foot Holics Match Manager!**

Hi {user.first_name}! I'll help you add a new match to your website.

Let's get started! 🚀

📝 **Step 1/7:** Please send the match name in this format:
`Home Team vs Away Team`

Example: `Chelsea vs Manchester United`

_Type /cancel anytime to stop_
"""

    await update.message.reply_text(welcome_message, parse_mode="Markdown")
    return MATCH_NAME


async def match_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store match name and ask for date/time."""
    text = update.message.text.strip()

    # Validate format
    if " vs " not in text.lower():
        await update.message.reply_text(
            "❌ Invalid format! Match name must contain ' vs '\n\n"
            "Example: `Chelsea vs Manchester United`",
            parse_mode="Markdown"
        )
        return MATCH_NAME

    # Split teams
    teams = re.split(r"\s+vs\s+", text, flags=re.IGNORECASE)
    if len(teams) != 2:
        await update.message.reply_text(
            "❌ Please provide exactly two teams separated by 'vs'",
            parse_mode="Markdown"
        )
        return MATCH_NAME

    context.user_data["match_name"] = text
    context.user_data["home_team"] = teams[0].strip()
    context.user_data["away_team"] = teams[1].strip()

    await update.message.reply_text(
        f"✅ Match: **{text}**\n\n"
        f"📅 **Step 2/7:** Please send the date and time:\n"
        f"`YYYY-MM-DD HH:MM`\n\n"
        f"Example: `2025-11-05 20:00`",
        parse_mode="Markdown"
    )
    return DATE_TIME


async def date_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store date/time and show league selection."""
    text = update.message.text.strip()

    # Validate format
    try:
        match_datetime = datetime.strptime(text, "%Y-%m-%d %H:%M")

        # Check if date is in the future
        if match_datetime < datetime.now():
            await update.message.reply_text(
                "⚠️ Warning: This date is in the past. Continue anyway?\n"
                "Type the date again to confirm or send a new date."
            )
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid format! Use: `YYYY-MM-DD HH:MM`\n\n"
            "Example: `2025-11-05 20:00`",
            parse_mode="Markdown"
        )
        return DATE_TIME

    context.user_data["date"] = match_datetime.strftime("%Y-%m-%d")
    context.user_data["time"] = match_datetime.strftime("%H:%M")
    context.user_data["datetime_obj"] = match_datetime

    # Create inline keyboard for league selection
    keyboard = [
        [
            InlineKeyboardButton("⚽ Premier League", callback_data="league_Premier League"),
            InlineKeyboardButton("⚽ La Liga", callback_data="league_La Liga"),
        ],
        [
            InlineKeyboardButton("⚽ Serie A", callback_data="league_Serie A"),
            InlineKeyboardButton("⚽ Bundesliga", callback_data="league_Bundesliga"),
        ],
        [
            InlineKeyboardButton("⚽ Ligue 1", callback_data="league_Ligue 1"),
            InlineKeyboardButton("🏆 Champions League", callback_data="league_Champions League"),
        ],
        [
            InlineKeyboardButton("⚽ Others (ISL, etc.)", callback_data="league_Others"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ Date & Time: **{text}**\n\n"
        f"🏆 **Step 3/7:** Select the league:",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return LEAGUE


async def league_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store league and ask for stadium."""
    query = update.callback_query
    await query.answer()

    league_name = query.data.replace("league_", "")
    league_data = LEAGUES.get(league_name, LEAGUES["Others"])

    context.user_data["league"] = league_name
    context.user_data["league_slug"] = league_data["slug"]
    context.user_data["league_emoji"] = league_data["emoji"]

    await query.edit_message_text(
        f"✅ League: **{league_name}** {league_data['emoji']}\n\n"
        f"🏟️ **Step 4/7:** Please send the stadium name:\n\n"
        f"Example: `Old Trafford` or `Santiago Bernabéu`",
        parse_mode="Markdown"
    )
    return STADIUM


async def stadium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store stadium and ask for match preview."""
    text = update.message.text.strip()

    if len(text) < 3:
        await update.message.reply_text("❌ Stadium name too short. Please try again.")
        return STADIUM

    context.user_data["stadium"] = text

    await update.message.reply_text(
        f"✅ Stadium: **{text}**\n\n"
        f"📰 **Step 5/7:** Please send a match preview (1-2 paragraphs):\n\n"
        f"This will be displayed on the match page. Include key details about the match, "
        f"team form, key players, or rivalry context.",
        parse_mode="Markdown"
    )
    return PREVIEW


async def preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store preview and ask for stream URLs."""
    text = update.message.text.strip()

    if len(text) < 50:
        await update.message.reply_text(
            "⚠️ Preview seems too short. Please provide a more detailed description "
            "(at least 50 characters)."
        )
        return PREVIEW

    context.user_data["preview"] = text

    await update.message.reply_text(
        f"✅ Preview saved!\n\n"
        f"🎥 **Step 6/7:** Please send stream URLs (one per line):\n\n"
        f"You can send 1-4 URLs. Each URL should be on a separate line.\n\n"
        f"Example:\n"
        f"`https://example.com/stream1\n"
        f"https://example.com/stream2`\n\n"
        f"Send `skip` if you want to add URLs later.",
        parse_mode="Markdown"
    )
    return STREAM_URLS


async def stream_urls(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store stream URLs and ask for image name."""
    text = update.message.text.strip()

    if text.lower() == "skip":
        context.user_data["stream_urls"] = []
    else:
        # Split by newlines and validate URLs
        urls = [url.strip() for url in text.split("\n") if url.strip()]

        # Basic URL validation
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        invalid_urls = [url for url in urls if not url_pattern.match(url)]

        if invalid_urls:
            await update.message.reply_text(
                f"❌ Invalid URL(s) detected:\n{chr(10).join(invalid_urls)}\n\n"
                f"Please send valid URLs starting with http:// or https://"
            )
            return STREAM_URLS

        if len(urls) > 4:
            await update.message.reply_text(
                "⚠️ Maximum 4 URLs allowed. I'll use the first 4 URLs."
            )
            urls = urls[:4]

        context.user_data["stream_urls"] = urls

    # Generate suggested image name
    home_slug = slugify(context.user_data["home_team"])
    away_slug = slugify(context.user_data["away_team"])
    suggested_name = f"{home_slug}-{away_slug}-poster.jpg"

    context.user_data["suggested_image"] = suggested_name

    stream_count = len(context.user_data["stream_urls"])

    await update.message.reply_text(
        f"✅ {stream_count} stream URL(s) saved!\n\n"
        f"🖼️ **Step 7/7:** Image file name:\n\n"
        f"Suggested: `{suggested_name}`\n\n"
        f"Press Enter to accept or type a custom name.\n"
        f"(Just the filename, it will be saved in `assets/img/`)",
        parse_mode="Markdown"
    )
    return IMAGE_NAME


async def image_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store image name and generate all code."""
    text = update.message.text.strip()

    if not text or text.lower() in ["ok", "yes", "confirm"]:
        image_file = context.user_data["suggested_image"]
    else:
        # Ensure it has an image extension
        if not any(text.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
            text += ".jpg"
        image_file = text

    context.user_data["image_file"] = image_file

    # Generate all code
    await update.message.reply_text("⏳ Generating code files... Please wait.")

    try:
        html_code = generate_html(context.user_data)
        json_code = generate_json(context.user_data)
        card_code = generate_card(context.user_data)

        # Save generated files
        date_slug = context.user_data["date"]
        home_slug = slugify(context.user_data["home_team"])
        away_slug = slugify(context.user_data["away_team"])
        filename_base = f"{date_slug}-{home_slug}-vs-{away_slug}"

        # Save to generated folder
        os.makedirs("generated/html_files", exist_ok=True)
        os.makedirs("generated/json_entries", exist_ok=True)
        os.makedirs("generated/cards", exist_ok=True)

        with open(f"generated/html_files/{filename_base}.html", "w", encoding="utf-8") as f:
            f.write(html_code)

        with open(f"generated/json_entries/{filename_base}.json", "w", encoding="utf-8") as f:
            f.write(json_code)

        with open(f"generated/cards/{filename_base}-card.html", "w", encoding="utf-8") as f:
            f.write(card_code)

        # Send results
        await send_generated_code(update, context, html_code, json_code, card_code, filename_base)

    except Exception as e:
        await update.message.reply_text(f"❌ Error generating code: {str(e)}")
        return ConversationHandler.END

    return ConversationHandler.END


def generate_html(data: Dict[str, Any]) -> str:
    """Generate complete HTML event file."""
    # Read template
    template_path = "templates/event_template.html"
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    else:
        # Use inline template if file doesn't exist
        template = get_inline_event_template()

    # Prepare data
    date_obj = data["datetime_obj"]
    home_slug = slugify(data["home_team"])
    away_slug = slugify(data["away_team"])
    filename = f"{data['date']}-{home_slug}-vs-{away_slug}.html"

    # Generate ISO date for JSON-LD
    iso_date = date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")

    # URL encode match name for social sharing
    from urllib.parse import quote
    match_name_encoded = quote(data["match_name"])

    # Generate stream links HTML
    stream_links = generate_stream_links_html(data["stream_urls"])

    # Replace placeholders
    html = template.replace("{{MATCH_NAME}}", data["match_name"])
    html = html.replace("{{HOME_TEAM}}", data["home_team"])
    html = html.replace("{{AWAY_TEAM}}", data["away_team"])
    html = html.replace("{{HOME_EMOJI}}", "⚽")  # Default emoji for home team
    html = html.replace("{{AWAY_EMOJI}}", "⚽")  # Default emoji for away team
    html = html.replace("{{DATE}}", date_obj.strftime("%B %d, %Y"))
    html = html.replace("{{DATE_SHORT}}", date_obj.strftime("%b %d, %Y"))
    html = html.replace("{{ISO_DATE}}", iso_date)
    html = html.replace("{{TIME}}", data["time"])
    html = html.replace("{{LEAGUE}}", data["league"])
    html = html.replace("{{LEAGUE_SLUG}}", data["league_slug"])
    html = html.replace("{{STADIUM}}", data["stadium"])
    html = html.replace("{{PREVIEW}}", data["preview"])
    html = html.replace("{{IMAGE_FILE}}", data["image_file"])
    html = html.replace("{{STREAM_LINKS}}", stream_links)
    html = html.replace("{{FILE_NAME}}", filename)
    html = html.replace("{{SLUG}}", f"{home_slug}-vs-{away_slug}")
    html = html.replace("{{MATCH_NAME_ENCODED}}", match_name_encoded)

    return html


def generate_json(data: Dict[str, Any]) -> str:
    """Generate JSON entry for events.json."""
    date_obj = data["datetime_obj"]
    home_slug = slugify(data["home_team"])
    away_slug = slugify(data["away_team"])
    slug = f"{data['date']}-{home_slug}-vs-{away_slug}"

    # Create excerpt from preview (first 150 chars)
    excerpt = data["preview"][:150] + "..." if len(data["preview"]) > 150 else data["preview"]

    event_data = {
        "id": generate_event_id(),
        "date": data["date"],
        "time": data["time"],
        "slug": slug,
        "title": data["match_name"],
        "homeTeam": data["home_team"],
        "awayTeam": data["away_team"],
        "league": data["league"],
        "leagueSlug": data["league_slug"],
        "stadium": data["stadium"],
        "poster": f"assets/img/{data['image_file']}",
        "excerpt": excerpt,
        "status": "upcoming",
        "broadcast": [
            {"name": "Stream 1", "url": data["stream_urls"][0] if len(data["stream_urls"]) > 0 else "#"},
            {"name": "Stream 2", "url": data["stream_urls"][1] if len(data["stream_urls"]) > 1 else "#"},
        ],
        "streams": len(data["stream_urls"])
    }

    return json.dumps(event_data, indent=2)


def generate_card(data: Dict[str, Any]) -> str:
    """Generate homepage card HTML."""
    template_path = "templates/card_template.html"
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    else:
        template = get_inline_card_template()

    date_obj = data["datetime_obj"]
    home_slug = slugify(data["home_team"])
    away_slug = slugify(data["away_team"])
    filename = f"{data['date']}-{home_slug}-vs-{away_slug}.html"

    # Create excerpt
    excerpt = data["preview"][:120] + "..." if len(data["preview"]) > 120 else data["preview"]

    card = template.replace("{{MATCH_NAME}}", data["match_name"])
    card = card.replace("{{IMAGE_FILE}}", data["image_file"])
    card = card.replace("{{LEAGUE}}", data["league"])
    card = card.replace("{{LEAGUE_SLUG}}", data["league_slug"])
    card = card.replace("{{DATE_SHORT}}", date_obj.strftime("%b %d, %Y"))
    card = card.replace("{{TIME}}", data["time"])
    card = card.replace("{{STADIUM}}", data["stadium"])
    card = card.replace("{{EXCERPT}}", excerpt)
    card = card.replace("{{FILE_NAME}}", filename)

    return card


def generate_stream_links_html(urls: list) -> str:
    """Generate HTML for stream links."""
    if not urls:
        return "<p>Stream links will be added soon.</p>"

    html_parts = []
    for i, url in enumerate(urls, 1):
        html_parts.append(f"""
                    <div class="stream-option">
                        <div class="stream-info">
                            <h4>🎥 Stream Option {i}</h4>
                            <p>HD Quality • Multiple Languages</p>
                        </div>
                        <a href="p/{i}-live.html" class="btn btn-primary">
                            Watch Stream {i}
                            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                                <polyline points="12 5 19 12 12 19"></polyline>
                            </svg>
                        </a>
                    </div>""")

    return "\n".join(html_parts)


async def send_generated_code(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    html_code: str,
    json_code: str,
    card_code: str,
    filename_base: str
) -> None:
    """Send generated code to user in formatted messages."""

    success_msg = """
🎉 **MATCH CODE GENERATED SUCCESSFULLY!**

All files have been saved in the `generated/` folder.
"""
    await update.message.reply_text(success_msg, parse_mode="Markdown")

    # Send HTML file (in parts if too long)
    html_msg = f"📄 **1. HTML FILE:** `{filename_base}.html`\n\n```html\n{html_code[:3800]}\n```"
    await update.message.reply_text(html_msg, parse_mode="Markdown")

    if len(html_code) > 3800:
        remaining = html_code[3800:]
        while remaining:
            chunk = remaining[:3900]
            await update.message.reply_text(f"```html\n{chunk}\n```", parse_mode="Markdown")
            remaining = remaining[3900:]

    # Send JSON entry
    json_msg = f"📊 **2. JSON ENTRY** (add to top of events.json):\n\n```json\n{json_code}\n```"
    await update.message.reply_text(json_msg, parse_mode="Markdown")

    # Send card HTML
    card_msg = f"🏠 **3. HOMEPAGE CARD** (add to matches grid):\n\n```html\n{card_code[:3800]}\n```"
    await update.message.reply_text(card_msg, parse_mode="Markdown")

    # Send instructions
    instructions = f"""
📋 **NEXT STEPS:**

1️⃣ Create HTML file:
   • Copy the HTML code above
   • Save as `{filename_base}.html` in root directory

2️⃣ Update events.json:
   • Open `data/events.json`
   • Add the JSON entry at the **top** of the array

3️⃣ Update homepage:
   • Open `index.html`
   • Add the card HTML at the **top** of matches grid (line ~123)

4️⃣ Add match image:
   • Upload poster image to `assets/img/{context.user_data['image_file']}`
   • Recommended size: 1200x630px

5️⃣ Create player pages:
   • Copy `p/1-live.html` to `p/2-live.html`, `p/3-live.html`, etc.
   • Update the iframe `src` URLs in each file

6️⃣ Push to GitHub:
   ```bash
   git add .
   git commit -m "Add {context.user_data['match_name']} match"
   git push
   ```

✅ All done! Your match is ready to go live!

Type /start to add another match.
"""

    await update.message.reply_text(instructions, parse_mode="Markdown")


def get_inline_event_template() -> str:
    """Return inline HTML template matching the brentford-vs-liverpool structure."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Watch {{MATCH_NAME}} live - {{LEAGUE}} clash on {{DATE}} at {{STADIUM}}. Find multiple streaming links and match preview.">
    <meta name="keywords" content="{{MATCH_NAME}}, {{LEAGUE}} live stream, watch football online, {{STADIUM}}">

    <!-- Open Graph -->
    <meta property="og:title" content="{{MATCH_NAME}} - {{LEAGUE}} Live Stream">
    <meta property="og:description" content="Watch the {{LEAGUE}} match between {{HOME_TEAM}} and {{AWAY_TEAM}} live on {{DATE}}.">
    <meta property="og:type" content="website">
    <meta property="og:image" content="/assets/img/{{IMAGE_FILE}}">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{{MATCH_NAME}} - {{LEAGUE}} Live Stream">
    <meta name="twitter:description" content="Watch the {{LEAGUE}} match live with multiple streaming options.">

    <title>{{MATCH_NAME}} - {{LEAGUE}} Live Stream | Foot Holics</title>

    <!-- Canonical -->
    <link rel="canonical" href="https://footholics.example/{{FILE_NAME}}">

    <!-- Preconnect to Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">

    <!-- Stylesheet -->
    <link rel="stylesheet" href="assets/css/main.css">

    <!-- Favicon -->
    <link rel="icon" type="image/png" href="assets/img/favicon.png">

    <!-- JSON-LD Structured Data -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "SportsEvent",
      "name": "{{MATCH_NAME}}",
      "startDate": "{{ISO_DATE}}",
      "location": {
        "@type": "Place",
        "name": "{{STADIUM}}"
      },
      "homeTeam": {
        "@type": "SportsTeam",
        "name": "{{HOME_TEAM}}"
      },
      "awayTeam": {
        "@type": "SportsTeam",
        "name": "{{AWAY_TEAM}}"
      },
      "sport": "Football"
    }
    </script>
</head>
<body>
    <!-- Header -->
    <header class="site-header">
        <div class="container">
            <div class="header-inner">
                <a href="index.html" class="logo">
                    <div class="logo-icon">⚽</div>
                    <span>Foot Holics</span>
                </a>

                <nav class="primary-nav" id="primaryNav">
                    <a href="index.html">Home</a>
                    <a href="/#leagues">Leagues</a>
                    <a href="/#about">About</a>
                </nav>

                <div class="cta-group" id="ctaGroup">
                    <a href="https://chat.whatsapp.com/KG7DBpC0BKv6bFtlzfOr2T" target="_blank" rel="noopener noreferrer" class="btn btn-secondary">
                        <svg class="btn-icon" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z"/>
                        </svg>
                        WhatsApp
                    </a>
                    <a href="https://t.me/+XyKdBR9chQpjM2I9" target="_blank" rel="noopener noreferrer" class="btn btn-primary">
                        <svg class="btn-icon" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/>
                        </svg>
                        Telegram
                    </a>
                </div>

                <button class="mobile-menu-btn" id="mobileMenuBtn" aria-label="Toggle menu">☰</button>
            </div>
        </div>
    </header>

    <!-- Breadcrumbs -->
    <div class="container" style="margin-top: 2rem;">
        <nav class="breadcrumbs" aria-label="Breadcrumb">
            <a href="index.html">Home</a>
            <span class="breadcrumb-separator">›</span>
            <a href="/#leagues">{{LEAGUE}}</a>
            <span class="breadcrumb-separator">›</span>
            <span>{{MATCH_NAME}}</span>
        </nav>
    </div>

    <!-- Event Hero -->
    <div class="container" style="margin-top: 2rem;">
        <div class="event-hero">
            <img src="assets/img/{{IMAGE_FILE}}" alt="{{MATCH_NAME}}" class="event-hero-bg">
            <div class="event-hero-content animate-fade-in">
                <h1 class="event-title">{{MATCH_NAME}}</h1>
                <div class="event-meta-row">
                    <span class="league-badge {{LEAGUE_SLUG}}">{{LEAGUE}}</span>
                    <div class="match-meta-item">
                        <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                            <line x1="16" y1="2" x2="16" y2="6"></line>
                            <line x1="8" y1="2" x2="8" y2="6"></line>
                            <line x1="3" y1="10" x2="21" y2="10"></line>
                        </svg>
                        <span>{{DATE}} at {{TIME}} GMT</span>
                    </div>
                    <div class="match-meta-item">
                        <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                            <circle cx="12" cy="10" r="3"></circle>
                        </svg>
                        <span>{{STADIUM}}</span>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Main Content -->
    <main class="container" style="margin-top: 3rem;">
        <!-- Teams Block -->
        <div class="teams-block">
            <div class="team">
                <div class="team-crest" style="background: linear-gradient(135deg, #D4AF37 0%, #FFD700 100%);">{{HOME_EMOJI}}</div>
                <h2 class="team-name">{{HOME_TEAM}}</h2>
                <p class="text-muted">Home</p>
            </div>
            <div class="vs">VS</div>
            <div class="team">
                <div class="team-crest" style="background: linear-gradient(135deg, #0EA5E9 0%, #06B6D4 100%);">{{AWAY_EMOJI}}</div>
                <h2 class="team-name">{{AWAY_TEAM}}</h2>
                <p class="text-muted">Away</p>
            </div>
        </div>

        <!-- Match Preview -->
        <section class="glass-card mb-4">
            <h2 style="color: var(--accent); margin-bottom: 1rem;">Match Preview</h2>
            <p>{{PREVIEW}}</p>
        </section>

        <!-- Broadcast Channels -->
        <section class="glass-card mb-4">
            <h2 style="color: var(--accent); margin-bottom: 1rem;">Official Broadcast Channels</h2>
            <table class="broadcast-table">
                <thead>
                    <tr>
                        <th>Country</th>
                        <th>Channel / Platform</th>
                        <th>Notes</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>🇬🇧 United Kingdom</td>
                        <td>Sky Sports Premier League</td>
                        <td>HD, Sky Go available</td>
                    </tr>
                    <tr>
                        <td>🇺🇸 United States</td>
                        <td>NBC Sports, Peacock</td>
                        <td>Streaming available</td>
                    </tr>
                    <tr>
                        <td>🇮🇳 India</td>
                        <td>Star Sports, Hotstar</td>
                        <td>Hindi & English commentary</td>
                    </tr>
                    <tr>
                        <td>🇪🇸 Spain</td>
                        <td>DAZN</td>
                        <td>Streaming, HD</td>
                    </tr>
                    <tr>
                        <td>🌍 International</td>
                        <td>Various (check local listings)</td>
                        <td>Contact your provider</td>
                    </tr>
                </tbody>
            </table>
        </section>

        <!-- Watch Live Section -->
        <section class="glass-card mb-4">
            <h2 style="color: var(--accent); margin-bottom: 1rem;">📺 Watch Live - Streaming Links</h2>
            <p class="text-muted mb-3" style="font-size: 0.9rem;">
                If one stream doesn't work, try another link. Click any link to open the live player.
                <strong>Note:</strong> These links are from third-party sources. Quality and availability may vary.
            </p>

            <div class="stream-links">
                <a href="p/1-live.html?match={{SLUG}}" class="stream-link-card">
                    <span class="live-badge">
                        <span class="live-dot"></span>
                        LIVE
                    </span>
                    <span class="stream-link-label">LINK 1</span>
                    <div class="stream-badges">
                        <span class="quality-badge hd">HD</span>
                        <span class="lang-badge">EN</span>
                    </div>
                    <p style="font-size: 0.75rem; color: var(--muted); margin-top: 0.5rem;">Desktop / Mobile</p>
                </a>

                <a href="p/2-live.html?match={{SLUG}}" class="stream-link-card">
                    <span class="live-badge">
                        <span class="live-dot"></span>
                        LIVE
                    </span>
                    <span class="stream-link-label">LINK 2</span>
                    <div class="stream-badges">
                        <span class="quality-badge hd">HD</span>
                        <span class="lang-badge">EN</span>
                    </div>
                    <p style="font-size: 0.75rem; color: var(--muted); margin-top: 0.5rem;">Desktop / Mobile</p>
                </a>

                <a href="p/3-live.html?match={{SLUG}}" class="stream-link-card">
                    <span class="stream-link-label">LINK 3</span>
                    <div class="stream-badges">
                        <span class="quality-badge sd">SD</span>
                        <span class="lang-badge">EN</span>
                    </div>
                    <p style="font-size: 0.75rem; color: var(--muted); margin-top: 0.5rem;">Mobile Optimized</p>
                </a>

                <a href="p/4-live.html?match={{SLUG}}" class="stream-link-card">
                    <span class="live-badge">
                        <span class="live-dot"></span>
                        LIVE
                    </span>
                    <span class="stream-link-label">LINK 4</span>
                    <div class="stream-badges">
                        <span class="quality-badge hd">HD</span>
                        <span class="lang-badge">Multi</span>
                    </div>
                    <p style="font-size: 0.75rem; color: var(--muted); margin-top: 0.5rem;">Multi-language</p>
                </a>
            </div>

            <p class="text-muted" style="margin-top: 1.5rem; font-size: 0.85rem;">
                💡 <strong>Tip:</strong> If a player fails to load, wait 20 seconds or try opening in a new tab.
                Video quality depends on the third-party source.
            </p>
        </section>

        <!-- Social Share -->
        <section class="glass-card mb-4">
            <h3 style="color: var(--accent); margin-bottom: 1rem;">Share This Match</h3>
            <div style="display: flex; gap: 1rem; flex-wrap: wrap;">
                <a href="https://api.whatsapp.com/send?text=Watch%20{{MATCH_NAME_ENCODED}}%20Live%20-%20https://footholics.example/{{FILE_NAME}}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="font-size: 0.9rem;">
                    💚 WhatsApp
                </a>
                <a href="https://www.facebook.com/sharer/sharer.php?u=https://footholics.example/{{FILE_NAME}}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="font-size: 0.9rem;">
                    📘 Facebook
                </a>
                <a href="https://twitter.com/intent/tweet?url=https://footholics.example/{{FILE_NAME}}&text=Watch%20{{MATCH_NAME_ENCODED}}%20Live" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="font-size: 0.9rem;">
                    ✖️ X
                </a>
                <a href="https://t.me/share/url?url=https://footholics.example/{{FILE_NAME}}&text=Watch%20{{MATCH_NAME_ENCODED}}%20Live" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="font-size: 0.9rem;">
                    ✈️ Telegram
                </a>
                <a href="https://discord.com/channels/@me" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="font-size: 0.9rem;" onclick="navigator.clipboard.writeText('Watch {{MATCH_NAME}} Live - https://footholics.example/{{FILE_NAME}}'); alert('Link copied! Paste it in Discord.'); return false;">
                    💬 Discord
                </a>
            </div>
        </section>

        <!-- Disclaimer -->
        <div class="disclaimer">
            <h3 class="disclaimer-title">
                <svg width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" style="display: inline;">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                Important Legal Disclaimer
            </h3>
            <p>
                <strong>Foot Holics does NOT host any streaming content.</strong> All streaming links shown are from
                third-party public sources. We act solely as a link aggregator and have no control over the content,
                quality, or availability of these streams. If you are a copyright holder and wish to have content removed,
                please contact the host site directly. We do not control third-party content and are not responsible for it.
                All team names, logos, and trademarks are property of their respective owners.
            </p>
            <p style="margin-top: 1rem;">
                For takedown requests or concerns, contact: <a href="mailto:copyright@footholics.example" style="color: var(--accent);">copyright@footholics.example</a>
            </p>
        </div>
    </main>

    <!-- Footer -->
    <footer class="site-footer">
        <div class="container">
            <div class="footer-content">
                <div class="footer-section">
                    <h4>About Foot Holics</h4>
                    <p>
                        Foot Holics is your premium sports streaming aggregator, providing links to
                        live football matches from around the world. We curate the best streaming
                        sources so you never miss a game.
                    </p>
                </div>

                <div class="footer-section">
                    <h4>Quick Links</h4>
                    <ul class="footer-links">
                        <li><a href="index.html">Home</a></li>
                        <li><a href="#" onclick="document.getElementById('heroSearch').focus(); scrollTo(0, 0); return false;">Search Matches</a></li>
                        <li><a href="/#leagues">Browse Leagues</a></li>
                        <li><a href="mailto:contact@footholics.example">Contact</a></li>
                    </ul>
                </div>

                <div class="footer-section">
                    <h4>Legal</h4>
                    <ul class="footer-links">
                        <li><a href="privacy.html">Privacy Policy</a></li>
                        <li><a href="terms.html">Terms & Conditions</a></li>
                        <li><a href="dmca.html">DMCA / Copyright</a></li>
                        <li><a href="disclaimer.html">Disclaimer</a></li>
                    </ul>
                </div>

                <div class="footer-section">
                    <h4>Connect With Us</h4>
                    <ul class="footer-links">
                        <li><a href="https://chat.whatsapp.com/KG7DBpC0BKv6bFtlzfOr2T" target="_blank" rel="noopener noreferrer">WhatsApp Channel</a></li>
                        <li><a href="https://t.me/+XyKdBR9chQpjM2I9" target="_blank" rel="noopener noreferrer">Telegram</a></li>
                        <li><a href="https://discord.gg/example" target="_blank" rel="noopener noreferrer">Discord</a></li>
                    </ul>
                </div>
            </div>

            <div class="footer-bottom">
                <p>&copy; 2025 Foot Holics. All rights reserved.</p>
                <p style="margin-top: 1rem; font-size: 0.8rem;">
                    This site does not host any media. All links are shared from open third-party sources.
                    Copyright owners may contact host sites for issues. All trademarks belong to their respective owners.
                </p>
            </div>
        </div>
    </footer>

    <!-- Adsterra Ad Scripts -->
    <!-- Popunder Ad (triggers on click) -->
    <script type="text/javascript" src="//pl28190353.effectivegatecpm.com/52/30/74/5230747febbb777e6e14a3c30aa1fd30.js"></script>

    <!-- Social Bar Ad (sticky) -->
    <script type="text/javascript" src="//pl28190484.effectivegatecpm.com/ad/f7/17/adf7172d701fdcad288330f7b67c9293.js"></script>

    <!-- JavaScript -->
    <script src="assets/js/main.js" defer></script>
</body>
</html>"""


def get_inline_card_template() -> str:
    """Return inline card template if file doesn't exist."""
    return """                    <!-- Match Card -->
                    <article class="glass-card match-card">
                        <img src="assets/img/{{IMAGE_FILE}}" alt="{{MATCH_NAME}}" class="match-poster" loading="lazy">
                        <div class="match-header">
                            <h3 class="match-title">{{MATCH_NAME}}</h3>
                            <span class="league-badge {{LEAGUE_SLUG}}">{{LEAGUE}}</span>
                        </div>
                        <div class="match-meta">
                            <div class="match-meta-item">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                                    <line x1="16" y1="2" x2="16" y2="6"></line>
                                    <line x1="8" y1="2" x2="8" y2="6"></line>
                                    <line x1="3" y1="10" x2="21" y2="10"></line>
                                </svg>
                                <span>{{DATE_SHORT}}</span>
                            </div>
                            <div class="match-meta-item">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="12" cy="12" r="10"></circle>
                                    <polyline points="12 6 12 12 16 14"></polyline>
                                </svg>
                                <span>{{TIME}} GMT</span>
                            </div>
                            <div class="match-meta-item">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                                    <circle cx="12" cy="10" r="3"></circle>
                                </svg>
                                <span>{{STADIUM}}</span>
                            </div>
                        </div>
                        <p class="match-excerpt">{{EXCERPT}}</p>
                        <a href="{{FILE_NAME}}" class="match-link">
                            Read More & Watch Live
                            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                                <polyline points="12 5 19 12 12 19"></polyline>
                            </svg>
                        </a>
                    </article>"""


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(
        "❌ Operation cancelled. Type /start to begin again.",
        parse_mode="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END


def main() -> None:
    """Start the bot."""
    # Get token from environment
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in environment variables!")
        print("Please create a .env file with your bot token.")
        return

    # Create application
    application = Application.builder().token(token).build()

    # Define conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MATCH_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_name)],
            DATE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_time)],
            LEAGUE: [CallbackQueryHandler(league_selection, pattern="^league_")],
            STADIUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, stadium)],
            PREVIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, preview)],
            STREAM_URLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, stream_urls)],
            IMAGE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, image_name)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)

    # Start bot
    print("🤖 Foot Holics Match Manager Bot is running!")
    print("Press Ctrl+C to stop")

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
