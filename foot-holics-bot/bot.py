#!/usr/bin/env python3
"""
Foot Holics Match Manager Bot
A Telegram bot for managing football matches on the Foot Holics website.
"""

import os
import json
import re
import glob
import base64
import logging
from datetime import datetime
from typing import Dict, Any
from urllib.parse import quote
from dotenv import load_dotenv
from io import BytesIO

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

# Logging setup
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)
# Silence noisy PTB internals
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# ── Authorization ────────────────────────────────────────────────────────────
# Comma-separated Telegram user IDs allowed to operate the bot.
# Leave empty to allow everyone (not recommended in production).
_raw_ids = os.getenv("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: set[int] = {int(uid.strip()) for uid in _raw_ids.split(",") if uid.strip()}


def is_authorized(user_id: int) -> bool:
    """Return True if the user is allowed to use the bot."""
    return not ALLOWED_USER_IDS or user_id in ALLOWED_USER_IDS

# Conversation states
(
    MAIN_MENU,
    MATCH_NAME,
    DATE_TIME,
    LEAGUE,
    STADIUM,
    PREVIEW,
    STREAM_URLS,
    IMAGE_NAME,
    DELETE_SELECT,
    UPDATE_SELECT,
    UPDATE_FIELD_CHOICE,
    UPDATE_FIELD_INPUT,
    UPDATE_STREAM_LINKS,
    GENERATE_CARD_INPUT,
    UPDATE_STREAM_SELECT,  # New state for button-based stream link selection
    UPDATE_STREAM_INPUT,   # New state for individual stream link input
) = range(16)

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
    "World Cup 2026": {
        "emoji": "🏆",
        "slug": "wc",
        "color": "#FFD700",
    },
    "Nationals": {
        "emoji": "🌍",
        "slug": "nationals",
        "color": "#00A651",
    },
    "Others": {
        "emoji": "⚽",
        "slug": "others",
        "color": "#8B5CF6",
    },
}


def encode_stream_url(url: str) -> str:
    """Encode stream URL to base64 for the branded player."""
    if not url or url == "#" or url.startswith("https://t.me/"):
        return "#"
    # Encode the URL to base64
    encoded_bytes = base64.b64encode(url.encode('utf-8'))
    encoded_str = encoded_bytes.decode('utf-8')
    return encoded_str


def detect_stream_type(url: str) -> str:
    """
    Detect stream type based on URL extension.
    Returns: 'hls' for m3u8 streams, 'video' for other video formats, 'unknown' otherwise.
    """
    if not url or url == "#":
        return "unknown"
    
    url_lower = url.lower()
    
    # Check for HLS/m3u8 streams
    if '.m3u8' in url_lower or 'm3u8' in url_lower:
        return "hls"
    
    # Check for other video formats (MP4, WebM, etc.)
    video_extensions = ['.mp4', '.webm', '.ogg', '.mov', '.avi', '.mkv', '.flv', '.m4v']
    if any(ext in url_lower for ext in video_extensions):
        return "video"
    
    # Check for streaming protocols
    if 'rtmp://' in url_lower or 'rtsp://' in url_lower:
        return "stream"
    
    # Default to unknown (player.html will try to auto-detect)
    return "unknown"


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def detect_player_type(url: str) -> str:
    """
    Detect which player to use based on URL type.

    Returns:
        'hls' for m3u8/HLS streams
        'iframe' for external pages (php, embed, etc.)
        'direct' for other video files (mp4, webm …)
        'unknown' otherwise — universal-player.html will auto-detect
    """
    if not url or url == "#":
        return "unknown"

    url_lower = url.lower()

    # Check for iframe/external embed URLs (PHP pages, embed pages, etc.)
    iframe_indicators = ['.php', '/embed/', '/player/', 'embed.', 'player.',
                         'sportsonline', 'stream2watch', 'rojadirecta',
                         'hesgoal', 'totalsportek', 'livesoccertv']
    if any(indicator in url_lower for indicator in iframe_indicators):
        return "iframe"

    # Check for HLS/m3u8 streams
    if '.m3u8' in url_lower or 'm3u8' in url_lower or '/hls/' in url_lower:
        return "hls"

    # Check for direct video files
    video_extensions = ['.mp4', '.webm', '.ogg', '.mov', '.avi', '.mkv', '.flv', '.m4v']
    if any(ext in url_lower for ext in video_extensions):
        return "direct"

    # Default to HLS player (it handles most streams)
    return "hls"


def get_type_param(url: str) -> str:
    """Map detected player type to universal-player.html &type= hint."""
    t = detect_player_type(url)
    if t == "iframe":
        return "iframe"
    if t == "hls":
        return "hls"
    if t == "direct":
        return "video"
    return ""  # let the player auto-detect


def get_player_url(url: str, base_url: str = "https://footholics.in", title: str = "", thumb: str = "") -> str:
    """
    Generate a universal-player.html URL for any stream type.
    Handles HLS, MP4, DASH, iframes, YouTube, Twitch and unknown streams.

    Args:
        url: Original stream URL
        base_url: Base URL of the website
        title: Optional match title shown as overlay in the player
        thumb: Optional thumbnail/poster image URL shown before stream loads

    Returns:
        Full player URL with encoded stream
    """
    if not url or url == "#" or url.startswith("https://t.me/"):
        return "#"

    # Already a player URL — don't double-wrap
    if "universal-player.html" in url or "player.html" in url or "iframe-player.html" in url:
        return url

    encoded_url = base64.b64encode(url.encode()).decode()
    type_hint = get_type_param(url)

    params = f"get={encoded_url}"
    if type_hint:
        params += f"&type={type_hint}"
    if title:
        params += f"&title={quote(title)}"
    if thumb:
        params += f"&thumb={quote(thumb)}"

    return f"{base_url}/universal-player.html?{params}"


def wrap_m3u8_with_proxy(url: str) -> str:
    """
    DEPRECATED: Use get_player_url() instead.
    Kept for backward compatibility - now routes to appropriate player.

    Args:
        url: Original stream URL

    Returns:
        Player URL with encoded stream
    """
    if not url or url == "#" or url.startswith("https://t.me/"):
        return url

    # Check if it's already wrapped with a player or proxy
    if "universal-player.html" in url or "player.html" in url or "iframe-player.html" in url:
        return url
    if "aeriswispx.github.io" in url or "mpdhls" in url:
        return url

    # Use the new smart player routing
    return get_player_url(url, "https://footholics.in")


def find_team_logo(team_name: str, league_slug: str = None) -> str:
    """
    Automatically find team logo based on team name.
    Searches in league-specific folder first, then all folders.

    Args:
        team_name: Name of the team (e.g., "Real Madrid", "Man City")
        league_slug: League slug (CSS class) to search first (optional)

    Returns:
        Logo path relative to website root, or empty string if not found
    """
    project_root = get_project_root()
    team_slug = slugify(team_name)

    # CSS slugs can differ from the actual folder names on disk.
    # Map any mismatches here so the filesystem lookup always uses the real folder name.
    CSS_SLUG_TO_FOLDER = {
        "laliga": "la-liga",
    }

    # Actual disk folder names under assets/img/logos/teams/
    logo_folders = [
        "premier-league",
        "la-liga",
        "serie-a",
        "bundesliga",
        "ligue-1",
        "champions-league",
        "wc",
        "nationals",
        "others",
    ]

    # Translate CSS slug → disk folder name
    disk_folder = CSS_SLUG_TO_FOLDER.get(league_slug, league_slug)

    # Prioritise the league's own folder
    if disk_folder and disk_folder in logo_folders:
        logo_folders.remove(disk_folder)
        logo_folders.insert(0, disk_folder)

    # Search for logo file
    for folder in logo_folders:
        logo_dir = os.path.join(project_root, "assets", "img", "logos", "teams", folder)
        if not os.path.exists(logo_dir):
            continue

        # Try exact slug match first
        for ext in [".png", ".jpg", ".jpeg", ".svg", ".webp"]:
            logo_path = os.path.join(logo_dir, f"{team_slug}{ext}")
            if os.path.isfile(logo_path):
                return f"assets/img/logos/teams/{folder}/{team_slug}{ext}"

        # Try partial match (handles "man-city" vs "manchester-city" etc.)
        for file in os.listdir(logo_dir):
            file_stem = os.path.splitext(file)[0].lower()
            if team_slug in file_stem or file_stem in team_slug:
                return f"assets/img/logos/teams/{folder}/{file}"

    # No logo found — return a path that reliably triggers the onerror fallback in the template
    fallback_folder = CSS_SLUG_TO_FOLDER.get(league_slug, league_slug) or "others"
    return f"assets/img/logos/teams/{fallback_folder}/missing.png"


def generate_event_id() -> str:
    """Generate unique event ID based on millisecond timestamp."""
    return f"event-{int(datetime.now().timestamp() * 1000)}"


def get_project_root() -> str:
    """Get the project root directory (one level up from bot directory)."""
    bot_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(bot_dir)


def list_match_files() -> list:
    """List all match HTML files in the project."""
    root_dir = get_project_root()
    pattern = os.path.join(root_dir, "20*.html")
    files = glob.glob(pattern)
    return [os.path.basename(f) for f in sorted(files, reverse=True)]


def remove_match_from_index(filename: str) -> bool:
    """Remove match card from index.html."""
    try:
        root_dir = get_project_root()
        index_path = os.path.join(root_dir, "index.html")

        if not os.path.exists(index_path):
            return False

        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()

        target_href = f'href="{filename}"'
        href_pos = content.find(target_href)
        if href_pos == -1:
            return False

        # Walk backwards from the href to find the opening <article tag.
        # Using rfind(0, href_pos) guarantees we get the article that CONTAINS
        # this href, never a preceding unrelated article.
        article_start = content.rfind("<article", 0, href_pos)
        if article_start == -1:
            return False

        # Include the optional <!-- Match Card --> comment if it immediately
        # precedes the article (only whitespace between them).
        comment = "<!-- Match Card -->"
        comment_pos = content.rfind(comment, 0, article_start)
        if comment_pos != -1 and content[comment_pos + len(comment):article_start].strip() == "":
            remove_start = comment_pos
        else:
            remove_start = article_start

        # Walk forward from the href to find the closing tag.
        article_end = content.find("</article>", href_pos)
        if article_end == -1:
            return False
        article_end += len("</article>")

        # Consume one trailing newline so we don't leave a blank line.
        if article_end < len(content) and content[article_end] == "\n":
            article_end += 1

        new_content = content[:remove_start] + content[article_end:]

        with open(index_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return True
    except Exception as e:
        logger.error(f"Error removing from index.html: {e}", exc_info=True)
        return False


def remove_match_from_events_json(filename: str) -> bool:
    """Remove match entry from events.json."""
    try:
        root_dir = get_project_root()
        events_path = os.path.join(root_dir, "data", "events.json")

        if not os.path.exists(events_path):
            return False

        with open(events_path, "r", encoding="utf-8") as f:
            events = json.load(f)

        # Find and remove matching event
        # The slug in events.json might have or not have leading slash
        filename_without_ext = filename.replace(".html", "")

        original_length = len(events)
        events = [
            event for event in events
            if not (
                event.get("slug", "").strip("/").endswith(filename_without_ext) or
                event.get("slug", "") == filename or
                event.get("slug", "") == filename_without_ext
            )
        ]

        if len(events) == original_length:
            return False

        # Write back
        with open(events_path, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        logger.error(f"Error removing from events.json: {e}", exc_info=True)
        return False


def copy_html_to_root(filename: str, html_content: str) -> bool:
    """Copy HTML file to project root."""
    try:
        root_dir = get_project_root()
        target_path = os.path.join(root_dir, filename)

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        return True
    except Exception as e:
        logger.error(f"Error copying HTML to root: {e}", exc_info=True)
        return False


def add_to_events_json(json_entry: str) -> bool:
    """Add new match entry to the top of events.json."""
    try:
        root_dir = get_project_root()
        events_path = os.path.join(root_dir, "data", "events.json")

        # Parse the new entry
        new_event = json.loads(json_entry)

        # Read existing events
        if os.path.exists(events_path):
            with open(events_path, "r", encoding="utf-8") as f:
                events = json.load(f)
        else:
            events = []

        # Add new event at the top
        events.insert(0, new_event)

        # Write back
        with open(events_path, "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        logger.error(f"Error adding to events.json: {e}", exc_info=True)
        return False


def add_card_to_index(card_html: str) -> bool:
    """Add match card to the top of matches grid in index.html."""
    try:
        root_dir = get_project_root()
        index_path = os.path.join(root_dir, "index.html")

        if not os.path.exists(index_path):
            return False

        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Find the matches grid section
        # Look for the first <article class="glass-card match-card"> or the grid container
        # Pattern: Find the matches grid div and insert after its opening tag

        # Try to find existing match cards
        match_card_pattern = r'(<article class="glass-card match-card">)'

        if re.search(match_card_pattern, content):
            # Insert before the first match card
            new_content = re.sub(
                match_card_pattern,
                f'{card_html}\n\n                    \\1',
                content,
                count=1
            )
        else:
            # Try to find the matches grid container
            grid_pattern = r'(<div[^>]*class="[^"]*matches-grid[^"]*"[^>]*>)'

            if re.search(grid_pattern, content):
                # Insert after the grid opening tag
                new_content = re.sub(
                    grid_pattern,
                    f'\\1\n{card_html}\n',
                    content,
                    count=1
                )
            else:
                logger.error("Could not find matches grid in index.html")
                return False

        # Write back
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return True
    except Exception as e:
        logger.error(f"Error adding card to index.html: {e}", exc_info=True)
        return False


def add_to_sitemap(filename: str, date: str = None) -> bool:
    """Add a match to sitemap.xml."""
    try:
        root_dir = get_project_root()
        sitemap_path = os.path.join(root_dir, "sitemap.xml")

        if not os.path.exists(sitemap_path):
            return False

        with open(sitemap_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Use current date if not provided
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        # Create new URL entry
        new_url = f"""    <url>
        <loc>https://footholics.in/{filename}</loc>
        <lastmod>{date}</lastmod>
        <changefreq>daily</changefreq>
        <priority>0.9</priority>
    </url>

"""

        # Find the Event Detail Pages section and add after the comment
        pattern = r'(<!-- Event Detail Pages -->\n)'

        if re.search(pattern, content):
            new_content = re.sub(
                pattern,
                f'\\1{new_url}',
                content,
                count=1
            )

            # Write back
            with open(sitemap_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return True
        else:
            logger.error("Could not find Event Detail Pages section in sitemap.xml")
            return False

    except Exception as e:
        logger.error(f"Error adding to sitemap.xml: {e}", exc_info=True)
        return False


def remove_from_sitemap(filename: str) -> bool:
    """Remove a match from sitemap.xml."""
    try:
        root_dir = get_project_root()
        sitemap_path = os.path.join(root_dir, "sitemap.xml")

        if not os.path.exists(sitemap_path):
            return False

        with open(sitemap_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Pattern to match the entire URL block for this file
        pattern = rf'    <url>\s*<loc>https://footholics\.in/{re.escape(filename)}</loc>.*?</url>\s*\n'

        # Check if match exists
        if not re.search(pattern, content, re.DOTALL):
            return False

        # Remove the URL block
        new_content = re.sub(pattern, '', content, flags=re.DOTALL)

        # Write back
        with open(sitemap_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        return True

    except Exception as e:
        logger.error(f"Error removing from sitemap.xml: {e}", exc_info=True)
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and show main menu."""
    user = update.effective_user
    if not is_authorized(user.id):
        logger.warning(f"Unauthorized access attempt by user {user.id} (@{user.username})")
        await update.message.reply_text("⛔ You are not authorized to use this bot.")
        return ConversationHandler.END
    logger.info(f"User {user.id} (@{user.username}) started the bot")
    return await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False) -> int:
    """Show the main menu with operation buttons."""
    keyboard = [
        [
            InlineKeyboardButton("➕ Add New Match", callback_data="menu_add"),
        ],
        [
            InlineKeyboardButton("📋 List Matches", callback_data="menu_list"),
        ],
        [
            InlineKeyboardButton("✏️ Update Match", callback_data="menu_update"),
            InlineKeyboardButton("🗑️ Delete Match", callback_data="menu_delete"),
        ],
        [
            InlineKeyboardButton("🎨 Generate Card", callback_data="menu_card"),
        ],
        [
            InlineKeyboardButton("📊 Match Stats", callback_data="menu_stats"),
        ],
        [
            InlineKeyboardButton("❌ Exit", callback_data="menu_exit"),
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = """
🤖 **Foot Holics Match Manager**

Welcome! Choose an operation:

➕ **Add New Match** - Create a new match page
📋 **List Matches** - View all match files
✏️ **Update Match** - Edit existing match
🗑️ **Delete Match** - Remove a match (auto cleanup!)
🎨 **Generate Card** - Create match card HTML
📊 **Match Stats** - View statistics
❌ **Exit** - Close the bot

What would you like to do?
"""

    if edit_message and update.callback_query:
        await update.callback_query.edit_message_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        if update.callback_query:
            await update.callback_query.message.reply_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                message_text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )

    return MAIN_MENU


async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle main menu button selections."""
    query = update.callback_query
    await query.answer()

    action = query.data.replace("menu_", "")

    if action == "add":
        await query.edit_message_text(
            "📝 **Add New Match**\n\n"
            "Please send the match name in this format:\n"
            "`Home Team vs Away Team`\n\n"
            "Example: `Chelsea vs Manchester United`\n\n"
            "_Type /cancel to go back_",
            parse_mode="Markdown"
        )
        return MATCH_NAME

    elif action == "list":
        matches = list_match_files()
        if not matches:
            await query.edit_message_text(
                "📋 **No matches found!**\n\n"
                "No match HTML files found in the project.\n\n"
                "Use 'Add New Match' to create one.",
                parse_mode="Markdown"
            )
            await show_main_menu(update, context, edit_message=False)
            return MAIN_MENU

        match_list = "\n".join([f"• `{m}`" for m in matches[:20]])
        if len(matches) > 20:
            match_list += f"\n\n_...and {len(matches) - 20} more_"

        await query.edit_message_text(
            f"📋 **Match Files** ({len(matches)} total):\n\n{match_list}",
            parse_mode="Markdown"
        )
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    elif action == "delete":
        matches = list_match_files()
        if not matches:
            await query.edit_message_text(
                "🗑️ **No matches to delete!**\n\n"
                "No match HTML files found.",
                parse_mode="Markdown"
            )
            await show_main_menu(update, context, edit_message=False)
            return MAIN_MENU

        # Show first 10 matches with delete buttons
        keyboard = []
        for match in matches[:10]:
            keyboard.append([InlineKeyboardButton(f"🗑️ {match}", callback_data=f"delete_{match}")])
        keyboard.append([InlineKeyboardButton("« Back to Menu", callback_data="menu_back")])

        await query.edit_message_text(
            "🗑️ **Delete Match**\n\n"
            "Select a match to delete:\n\n"
            "⚠️ This will automatically remove from:\n"
            "• Main HTML file\n"
            "• index.html match card\n"
            "• data/events.json entry\n"
            "• Generated files",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return DELETE_SELECT

    elif action == "update":
        matches = list_match_files()
        if not matches:
            await query.edit_message_text(
                "✏️ **No matches to update!**\n\n"
                "No match HTML files found.",
                parse_mode="Markdown"
            )
            await show_main_menu(update, context, edit_message=False)
            return MAIN_MENU

        # Show first 10 matches with update buttons
        keyboard = []
        for match in matches[:10]:
            keyboard.append([InlineKeyboardButton(f"✏️ {match}", callback_data=f"update_{match}")])
        keyboard.append([InlineKeyboardButton("« Back to Menu", callback_data="menu_back")])

        await query.edit_message_text(
            "✏️ **Update Match**\n\n"
            "Select a match to update:\n\n"
            "You'll be able to edit:\n"
            "• Match details (teams, date, time)\n"
            "• Stadium\n"
            "• Match preview text\n"
            "• Stream URLs",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return UPDATE_SELECT

    elif action == "card":
        matches = list_match_files()
        if not matches:
            await query.edit_message_text(
                "🎨 **No matches found!**\n\n"
                "No match HTML files found to generate cards for.",
                parse_mode="Markdown"
            )
            await show_main_menu(update, context, edit_message=False)
            return MAIN_MENU

        await query.edit_message_text(
            "🎨 **Generate Match Card**\n\n"
            "Please send the match filename to generate a card for:\n\n"
            "Example: `2025-10-26-brentford-vs-liverpool.html`\n\n"
            "_Type /cancel to go back_",
            parse_mode="Markdown"
        )
        return GENERATE_CARD_INPUT

    elif action == "stats":
        matches = list_match_files()
        root_dir = get_project_root()

        # Count leagues from events.json (accurate) with fallback to filename heuristics
        league_counts = {}
        events_path = os.path.join(root_dir, "data", "events.json")
        if os.path.exists(events_path):
            try:
                with open(events_path, "r", encoding="utf-8") as f:
                    events_data = json.load(f)
                for event in events_data:
                    league_name = event.get("league", "Others")
                    league_counts[league_name] = league_counts.get(league_name, 0) + 1
            except Exception:
                league_counts = {"All": len(matches)}
        else:
            league_counts = {"All": len(matches)}

        league_stats = "\n".join([f"• {league}: {count}" for league, count in sorted(league_counts.items())])

        stats_text = f"""
📊 **Match Statistics**

**Total Matches:** {len(matches)}

**By League:**
{league_stats}

**Recent Matches:**
{chr(10).join([f"• {m}" for m in matches[:5]])}
"""

        await query.edit_message_text(
            stats_text,
            parse_mode="Markdown"
        )
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    elif action == "exit":
        await query.edit_message_text(
            "👋 **Goodbye!**\n\n"
            "Bot closed. Type /start to use again.",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    elif action == "back":
        return await show_main_menu(update, context, edit_message=True)

    return MAIN_MENU


async def generate_card_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle generate card file input."""
    filename = update.message.text.strip()

    root_dir = get_project_root()
    match_file = os.path.join(root_dir, filename)

    if not os.path.exists(match_file):
        await update.message.reply_text(
            f"❌ File not found: `{filename}`\n\n"
            "Please enter a valid filename.",
            parse_mode="Markdown"
        )
        return GENERATE_CARD_INPUT

    await update.message.reply_text("⏳ Generating card... Please wait.")

    try:
        # Read the match HTML
        with open(match_file, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Extract match details from HTML
        match_name = re.search(r'<h1 class="event-title">(.*?)</h1>', html_content)
        league = re.search(r'<span class="league-badge (.*?)">(.*?)</span>', html_content)
        date = re.search(r'<span>(.*? at .*? GMT)</span>', html_content)
        stadium = re.search(r'<svg.*?</svg>\s*<span>(.*?)</span>(?!.*at.*GMT)', html_content, re.DOTALL)
        poster = re.search(r'<img src="(assets/img/.*?\.jpg)".*?class="event-hero-bg"', html_content)

        if not all([match_name, league, date]):
            await update.message.reply_text("❌ Could not extract match details from HTML.")
            await show_main_menu(update, context, edit_message=False)
            return MAIN_MENU

        # Parse details
        match_title = match_name.group(1)
        league_slug = league.group(1)
        league_name = league.group(2)
        date_time = date.group(1)
        stadium_name = stadium.group(1) if stadium else "Stadium TBD"
        poster_img = poster.group(1) if poster else "assets/img/match-poster.jpg"

        # Generate card
        card_html = f"""                    <!-- Match Card -->
                    <article class="glass-card match-card">
                        <img src="{poster_img}" alt="{match_title}" class="match-poster" loading="lazy">
                        <div class="match-header">
                            <h3 class="match-title">{match_title}</h3>
                            <span class="league-badge {league_slug}">{league_name}</span>
                        </div>
                        <div class="match-meta">
                            <div class="match-meta-item">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                                    <line x1="16" y1="2" x2="16" y2="6"></line>
                                    <line x1="8" y1="2" x2="8" y2="6"></line>
                                    <line x1="3" y1="10" x2="21" y2="10"></line>
                                </svg>
                                <span>{date_time}</span>
                            </div>
                            <div class="match-meta-item">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                                    <circle cx="12" cy="10" r="3"></circle>
                                </svg>
                                <span>{stadium_name}</span>
                            </div>
                        </div>
                        <p class="match-excerpt">
                            {match_title} live streaming links. Watch the match with HD quality streams.
                        </p>
                        <a href="{filename}" class="match-link">
                            Read More & Watch Live
                            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                                <polyline points="12 5 19 12 12 19"></polyline>
                            </svg>
                        </a>
                    </article>"""

        # Create file
        card_filename = filename.replace(".html", "-card.txt")

        # Send as document
        card_bytes = BytesIO(card_html.encode('utf-8'))
        card_bytes.name = card_filename

        await update.message.reply_document(
            document=card_bytes,
            filename=card_filename,
            caption=f"✅ **Card Generated!**\n\n"
                    f"Match: {match_title}\n\n"
                    f"**Instructions:**\n"
                    f"1. Open `index.html`\n"
                    f"2. Find the matches grid (around line 123)\n"
                    f"3. Paste this card at the TOP of the grid\n"
                    f"4. Save and commit!",
            parse_mode="Markdown"
        )

    except Exception as e:
        await update.message.reply_text(f"❌ Error generating card: {str(e)}")

    await show_main_menu(update, context, edit_message=False)
    return MAIN_MENU


async def delete_match_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle match deletion."""
    query = update.callback_query
    await query.answer()

    if query.data == "menu_back":
        return await show_main_menu(update, context, edit_message=True)

    filename = query.data.replace("delete_", "")

    # Confirm deletion
    keyboard = [
        [
            InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete_{filename}"),
            InlineKeyboardButton("❌ Cancel", callback_data="menu_back"),
        ]
    ]

    await query.edit_message_text(
        f"⚠️ **Confirm Deletion**\n\n"
        f"Are you sure you want to delete:\n"
        f"`{filename}`\n\n"
        f"This will automatically remove:\n"
        f"✓ Main HTML file\n"
        f"✓ Match card from index.html\n"
        f"✓ Entry from events.json\n"
        f"✓ Generated files\n\n"
        f"**This cannot be undone!**",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return DELETE_SELECT


async def confirm_delete_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Confirm and execute match deletion."""
    query = update.callback_query
    await query.answer()

    if query.data == "menu_back":
        return await show_main_menu(update, context, edit_message=True)

    filename = query.data.replace("confirm_delete_", "")
    root_dir = get_project_root()

    deleted_files = []
    failed_operations = []

    # Delete main HTML file
    main_file = os.path.join(root_dir, filename)
    if os.path.exists(main_file):
        try:
            os.remove(main_file)
            deleted_files.append(f"✓ {filename}")
        except Exception as e:
            failed_operations.append(f"✗ Main file: {str(e)}")
    else:
        failed_operations.append(f"✗ Main file not found")

    # Remove from index.html
    if remove_match_from_index(filename):
        deleted_files.append("✓ Removed from index.html")
    else:
        failed_operations.append("✗ Could not remove from index.html (may not exist)")

    # Remove from events.json
    if remove_match_from_events_json(filename):
        deleted_files.append("✓ Removed from events.json")
    else:
        failed_operations.append("✗ Could not remove from events.json (may not exist)")

    # Remove from sitemap.xml
    if remove_from_sitemap(filename):
        deleted_files.append("✓ Removed from sitemap.xml")
    else:
        failed_operations.append("✗ Could not remove from sitemap.xml (may not exist)")

    # Delete card file
    card_filename = filename.replace(".html", "-card.html")
    card_file = os.path.join(root_dir, "foot-holics-bot", "generated", "cards", card_filename)
    if os.path.exists(card_file):
        try:
            os.remove(card_file)
            deleted_files.append(f"✓ Card: {card_filename}")
        except Exception as e:
            failed_operations.append(f"✗ Card file: {str(e)}")

    # Delete generated HTML
    gen_file = os.path.join(root_dir, "foot-holics-bot", "generated", "html_files", filename)
    if os.path.exists(gen_file):
        try:
            os.remove(gen_file)
            deleted_files.append(f"✓ Generated: {filename}")
        except Exception as e:
            failed_operations.append(f"✗ Generated file: {str(e)}")

    # Delete JSON entry
    json_filename = filename.replace(".html", ".json")
    json_file = os.path.join(root_dir, "foot-holics-bot", "generated", "json_entries", json_filename)
    if os.path.exists(json_file):
        try:
            os.remove(json_file)
            deleted_files.append(f"✓ JSON: {json_filename}")
        except Exception as e:
            failed_operations.append(f"✗ JSON file: {str(e)}")

    deleted_list = "\n".join(deleted_files) if deleted_files else "Nothing deleted"
    failed_list = "\n\n**Issues:**\n" + "\n".join(failed_operations) if failed_operations else ""

    await query.edit_message_text(
        f"✅ **Match Deletion Complete!**\n\n"
        f"**Deleted:**\n{deleted_list}{failed_list}\n\n"
        f"**Next steps:**\n"
        f"1. Commit changes:\n"
        f"```bash\n"
        f"git add .\n"
        f"git commit -m \"Remove {filename.replace('.html', '')} match\"\n"
        f"git push\n"
        f"```\n"
        f"2. Your site will update automatically!",
        parse_mode="Markdown"
    )

    await show_main_menu(update, context, edit_message=False)
    return MAIN_MENU


async def update_match_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle match update selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "menu_back":
        return await show_main_menu(update, context, edit_message=True)

    filename = query.data.replace("update_", "")
    context.user_data["update_filename"] = filename

    # Read current match data from HTML file
    root_dir = get_project_root()
    match_file = os.path.join(root_dir, filename)

    if not os.path.exists(match_file):
        await query.edit_message_text(
            f"❌ Match file not found: `{filename}`",
            parse_mode="Markdown"
        )
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    # Extract current match details
    with open(match_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Parse current values
    match_title = re.search(r'<h1 class="event-title">(.*?)</h1>', html_content)
    league = re.search(r'<span class="league-badge .*?">(.*?)</span>', html_content)
    date_match = re.search(r'<span>(.*?) at (.*?) GMT</span>', html_content)
    stadium = re.search(r'<path d="M21 10.*?</svg>\s*<span>(.*?)</span>', html_content, re.DOTALL)
    preview_match = re.search(r'<h2[^>]*>Match Preview</h2>\s*<p>(.*?)</p>', html_content, re.DOTALL)

    if match_title:
        context.user_data["current_title"] = match_title.group(1)
    if league:
        context.user_data["current_league"] = league.group(1)
    if date_match:
        context.user_data["current_date"] = date_match.group(1)
        context.user_data["current_time"] = date_match.group(2)
    if stadium:
        context.user_data["current_stadium"] = stadium.group(1)
    if preview_match:
        context.user_data["current_preview"] = preview_match.group(1).strip()

    # Extract existing stream links from HTML
    stream_links = ["#", "#", "#", "#"]
    # Look for any player URL with encoded stream (universal, legacy player.html, or iframe-player.html)
    stream_patterns = re.findall(r'href="(?:universal-player\.html|player\.html|iframe-player\.html)\?get=([^"&]+)', html_content)
    for i, encoded_url in enumerate(stream_patterns[:4]):
        try:
            decoded_url = base64.b64decode(encoded_url).decode('utf-8')
            stream_links[i] = decoded_url
        except:
            stream_links[i] = "#"
    # Also try old format (p/X-live.html)
    if all(link == "#" for link in stream_links):
        old_patterns = re.findall(r'href="p/(\d)-live\.html\?(?:url|get)=([^"]+)"', html_content)
        for num, encoded_url in old_patterns:
            idx = int(num) - 1
            if 0 <= idx < 4:
                try:
                    decoded_url = base64.b64decode(encoded_url).decode('utf-8')
                    stream_links[idx] = decoded_url
                except:
                    pass
    context.user_data["current_stream_links"] = stream_links

    # Show update options
    keyboard = [
        [InlineKeyboardButton("📝 Match Name", callback_data="update_field_title")],
        [InlineKeyboardButton("📅 Date & Time", callback_data="update_field_datetime")],
        [InlineKeyboardButton("🏆 League", callback_data="update_field_league")],
        [InlineKeyboardButton("🏟️ Stadium", callback_data="update_field_stadium")],
        [InlineKeyboardButton("📰 Preview Text", callback_data="update_field_preview")],
        [InlineKeyboardButton("🔗 Streaming Links", callback_data="update_field_streams")],
        [InlineKeyboardButton("🖼️ Thumbnail", callback_data="update_field_thumbnail")],
        [InlineKeyboardButton("✅ Save Changes", callback_data="update_save")],
        [InlineKeyboardButton("« Cancel", callback_data="menu_back")]
    ]

    current_info = f"""
✏️ **Update Match: {context.user_data.get('current_title', 'Unknown')}**

**Current values:**
• Match: {context.user_data.get('current_title', 'N/A')}
• Date: {context.user_data.get('current_date', 'N/A')}
• Time: {context.user_data.get('current_time', 'N/A')} GMT
• League: {context.user_data.get('current_league', 'N/A')}
• Stadium: {context.user_data.get('current_stadium', 'N/A')}

Select a field to edit or save changes:
"""

    await query.edit_message_text(
        current_info,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return UPDATE_FIELD_CHOICE


async def update_field_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle field choice for updating."""
    query = update.callback_query
    await query.answer()

    if query.data == "menu_back":
        return await show_main_menu(update, context, edit_message=True)

    if query.data == "update_save":
        # Save all changes
        return await save_match_updates(update, context)

    field = query.data.replace("update_field_", "")
    context.user_data["update_field"] = field

    if field == "title":
        await query.edit_message_text(
            f"📝 **Update Match Name**\n\n"
            f"Current: `{context.user_data.get('current_title', 'N/A')}`\n\n"
            f"Enter new match name (format: Team1 vs Team2):\n\n"
            f"_Type /cancel to go back_",
            parse_mode="Markdown"
        )
        return UPDATE_FIELD_INPUT

    elif field == "datetime":
        await query.edit_message_text(
            f"📅 **Update Date & Time**\n\n"
            f"Current: `{context.user_data.get('current_date', 'N/A')} at {context.user_data.get('current_time', 'N/A')} GMT`\n\n"
            f"Enter new date and time (format: YYYY-MM-DD HH:MM):\n"
            f"Example: `2025-12-25 20:00`\n\n"
            f"_Type /cancel to go back_",
            parse_mode="Markdown"
        )
        return UPDATE_FIELD_INPUT

    elif field == "league":
        keyboard = [
            [
                InlineKeyboardButton("⚽ Premier League", callback_data="update_league_Premier League"),
                InlineKeyboardButton("⚽ La Liga", callback_data="update_league_La Liga"),
            ],
            [
                InlineKeyboardButton("⚽ Serie A", callback_data="update_league_Serie A"),
                InlineKeyboardButton("⚽ Bundesliga", callback_data="update_league_Bundesliga"),
            ],
            [
                InlineKeyboardButton("⚽ Ligue 1", callback_data="update_league_Ligue 1"),
                InlineKeyboardButton("🏆 Champions League", callback_data="update_league_Champions League"),
            ],
            [
                InlineKeyboardButton("🏆 World Cup 2026", callback_data="update_league_World Cup 2026"),
                InlineKeyboardButton("🌍 Nationals", callback_data="update_league_Nationals"),
            ],
            [
                InlineKeyboardButton("⚽ Others", callback_data="update_league_Others"),
            ],
        ]
        await query.edit_message_text(
            f"🏆 **Update League**\n\n"
            f"Current: `{context.user_data.get('current_league', 'N/A')}`\n\n"
            f"Select new league:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return UPDATE_FIELD_CHOICE

    elif field == "stadium":
        await query.edit_message_text(
            f"🏟️ **Update Stadium**\n\n"
            f"Current: `{context.user_data.get('current_stadium', 'N/A')}`\n\n"
            f"Enter new stadium name:\n\n"
            f"_Type /cancel to go back_",
            parse_mode="Markdown"
        )
        return UPDATE_FIELD_INPUT

    elif field == "preview":
        await query.edit_message_text(
            f"📰 **Update Preview Text**\n\n"
            f"Current preview: (check your match page)\n\n"
            f"Enter new match preview (1-2 paragraphs):\n\n"
            f"_Type /cancel to go back_",
            parse_mode="Markdown"
        )
        return UPDATE_FIELD_INPUT

    elif field == "thumbnail":
        current_thumb = context.user_data.get("current_thumbnail", "auto (team logo)")
        await query.edit_message_text(
            f"🖼️ **Update Thumbnail**\n\n"
            f"Current: `{current_thumb}`\n\n"
            f"Send an image URL to use as the player thumbnail.\n"
            f"This shows before the stream starts loading.\n\n"
            f"Examples:\n"
            f"• `https://example.com/match-banner.jpg`\n"
            f"• Any direct image link (jpg, png, webp)\n\n"
            f"_Type /cancel to go back_",
            parse_mode="Markdown"
        )
        return UPDATE_FIELD_INPUT

    elif field == "streams":
        # Show button-based stream link selection UI
        stream_links = context.user_data.get("current_stream_links", ["#", "#", "#", "#"])

        # Build buttons showing link status
        keyboard = []
        for i in range(4):
            link = stream_links[i] if i < len(stream_links) else "#"
            if link and link != "#":
                # Show truncated URL for filled links
                display_url = link[:35] + "..." if len(link) > 35 else link
                status = f"✅ Link {i+1}: {display_url}"
            else:
                status = f"⬜ Link {i+1}: (empty)"
            keyboard.append([InlineKeyboardButton(status, callback_data=f"stream_link_{i}")])

        keyboard.append([InlineKeyboardButton("💾 Save Changes", callback_data="update_save")])
        keyboard.append([InlineKeyboardButton("« Back to Menu", callback_data="stream_done")])
        keyboard.append([InlineKeyboardButton("« Cancel", callback_data="menu_back")])

        # Count active links
        active_count = len([l for l in stream_links if l and l != "#"])

        await query.edit_message_text(
            f"🔗 **Update Streaming Links**\n\n"
            f"📊 Active streams: {active_count}/4\n\n"
            f"Select a link to view/edit:\n"
            f"_(Click any link to update it, then Save)_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return UPDATE_STREAM_SELECT

    return UPDATE_FIELD_CHOICE


async def stream_link_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle stream link button selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "menu_back":
        return await show_main_menu(update, context, edit_message=True)

    if query.data == "stream_done":
        # Return to main update menu
        return await show_update_field_menu(update, context)

    # Extract link index from callback data (stream_link_0, stream_link_1, etc.)
    link_index = int(query.data.replace("stream_link_", ""))
    context.user_data["editing_stream_index"] = link_index

    stream_links = context.user_data.get("current_stream_links", ["#", "#", "#", "#"])
    current_link = stream_links[link_index] if link_index < len(stream_links) else "#"

    # Build keyboard with options
    keyboard = [
        [InlineKeyboardButton("🗑️ Clear this link", callback_data=f"stream_clear_{link_index}")],
        [InlineKeyboardButton("« Back to Links", callback_data="stream_back")]
    ]

    if current_link and current_link != "#":
        link_display = current_link if len(current_link) <= 50 else current_link[:50] + "..."
        await query.edit_message_text(
            f"🔗 **Edit Link {link_index + 1}**\n\n"
            f"📍 **Current URL:**\n`{link_display}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 **To replace this link:**\n"
            f"Simply paste the new URL below.\n\n"
            f"_Your new link will replace the current one._",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await query.edit_message_text(
            f"🔗 **Edit Link {link_index + 1}**\n\n"
            f"📍 **Current status:** Empty\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 **To add a stream:**\n"
            f"Paste the stream URL below.\n\n"
            f"_Supports: m3u8, embed pages, direct video links_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return UPDATE_STREAM_INPUT


async def stream_link_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle stream link clear/back actions."""
    query = update.callback_query
    await query.answer()

    if query.data == "stream_done":
        # Return to the main update-field menu so user can hit Save Changes
        return await show_update_field_menu(update, context)

    if query.data == "stream_back":
        # Go back to stream links menu
        context.user_data["update_field"] = "streams"
        return await show_stream_links_menu(update, context)

    if query.data.startswith("stream_clear_"):
        # Clear the specified link
        link_index = int(query.data.replace("stream_clear_", ""))
        stream_links = context.user_data.get("current_stream_links", ["#", "#", "#", "#"])
        if link_index < len(stream_links):
            stream_links[link_index] = "#"
            context.user_data["current_stream_links"] = stream_links

        await query.answer(f"✅ Link {link_index + 1} cleared!")
        # Return to stream links menu
        return await show_stream_links_menu(update, context)

    return UPDATE_STREAM_SELECT


async def stream_link_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle new stream link URL input."""
    text = update.message.text.strip()
    link_index = context.user_data.get("editing_stream_index", 0)

    # Validate URL (basic check)
    if not text.startswith(("http://", "https://")):
        await update.message.reply_text(
            "❌ Invalid URL! Must start with http:// or https://\n\n"
            "Please paste a valid stream URL:"
        )
        return UPDATE_STREAM_INPUT

    # Update the stream link
    stream_links = context.user_data.get("current_stream_links", ["#", "#", "#", "#"])
    while len(stream_links) < 4:
        stream_links.append("#")
    stream_links[link_index] = text
    context.user_data["current_stream_links"] = stream_links

    # Detect player type for feedback
    player_type = detect_player_type(text)
    type_labels = {"hls": "HLS", "iframe": "iFrame/Embed", "direct": "Direct Video"}
    stream_kind = type_labels.get(player_type, "Auto-detect")
    player_info = f"🎬 Universal Player ({stream_kind})"

    await update.message.reply_text(
        f"✅ **Link {link_index + 1} Updated!**\n\n"
        f"🔗 URL saved successfully\n"
        f"{player_info} will be used\n\n"
        f"_Returning to links menu..._",
        parse_mode="Markdown"
    )

    # Return to stream links menu
    return await show_stream_links_menu_after_input(update, context)


async def show_stream_links_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show the stream links menu (used after actions)."""
    query = update.callback_query

    stream_links = context.user_data.get("current_stream_links", ["#", "#", "#", "#"])

    # Build buttons showing link status
    keyboard = []
    for i in range(4):
        link = stream_links[i] if i < len(stream_links) else "#"
        if link and link != "#":
            display_url = link[:35] + "..." if len(link) > 35 else link
            status = f"✅ Link {i+1}: {display_url}"
        else:
            status = f"⬜ Link {i+1}: (empty)"
        keyboard.append([InlineKeyboardButton(status, callback_data=f"stream_link_{i}")])

    keyboard.append([InlineKeyboardButton("💾 Save Changes", callback_data="update_save")])
    keyboard.append([InlineKeyboardButton("« Back to Menu", callback_data="stream_done")])
    keyboard.append([InlineKeyboardButton("« Cancel", callback_data="menu_back")])

    active_count = len([l for l in stream_links if l and l != "#"])

    await query.edit_message_text(
        f"🔗 **Update Streaming Links**\n\n"
        f"📊 Active streams: {active_count}/4\n\n"
        f"Select a link to view/edit:\n"
        f"_(Click any link to update it, then Save)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return UPDATE_STREAM_SELECT


async def show_stream_links_menu_after_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show the stream links menu after text input (sends new message)."""
    stream_links = context.user_data.get("current_stream_links", ["#", "#", "#", "#"])

    # Build buttons showing link status
    keyboard = []
    for i in range(4):
        link = stream_links[i] if i < len(stream_links) else "#"
        if link and link != "#":
            display_url = link[:35] + "..." if len(link) > 35 else link
            status = f"✅ Link {i+1}: {display_url}"
        else:
            status = f"⬜ Link {i+1}: (empty)"
        keyboard.append([InlineKeyboardButton(status, callback_data=f"stream_link_{i}")])

    keyboard.append([InlineKeyboardButton("💾 Save Changes", callback_data="update_save")])
    keyboard.append([InlineKeyboardButton("« Back to Menu", callback_data="stream_done")])
    keyboard.append([InlineKeyboardButton("« Cancel", callback_data="menu_back")])

    active_count = len([l for l in stream_links if l and l != "#"])

    await update.message.reply_text(
        f"🔗 **Update Streaming Links**\n\n"
        f"📊 Active streams: {active_count}/4\n\n"
        f"Select a link to view/edit:\n"
        f"_(Click any link to update it, then Save)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return UPDATE_STREAM_SELECT


async def show_update_field_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show the main update field selection menu."""
    query = update.callback_query

    keyboard = [
        [InlineKeyboardButton("📝 Match Name", callback_data="update_field_title")],
        [InlineKeyboardButton("📅 Date & Time", callback_data="update_field_datetime")],
        [InlineKeyboardButton("🏆 League", callback_data="update_field_league")],
        [InlineKeyboardButton("🏟️ Stadium", callback_data="update_field_stadium")],
        [InlineKeyboardButton("📰 Preview Text", callback_data="update_field_preview")],
        [InlineKeyboardButton("🔗 Streaming Links", callback_data="update_field_streams")],
        [InlineKeyboardButton("🖼️ Thumbnail", callback_data="update_field_thumbnail")],
        [InlineKeyboardButton("✅ Save Changes", callback_data="update_save")],
        [InlineKeyboardButton("« Cancel", callback_data="menu_back")]
    ]

    current_info = f"""
✏️ **Update Match: {context.user_data.get('current_title', 'Unknown')}**

**Current values:**
• Match: {context.user_data.get('current_title', 'N/A')}
• Date: {context.user_data.get('current_date', 'N/A')}
• Time: {context.user_data.get('current_time', 'N/A')} GMT
• League: {context.user_data.get('current_league', 'N/A')}
• Stadium: {context.user_data.get('current_stadium', 'N/A')}

Select a field to edit or save changes:
"""

    await query.edit_message_text(
        current_info,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return UPDATE_FIELD_CHOICE


async def update_field_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle field input for updating."""
    text = update.message.text.strip()
    field = context.user_data.get("update_field")

    if field == "title":
        if " vs " not in text.lower():
            await update.message.reply_text("❌ Invalid format! Must contain ' vs '")
            return UPDATE_FIELD_INPUT
        context.user_data["current_title"] = text
        teams = re.split(r"\s+vs\s+", text, flags=re.IGNORECASE)
        context.user_data["current_home_team"] = teams[0].strip()
        context.user_data["current_away_team"] = teams[1].strip()

    elif field == "datetime":
        try:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M")
            context.user_data["current_date"] = dt.strftime("%B %d, %Y")
            context.user_data["current_time"] = dt.strftime("%H:%M")
            context.user_data["current_datetime_obj"] = dt
        except ValueError:
            await update.message.reply_text("❌ Invalid format! Use: YYYY-MM-DD HH:MM")
            return UPDATE_FIELD_INPUT

    elif field == "stadium":
        context.user_data["current_stadium"] = text

    elif field == "preview":
        if len(text) < 50:
            await update.message.reply_text("⚠️ Preview too short. Please provide at least 50 characters.")
            return UPDATE_FIELD_INPUT
        context.user_data["current_preview"] = text

    elif field == "thumbnail":
        if not text.startswith("http"):
            await update.message.reply_text("❌ Must be a valid image URL starting with http/https")
            return UPDATE_FIELD_INPUT
        context.user_data["current_thumbnail"] = text

    # Note: streams are now handled via button-based UI in UPDATE_STREAM_SELECT state

    await update.message.reply_text(f"✅ Updated! Continue editing or save changes.")

    # Return to field choice menu
    keyboard = [
        [InlineKeyboardButton("📝 Match Name", callback_data="update_field_title")],
        [InlineKeyboardButton("📅 Date & Time", callback_data="update_field_datetime")],
        [InlineKeyboardButton("🏆 League", callback_data="update_field_league")],
        [InlineKeyboardButton("🏟️ Stadium", callback_data="update_field_stadium")],
        [InlineKeyboardButton("📰 Preview Text", callback_data="update_field_preview")],
        [InlineKeyboardButton("🔗 Streaming Links", callback_data="update_field_streams")],
        [InlineKeyboardButton("🖼️ Thumbnail", callback_data="update_field_thumbnail")],
        [InlineKeyboardButton("✅ Save Changes", callback_data="update_save")],
        [InlineKeyboardButton("« Cancel", callback_data="menu_back")]
    ]

    current_info = f"""
✏️ **Update Match: {context.user_data.get('current_title', 'Unknown')}**

**Current values:**
• Match: {context.user_data.get('current_title', 'N/A')}
• Date: {context.user_data.get('current_date', 'N/A')}
• Time: {context.user_data.get('current_time', 'N/A')} GMT
• League: {context.user_data.get('current_league', 'N/A')}
• Stadium: {context.user_data.get('current_stadium', 'N/A')}

Select a field to edit or save changes:
"""

    await update.message.reply_text(
        current_info,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return UPDATE_FIELD_CHOICE


async def update_league_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle league selection for update."""
    query = update.callback_query
    await query.answer()

    league = query.data.replace("update_league_", "")
    context.user_data["current_league"] = league
    context.user_data["current_league_slug"] = LEAGUES[league]["slug"]

    await query.answer(f"✅ League updated to {league}")

    # Return to field choice menu
    keyboard = [
        [InlineKeyboardButton("📝 Match Name", callback_data="update_field_title")],
        [InlineKeyboardButton("📅 Date & Time", callback_data="update_field_datetime")],
        [InlineKeyboardButton("🏆 League", callback_data="update_field_league")],
        [InlineKeyboardButton("🏟️ Stadium", callback_data="update_field_stadium")],
        [InlineKeyboardButton("📰 Preview Text", callback_data="update_field_preview")],
        [InlineKeyboardButton("🔗 Streaming Links", callback_data="update_field_streams")],
        [InlineKeyboardButton("🖼️ Thumbnail", callback_data="update_field_thumbnail")],
        [InlineKeyboardButton("✅ Save Changes", callback_data="update_save")],
        [InlineKeyboardButton("« Cancel", callback_data="menu_back")]
    ]

    current_info = f"""
✏️ **Update Match: {context.user_data.get('current_title', 'Unknown')}**

**Current values:**
• Match: {context.user_data.get('current_title', 'N/A')}
• Date: {context.user_data.get('current_date', 'N/A')}
• Time: {context.user_data.get('current_time', 'N/A')} GMT
• League: {context.user_data.get('current_league', 'N/A')}
• Stadium: {context.user_data.get('current_stadium', 'N/A')}

Select a field to edit or save changes:
"""

    await query.edit_message_text(
        current_info,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    return UPDATE_FIELD_CHOICE


async def save_match_updates(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save all match updates to files."""
    query = update.callback_query if hasattr(update, 'callback_query') else None

    if query:
        await query.answer()
        await query.edit_message_text("⏳ Saving changes... Please wait.")
    else:
        await update.message.reply_text("⏳ Saving changes... Please wait.")

    filename = context.user_data.get("update_filename")
    root_dir = get_project_root()
    match_file = os.path.join(root_dir, filename)

    try:
        # Read current HTML
        with open(match_file, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Update HTML content
        if "current_title" in context.user_data:
            html_content = re.sub(
                r'<h1 class="event-title">.*?</h1>',
                f'<h1 class="event-title">{context.user_data["current_title"]}</h1>',
                html_content
            )
            html_content = re.sub(
                r'<title>.*?</title>',
                f'<title>{context.user_data["current_title"]} - {context.user_data.get("current_league", "Football")} Live Stream | Foot Holics</title>',
                html_content
            )

            # Extract team names and update logos
            title = context.user_data["current_title"]
            if " vs " in title.lower():
                teams = re.split(r"\s+vs\s+", title, flags=re.IGNORECASE)
                if len(teams) == 2:
                    home_team = teams[0].strip()
                    away_team = teams[1].strip()
                    league_slug = context.user_data.get("current_league_slug", "others")

                    # Fetch team logos
                    home_logo = find_team_logo(home_team, league_slug)
                    away_logo = find_team_logo(away_team, league_slug)

                    # Update home team logo in HTML
                    html_content = re.sub(
                        r'(<img src=")([^"]*?)(" alt="[^"]*?" class="team-logo"[^>]*?>)',
                        f'\\1{home_logo}\\3',
                        html_content,
                        count=1
                    )

                    # Update away team logo in HTML (second occurrence)
                    # Find all team logo img tags and replace the second one
                    def replace_second_logo(match_obj):
                        replace_second_logo.counter += 1
                        if replace_second_logo.counter == 2:
                            return f'{match_obj.group(1)}{away_logo}{match_obj.group(3)}'
                        return match_obj.group(0)

                    replace_second_logo.counter = 0
                    html_content = re.sub(
                        r'(<img src=")([^"]*?)(" alt="[^"]*?" class="team-logo"[^>]*?>)',
                        replace_second_logo,
                        html_content
                    )

        if "current_date" in context.user_data:
            html_content = re.sub(
                r'<span>(.*?) at (.*?) GMT</span>',
                f'<span>{context.user_data["current_date"]} at {context.user_data["current_time"]} GMT</span>',
                html_content
            )

        if "current_league" in context.user_data:
            # Update league badge
            old_league_pattern = r'<span class="league-badge .*?">(.*?)</span>'
            html_content = re.sub(
                old_league_pattern,
                f'<span class="league-badge {context.user_data.get("current_league_slug", "others")}">{context.user_data["current_league"]}</span>',
                html_content
            )

            # Refresh team logos with new league context
            # Extract team names from title
            title_match = re.search(r'<h1 class="event-title">(.*?)</h1>', html_content)
            if title_match:
                title = title_match.group(1)
                if " vs " in title.lower():
                    teams = re.split(r"\s+vs\s+", title, flags=re.IGNORECASE)
                    if len(teams) == 2:
                        home_team = teams[0].strip()
                        away_team = teams[1].strip()
                        league_slug = context.user_data.get("current_league_slug", "others")

                        # Fetch team logos with new league context
                        home_logo = find_team_logo(home_team, league_slug)
                        away_logo = find_team_logo(away_team, league_slug)

                        # Update home team logo in HTML
                        html_content = re.sub(
                            r'(<img src=")([^"]*?)(" alt="[^"]*?" class="team-logo"[^>]*?>)',
                            f'\\1{home_logo}\\3',
                            html_content,
                            count=1
                        )

                        # Update away team logo in HTML (second occurrence)
                        def replace_second_logo(match_obj):
                            replace_second_logo.counter += 1
                            if replace_second_logo.counter == 2:
                                return f'{match_obj.group(1)}{away_logo}{match_obj.group(3)}'
                            return match_obj.group(0)

                        replace_second_logo.counter = 0
                        html_content = re.sub(
                            r'(<img src=")([^"]*?)(" alt="[^"]*?" class="team-logo"[^>]*?>)',
                            replace_second_logo,
                            html_content
                        )

        if "current_stadium" in context.user_data:
            html_content = re.sub(
                r'(<path d="M21 10.*?</svg>\s*<span>).*?(</span>)',
                f'\\1{context.user_data["current_stadium"]}\\2',
                html_content,
                flags=re.DOTALL
            )

        if "current_preview" in context.user_data:
            html_content = re.sub(
                r'(<h2[^>]*>Match Preview</h2>\s*<p>).*?(</p>)',
                f'\\1{context.user_data["current_preview"]}\\2',
                html_content,
                flags=re.DOTALL
            )

        # Thumbnail update: replace &thumb= in all 4 player hrefs
        if "current_thumbnail" in context.user_data:
            new_thumb = context.user_data["current_thumbnail"]
            enc_new_thumb = quote(new_thumb)
            # Remove existing &thumb=... then append new one to every player href
            def _update_thumb(m):
                href = m.group(0)
                href = re.sub(r'&thumb=[^"&]*', '', href)   # strip old thumb
                href = href.rstrip('"') + f'&thumb={enc_new_thumb}"'
                return href
            html_content = re.sub(
                r'href="universal-player\.html\?[^"]*"(?=\s[^>]*class="stream-link-card")',
                _update_thumb,
                html_content
            )

        if "current_stream_links" in context.user_data:
            stream_links = context.user_data["current_stream_links"]
            match_title  = context.user_data.get("current_title", "")
            enc_title    = quote(match_title) if match_title else ""

            # Preserve existing thumbnail from HTML (or use updated one)
            existing_thumb = context.user_data.get("current_thumbnail", "")
            if not existing_thumb:
                _t = re.search(r'[?&]thumb=([^"&]*)', html_content)
                existing_thumb = _t.group(1) if _t else ""

            # Pre-build all 4 player URLs
            player_urls_upd = []
            for _url in (list(stream_links) + ["#"] * 4)[:4]:
                if _url and _url != "#" and not _url.startswith("https://t.me/"):
                    _enc  = base64.b64encode(_url.encode()).decode()
                    _hint = get_type_param(_url)
                    _p    = f"get={_enc}"
                    if _hint:         _p += f"&type={_hint}"
                    if enc_title:     _p += f"&title={enc_title}"
                    if existing_thumb: _p += f"&thumb={existing_thumb}"
                    player_urls_upd.append(f"universal-player.html?{_p}")
                else:
                    player_urls_upd.append("#")

            # Single-pass positional replacement using the stream-link-card class
            # as the anchor — matches ALL 4 stream hrefs including empty href="#" ones.
            # Lookahead ensures we only touch stream link anchors, nothing else.
            _href_pat = r'href="[^"]*"(?=\s[^>]*class="stream-link-card")'
            _pos = [0]
            def _repl(m):
                i = _pos[0]; _pos[0] += 1
                return f'href="{player_urls_upd[i]}"' if i < 4 else m.group(0)
            html_content = re.sub(_href_pat, _repl, html_content)

        # Write updated HTML
        with open(match_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Also update the generated backup file if it exists
        gen_file = os.path.join(root_dir, "foot-holics-bot", "generated", "html_files", filename)
        if os.path.exists(gen_file):
            with open(gen_file, "w", encoding="utf-8") as f:
                f.write(html_content)

        # Update events.json
        events_path = os.path.join(root_dir, "data", "events.json")
        if os.path.exists(events_path):
            with open(events_path, "r", encoding="utf-8") as f:
                events = json.load(f)

            filename_without_ext = filename.replace(".html", "")
            for event in events:
                if filename_without_ext in event.get("slug", ""):
                    if "current_title" in context.user_data:
                        event["title"] = context.user_data["current_title"]
                    if "current_league" in context.user_data:
                        event["league"] = context.user_data["current_league"]
                        event["leagueSlug"] = context.user_data.get("current_league_slug", "others")
                    if "current_stadium" in context.user_data:
                        event["stadium"] = context.user_data["current_stadium"]
                    if "current_stream_links" in context.user_data:
                        # Update all 4 streaming links (wrap m3u8 with proxy)
                        stream_links = context.user_data["current_stream_links"]
                        event["broadcast"] = [
                            {"name": "Stream 1", "url": wrap_m3u8_with_proxy(stream_links[0]) if len(stream_links) > 0 else "#"},
                            {"name": "Stream 2", "url": wrap_m3u8_with_proxy(stream_links[1]) if len(stream_links) > 1 else "#"},
                            {"name": "Stream 3", "url": wrap_m3u8_with_proxy(stream_links[2]) if len(stream_links) > 2 else "#"},
                            {"name": "Stream 4", "url": wrap_m3u8_with_proxy(stream_links[3]) if len(stream_links) > 3 else "#"},
                        ]
                        event["streams"] = len([url for url in stream_links if url and url != "#" and not url.startswith("https://t.me/")])
                    break

            with open(events_path, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2, ensure_ascii=False)

            # Also update the generated JSON entry file if it exists
            filename_without_ext = filename.replace(".html", "")
            gen_json_file = os.path.join(root_dir, "foot-holics-bot", "generated", "json_entries", f"{filename_without_ext}.json")
            if os.path.exists(gen_json_file):
                # Find the updated event data
                for event in events:
                    if filename_without_ext in event.get("slug", ""):
                        with open(gen_json_file, "w", encoding="utf-8") as f:
                            json.dump(event, f, indent=2, ensure_ascii=False)
                        break

        # Update index.html card (remove old, add new)
        remove_match_from_index(filename)

        # Get poster from events.json for the updated card
        poster_path = "assets/img/match-poster.jpg"  # fallback
        filename_without_ext = filename.replace(".html", "")
        for event in events:
            if filename_without_ext in event.get("slug", ""):
                poster_path = event.get("poster", poster_path)
                break

        # Generate new card with updated info
        card_html = generate_updated_card(context.user_data, filename, poster_path)
        add_card_to_index(card_html)

        success_msg = f"""
✅ **Match Updated Successfully!**

Updated: `{filename}`

**Changes saved to:**
• Match HTML file
• data/events.json
• index.html card

**Next steps:**
```bash
git add .
git commit -m "Update {context.user_data.get('current_title', 'match')}"
git push
```

Your changes will be live in 60 seconds!
"""

        if query:
            await query.edit_message_text(success_msg, parse_mode="Markdown")
        else:
            await update.message.reply_text(success_msg, parse_mode="Markdown")

    except Exception as e:
        error_msg = f"❌ Error updating match: {str(e)}"
        if query:
            await query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)

    await show_main_menu(update, context, edit_message=False)
    context.user_data.clear()
    return MAIN_MENU


def generate_updated_card(data: dict, filename: str, poster_path: str = "assets/img/match-poster.jpg") -> str:
    """Generate updated card HTML."""
    card_html = f"""                    <!-- Match Card -->
                    <article class="glass-card match-card">
                        <img src="{poster_path}" alt="{data.get('current_title', 'Match')}" class="match-poster" loading="lazy">
                        <div class="match-header">
                            <h3 class="match-title">{data.get('current_title', 'Match')}</h3>
                            <span class="league-badge {data.get('current_league_slug', 'others')}">{data.get('current_league', 'Football')}</span>
                        </div>
                        <div class="match-meta">
                            <div class="match-meta-item">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                                    <line x1="16" y1="2" x2="16" y2="6"></line>
                                    <line x1="8" y1="2" x2="8" y2="6"></line>
                                    <line x1="3" y1="10" x2="21" y2="10"></line>
                                </svg>
                                <span>{data.get('current_date', 'TBD')}</span>
                            </div>
                            <div class="match-meta-item">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="12" cy="12" r="10"></circle>
                                    <polyline points="12 6 12 12 16 14"></polyline>
                                </svg>
                                <span>{data.get('current_time', 'TBD')} GMT</span>
                            </div>
                            <div class="match-meta-item">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                                    <circle cx="12" cy="10" r="3"></circle>
                                </svg>
                                <span>{data.get('current_stadium', 'Stadium TBD')}</span>
                            </div>
                        </div>
                        <p class="match-excerpt">{(lambda p: p[:150] + '...' if len(p) > 150 else p)(data.get('current_preview', 'Match preview'))}</p>
                        <a href="{filename}" class="match-link">
                            Read More & Watch Live
                            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                                <polyline points="12 5 19 12 12 19"></polyline>
                            </svg>
                        </a>
                    </article>"""
    return card_html


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

        # Check if date is in the past
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
            InlineKeyboardButton("🏆 World Cup 2026", callback_data="league_World Cup 2026"),
            InlineKeyboardButton("🌍 Nationals", callback_data="league_Nationals"),
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

        # Save to generated folder (always relative to bot directory, not cwd)
        bot_dir = os.path.dirname(os.path.abspath(__file__))
        gen_html = os.path.join(bot_dir, "generated", "html_files")
        gen_json = os.path.join(bot_dir, "generated", "json_entries")
        gen_cards = os.path.join(bot_dir, "generated", "cards")
        os.makedirs(gen_html, exist_ok=True)
        os.makedirs(gen_json, exist_ok=True)
        os.makedirs(gen_cards, exist_ok=True)

        with open(os.path.join(gen_html, f"{filename_base}.html"), "w", encoding="utf-8") as f:
            f.write(html_code)

        with open(os.path.join(gen_json, f"{filename_base}.json"), "w", encoding="utf-8") as f:
            f.write(json_code)

        with open(os.path.join(gen_cards, f"{filename_base}-card.html"), "w", encoding="utf-8") as f:
            f.write(card_code)

        # AUTO-INTEGRATE: Copy files and update index/events
        await update.message.reply_text("⏳ Auto-integrating into your website... Please wait.")

        integration_results = []

        # 1. Copy HTML to project root
        html_filename = f"{filename_base}.html"
        if copy_html_to_root(html_filename, html_code):
            integration_results.append("✅ HTML copied to project root")
        else:
            integration_results.append("⚠️ Could not copy HTML to root")

        # 2. Add entry to events.json
        if add_to_events_json(json_code):
            integration_results.append("✅ Added to data/events.json")
        else:
            integration_results.append("⚠️ Could not add to events.json")

        # 3. Add card to index.html
        if add_card_to_index(card_code):
            integration_results.append("✅ Added card to index.html")
        else:
            integration_results.append("⚠️ Could not add card to index.html")

        # 4. Add to sitemap.xml
        if add_to_sitemap(html_filename, context.user_data["date"]):
            integration_results.append("✅ Added to sitemap.xml")
        else:
            integration_results.append("⚠️ Could not add to sitemap.xml")

        # Send results as files
        await send_generated_files(update, context, html_code, json_code, card_code, filename_base, integration_results)

    except Exception as e:
        await update.message.reply_text(f"❌ Error generating code: {str(e)}")
        return ConversationHandler.END

    # Show main menu again
    await show_main_menu(update, context, edit_message=False)
    return MAIN_MENU


def generate_html(data: Dict[str, Any]) -> str:
    """Generate complete HTML event file."""
    # Prepare data
    date_obj = data["datetime_obj"]
    home_slug = slugify(data["home_team"])
    away_slug = slugify(data["away_team"])
    filename = f"{data['date']}-{home_slug}-vs-{away_slug}.html"

    # Generate ISO date for JSON-LD
    iso_date = date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")

    # URL encode match name for social sharing
    match_name_encoded = quote(data["match_name"])

    # Use template
    html = get_inline_event_template()

    # Auto-find team logos
    home_logo = find_team_logo(data["home_team"], data["league_slug"])
    away_logo = find_team_logo(data["away_team"], data["league_slug"])

    # Generate player URLs with smart routing based on stream type
    stream_urls = data.get("stream_urls", ["#", "#", "#", "#"])
    player_urls = []

    # Build universal-player.html URLs for each stream with type hint + match title + thumbnail
    encoded_title = quote(data.get("match_name", ""))
    # Thumbnail: use explicit thumb from data, else home team logo, else nothing
    thumb_src = data.get("thumbnail", "") or home_logo or ""
    encoded_thumb = quote(thumb_src) if thumb_src else ""

    for i in range(4):
        url = stream_urls[i] if i < len(stream_urls) else "#"

        if url and url != "#" and not url.startswith("https://t.me/"):
            encoded_url = base64.b64encode(url.encode()).decode()
            type_hint = get_type_param(url)
            params = f"get={encoded_url}"
            if type_hint:
                params += f"&type={type_hint}"
            if encoded_title:
                params += f"&title={encoded_title}"
            if encoded_thumb:
                params += f"&thumb={encoded_thumb}"
            player_url = f"universal-player.html?{params}"
        else:
            player_url = "#"

        player_urls.append(player_url)

    # Ensure we have exactly 4 URLs
    while len(player_urls) < 4:
        player_urls.append("#")

    # Replace placeholders
    html = html.replace("{{MATCH_NAME}}", data["match_name"])
    html = html.replace("{{HOME_TEAM}}", data["home_team"])
    html = html.replace("{{AWAY_TEAM}}", data["away_team"])
    html = html.replace("{{HOME_TEAM_LOGO}}", home_logo)
    html = html.replace("{{AWAY_TEAM_LOGO}}", away_logo)
    html = html.replace("{{DATE}}", date_obj.strftime("%B %d, %Y"))
    html = html.replace("{{DATE_SHORT}}", date_obj.strftime("%b %d, %Y"))
    html = html.replace("{{ISO_DATE}}", iso_date)
    html = html.replace("{{TIME}}", data["time"])
    html = html.replace("{{LEAGUE}}", data["league"])
    html = html.replace("{{LEAGUE_SLUG}}", data["league_slug"])
    html = html.replace("{{STADIUM}}", data["stadium"])
    html = html.replace("{{PREVIEW}}", data["preview"])
    html = html.replace("{{IMAGE_FILE}}", data["image_file"])
    html = html.replace("{{FILE_NAME}}", filename)
    html = html.replace("{{SLUG}}", f"{home_slug}-vs-{away_slug}")
    html = html.replace("{{MATCH_NAME_ENCODED}}", match_name_encoded)

    # Replace stream URLs with branded player links
    html = html.replace("{{STREAM_URL_1}}", player_urls[0])
    html = html.replace("{{STREAM_URL_2}}", player_urls[1])
    html = html.replace("{{STREAM_URL_3}}", player_urls[2])
    html = html.replace("{{STREAM_URL_4}}", player_urls[3])

    return html


def generate_json(data: Dict[str, Any]) -> str:
    """Generate JSON entry for events.json."""
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
            {"name": "Stream 1", "url": wrap_m3u8_with_proxy(data["stream_urls"][0]) if len(data["stream_urls"]) > 0 else "#"},
            {"name": "Stream 2", "url": wrap_m3u8_with_proxy(data["stream_urls"][1]) if len(data["stream_urls"]) > 1 else "#"},
            {"name": "Stream 3", "url": wrap_m3u8_with_proxy(data["stream_urls"][2]) if len(data["stream_urls"]) > 2 else "#"},
            {"name": "Stream 4", "url": wrap_m3u8_with_proxy(data["stream_urls"][3]) if len(data["stream_urls"]) > 3 else "#"},
        ],
        "streams": len([url for url in data["stream_urls"] if url and url != "#" and not url.startswith("https://t.me/")])
    }

    return json.dumps(event_data, indent=2)


def generate_card(data: Dict[str, Any]) -> str:
    """Generate homepage card HTML."""
    template = get_inline_card_template()

    date_obj = data["datetime_obj"]
    home_slug = slugify(data["home_team"])
    away_slug = slugify(data["away_team"])
    filename = f"{data['date']}-{home_slug}-vs-{away_slug}.html"

    # Create excerpt
    excerpt = data["preview"][:150] + "..." if len(data["preview"]) > 150 else data["preview"]

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


async def send_generated_files(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    html_code: str,
    json_code: str,
    card_code: str,
    filename_base: str,
    integration_results: list = None
) -> None:
    """Send generated code as files instead of text."""

    # Show integration results
    if integration_results:
        integration_status = "\n".join(integration_results)
        await update.message.reply_text(
            f"🎉 **AUTO-INTEGRATION COMPLETE!**\n\n{integration_status}",
            parse_mode="Markdown"
        )

    await update.message.reply_text(
        "📦 **Files Generated & Saved**\n\n"
        "Sending backup files to you...",
        parse_mode="Markdown"
    )

    # Send HTML file (as backup)
    html_bytes = BytesIO(html_code.encode('utf-8'))
    html_bytes.name = f"{filename_base}.html"
    await update.message.reply_document(
        document=html_bytes,
        filename=f"{filename_base}.html",
        caption="📄 **HTML File** (Backup - Already copied to root!)"
    )

    # Send JSON entry (as backup)
    json_bytes = BytesIO(json_code.encode('utf-8'))
    json_bytes.name = f"{filename_base}.json"
    await update.message.reply_document(
        document=json_bytes,
        filename=f"{filename_base}.json",
        caption="📊 **JSON Entry** (Backup - Already added to events.json!)"
    )

    # Send card HTML (as backup)
    card_bytes = BytesIO(card_code.encode('utf-8'))
    card_bytes.name = f"{filename_base}-card.html"
    await update.message.reply_document(
        document=card_bytes,
        filename=f"{filename_base}-card.html",
        caption="🏠 **Homepage Card** (Backup - Already added to index.html!)"
    )

    # Send simplified instructions
    instructions = f"""
🎉 **MATCH CREATED & INTEGRATED!**

✅ **Automatically Done:**
• HTML file copied to project root
• Entry added to `data/events.json`
• Card added to `index.html`

📋 **You Just Need To:**

1️⃣ **Upload Image:**
   Upload match poster to `assets/img/{context.user_data['image_file']}`
   Recommended size: 1200x630px

2️⃣ **Commit and push:**
```bash
git add .
git commit -m "Add {context.user_data['match_name']} match"
git push
```

🚀 **That's it!** Your match will be live in 60 seconds!

💡 **Tip:** The files sent above are backups in case you need them later.
"""

    await update.message.reply_text(instructions, parse_mode="Markdown")


def get_inline_event_template() -> str:
    """Return inline HTML template."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Watch {{MATCH_NAME}} live stream free - {{LEAGUE}} clash on {{DATE}} at {{STADIUM}}. Find HD streaming links, match preview, and live football coverage on Foot Holics.">
    <meta name="keywords" content="{{MATCH_NAME}}, {{HOME_TEAM}} vs {{AWAY_TEAM}}, {{LEAGUE}} live stream, watch football online, football live streaming, free football stream, {{STADIUM}}, {{HOME_TEAM}} live, {{AWAY_TEAM}} live, football match today, live soccer stream, watch {{LEAGUE}} online">

    <!-- Open Graph -->
    <meta property="og:title" content="{{MATCH_NAME}} - {{LEAGUE}} Live Stream">
    <meta property="og:description" content="Watch the {{LEAGUE}} match between {{HOME_TEAM}} and {{AWAY_TEAM}} live on {{DATE}}.">
    <meta property="og:type" content="website">
    <meta property="og:image" content="assets/img/{{IMAGE_FILE}}">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{{MATCH_NAME}} - {{LEAGUE}} Live Stream">
    <meta name="twitter:description" content="Watch the {{LEAGUE}} match live with multiple streaming options.">

    <title>{{MATCH_NAME}} - {{LEAGUE}} Live Stream | Foot Holics</title>

    <!-- Canonical -->
    <link rel="canonical" href="https://footholics.in/{{FILE_NAME}}">

    <!-- Preconnect to Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>

    <!-- Google Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">

    <!-- Font Awesome -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" integrity="sha512-DTOQO9RWCH3ppGqcWaEA1BIZOC6xxalwEsw9c2QQeAIftl+Vegovlnee1c9QX4TctnWMn13TZye+giMm8e2LwA==" crossorigin="anonymous" referrerpolicy="no-referrer" />

    <!-- Stylesheet -->
    <link rel="stylesheet" href="assets/css/main.css">

    <!-- Favicon -->
    <link rel="icon" type="image/png" href="assets/img/logos/site/logo.png">
    <link rel="apple-touch-icon" href="assets/img/logos/site/logo.png">

    <!-- JSON-LD Structured Data -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "SportsEvent",
      "name": "{{MATCH_NAME}}",
      "description": "Watch {{MATCH_NAME}} live stream free on Foot Holics. {{LEAGUE}} match with multiple HD streaming links.",
      "startDate": "{{ISO_DATE}}",
      "location": {
        "@type": "Place",
        "name": "{{STADIUM}}",
        "address": {
          "@type": "PostalAddress"
        }
      },
      "homeTeam": {
        "@type": "SportsTeam",
        "name": "{{HOME_TEAM}}",
        "sport": "Football"
      },
      "awayTeam": {
        "@type": "SportsTeam",
        "name": "{{AWAY_TEAM}}",
        "sport": "Football"
      },
      "sport": "Football",
      "competitor": [
        {
          "@type": "SportsTeam",
          "name": "{{HOME_TEAM}}"
        },
        {
          "@type": "SportsTeam",
          "name": "{{AWAY_TEAM}}"
        }
      ],
      "organizer": {
        "@type": "SportsOrganization",
        "name": "{{LEAGUE}}"
      },
      "eventStatus": "https://schema.org/EventScheduled",
      "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
      "isAccessibleForFree": false,
      "url": "https://footholics.in/{{FILENAME}}"
    }
    </script>

    <!-- Organization Schema for Foot Holics -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Organization",
      "name": "Foot Holics",
      "url": "https://footholics.in",
      "logo": "https://footholics.in/assets/img/logos/site/logo.png",
      "description": "Premium football streaming aggregator providing links to live football matches from around the world",
      "sameAs": [
        "https://t.me/+XyKdBR9chQpjM2I9",
        "https://chat.whatsapp.com/KG7DBpC0BKv6bFtlzfOr2T"
      ]
    }
    </script>

    <!-- BreadcrumbList Schema -->
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {
          "@type": "ListItem",
          "position": 1,
          "name": "Home",
          "item": "https://footholics.in/"
        },
        {
          "@type": "ListItem",
          "position": 2,
          "name": "{{LEAGUE}}",
          "item": "https://footholics.in/#leagues"
        },
        {
          "@type": "ListItem",
          "position": 3,
          "name": "{{MATCH_NAME}}",
          "item": "https://footholics.in/{{FILENAME}}"
        }
      ]
    }
    </script>
</head>
<body>
    <!-- Header -->
    <header class="site-header">
        <div class="container">
            <div class="header-inner">
                <a href="index.html" class="logo">
                    <img src="assets/img/logos/site/logo.png" alt="Foot Holics Logo" class="logo-icon">
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
                <img src="{{HOME_TEAM_LOGO}}" alt="{{HOME_TEAM}}" class="team-logo" style="width: 100px; height: 100px; border-radius: 50%; object-fit: contain; box-shadow: 0 4px 6px rgba(0,0,0,0.1);" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                <div class="team-crest" style="background: linear-gradient(135deg, #D4AF37 0%, #FFD700 100%); display: none;">⚽</div>
                <h2 class="team-name">{{HOME_TEAM}}</h2>
                <p class="text-muted">Home</p>
            </div>
            <div class="vs">VS</div>
            <div class="team">
                <img src="{{AWAY_TEAM_LOGO}}" alt="{{AWAY_TEAM}}" class="team-logo" style="width: 100px; height: 100px; border-radius: 50%; object-fit: contain; box-shadow: 0 4px 6px rgba(0,0,0,0.1);" onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                <div class="team-crest" style="background: linear-gradient(135deg, #0EA5E9 0%, #06B6D4 100%); display: none;">⚽</div>
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
                <a href="{{STREAM_URL_1}}" class="stream-link-card">
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

                <a href="{{STREAM_URL_2}}" class="stream-link-card">
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

                <a href="{{STREAM_URL_3}}" class="stream-link-card">
                    <span class="live-badge">
                        <span class="live-dot"></span>
                        LIVE
                    </span>
                    <span class="stream-link-label">LINK 3</span>
                    <div class="stream-badges">
                        <span class="quality-badge sd">SD</span>
                        <span class="lang-badge">EN</span>
                    </div>
                    <p style="font-size: 0.75rem; color: var(--muted); margin-top: 0.5rem;">Mobile Optimized</p>
                </a>

                <a href="{{STREAM_URL_4}}" class="stream-link-card">
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
                <a href="https://api.whatsapp.com/send?text=Watch%20{{MATCH_NAME_ENCODED}}%20Live%20-%20https://footholics.in/{{FILE_NAME}}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="font-size: 0.9rem;">
                    <i class="fa-brands fa-whatsapp" style="font-size: 20px; margin-right: 8px;"></i> WhatsApp
                </a>
                <a href="https://www.facebook.com/sharer/sharer.php?u=https://footholics.in/{{FILE_NAME}}" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="font-size: 0.9rem;">
                    <i class="fa-brands fa-facebook" style="font-size: 20px; margin-right: 8px;"></i> Facebook
                </a>
                <a href="https://twitter.com/intent/tweet?url=https://footholics.in/{{FILE_NAME}}&text=Watch%20{{MATCH_NAME_ENCODED}}%20Live" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="font-size: 0.9rem;">
                    <i class="fa-brands fa-x-twitter" style="font-size: 20px; margin-right: 8px;"></i> X
                </a>
                <a href="https://t.me/share/url?url=https://footholics.in/{{FILE_NAME}}&text=Watch%20{{MATCH_NAME_ENCODED}}%20Live" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="font-size: 0.9rem;">
                    <i class="fa-brands fa-telegram" style="font-size: 20px; margin-right: 8px;"></i> Telegram
                </a>
                <a href="https://discord.com/channels/@me" target="_blank" rel="noopener noreferrer" class="btn btn-secondary" style="font-size: 0.9rem;" onclick="navigator.clipboard.writeText('Watch {{MATCH_NAME}} Live - https://footholics.in/{{FILE_NAME}}'); alert('Link copied! Paste it in Discord.'); return false;">
                    <i class="fa-brands fa-discord" style="font-size: 20px; margin-right: 8px;"></i> Discord
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
                For takedown requests or concerns, contact: <a href="mailto:footholicsin@gmail.com" style="color: var(--accent);">footholicsin@gmail.com</a>
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
                        <li><a href="mailto:footholicsin@gmail.com">Contact</a></li>
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
                        <li><a href="https://chat.whatsapp.com/KG7DBpC0BKv6bFtlzfOr2T" target="_blank" rel="noopener noreferrer">
                            <i class="fa-brands fa-whatsapp" style="font-size: 18px; margin-right: 8px;"></i>WhatsApp Channel
                        </a></li>
                        <li><a href="https://t.me/+XyKdBR9chQpjM2I9" target="_blank" rel="noopener noreferrer">
                            <i class="fa-brands fa-telegram" style="font-size: 18px; margin-right: 8px;"></i>Telegram
                        </a></li>
                        <li><a href="https://discord.gg/example" target="_blank" rel="noopener noreferrer">
                            <i class="fa-brands fa-discord" style="font-size: 18px; margin-right: 8px;"></i>Discord
                        </a></li>
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

    <!-- ========================================
         ADSTERRA AD SLOTS - OPTIMIZED FOR MAXIMUM REVENUE
         ======================================== -->

    <!-- Native Banner Ad - Blends with content, high CTR -->
    <div id="ad-slot-native-1" style="margin: 30px auto; max-width: 1200px;">
        <script async="async" data-cfasync="false" src="https://pl28194628.effectivegatecpm.com/0eafec7e4106026e364203d54ba0c8e9/invoke.js"></script>
        <div id="container-0eafec7e4106026e364203d54ba0c8e9"></div>
    </div>

    <!-- 300x250 Banner Ad - High visibility placement -->
    <div id="ad-slot-banner-300x250" style="margin: 30px auto; text-align: center;">
        <script>
            atOptions = {
                'key' : '66dc201b64275feeae63bc4b419a241c',
                'format' : 'iframe',
                'height' : 250,
                'width' : 300,
                'params' : {}
            };
        </script>
        <script src="https://www.highperformanceformat.com/66dc201b64275feeae63bc4b419a241c/invoke.js"></script>
    </div>

    <!-- Popunder Ad Slots (Multiple for better coverage) -->
    <div id="ad-slot-popunder"></div>

    <!-- Smartlink Ad (Used for outbound links) -->
    <!-- Smartlink URL: https://www.effectivegatecpm.com/w5hzdwkr3h?key=bfbd283ffe1573110488645fe30c5cfd -->

    <!-- Social Bar Ad (Sticky - Always visible) -->
    <div id="ad-slot-social-bar">
        <script src="https://pl28190484.effectivegatecpm.com/ad/f7/17/adf7172d701fdcad288330f7b67c9293.js"></script>
    </div>

    <!-- Adsterra Scripts Section -->
    <!-- Popunder Ads - Only on match pages, not homepage -->
    <script src="https://pl28194614.effectivegatecpm.com/98/b2/61/98b2610dbd944ffe41efc4663be4b3ad.js"></script>
    <script src="https://pl28190353.effectivegatecpm.com/52/30/74/5230747febbb777e6e14a3c30aa1fd30.js"></script>

    <!-- JavaScript -->
    <script src="assets/js/main.js" defer></script>
</body>
</html>"""


def get_inline_card_template() -> str:
    """Return inline card template."""
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
        "❌ Operation cancelled.\n\nType /start to use the bot again.",
        parse_mode="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and notify the user so conversations don't silently hang."""
    logger.error("Unhandled exception", exc_info=context.error)

    # Try to notify the user
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ An unexpected error occurred. Please type /start to try again."
            )
        except Exception:
            pass


def main() -> None:
    """Start the bot."""
    # Get token from environment
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        logger.critical("TELEGRAM_BOT_TOKEN not set. Create a .env file with your bot token.")
        return

    # Create application
    application = Application.builder().token(token).build()

    # Define conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [CallbackQueryHandler(main_menu_handler)],
            MATCH_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, match_name)],
            DATE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, date_time)],
            LEAGUE: [CallbackQueryHandler(league_selection, pattern="^league_")],
            STADIUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, stadium)],
            PREVIEW: [MessageHandler(filters.TEXT & ~filters.COMMAND, preview)],
            STREAM_URLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, stream_urls)],
            IMAGE_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, image_name)],
            DELETE_SELECT: [
                CallbackQueryHandler(delete_match_handler, pattern="^delete_"),
                CallbackQueryHandler(confirm_delete_handler, pattern="^confirm_delete_"),
                CallbackQueryHandler(main_menu_handler, pattern="^menu_"),
            ],
            UPDATE_SELECT: [
                CallbackQueryHandler(update_match_handler, pattern="^update_"),
                CallbackQueryHandler(main_menu_handler, pattern="^menu_"),
            ],
            UPDATE_FIELD_CHOICE: [
                CallbackQueryHandler(update_field_choice_handler, pattern="^update_field_"),
                CallbackQueryHandler(update_field_choice_handler, pattern="^update_save"),
                CallbackQueryHandler(update_league_handler, pattern="^update_league_"),
                CallbackQueryHandler(main_menu_handler, pattern="^menu_"),
            ],
            UPDATE_FIELD_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, update_field_input_handler)
            ],
            UPDATE_STREAM_SELECT: [
                CallbackQueryHandler(stream_link_select_handler, pattern="^stream_link_"),
                CallbackQueryHandler(stream_link_action_handler, pattern="^stream_done"),
                CallbackQueryHandler(stream_link_action_handler, pattern="^stream_back"),
                CallbackQueryHandler(stream_link_action_handler, pattern="^stream_clear_"),
                CallbackQueryHandler(update_field_choice_handler, pattern="^update_save"),
                CallbackQueryHandler(main_menu_handler, pattern="^menu_"),
            ],
            UPDATE_STREAM_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, stream_link_input_handler),
                CallbackQueryHandler(stream_link_action_handler, pattern="^stream_back"),
                CallbackQueryHandler(stream_link_action_handler, pattern="^stream_clear_"),
            ],
            GENERATE_CARD_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, generate_card_input)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_error_handler(error_handler)

    auth_info = f"{len(ALLOWED_USER_IDS)} authorized user(s)" if ALLOWED_USER_IDS else "ALL users (no restriction)"
    logger.info("🤖 Foot Holics Match Manager Bot is starting...")
    logger.info(f"   Authorized: {auth_info}")
    logger.info("   Press Ctrl+C to stop")

    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,  # ignore stale messages from when bot was offline
    )


if __name__ == "__main__":
    main()
