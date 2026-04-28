#!/usr/bin/env python3
"""
Foot Holics Match Manager Bot
A Telegram bot for managing football matches on the Foot Holics website.
"""

import os
import json
import re
import glob
import subprocess
import asyncio
import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from urllib.parse import quote
from dotenv import load_dotenv
from io import BytesIO
import html as _html

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

# India Standard Time (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# Conversation states
(
    MAIN_MENU,
    MATCH_NAME,
    DATE_TIME,
    LEAGUE,
    STADIUM,
    PREVIEW,
    STREAM_URLS,
    POSTER_IMAGE,
    DELETE_SELECT,
    UPDATE_SELECT,
    UPDATE_FIELD_CHOICE,
    UPDATE_FIELD_INPUT,
    UPDATE_STREAM_LINKS,
    GENERATE_CARD_INPUT,
    UPDATE_STREAM_SELECT,  # New state for button-based stream link selection
    UPDATE_STREAM_INPUT,   # New state for individual stream link input
    ARTICLE_TITLE,
    ARTICLE_CATEGORY,
    ARTICLE_EXCERPT,
    ARTICLE_COVER_IMAGE,
    ARTICLE_CONTENT,
    ARTICLE_CONFIRM,
    EDIT_ARTICLE_SELECT,
    EDIT_ARTICLE_FIELD,
    EDIT_ARTICLE_INPUT,
    EDIT_ARTICLE_CONFIRM,
    DELETE_ARTICLE_SELECT,
    DELETE_ARTICLE_CONFIRM,
    SET_GIT_CREDS,
) = range(29)

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


def get_player_url(url: str, base_url: str = "https://live.footholics.in", title: str = "", thumb: str = "") -> str:
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

    return f"{base_url}/player.html?{params}"


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
    return get_player_url(url, "https://live.footholics.in")


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



def get_live_project_root() -> str:
    """Return path to foot-holics-live/ project folder, or empty string if not found."""
    # 1. Docker container mount point: /foot-holics-live
    if os.path.isdir("/foot-holics-live"):
        return "/foot-holics-live"
    bot_dir = os.path.dirname(os.path.abspath(__file__))
    # 2. foot-holics-bot/ → foot-holics/ → parent → foot-holics-live/
    parent = os.path.dirname(os.path.dirname(bot_dir))
    live_root = os.path.join(parent, "foot-holics-live")
    if os.path.isdir(live_root):
        return live_root
    # 3. Fallback: sibling of foot-holics/
    foot_holics_root = os.path.dirname(bot_dir)
    sibling = os.path.join(os.path.dirname(foot_holics_root), "foot-holics-live")
    if os.path.isdir(sibling):
        return sibling
    return ""


def git_auto_push(repo_path: str, commit_message: str, username: str = "", token: str = "") -> tuple:
    """Run git add/commit/push in repo_path. Returns (success: bool, status: str).
    If username+token provided, injects them into the HTTPS remote URL so no
    credentials need to be stored on disk.

    Files are always staged+committed locally even if push credentials are missing,
    so they are never left as untracked on disk.
    """
    if not repo_path or not os.path.isdir(repo_path):
        return False, "repo path not found"

    # Pass safe.directory so git works correctly inside Docker regardless of
    # file ownership differences between the container user and the host.
    safe_flags = ["-c", f"safe.directory={repo_path}"]

    try:
        # Stage all changes (always, regardless of push credentials)
        r = subprocess.run(
            ["git"] + safe_flags + ["add", "."],
            cwd=repo_path, capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return False, f"git add failed: {r.stderr.strip()}"

        # Commit locally (always)
        r = subprocess.run(
            ["git"] + safe_flags + [
                "-c", f"user.name={username or 'footholics-bot'}",
                "-c", f"user.email={username or 'bot'}@users.noreply.github.com",
                "commit", "-m", commit_message,
            ],
            cwd=repo_path, capture_output=True, text=True, timeout=30
        )
        nothing_to_commit = r.returncode != 0 and (
            "nothing to commit" in r.stdout or "nothing to commit" in r.stderr
        )
        if r.returncode != 0 and not nothing_to_commit:
            return False, f"git commit failed: {r.stderr.strip()}"

        # Push requires credentials
        if not username or not token:
            return False, "committed locally — set git credentials to push"

        # Build authenticated push URL (never stored — only passed as arg to this call)
        r = subprocess.run(
            ["git"] + safe_flags + ["remote", "get-url", "origin"],
            cwd=repo_path, capture_output=True, text=True, timeout=10
        )
        remote_url = r.stdout.strip()
        if remote_url.startswith("https://"):
            push_url = remote_url.replace("https://", f"https://{username}:{token}@", 1)
        else:
            push_url = remote_url  # SSH — credentials not needed

        # Pull remote changes first to avoid "fetch first" rejection
        r = subprocess.run(
            ["git"] + safe_flags + ["pull", "--rebase", push_url],
            cwd=repo_path, capture_output=True, text=True, timeout=60
        )
        if r.returncode != 0:
            subprocess.run(["git"] + safe_flags + ["rebase", "--abort"],
                           cwd=repo_path, capture_output=True, timeout=15)
            return False, f"git pull failed: {r.stderr.strip()[:200]}"

        r = subprocess.run(
            ["git"] + safe_flags + ["push", push_url],
            cwd=repo_path, capture_output=True, text=True, timeout=60
        )
        if r.returncode != 0:
            err = r.stderr.strip()
            auth_keywords = ("authentication failed", "invalid username or password",
                             "could not read username", "403", "401", "bad credentials",
                             "token", "permission denied")
            if any(kw in err.lower() for kw in auth_keywords):
                return False, "AUTH_FAILED"
            return False, f"git push failed: {err}"

        return True, "pushed ✓"
    except subprocess.TimeoutExpired:
        return False, "timed out"
    except Exception as e:
        return False, str(e)


def _md_escape(s: str) -> str:
    """Escape Telegram Markdown v1 special chars in dynamic/untrusted text."""
    for ch in ('\\', '*', '_', '`', '['):
        s = s.replace(ch, '\\' + ch)
    return s


def push_summary(*results: tuple) -> str:
    """Format push results into a display string.
    Each result is (repo_label, ok, status).
    Appends a token-expired hint if any push got AUTH_FAILED."""
    lines = []
    auth_failed = False
    for label, ok, status in results:
        if status == "AUTH_FAILED":
            lines.append(f"❌ {label}: token expired or invalid")
            auth_failed = True
        else:
            lines.append(f"{'✅' if ok else '❌'} {label}: {_md_escape(status)}")
    text = "*Git push:*\n" + "\n".join(lines)
    if auth_failed:
        text += "\n\n⚠️ *Token expired — tap 🔑 Set Git Credentials to update.*"
    return text


def set_pending_push(context, jobs: list, results: list) -> None:
    """Store failed push jobs for retry.
    jobs:    list of (repo_path, commit_message)
    results: list of (ok, status) matching jobs"""
    failed = [
        {'path': path, 'msg': msg}
        for (path, msg), (ok, status) in zip(jobs, results)
        if not ok
    ]
    if failed:
        context.user_data['pending_push'] = failed
    else:
        context.user_data.pop('pending_push', None)


def copy_html_to_live(filename: str, html_code: str) -> bool:
    """Copy generated HTML to foot-holics-live/ folder."""
    live_root = get_live_project_root()
    if not live_root:
        logger.warning("foot-holics-live/ folder not found — live page not written")
        return False
    try:
        dest = os.path.join(live_root, filename)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(html_code)
        return True
    except Exception as e:
        logger.error(f"Error writing live page: {e}", exc_info=True)
        return False


BROADCASTER_MAP = {
    "premier-league":    {"uk": "Sky Sports", "us": "NBC Sports / Peacock", "in": "Star Sports / Hotstar"},
    "laliga":            {"uk": "DAZN",        "us": "ESPN+",               "in": "Star Sports"},
    "bundesliga":        {"uk": "Sky Sports",  "us": "ESPN+",               "in": "Sony Sports"},
    "serie-a":           {"uk": "TNT Sports",  "us": "Paramount+",          "in": "Sony Sports"},
    "ligue-1":           {"uk": "beIN Sports", "us": "beIN Sports",         "in": "beIN Sports"},
    "champions-league":  {"uk": "TNT Sports",  "us": "CBS / Paramount+",    "in": "Sony Sports"},
}


def get_broadcaster_table(league_slug: str) -> str:
    """Return HTML rows for broadcast table based on league."""
    bc = BROADCASTER_MAP.get(league_slug, {"uk": "Check local listings", "us": "Check local listings", "in": "Check local listings"})
    return f"""<tr>
                        <td>🇬🇧 United Kingdom</td>
                        <td>{bc['uk']}</td>
                        <td>HD, subscription required</td>
                    </tr>
                    <tr>
                        <td>🇺🇸 United States</td>
                        <td>{bc['us']}</td>
                        <td>Streaming available</td>
                    </tr>
                    <tr>
                        <td>🇮🇳 India</td>
                        <td>{bc['in']}</td>
                        <td>Hindi &amp; English commentary</td>
                    </tr>
                    <tr>
                        <td>🌍 International</td>
                        <td>Various (check local listings)</td>
                        <td>Contact your provider</td>
                    </tr>"""


def get_broadcaster_table_compact(league_slug: str) -> str:
    """Return compact HTML rows for the live page broadcast table (2-col)."""
    bc = BROADCASTER_MAP.get(league_slug, {"uk": "Check local listings", "us": "Check local listings", "in": "Check local listings"})
    rows = [
        ("🇬🇧 United Kingdom", bc['uk']),
        ("🇺🇸 United States",  bc['us']),
        ("🇮🇳 India",           bc['in']),
        ("🌍 International",    "Check local listings"),
    ]
    html = ""
    for region, channel in rows:
        html += f'<tr style="border-bottom:1px solid var(--glass-border);"><td style="padding:0.4rem 0;color:var(--text);">{region}</td><td style="padding:0.4rem 0;color:var(--muted);">{channel}</td></tr>\n'
    return html


def generate_live_html(data: dict) -> str:
    """Generate the live subdomain stream-links page."""
    from urllib.parse import quote
    import base64

    date_obj = data["datetime_obj"]
    home_slug = slugify(data["home_team"])
    away_slug = slugify(data["away_team"])
    filename = f"{data['date']}-{home_slug}-vs-{away_slug}.html"
    match_slug = filename.replace(".html", "")

    home_logo = find_team_logo(data["home_team"], data["league_slug"])
    away_logo = find_team_logo(data["away_team"], data["league_slug"])

    # Resolve absolute logo URLs for the live subdomain
    if home_logo and not home_logo.startswith("http"):
        home_logo = f"https://footholics.in/{home_logo.lstrip('/')}"
    if away_logo and not away_logo.startswith("http"):
        away_logo = f"https://footholics.in/{away_logo.lstrip('/')}"

    stream_urls = data.get("stream_urls", [])
    encoded_title = quote(data.get("match_name", ""))
    thumb_src = data.get("thumbnail", "") or ""
    encoded_thumb = quote(thumb_src) if thumb_src else ""

    # Build player URLs pointing to live.footholics.in/player.html
    player_urls = []
    for url in stream_urls[:4]:
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
            player_urls.append(f"player.html?{params}")
        else:
            player_urls.append(None)

    # Build stream link buttons HTML
    labels = ["Link 1 — HD | English | Desktop/Mobile", "Link 2 — HD | Multi-language", "Link 3 — SD | Mobile Optimized", "Link 4 — HD | Backup"]
    qualities = ["HD", "HD", "SD", "HD"]
    stream_buttons_html = ""
    for i, (pu, label, qual) in enumerate(zip(player_urls, labels, qualities)):
        if pu:
            stream_buttons_html += f"""
            <a href="{pu}" class="stream-link-btn">
                <div class="stream-play-icon">
                    <i class="fa-solid fa-play"></i>
                </div>
                <div class="stream-link-info">
                    <span class="stream-link-label">Link {i+1}</span>
                    <span class="stream-link-sub">{label.split(' — ')[1] if ' — ' in label else label}</span>
                </div>
                <span class="stream-quality-badge">{qual}</span>
            </a>"""

    # 24-hour time for the live badge script
    time_24h = date_obj.strftime("%H:%M")
    poster_url = data.get("thumbnail", "") or f"https://footholics.in/assets/img/{data.get('image_file', 'og-image.jpg')}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex, nofollow">
    <meta name="description" content="Watch {data['home_team']} vs {data['away_team']} live — {data['league']} on {date_obj.strftime('%B %d, %Y')}. Multiple stream links available.">
    <meta property="og:title" content="{data['match_name']} — Watch Live Stream">
    <meta property="og:description" content="Watch {data['match_name']} live online. {data['league']} — {date_obj.strftime('%B %d, %Y')}.">
    <meta property="og:type" content="website">
    <meta property="og:image" content="{poster_url}">
    <meta name="twitter:card" content="summary_large_image">
    <title>{data['match_name']} Live Stream — {data['league']} | Foot Holics</title>
    <link rel="canonical" href="https://live.footholics.in/{match_slug}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" integrity="sha512-DTOQO9RWCH3ppGqcWaEA1BIZOC6xxalwEsw9c2QQeAIftl+Vegovlnee1c9QX4TctnWMn13TZye+giMm8e2LwA==" crossorigin="anonymous" referrerpolicy="no-referrer" />
    <link rel="stylesheet" href="assets/css/live.css">
    <link rel="icon" type="image/png" href="https://footholics.in/assets/img/logos/site/logo.png">
    <script src="assets/js/live-match.js" defer></script>
</head>
<body>
    <header class="live-header">
        <div class="container">
            <div class="live-header-inner">
                <a href="https://footholics.in" class="live-logo">
                    <img src="https://footholics.in/assets/img/logos/site/logo.png" alt="Foot Holics" onerror="this.style.display=\'none\'">
                    Foot Holics
                </a>
                <a href="/detail?slug={match_slug}" class="back-link">
                    <i class="fa-solid fa-arrow-left" style="font-size:0.75rem;"></i>
                    Match Preview
                </a>
            </div>
        </div>
    </header>

    <div class="container">
        <div class="match-hero">
            <div style="display: flex; justify-content: center; gap: 0.75rem; margin-bottom: 1rem; flex-wrap: wrap;">
                <span class="live-badge-pill" id="liveBadge" style="display:none;">
                    <span class="live-dot"></span>
                    LIVE NOW
                </span>
                <span class="league-tag">{data['league']}</span>
            </div>
            <div class="teams-row">
                <div class="team-block">
                    <img src="{home_logo}" alt="{data['home_team']}" onerror="this.outerHTML=\'<div class=&quot;team-logo-placeholder&quot;>⚽</div>\'">
                    <span class="team-name-text">{data['home_team']}</span>
                </div>
                <div class="vs-text">vs</div>
                <div class="team-block">
                    <img src="{away_logo}" alt="{data['away_team']}" onerror="this.outerHTML=\'<div class=&quot;team-logo-placeholder&quot;>⚽</div>\'">
                    <span class="team-name-text">{data['away_team']}</span>
                </div>
            </div>
            <div class="match-meta-row">
                <span><i class="fa-regular fa-calendar" style="color:var(--accent);"></i> {date_obj.strftime('%B %d, %Y')}</span>
                <span><i class="fa-regular fa-clock" style="color:var(--accent);"></i> {data['time']} IST</span>
                <span><i class="fa-solid fa-location-dot" style="color:var(--accent);"></i> {data['stadium']}</span>
            </div>
        </div>

        <!-- ── LIVE SCORE WIDGET ──────────────────────────────────────────── -->
        <div id="liveScoreWidget" style="display:none;background:var(--panel);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:1rem 1.5rem;margin-bottom:1.25rem;text-align:center;">
            <div id="liveScoreStatus" style="font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:0.5rem;"></div>
            <div id="liveScoreValue" style="font-size:2.2rem;font-weight:700;letter-spacing:4px;line-height:1;"></div>
        </div>

        <!-- ── MATCH DATA WIDGET (Timeline + Tabs) ───────────────────────── -->
        <div id="matchDataSection" style="display:none;margin-bottom:1.25rem;">
            <div id="mdTimeline" class="md-timeline" style="display:none;">
                <div class="tl-header">Match Timeline</div>
                <div class="tl-track">
                    <div class="tl-line"></div>
                    <div class="tl-ht" style="left:50%"></div>
                </div>
                <div class="tl-minute-labels"><span>0'</span><span>45'</span><span>90'</span></div>
            </div>
            <div class="md-panel">
                <div class="md-tabs">
                    <button class="md-tab active" onclick="mdTab(this,'mdStats')">Stats</button>
                    <button class="md-tab" onclick="mdTab(this,'mdLineups')">Lineups</button>
                    <button class="md-tab" onclick="mdTab(this,'mdFormation')">Formation</button>
                    <button class="md-tab" onclick="mdTab(this,'mdCommentary')">Commentary</button>
                </div>
                <div id="mdStats" class="md-pane"></div>
                <div id="mdLineups" class="md-pane" style="display:none;"></div>
                <div id="mdFormation" class="md-pane" style="display:none;"></div>
                <div id="mdCommentary" class="md-pane" style="display:none;"></div>
            </div>
        </div>

        <p class="stream-section-title">Watch {data['home_team']} vs {data['away_team']} Live</p>

        <div class="stream-links-list">
{stream_buttons_html}
        </div>

        <p class="stream-note">
            <i class="fa-solid fa-circle-info" style="color:var(--accent);"></i>
            If one stream is down, try the next link. Streams go live ~15 minutes before kickoff.
        </p>

        <div class="community-row" style="margin-top: 1.5rem;">
            <a href="https://t.me/+XyKdBR9chQpjM2I9" target="_blank" rel="noopener noreferrer" class="community-btn btn-telegram">
                <i class="fa-brands fa-telegram"></i> Join Telegram for Updates
            </a>
            <a href="https://chat.whatsapp.com/KG7DBpC0BKv6bFtlzfOr2T" target="_blank" rel="noopener noreferrer" class="community-btn btn-whatsapp">
                <i class="fa-brands fa-whatsapp"></i> WhatsApp Channel
            </a>
        </div>

        <!-- ── MATCH INFO SECTION ────────────────────────────────────────── -->
        <div style="background:var(--panel);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:1.25rem;margin:1.5rem 0;">
            <h2 style="color:var(--accent);font-size:1rem;margin-bottom:0.9rem;">Match Information</h2>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.65rem 1.25rem;font-size:0.84rem;">
                <div><span style="color:var(--muted);display:block;margin-bottom:0.15rem;">Competition</span><strong style="color:var(--text);">{data['league']}</strong></div>
                <div><span style="color:var(--muted);display:block;margin-bottom:0.15rem;">Kickoff (IST)</span><strong style="color:var(--text);">{data['time']} IST</strong></div>
                <div><span style="color:var(--muted);display:block;margin-bottom:0.15rem;">Date</span><strong style="color:var(--text);">{date_obj.strftime('%B %d, %Y')}</strong></div>
                <div><span style="color:var(--muted);display:block;margin-bottom:0.15rem;">Venue</span><strong style="color:var(--text);">{data['stadium']}</strong></div>
            </div>
        </div>

        <!-- ── OFFICIAL BROADCAST ────────────────────────────────────────── -->
        <div style="background:var(--panel);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:1.25rem;margin-bottom:1.5rem;">
            <h2 style="color:var(--accent);font-size:1rem;margin-bottom:0.9rem;">Official Broadcast</h2>
            <table style="width:100%;border-collapse:collapse;font-size:0.82rem;">
                <thead><tr style="border-bottom:1px solid var(--glass-border);">
                    <th style="text-align:left;padding:0.35rem 0;color:var(--muted);font-weight:600;">Region</th>
                    <th style="text-align:left;padding:0.35rem 0;color:var(--muted);font-weight:600;">Channel / Platform</th>
                </tr></thead>
                <tbody>{get_broadcaster_table_compact(data['league_slug'])}</tbody>
            </table>
        </div>

        <!-- ── MATCH PREVIEW ─────────────────────────────────────────────── -->
        <div style="background:var(--panel);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:1.25rem;margin-bottom:1.5rem;">
            <h2 style="color:var(--accent);font-size:1rem;margin-bottom:0.75rem;">Match Preview</h2>
            <p style="color:var(--muted);font-size:0.86rem;line-height:1.7;">{data.get('preview', f"Stay tuned for the latest updates on this {data['league']} clash.")[:350]}</p>
            <p style="margin-top:0.75rem;"><a href="/detail?slug={match_slug}" style="color:var(--accent);font-size:0.84rem;font-weight:600;">Full preview &amp; analysis &rarr;</a></p>
        </div>

        <div class="live-disclaimer">
            <strong>Disclaimer:</strong> Foot Holics does not host any streaming content. All links point to third-party sources found publicly on the internet. We have no control over the availability or content of these streams. For takedown requests contact <a href="mailto:footholicsin@gmail.com" style="color:var(--accent);">footholicsin@gmail.com</a>.
        </div>
    </div>

    <footer class="live-footer">
        <div class="container">
            <nav class="footer-nav">
                <a href="https://footholics.in">Home</a>
                <a href="https://footholics.in/news.html">News</a>
                <a href="https://footholics.in/fixtures.html">Fixtures</a>
                <a href="https://footholics.in/standings.html">Standings</a>
                <a href="https://footholics.in/contact.html">Contact</a>
            </nav>
            <p>&copy; 2026 Foot Holics. All rights reserved.</p>
        </div>
    </footer>

    <div id="cookieBar" class="cookie-bar" style="display:none;">
        <span>This site uses cookies. <a href="https://footholics.in/privacy.html" style="color:var(--accent);">Privacy Policy</a></span>
        <button onclick="document.getElementById(\'cookieBar\').style.display=\'none\';localStorage.setItem(\'lhCookieOk\',\'1\');">OK</button>
    </div>

    <script>
    (function () {{
        // ── Live badge ───────────────────────────────────────────────────
        var kickoffIST = new Date('{data['date']}T{time_24h}:00+05:30');
        function checkLive() {{
            var now = new Date();
            var diff = (now - kickoffIST) / 60000;
            var badge = document.getElementById('liveBadge');
            if (!badge) return;
            if (diff >= -15 && diff <= 120) badge.style.display = 'inline-flex';
            else badge.style.display = 'none';
        }}
        checkLive();
        setInterval(checkLive, 60000);

        // ── Live score widget ────────────────────────────────────────────
        var scoreSlug = window.location.pathname.replace(/^\//, '').replace(/\/$/, '');
        if (scoreSlug) {{
            function fetchScore() {{
                fetch('https://footholics.in/api/match-info?slug=' + encodeURIComponent(scoreSlug))
                    .then(function(r) {{ return r.ok ? r.json() : null; }})
                    .then(function(info) {{
                        if (!info || !info.fixtureId) return null;
                        return fetch('https://footholics.in/api/match-live?id=' + info.fixtureId)
                            .then(function(r) {{ return r.ok ? r.json() : null; }});
                    }})
                    .then(function(d) {{
                        if (!d || !d.fixture) return;
                        var gs = d.fixture.goals;
                        var fs = d.fixture.fixture.status;
                        renderMatchData(d);
                        if (fs.short === 'NS' || fs.short === 'TBD') return;
                        var widget = document.getElementById('liveScoreWidget');
                        var statusEl = document.getElementById('liveScoreStatus');
                        var scoreEl = document.getElementById('liveScoreValue');
                        if (!widget) return;
                        widget.style.display = 'block';
                        scoreEl.textContent = (gs.home !== null ? gs.home : 0) + ' \u2013 ' + (gs.away !== null ? gs.away : 0);
                        if (fs.short === 'FT' || fs.short === 'AET' || fs.short === 'PEN') {{
                            statusEl.innerHTML = '<span style="color:var(--muted)">Full Time</span>';
                        }} else if (fs.short === 'HT') {{
                            statusEl.innerHTML = '<span style="color:var(--accent)">Half Time</span>';
                        }} else {{
                            var min = fs.elapsed ? fs.elapsed + "\'" : '';
                            statusEl.innerHTML = '<span style="display:inline-flex;align-items:center;gap:5px;color:#f87171"><span style="width:7px;height:7px;background:#f87171;border-radius:50%;display:inline-block;animation:live-pulse 1.3s ease-in-out infinite"></span>LIVE ' + min + '</span>';
                        }}
                    }})
                    .catch(function() {{}});
            }}
            fetchScore();
            setInterval(fetchScore, 10 * 60 * 1000); // refresh every 10 min
        }}

        if (!localStorage.getItem('lhCookieOk')) {{
            document.getElementById('cookieBar').style.display = 'flex';
        }}
    }})();
    </script>
</body>
</html>"""



def list_match_files() -> list:
    """List all matches from events.json (matches live on live subdomain only)."""
    root_dir = get_project_root()
    events_path = os.path.join(root_dir, "data", "events.json")
    if not os.path.exists(events_path):
        return []
    try:
        with open(events_path, "r", encoding="utf-8") as f:
            events = json.load(f)
        return [
            f"{e['slug']}.html"
            for e in sorted(events, key=lambda x: x.get("date", ""), reverse=True)
            if "slug" in e
        ]
    except Exception:
        return []


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
    creds_set = bool(context.user_data.get('git_username') and context.user_data.get('git_token'))
    creds_label = "🔑 Git: ✅ ready" if creds_set else "🔑 Git: ❌ set credentials"
    pending_push = context.user_data.get('pending_push')

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
            InlineKeyboardButton("✍️ Publish Article", callback_data="menu_article"),
            InlineKeyboardButton("✏️ Edit Article", callback_data="menu_edit_article"),
        ],
        [
            InlineKeyboardButton("🗑️ Delete Article", callback_data="menu_delete_article"),
        ],
        [
            InlineKeyboardButton(creds_label, callback_data="menu_git_creds"),
        ],
    ]
    if pending_push:
        keyboard.append([InlineKeyboardButton("🔄 Retry Last Push", callback_data="menu_retry_push")])
    if creds_set:
        keyboard.append([InlineKeyboardButton("📤 Force Push (sync unpushed commits)", callback_data="menu_force_push")])
    keyboard.append([InlineKeyboardButton("❌ Exit", callback_data="menu_exit")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    creds_status = "✅ Git credentials set" if creds_set else "❌ Git credentials not set — push will fail"
    pending_note = f"\n⚠️ *Last push failed — tap 🔄 Retry Last Push*" if pending_push else ""
    message_text = f"""
🤖 **Foot Holics Match Manager**

Welcome! Choose an operation:

➕ **Add New Match** - Create a new match page
📋 **List Matches** - View all match files
✏️ **Update Match** - Edit existing match
🗑️ **Delete Match** - Remove a match (auto cleanup!)
🎨 **Generate Card** - Create match card HTML
📊 **Match Stats** - View statistics
✍️ **Publish Article** - Write and publish an editorial
✏️ **Edit Article** - Edit a published article
🗑️ **Delete Article** - Remove a published article
🔑 **Git Credentials** - {creds_status}
❌ **Exit** - Close the bot
{pending_note}
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

    elif action == "article":
        await query.edit_message_text(
            "✍️ *Publish Article*\n\n"
            "Let's write a new editorial article.\n\n"
            "Step 1 of 5: Send me the *article title*.\n\n"
            "Example: `Top Premier League Signings of the Summer`\n\n"
            "_Type /cancel to go back_",
            parse_mode="Markdown"
        )
        return ARTICLE_TITLE

    elif action == "edit_article":
        return await edit_article_start(update, context)

    elif action == "delete_article":
        return await delete_article_start(update, context)

    elif action == "retry_push":
        pending = context.user_data.get('pending_push')
        if not pending:
            await query.edit_message_text("✅ No pending push — everything is already live.")
            await show_main_menu(update, context, edit_message=False)
            return MAIN_MENU

        git_user = context.user_data.get('git_username', '')
        git_token = context.user_data.get('git_token', '')
        await query.edit_message_text("🔄 Retrying push...")

        results = []
        for job in pending:
            ok, status = await asyncio.to_thread(git_auto_push, job['path'], job['msg'], git_user, git_token)
            label = "foot-holics-live" if "live" in job['path'] else "foot-holics"
            results.append((label, ok, status, job['path'], job['msg']))

        display = push_summary(*[(label, ok, status) for label, ok, status, _, _ in results])
        all_ok = all(ok for _, ok, _, _, _ in results)

        if all_ok:
            context.user_data.pop('pending_push', None)
            outcome = "🚀 All pushed! Live in ~60 seconds."
        else:
            # keep only the ones still failing
            context.user_data['pending_push'] = [
                {'path': path, 'msg': msg}
                for _, ok, _, path, msg in results if not ok
            ]
            outcome = "⚠️ Some repos still failed. Update credentials and tap Retry again."

        try:
            await query.edit_message_text(
                f"*Retry Push Result*\n\n{display}\n\n{outcome}",
                parse_mode="Markdown"
            )
        except Exception:
            await query.edit_message_text(
                f"Retry Push Result\n\n{display}\n\n{outcome}".replace("*", "").replace("`", "").replace("_", "")
            )
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    elif action == "force_push":
        git_user = context.user_data.get('git_username', '')
        git_token = context.user_data.get('git_token', '')
        await query.edit_message_text("📤 Pushing any unpushed commits...")

        main_root = get_project_root()
        live_root = main_root.replace("foot-holics", "foot-holics-live").replace("foot-holics-bot", "").rstrip("/\\")
        # Use git pull+push directly without add/commit
        results = []
        for repo_path, label in [(main_root, "foot-holics"), (live_root, "foot-holics-live")]:
            ok, status = await asyncio.to_thread(git_auto_push, repo_path, "sync", git_user, git_token)
            results.append((label, ok, status))

        display = push_summary(*results)
        all_ok = all(ok for _, ok, _ in results)
        outcome = "🚀 All synced! Live in ~60 seconds." if all_ok else "⚠️ Some repos failed."
        try:
            await query.edit_message_text(
                f"*Force Push Result*\n\n{display}\n\n{outcome}",
                parse_mode="Markdown"
            )
        except Exception:
            await query.edit_message_text(
                f"Force Push Result\n\n{display}\n\n{outcome}".replace("*", "").replace("`", "").replace("_", "")
            )
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    elif action == "git_creds":
        creds_set = bool(context.user_data.get('git_username') and context.user_data.get('git_token'))
        if creds_set:
            current_user = context.user_data.get('git_username', '')
            keyboard = [
                [InlineKeyboardButton("✏️ Change Credentials", callback_data="menu_git_creds_update")],
                [InlineKeyboardButton("🗑️ Clear Credentials", callback_data="menu_git_creds_clear")],
                [InlineKeyboardButton("« Back", callback_data="menu_back")],
            ]
            await query.edit_message_text(
                f"🔑 *Git Credentials*\n\n"
                f"✅ Currently set for: `{current_user}`\n\n"
                f"What would you like to do?",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return MAIN_MENU
        else:
            await query.edit_message_text(
                f"🔑 *Set Git Credentials*\n\n"
                f"Send your GitHub username and Personal Access Token in this format:\n\n"
                f"`username:ghp_yourtoken`\n\n"
                f"⚠️ *Credentials are stored only in memory — cleared when bot restarts.*\n"
                f"⚠️ *Delete your message after sending for extra safety.*\n\n"
                f"_Type /cancel to go back_",
                parse_mode="Markdown"
            )
            return SET_GIT_CREDS

    elif action == "git_creds_update":
        await query.edit_message_text(
            f"🔑 *Change Git Credentials*\n\n"
            f"Send your new GitHub username and Personal Access Token:\n\n"
            f"`username:ghp_yourtoken`\n\n"
            f"⚠️ *Delete your message after sending for extra safety.*\n\n"
            f"_Type /cancel to go back_",
            parse_mode="Markdown"
        )
        return SET_GIT_CREDS

    elif action == "git_creds_clear":
        context.user_data.pop('git_username', None)
        context.user_data.pop('git_token', None)
        await query.edit_message_text(
            "🗑️ *Git credentials cleared.*\n\n"
            "All pushes will fail until you set them again.",
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


async def receive_git_creds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive username:token, store in RAM only, try to delete the message."""
    text = update.message.text.strip()
    username, sep, token = text.partition(":")
    if not sep or not username or not token:
        await update.message.reply_text(
            "❌ Wrong format. Send as `username:token` (colon between them).",
            parse_mode="Markdown"
        )
        return SET_GIT_CREDS

    context.user_data['git_username'] = username.strip()
    context.user_data['git_token'] = token.strip()

    # Try to delete the message containing the credentials
    try:
        await update.message.delete()
    except Exception:
        pass  # Can't delete — user should do it manually

    await update.message.reply_text(
        "✅ *Git credentials saved* (in memory only — not on disk).\n\n"
        "They will be used for all git pushes until the bot restarts.\n"
        "If your message above is still visible, please delete it manually.",
        parse_mode="Markdown"
    )
    await show_main_menu(update, context, edit_message=False)
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

    # Delete main HTML file if it exists (matches now live on live.footholics.in only)
    main_file = os.path.join(root_dir, filename)
    if os.path.exists(main_file):
        try:
            os.remove(main_file)
            deleted_files.append(f"✓ {filename} (main site)")
        except Exception as e:
            failed_operations.append(f"✗ Main file: {str(e)}")

    # Remove from live subdomain
    live_root = get_live_project_root()
    if live_root:
        live_file = os.path.join(live_root, filename)
        if os.path.exists(live_file):
            try:
                os.remove(live_file)
                deleted_files.append("✓ Removed from live.footholics.in")
            except Exception as e:
                failed_operations.append(f"✗ Live file: {str(e)}")

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

    _slug = filename.replace('.html', '')
    await query.edit_message_text(
        f"✅ **Match Deletion Complete!**\n\n"
        f"**Deleted:**\n{deleted_list}{failed_list}\n\n"
        f"⏳ Pushing to GitHub...",
        parse_mode="Markdown"
    )

    commit_msg = f"Remove {_slug}"
    git_user = context.user_data.get('git_username', '')
    git_token = context.user_data.get('git_token', '')
    main_ok, main_status = await asyncio.to_thread(git_auto_push, get_project_root(), commit_msg, git_user, git_token)
    live_root = get_live_project_root()
    live_ok, live_status = await asyncio.to_thread(git_auto_push, live_root, commit_msg, git_user, git_token)

    push_line = push_summary(
        ("foot-holics", main_ok, main_status),
        ("foot-holics-live", live_ok, live_status),
    )
    all_ok = main_ok and live_ok
    set_pending_push(context,
        [(get_project_root(), commit_msg), (live_root, commit_msg)],
        [(main_ok, main_status), (live_ok, live_status)]
    )
    try:
        await query.edit_message_text(
            f"✅ **Match Deletion Complete!**\n\n"
            f"**Deleted:**\n{deleted_list}{failed_list}\n\n"
            f"{push_line}",
            parse_mode="Markdown"
        )
    except Exception:
        await query.edit_message_text(
            f"✅ Match Deletion Complete!\n\n"
            f"Deleted:\n{deleted_list}{failed_list}\n\n"
            f"{push_line}".replace("*", "").replace("`", "").replace("_", "")
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

    # Read current match data from events.json
    root_dir = get_project_root()
    events_path = os.path.join(root_dir, "data", "events.json")
    event = None
    if os.path.exists(events_path):
        with open(events_path, "r", encoding="utf-8") as f:
            events_data = json.load(f)
        fn_no_ext = filename.replace(".html", "")
        for e in events_data:
            if fn_no_ext in e.get("slug", ""):
                event = e
                break

    if not event:
        await query.edit_message_text(
            f"❌ Match not found in events.json: `{filename}`",
            parse_mode="Markdown"
        )
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    # Load current values from event dict
    context.user_data["current_title"] = event.get("title", "")
    context.user_data["current_league"] = event.get("league", "Football")
    context.user_data["current_league_slug"] = event.get("leagueSlug", "others")
    context.user_data["current_date"] = event.get("date", "")
    context.user_data["current_time"] = event.get("time", "")
    context.user_data["current_stadium"] = event.get("stadium", "")
    context.user_data["current_preview"] = event.get("excerpt", "")

    # Decode raw stream URLs from broadcast entries
    stream_links = ["#", "#", "#", "#"]
    from urllib.parse import urlparse as _up, parse_qs as _pq
    for i, bc in enumerate(event.get("broadcast", [])[:4]):
        bc_url = bc.get("url", "#")
        if "player.html?get=" in bc_url:
            _qs = _pq(_up(bc_url).query)
            _enc = _qs.get("get", [""])[0]
            if _enc:
                try:
                    stream_links[i] = base64.b64decode(_enc).decode("utf-8")
                except Exception:
                    pass
        elif bc_url and bc_url != "#":
            stream_links[i] = bc_url
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
        now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M")
        await query.edit_message_text(
            f"📅 **Update Date & Time**\n\n"
            f"Current: `{context.user_data.get('current_date', 'N/A')} at {context.user_data.get('current_time', 'N/A')} IST`\n\n"
            f"Enter new date and time in IST (format: DD-MM-YYYY HH:MM):\n"
            f"Example: `{now_ist}`\n\n"
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
            ist_dt = datetime.strptime(text, "%d-%m-%Y %H:%M")
            utc_dt = ist_dt - timedelta(hours=5, minutes=30)
            context.user_data["current_date"] = ist_dt.strftime("%B %d, %Y")
            context.user_data["current_time"] = ist_dt.strftime("%H:%M")
            context.user_data["current_utc_time"] = utc_dt.strftime("%H:%M")
            context.user_data["current_datetime_obj"] = utc_dt
        except ValueError:
            now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M")
            await update.message.reply_text(
                f"❌ Invalid format! Use: `DD-MM-YYYY HH:MM` (IST)\n\nExample: `{now_ist}`",
                parse_mode="Markdown"
            )
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
        # Update main-site HTML if it exists (legacy; new matches only live on live subdomain)
        if os.path.exists(match_file):
            with open(match_file, "r", encoding="utf-8") as f:
                html_content = f.read()
        else:
            html_content = None

        # Update HTML content (only if main-site file exists)
        if html_content is not None and "current_title" in context.user_data:
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

        if html_content is not None and "current_date" in context.user_data:
            utc_t = context.user_data.get("current_utc_time", context.user_data["current_time"])
            html_content = re.sub(
                r'<span>(.*?) at (.*?) (?:GMT|IST.*?)</span>',
                f'<span>{context.user_data["current_date"]} at {context.user_data["current_time"]} IST ({utc_t} UTC)</span>',
                html_content
            )

        if html_content is not None and "current_league" in context.user_data:
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

        if html_content is not None and "current_stadium" in context.user_data:
            html_content = re.sub(
                r'(<path d="M21 10.*?</svg>\s*<span>).*?(</span>)',
                f'\\1{context.user_data["current_stadium"]}\\2',
                html_content,
                flags=re.DOTALL
            )

        if html_content is not None and "current_preview" in context.user_data:
            html_content = re.sub(
                r'(<h2[^>]*>Match Preview</h2>\s*<p>).*?(</p>)',
                f'\\1{context.user_data["current_preview"]}\\2',
                html_content,
                flags=re.DOTALL
            )

        # Thumbnail update: replace &thumb= in all 4 player hrefs
        if html_content is not None and "current_thumbnail" in context.user_data:
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

        if html_content is not None and "current_stream_links" in context.user_data:
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

        # Write updated HTML (only if main-site file existed)
        if html_content is not None:
            with open(match_file, "w", encoding="utf-8") as f:
                f.write(html_content)
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

        # Regenerate live subdomain page with updated data
        _live_updated = False
        try:
            import datetime as _dt
            import base64 as _b64
            from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs
            _fn_no_ext = filename.replace(".html", "")
            _updated_ev = None
            for _ev in events:
                if _fn_no_ext in _ev.get("slug", ""):
                    _updated_ev = _ev
                    break
            if _updated_ev:
                # Decode raw stream URLs from broadcast entries
                _raw_streams = []
                for _bc in _updated_ev.get("broadcast", []):
                    _bc_url = _bc.get("url", "#")
                    if not _bc_url or _bc_url == "#":
                        _raw_streams.append("#")
                    elif "player.html?get=" in _bc_url:
                        _qs = _parse_qs(_urlparse(_bc_url).query)
                        _enc = _qs.get("get", [""])[0]
                        try:
                            _raw_streams.append(_b64.b64decode(_enc).decode("utf-8"))
                        except Exception:
                            _raw_streams.append("#")
                    else:
                        _raw_streams.append(_bc_url)
                # If stream links were explicitly updated this session, prefer those
                if "current_stream_links" in context.user_data:
                    _raw_streams = list(context.user_data["current_stream_links"])
                _date_str = _updated_ev.get("date", "")
                _time_str = _updated_ev.get("time", "00:00")
                try:
                    _dt_obj = _dt.datetime.strptime(f"{_date_str} {_time_str}", "%Y-%m-%d %H:%M")
                except Exception:
                    _dt_obj = _dt.datetime.now()
                _home = _updated_ev.get("homeTeam", "")
                _away = _updated_ev.get("awayTeam", "")
                _live_data = {
                    "datetime_obj": _dt_obj,
                    "home_team": _home,
                    "away_team": _away,
                    "league": _updated_ev.get("league", "Football"),
                    "league_slug": _updated_ev.get("leagueSlug", "others"),
                    "date": _date_str,
                    "time": _time_str,
                    "stadium": _updated_ev.get("stadium", ""),
                    "match_name": _updated_ev.get("title", f"{_home} vs {_away}"),
                    "thumbnail": _updated_ev.get("poster", ""),
                    "stream_urls": _raw_streams,
                    "image_file": "og-image.jpg",
                    "preview": _updated_ev.get("excerpt", ""),
                }
                _live_html = generate_live_html(_live_data)
                _live_updated = copy_html_to_live(filename, _live_html)
        except Exception as _le:
            logger.warning(f"Could not regenerate live page: {_le}")

        _live_line = "\n• live.footholics.in stream page" if _live_updated else ""
        _title = context.user_data.get('current_title', 'match')
        commit_msg = f"Update {_title}"
        git_user = context.user_data.get('git_username', '')
        git_token = context.user_data.get('git_token', '')
        main_ok, main_status = await asyncio.to_thread(git_auto_push, get_project_root(), commit_msg, git_user, git_token)
        live_root = get_live_project_root()
        if _live_updated and live_root:
            live_ok, live_status = await asyncio.to_thread(git_auto_push, live_root, commit_msg, git_user, git_token)
            push_line = push_summary(
                ("foot-holics", main_ok, main_status),
                ("foot-holics-live", live_ok, live_status),
            )
            all_ok = main_ok and live_ok
            set_pending_push(context,
                [(get_project_root(), commit_msg), (live_root, commit_msg)],
                [(main_ok, main_status), (live_ok, live_status)]
            )
        else:
            push_line = push_summary(("foot-holics", main_ok, main_status))
            all_ok = main_ok
            set_pending_push(context,
                [(get_project_root(), commit_msg)],
                [(main_ok, main_status)]
            )

        success_msg = (
            f"✅ *Match Updated Successfully!*\n\n"
            f"Updated: `{filename}`\n\n"
            f"*Changes saved to:*\n"
            f"• Match HTML file\n"
            f"• data/events.json{_live_line}\n\n"
            f"{push_line}\n\n"
            f"{'🚀 Live in ~60 seconds!' if all_ok else '⚠️ Some pushes failed — check VPS!'}"
        )

        if query:
            try:
                await query.edit_message_text(success_msg, parse_mode="Markdown")
            except Exception:
                await query.edit_message_text(success_msg.replace("*", "").replace("`", "").replace("_", ""))
        else:
            try:
                await update.message.reply_text(success_msg, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(success_msg.replace("*", "").replace("`", "").replace("_", ""))

    except Exception as e:
        error_msg = f"❌ Error updating match: {str(e)}"
        if query:
            await query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)

    await show_main_menu(update, context, edit_message=False)
    _keep = {k: context.user_data[k] for k in ('git_username', 'git_token', 'pending_push') if k in context.user_data}
    context.user_data.clear()
    context.user_data.update(_keep)
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

    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M")
    await update.message.reply_text(
        f"✅ Match: **{text}**\n\n"
        f"📅 **Step 2/7:** Please send the date and time (IST):\n"
        f"`DD-MM-YYYY HH:MM`\n\n"
        f"Example: `{now_ist}`",
        parse_mode="Markdown"
    )
    return DATE_TIME


async def date_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Store date/time (IST input) and show league selection."""
    text = update.message.text.strip()

    # Validate format DD-MM-YYYY HH:MM
    try:
        ist_dt = datetime.strptime(text, "%d-%m-%Y %H:%M")
    except ValueError:
        now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M")
        await update.message.reply_text(
            "❌ Invalid format! Use: `DD-MM-YYYY HH:MM` (IST)\n\n"
            f"Example: `{now_ist}`",
            parse_mode="Markdown"
        )
        return DATE_TIME

    # Convert IST → UTC for ISO date / JSON-LD
    utc_dt = ist_dt - timedelta(hours=5, minutes=30)

    # Check if date is in the past (compare naive IST datetimes)
    if ist_dt < datetime.now(IST).replace(tzinfo=None):
        await update.message.reply_text(
            "⚠️ Warning: This date is in the past. Continue anyway?\n"
            "Send the same date again to confirm, or send a new date."
        )

    context.user_data["date"] = ist_dt.strftime("%Y-%m-%d")   # filename slug (YYYY-MM-DD)
    context.user_data["time"] = ist_dt.strftime("%H:%M")        # IST display time
    context.user_data["utc_time"] = utc_dt.strftime("%H:%M")   # UTC display time
    context.user_data["datetime_obj"] = utc_dt                  # UTC for ISO date / JSON-LD

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
        f"✅ Date & Time: **{text} IST** ({context.user_data['utc_time']} UTC)\n\n"
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

    # Generate suggested image filename
    home_slug = slugify(context.user_data["home_team"])
    away_slug = slugify(context.user_data["away_team"])
    date_slug = context.user_data["date"]
    suggested_name = f"{date_slug}-{home_slug}-vs-{away_slug}-poster.jpg"

    context.user_data["suggested_image"] = suggested_name

    stream_count = len(context.user_data["stream_urls"])

    date_slug = context.user_data["date"]
    home_slug_preview = slugify(context.user_data["home_team"])
    away_slug_preview = slugify(context.user_data["away_team"])
    preview_name = f"{date_slug}-{home_slug_preview}-vs-{away_slug_preview}-poster"

    await update.message.reply_text(
        f"✅ {stream_count} stream URL(s) saved!\n\n"
        f"🖼️ **Step 7/7:** Match Poster Image\n\n"
        f"Send me the poster image (JPG/PNG/WebP, 1920×1080px recommended).\n"
        f"You can send it as a **photo** or as a **file** (file = original quality, no compression).\n\n"
        f"Will be saved as: `assets/img/{preview_name}.<ext>`\n"
        f"_(date is included so same teams playing again won't clash)_\n\n"
        f"Or type `skip` to use the default thumbnail.",
        parse_mode="Markdown"
    )
    return POSTER_IMAGE


async def poster_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive match poster image (photo or document) or skip, then generate all code."""
    # Base filename without extension (date already included → no clashes for same teams)
    image_base = os.path.splitext(context.user_data["suggested_image"])[0]
    image_file = context.user_data["suggested_image"]  # fallback with .jpg
    poster_saved = False

    # Determine whether a photo or document image was sent
    file_id = None
    if update.message.photo:
        # Telegram compresses photos → always JPEG
        file_id = update.message.photo[-1].file_id
    elif update.message.document and (update.message.document.mime_type or "").startswith("image/"):
        # Original-quality file (PNG, WebP, JPG, etc.)
        file_id = update.message.document.file_id

    if file_id:
        try:
            tg_file = await context.bot.get_file(file_id)

            # Auto-detect extension from Telegram's file_path
            _, ext = os.path.splitext(tg_file.file_path)
            ext = ext.lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
                ext = '.jpg'  # safe fallback

            image_file = image_base + ext

            project_root = get_project_root()
            img_dir = os.path.join(project_root, "assets", "img")
            os.makedirs(img_dir, exist_ok=True)
            save_path = os.path.join(img_dir, image_file)
            await tg_file.download_to_drive(save_path)
            poster_saved = True
            await update.message.reply_text(
                f"✅ Poster saved as `assets/img/{image_file}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(
                f"⚠️ Could not save poster image: {e}\nUsing default thumbnail instead."
            )
            image_file = "default-player-thumb.jpg"
    else:
        # Text message — "skip" or anything else
        image_file = "default-player-thumb.jpg"
        await update.message.reply_text("⏭️ Using default thumbnail.")

    context.user_data["image_file"] = image_file
    context.user_data["poster_saved"] = poster_saved

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

        html_filename = f"{filename_base}.html"

        # 1. Add entry to events.json (bot's match registry)
        if add_to_events_json(json_code):
            integration_results.append("✅ Added to data/events.json")
        else:
            integration_results.append("⚠️ Could not add to events.json")

        # 2. Generate and copy live subdomain page (matches live on live.footholics.in only)
        live_html_code = generate_live_html(context.user_data)
        if copy_html_to_live(html_filename, live_html_code):
            integration_results.append("✅ Live page copied to foot-holics-live/")
        else:
            integration_results.append("⚠️ Could not copy live page (foot-holics-live/ not found)")

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
    # Thumbnail: use explicit thumb from data, else the site-wide default image
    thumb_src = data.get("thumbnail", "") or "assets/img/default-player-thumb.jpg"
    encoded_thumb = quote(thumb_src)

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
            player_url = f"https://live.footholics.in/player.html?{params}"
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
    html = html.replace("{{UTC_TIME}}", data.get("utc_time", date_obj.strftime("%H:%M")))
    html = html.replace("{{LEAGUE}}", data["league"])
    html = html.replace("{{LEAGUE_SLUG}}", data["league_slug"])
    html = html.replace("{{STADIUM}}", data["stadium"])
    html = html.replace("{{PREVIEW}}", data["preview"])
    html = html.replace("{{IMAGE_FILE}}", data["image_file"])
    html = html.replace("{{FILE_NAME}}", filename)
    match_slug = filename.replace(".html", "")
    html = html.replace("{{MATCH_SLUG}}", match_slug)
    html = html.replace("{{SLUG}}", f"{home_slug}-vs-{away_slug}")
    html = html.replace("{{MATCH_NAME_ENCODED}}", match_name_encoded)
    html = html.replace("{{BROADCAST_ROWS}}", get_broadcaster_table(data["league_slug"]))

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

    # Resolve logo URLs as absolute paths (so detail page can use them directly)
    home_logo_rel = find_team_logo(data["home_team"], data["league_slug"])
    away_logo_rel = find_team_logo(data["away_team"], data["league_slug"])
    home_logo_abs = f"https://footholics.in/{home_logo_rel.lstrip('/')}" if home_logo_rel else ""
    away_logo_abs = f"https://footholics.in/{away_logo_rel.lstrip('/')}" if away_logo_rel else ""

    event_data = {
        "id": generate_event_id(),
        "date": data["date"],
        "time": data["time"],
        "slug": slug,
        "title": data["match_name"],
        "homeTeam": data["home_team"],
        "awayTeam": data["away_team"],
        "homeLogo": home_logo_abs,
        "awayLogo": away_logo_abs,
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

    # Send HTML file (live subdomain backup)
    html_bytes = BytesIO(html_code.encode('utf-8'))
    html_bytes.name = f"{filename_base}.html"
    await update.message.reply_document(
        document=html_bytes,
        filename=f"{filename_base}.html",
        caption="📄 **Live Page HTML** (Backup - Already written to foot-holics-live/)"
    )

    # Send JSON entry (as backup)
    json_bytes = BytesIO(json_code.encode('utf-8'))
    json_bytes.name = f"{filename_base}.json"
    await update.message.reply_document(
        document=json_bytes,
        filename=f"{filename_base}.json",
        caption="📊 **JSON Entry** (Backup - Already added to events.json!)"
    )

    # Build push instructions
    poster_saved = context.user_data.get("poster_saved", False)
    image_file = context.user_data.get("image_file", "default-player-thumb.jpg")
    match_name = context.user_data.get("match_name", "match")
    home_slug = slugify(context.user_data.get("home_team", "home"))
    away_slug = slugify(context.user_data.get("away_team", "away"))
    date_slug = context.user_data.get("date", "")
    match_slug_str = f"{date_slug}-{home_slug}-vs-{away_slug}"
    detail_url     = f"https://live.footholics.in/detail?slug={match_slug_str}"
    streams_url    = f"https://live.footholics.in/{match_slug_str}"

    if poster_saved:
        poster_note = f"• Poster saved to `assets/img/{image_file}`"
    else:
        poster_note = f"• Using default thumbnail"

    await update.message.reply_text("🚀 Pushing to GitHub...", parse_mode="Markdown")
    commit_msg = f"Add {match_name}"
    git_user = context.user_data.get('git_username', '')
    git_token = context.user_data.get('git_token', '')
    main_ok, main_status = await asyncio.to_thread(git_auto_push, get_project_root(), commit_msg, git_user, git_token)
    live_root = get_live_project_root()
    live_ok, live_status = await asyncio.to_thread(git_auto_push, live_root, commit_msg, git_user, git_token)

    push_line = push_summary(
        ("foot-holics", main_ok, main_status),
        ("foot-holics-live", live_ok, live_status),
    )
    all_ok = main_ok and live_ok
    set_pending_push(context,
        [(get_project_root(), commit_msg), (live_root, commit_msg)],
        [(main_ok, main_status), (live_ok, live_status)]
    )
    live_note = "🚀 Live in ~60 seconds!" if all_ok else "⚠️ Some pushes failed — check above."

    instructions = (
        f"🎉 *MATCH CREATED!*\n\n"
        f"✅ *Done automatically:*\n"
        f"• Stream links page → `foot-holics-live/`\n"
        f"• Entry added to `data/events.json`\n"
        f"{poster_note}\n\n"
        f"🔗 *Share this card link with users:*\n"
        f"`{detail_url}`\n\n"
        f"📄 *Direct stream page (for reference):*\n"
        f"`{streams_url}`\n\n"
        f"{push_line}\n\n"
        f"{live_note}"
    )

    try:
        await update.message.reply_text(instructions, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(instructions.replace("*", "").replace("`", "").replace("_", ""))


def get_inline_event_template() -> str:
    """Return inline HTML template."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="index, follow">
    <meta name="description" content="{{MATCH_NAME}} \u2014 {{LEAGUE}} match preview, official broadcast channels, live score and kickoff time on {{DATE}} at {{STADIUM}}.">
    <meta name="keywords" content="{{MATCH_NAME}}, {{HOME_TEAM}} vs {{AWAY_TEAM}}, {{LEAGUE}} preview, football match, kickoff time, {{STADIUM}}, {{HOME_TEAM}}, {{AWAY_TEAM}}, football today">

    <!-- Open Graph -->
    <meta property="og:title" content="{{MATCH_NAME}} \u2014 {{LEAGUE}} Match Preview">
    <meta property="og:description" content="{{LEAGUE}} match preview: {{HOME_TEAM}} vs {{AWAY_TEAM}} on {{DATE}}. Kickoff time, broadcast info and live score.">
    <meta property="og:type" content="article">
    <meta property="og:image" content="assets/img/{{IMAGE_FILE}}">

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{{MATCH_NAME}} \u2014 {{LEAGUE}} Match Preview">
    <meta name="twitter:description" content="{{LEAGUE}} preview: {{HOME_TEAM}} vs {{AWAY_TEAM}} on {{DATE}}. Kickoff time and broadcast info.">

    <title>{{MATCH_NAME}} \u2014 {{LEAGUE}} Match Preview | Foot Holics</title>

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
      "description": "{{MATCH_NAME}} \u2014 {{LEAGUE}} match preview on Foot Holics. Kickoff time, official broadcast channels, live score and editorial coverage.",
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
      "isAccessibleForFree": true,
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
      "description": "Premium football media platform covering match previews, standings, fixtures and the latest football news from around the world",
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
                    <a href="news.html">News</a>
                    <a href="articles/index.html">Articles</a>
                    <a href="standings.html">Standings</a>
                    <a href="fixtures.html">Fixtures</a>
                    <a href="about.html">About</a>
                    <a href="contact.html">Contact</a>
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
                        <span>{{DATE}} at {{TIME}} IST ({{UTC_TIME}} UTC)</span>
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

        <!-- Live Score Widget -->
        <div id="liveScoreWidget"
             class="live-score-widget"
             data-home="{{HOME_TEAM}}"
             data-away="{{AWAY_TEAM}}"
             data-league="{{LEAGUE_SLUG}}"
             data-date="{{DATE_ISO}}"
             data-home-logo="{{HOME_TEAM_LOGO}}"
             data-away-logo="{{AWAY_TEAM_LOGO}}">
            <div class="ls-status-bar upcoming-status">
                <span>&#9200;</span> <span>Loading score...</span>
            </div>
            <div class="ls-scoreboard">
                <div class="ls-team-col">
                    <span class="ls-team-name">{{HOME_TEAM}}</span>
                </div>
                <div class="ls-score-col">
                    <div class="ls-countdown" id="lsCountdown">--:--:--</div>
                </div>
                <div class="ls-team-col">
                    <span class="ls-team-name">{{AWAY_TEAM}}</span>
                </div>
            </div>
            <p class="ls-powered">Live data via ESPN</p>
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
                    {{BROADCAST_ROWS}}
                </tbody>
            </table>
        </section>

        <!-- Watch Live CTA -->
        <section class="glass-card mb-4" style="text-align: center;">
            <h2 style="color: var(--accent); margin-bottom: 1rem;">Watch This Match Live</h2>
            <p class="text-muted" style="margin-bottom: 1.5rem; font-size: 0.95rem;">
                Multiple live stream links are available for this match. Click below to access them.
            </p>
            <a href="https://live.footholics.in/{{MATCH_SLUG}}"
               class="btn btn-primary"
               style="font-size: 1.1rem; padding: 0.9rem 2.5rem; display: inline-block;"
               target="_blank" rel="noopener noreferrer">
                Watch Live &rarr;
            </a>
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
                    <p>Your premium football destination for news, standings, fixtures and in-depth match coverage from all the leagues you love.</p>
                </div>

                <div class="footer-section">
                    <h4>Quick Links</h4>
                    <ul class="footer-links">
                        <li><a href="index.html">Home</a></li>
                        <li><a href="news.html">Football News</a></li>
                        <li><a href="articles/index.html">Articles</a></li>
                        <li><a href="standings.html">Standings</a></li>
                        <li><a href="fixtures.html">Fixtures</a></li>
                        <li><a href="contact.html">Contact</a></li>
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

    <!-- JavaScript -->
    <script src="assets/js/main.js" defer></script>
    <script src="assets/js/livescore-widget.js" defer></script>

    <!-- Live Score Widget Script (inline — handles all logic) -->
    <script>
    (function () {
        'use strict';
        // If the external livescore-widget.js already ran, skip.
        if (window.__lsWidgetLoaded) return;
        var widget = document.getElementById('liveScoreWidget');
        if (!widget) return;

        var homeTeam  = widget.dataset.home;
        var awayTeam  = widget.dataset.away;
        var leagueSlug = widget.dataset.league;
        var matchDate = widget.dataset.date;   // ISO: "2026-04-04T19:00:00Z"
        var homeLogo  = widget.dataset.homeLogo;
        var awayLogo  = widget.dataset.awayLogo;

        // Extract date part only (YYYY-MM-DD)
        var dateOnly = matchDate ? matchDate.slice(0, 10) : '';

        // Slug → ESPN code for the API
        var SLUG_MAP = {
            'premier-league':   'eng.1',
            'laliga':           'esp.1',
            'bundesliga':       'ger.1',
            'serie-a':          'ita.1',
            'ligue-1':          'fra.1',
            'champions-league': 'UEFA.CHAMPIONS',
        };
        var espnLeague = SLUG_MAP[leagueSlug] || leagueSlug;

        var apiUrl = '/api/livescore?home=' + encodeURIComponent(homeTeam)
                   + '&away=' + encodeURIComponent(awayTeam)
                   + (espnLeague ? '&league=' + encodeURIComponent(espnLeague) : '')
                   + (dateOnly ? '&date=' + encodeURIComponent(dateOnly) : '');

        var countdownInterval = null;
        var pollInterval = null;
        var kickoffTime = matchDate ? new Date(matchDate) : null;

        function escHtml(s) {
            if (!s) return '';
            return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
        }

        function logoImg(src, name) {
            if (!src || src === '#' || src === '') return '';
            return '<img src="' + escHtml(src) + '" alt="' + escHtml(name) + '" class="ls-team-logo" onerror="this.style.display=\'none\'">';
        }

        function formatCountdown(ms) {
            if (ms <= 0) return '00:00:00';
            var s = Math.floor(ms / 1000);
            var h = Math.floor(s / 3600);
            var m = Math.floor((s % 3600) / 60);
            var sec = s % 60;
            var pad = function(n){ return n < 10 ? '0' + n : String(n); };
            return pad(h) + ':' + pad(m) + ':' + pad(sec);
        }

        function renderPrematch() {
            if (countdownInterval) clearInterval(countdownInterval);
            var now = Date.now();
            var diff = kickoffTime ? kickoffTime.getTime() - now : 0;
            var timeStr = kickoffTime ? kickoffTime.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC' : '';

            widget.classList.remove('is-live', 'is-finished');

            function tick() {
                var remaining = kickoffTime ? kickoffTime.getTime() - Date.now() : 0;
                var cdEl = widget.querySelector('#lsCountdown');
                if (cdEl) cdEl.textContent = remaining > 0 ? formatCountdown(remaining) : '00:00:00';
            }
            tick();
            countdownInterval = setInterval(tick, 1000);

            widget.innerHTML = '<div class="ls-status-bar upcoming-status"><span>&#9200;</span> <span>UPCOMING</span></div>'
                + '<div class="ls-scoreboard">'
                    + '<div class="ls-team-col">' + logoImg(homeLogo, homeTeam) + '<span class="ls-team-name">' + escHtml(homeTeam) + '</span></div>'
                    + '<div class="ls-score-col"><div class="ls-countdown" id="lsCountdown">--:--:--</div>'
                        + (timeStr ? '<div class="ls-kickoff-time">Kick off ' + escHtml(timeStr) + '</div>' : '') + '</div>'
                    + '<div class="ls-team-col">' + logoImg(awayLogo, awayTeam) + '<span class="ls-team-name">' + escHtml(awayTeam) + '</span></div>'
                + '</div>'
                + '<p class="ls-powered">Live data via ESPN</p>';

            // Restart countdown in the new DOM
            var cdEl = widget.querySelector('#lsCountdown');
            if (cdEl && kickoffTime) {
                countdownInterval = setInterval(function() {
                    var remaining = kickoffTime.getTime() - Date.now();
                    cdEl.textContent = remaining > 0 ? formatCountdown(remaining) : '00:00:00';
                }, 1000);
            }
        }

        function renderLive(data) {
            if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
            widget.classList.add('is-live');
            widget.classList.remove('is-finished');

            var homeGoals = data.goalEvents.filter(function(e){ return e.side === 'home'; });
            var awayGoals = data.goalEvents.filter(function(e){ return e.side === 'away'; });

            var homeGoalHtml = homeGoals.map(function(e){
                return '<span class="ls-goal-event"><span class="scorer">&#9917; ' + escHtml(e.scorer) + '</span> <span class="minute">' + escHtml(e.minute) + '</span></span>';
            }).join('');
            var awayGoalHtml = awayGoals.map(function(e){
                return '<span class="ls-goal-event"><span class="scorer">&#9917; ' + escHtml(e.scorer) + '</span> <span class="minute">' + escHtml(e.minute) + '</span></span>';
            }).join('');

            widget.innerHTML = '<div class="ls-status-bar live-status"><span class="live-dot" style="width:8px;height:8px;background:#ef4444;border-radius:50%;display:inline-block;animation:blink 1.5s infinite;"></span> <span>LIVE &bull; ' + escHtml(data.minute || data.detail) + '</span></div>'
                + '<div class="ls-scoreboard">'
                    + '<div class="ls-team-col">' + logoImg(homeLogo, homeTeam) + '<span class="ls-team-name">' + escHtml(data.homeTeam || homeTeam) + '</span></div>'
                    + '<div class="ls-score-col"><div class="ls-score-display">'
                        + '<span class="ls-score">' + (data.homeScore !== null ? escHtml(String(data.homeScore)) : '-') + '</span>'
                        + '<span class="ls-score-sep">:</span>'
                        + '<span class="ls-score">' + (data.awayScore !== null ? escHtml(String(data.awayScore)) : '-') + '</span>'
                    + '</div></div>'
                    + '<div class="ls-team-col">' + logoImg(awayLogo, awayTeam) + '<span class="ls-team-name">' + escHtml(data.awayTeam || awayTeam) + '</span></div>'
                + '</div>'
                + (homeGoalHtml || awayGoalHtml ? '<div class="ls-events"><div class="ls-events-side home">' + homeGoalHtml + '</div><div class="ls-events-side away">' + awayGoalHtml + '</div></div>' : '')
                + '<p class="ls-powered">Live data via ESPN &bull; updates every 30s</p>';
        }

        function renderFinished(data) {
            if (countdownInterval) { clearInterval(countdownInterval); countdownInterval = null; }
            if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
            widget.classList.remove('is-live');
            widget.classList.add('is-finished');

            var homeGoals = data.goalEvents.filter(function(e){ return e.side === 'home'; });
            var awayGoals = data.goalEvents.filter(function(e){ return e.side === 'away'; });
            var homeGoalHtml = homeGoals.map(function(e){
                return '<span class="ls-goal-event"><span class="scorer">&#9917; ' + escHtml(e.scorer) + '</span> <span class="minute">' + escHtml(e.minute) + '</span></span>';
            }).join('');
            var awayGoalHtml = awayGoals.map(function(e){
                return '<span class="ls-goal-event"><span class="scorer">&#9917; ' + escHtml(e.scorer) + '</span> <span class="minute">' + escHtml(e.minute) + '</span></span>';
            }).join('');

            widget.innerHTML = '<div class="ls-status-bar finished-status"><span>&#10003;</span> <span>FULL TIME</span></div>'
                + '<div class="ls-scoreboard">'
                    + '<div class="ls-team-col">' + logoImg(homeLogo, homeTeam) + '<span class="ls-team-name">' + escHtml(data.homeTeam || homeTeam) + '</span></div>'
                    + '<div class="ls-score-col"><div class="ls-score-display">'
                        + '<span class="ls-score">' + (data.homeScore !== null ? escHtml(String(data.homeScore)) : '-') + '</span>'
                        + '<span class="ls-score-sep">:</span>'
                        + '<span class="ls-score">' + (data.awayScore !== null ? escHtml(String(data.awayScore)) : '-') + '</span>'
                    + '</div></div>'
                    + '<div class="ls-team-col">' + logoImg(awayLogo, awayTeam) + '<span class="ls-team-name">' + escHtml(data.awayTeam || awayTeam) + '</span></div>'
                + '</div>'
                + (homeGoalHtml || awayGoalHtml ? '<div class="ls-events"><div class="ls-events-side home">' + homeGoalHtml + '</div><div class="ls-events-side away">' + awayGoalHtml + '</div></div>' : '')
                + '<p class="ls-powered">Final score via ESPN</p>';
        }

        async function fetchScore() {
            try {
                var res = await fetch(apiUrl);
                if (!res.ok) throw new Error();
                var data = await res.json();
                if (!data.found) {
                    renderPrematch();
                    return;
                }
                if (data.isCompleted || data.state === 'post') {
                    renderFinished(data);
                } else if (data.isLive || data.state === 'in') {
                    renderLive(data);
                } else {
                    renderPrematch();
                }
            } catch (e) {
                renderPrematch();
            }
        }

        // Initial fetch
        fetchScore();

        // Poll every 30s during potential match window
        // (2h window around kickoff)
        if (kickoffTime) {
            var windowStart = kickoffTime.getTime() - 5 * 60 * 1000;
            var windowEnd   = kickoffTime.getTime() + 130 * 60 * 1000;
            var now = Date.now();
            if (now >= windowStart && now <= windowEnd) {
                pollInterval = setInterval(fetchScore, 30000);
            }
        }
    })();
    </script>
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
                                <span>{{TIME}} IST</span>
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
    _keep = {k: context.user_data[k] for k in ('git_username', 'git_token', 'pending_push') if k in context.user_data}
    context.user_data.clear()
    context.user_data.update(_keep)
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


# ── Article Publishing ────────────────────────────────────────────────────────

def generate_article_html(title: str, slug: str, category: str, excerpt: str, content: str, date: str, cover_image: str = None) -> str:
    """Generate a full editorial article HTML page."""
    try:
        date_display = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        date_display = date

    # Resolve OG / JSON-LD image
    og_image = cover_image if cover_image else "https://footholics.in/assets/img/og-image.jpg"

    # Convert Markdown-like content to HTML paragraphs / headings / inline images
    # Supports:
    #   ## Heading        → <h2>
    #   ### Heading       → <h3>
    #   ![caption](url)   → <figure><img ...><figcaption>
    #   blank line        → paragraph break
    #   regular text      → <p>
    INLINE_IMG_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')

    html_parts = []
    current_para_lines = []

    def flush_para():
        if current_para_lines:
            html_parts.append(f"                <p>{' '.join(current_para_lines)}</p>")
            current_para_lines.clear()

    for line in content.split("\n"):
        line = line.rstrip()
        if line.startswith("## "):
            flush_para()
            html_parts.append(f"\n                <h2>{_html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            flush_para()
            html_parts.append(f"\n                <h3>{_html.escape(line[4:])}</h3>")
        elif line == "":
            flush_para()
        else:
            # Check for standalone inline image line
            m = INLINE_IMG_RE.fullmatch(line.strip())  # noqa: F821 — re compiled above
            if m:
                flush_para()
                caption = _html.escape(m.group(1))
                url = _html.escape(m.group(2))
                figcap = f"\n                    <figcaption style=\"color:var(--muted);font-size:0.85rem;margin-top:0.5rem;\">{caption}</figcaption>" if caption else ""
                html_parts.append(
                    f"\n                <figure style=\"margin:2rem 0;text-align:center;\">"
                    f"\n                    <img src=\"{url}\" alt=\"{caption}\" style=\"max-width:100%;border-radius:10px;\">"
                    f"{figcap}"
                    f"\n                </figure>"
                )
            else:
                current_para_lines.append(_html.escape(line))
    flush_para()

    html_body = "\n".join(html_parts)

    # Cover image block (rendered after article header, before body)
    cover_html = ""
    if cover_image:
        cover_html = (
            f"\n            <figure style=\"margin:0 0 2rem;\">"
            f"\n                <img src=\"{_html.escape(cover_image)}\" alt=\"{_html.escape(title)}\" "
            f"style=\"width:100%;border-radius:12px;display:block;\">"
            f"\n            </figure>"
        )

    # Partial slug for the related-articles filter (strip date prefix)
    slug_parts = slug.split("-")
    slug_filter = "-".join(slug_parts[3:]) if len(slug_parts) > 3 else slug

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="index, follow">
    <meta name="description" content="{_html.escape(excerpt)}">
    <meta property="og:title" content="{_html.escape(title)} - Foot Holics">
    <meta property="og:description" content="{_html.escape(excerpt[:160])}">
    <meta property="og:type" content="article">
    <meta property="og:image" content="{_html.escape(og_image)}">
    <meta name="twitter:card" content="summary_large_image">
    <title>{_html.escape(title)} | Foot Holics</title>
    <link rel="canonical" href="https://footholics.in/articles/{slug}.html">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Playfair+Display:wght@700&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css" integrity="sha512-DTOQO9RWCH3ppGqcWaEA1BIZOC6xxalwEsw9c2QQeAIftl+Vegovlnee1c9QX4TctnWMn13TZye+giMm8e2LwA==" crossorigin="anonymous" referrerpolicy="no-referrer" />
    <link rel="stylesheet" href="../assets/css/main.css">
    <link rel="icon" type="image/png" href="../assets/img/logos/site/logo.png">
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": "{_html.escape(title)}",
      "datePublished": "{date}",
      "dateModified": "{date}",
      "author": {{ "@type": "Person", "name": "OnixWhite", "url": "https://footholics.in/about.html" }},
      "publisher": {{
        "@type": "Organization",
        "name": "Foot Holics",
        "logo": {{ "@type": "ImageObject", "url": "https://footholics.in/assets/img/logos/site/logo.png" }}
      }},
      "image": "{_html.escape(og_image)}",
      "url": "https://footholics.in/articles/{slug}.html"
    }}
    </script>
    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-8308140971175602"
     crossorigin="anonymous"></script>
</head>
<body>
    <header class="site-header">
        <div class="container">
            <div class="header-inner">
                <a href="../index.html" class="logo">
                    <img src="../assets/img/logos/site/logo.png" alt="Foot Holics Logo" class="logo-icon">
                    <span>Foot Holics</span>
                </a>
                <nav class="primary-nav" id="primaryNav">
                    <a href="../index.html">Home</a>
                    <a href="../news.html">News</a>
                    <a href="index.html" class="active">Articles</a>
                    <a href="../standings.html">Standings</a>
                    <a href="../fixtures.html">Fixtures</a>
                    <a href="../about.html">About</a>
                    <a href="../contact.html">Contact</a>
                </nav>
                <div class="cta-group" id="ctaGroup">
                    <a href="https://chat.whatsapp.com/KG7DBpC0BKv6bFtlzfOr2T" target="_blank" rel="noopener noreferrer" class="btn btn-secondary">WhatsApp</a>
                    <a href="https://t.me/+XyKdBR9chQpjM2I9" target="_blank" rel="noopener noreferrer" class="btn btn-primary">Telegram</a>
                </div>
                <button class="mobile-menu-btn" id="mobileMenuBtn" aria-label="Toggle menu">☰</button>
            </div>
        </div>
    </header>

    <div class="container" style="margin-top: 2rem;">
        <nav class="breadcrumbs" aria-label="Breadcrumb">
            <a href="../index.html">Home</a>
            <span class="breadcrumb-separator">&rsaquo;</span>
            <a href="index.html">Articles</a>
            <span class="breadcrumb-separator">&rsaquo;</span>
            <span>{_html.escape(title[:60])}</span>
        </nav>
    </div>

    <main class="container" style="margin-top: 2rem; max-width: 860px;">
        <article>
            <header style="margin-bottom: 2rem;">
                <div style="display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; margin-bottom: 1rem;">
                    <span class="news-cat-badge">{_html.escape(category)}</span>
                    <span style="color: var(--muted); font-size: 0.85rem;">{date_display}</span>
                    <span style="color: var(--muted); font-size: 0.85rem;">By OnixWhite</span>
                </div>
                <h1 style="font-family: 'Playfair Display', serif; font-size: clamp(1.6rem, 4vw, 2.4rem); line-height: 1.25; margin-bottom: 1.25rem;">{_html.escape(title)}</h1>
                <p style="font-size: 1.1rem; color: var(--muted); line-height: 1.7;">{_html.escape(excerpt)}</p>
            </header>
{cover_html}
            <div class="article-body" style="font-size: 1rem; line-height: 1.8; color: var(--text);">

{html_body}

                <hr style="border: none; border-top: 1px solid var(--glass-border); margin: 2rem 0;">

                <div style="margin: 2.5rem 0 0; padding: 1.5rem; background: var(--glass); border: 1px solid var(--glass-border); border-radius: 12px; display: flex; gap: 1.25rem; align-items: flex-start;">
                    <div style="flex-shrink:0; width:48px; height:48px; border-radius:50%; background:var(--accent); display:flex; align-items:center; justify-content:center;">
                        <i class="fa-solid fa-pen-nib" style="color:#000; font-size:1rem;"></i>
                    </div>
                    <div>
                        <div style="font-weight:700; color:var(--text); margin-bottom:0.2rem;">OnixWhite</div>
                        <div style="font-size:0.78rem; color:var(--accent); margin-bottom:0.5rem; font-weight:600; text-transform:uppercase; letter-spacing:0.04em;">Football Writer &amp; Analyst</div>
                        <p style="font-size:0.88rem; color:var(--muted); line-height:1.65; margin:0;">OnixWhite has covered European football for over eight years, with a focus on the Champions League, La Liga, and the Premier League. He writes regularly on tactics, team dynamics, and the stories that shape a season.</p>
                    </div>
                </div>

                <p style="color: var(--muted); font-size: 0.9rem; margin-top: 1.5rem;">Stay up to date with our <a href="../fixtures.html" style="color: var(--accent);">Fixtures page</a> and live <a href="../standings.html" style="color: var(--accent);">Standings</a>.</p>
            </div>
        </article>

        <section class="more-articles-section">
            <div class="more-articles-header">
                <h2 class="more-articles-title">More Articles</h2>
                <a href="index.html" class="more-articles-view-all">View All &rarr;</a>
            </div>
            <div class="rel-grid" id="relatedArticles">
                <div class="content-loading" style="grid-column:1/-1;">
                    <div class="spinner"></div>
                    <span>Loading...</span>
                </div>
            </div>
        </section>
    </main>

    <footer class="site-footer" style="margin-top: 4rem;">
        <div class="container">
            <div class="footer-content">
                <div class="footer-section">
                    <h4>About Foot Holics</h4>
                    <p>Your premium football destination for news, standings, fixtures and in-depth match coverage from all the leagues you love.</p>
                </div>
                <div class="footer-section">
                    <h4>Quick Links</h4>
                    <ul class="footer-links">
                        <li><a href="../index.html">Home</a></li>
                        <li><a href="../news.html">Football News</a></li>
                        <li><a href="index.html">Articles</a></li>
                        <li><a href="../standings.html">Standings</a></li>
                        <li><a href="../fixtures.html">Fixtures</a></li>
                        <li><a href="../contact.html">Contact</a></li>
                    </ul>
                </div>
                <div class="footer-section">
                    <h4>Legal</h4>
                    <ul class="footer-links">
                        <li><a href="../privacy.html">Privacy Policy</a></li>
                        <li><a href="../terms.html">Terms &amp; Conditions</a></li>
                        <li><a href="../dmca.html">DMCA / Copyright</a></li>
                        <li><a href="../disclaimer.html">Disclaimer</a></li>
                    </ul>
                </div>
                <div class="footer-section">
                    <h4>Connect With Us</h4>
                    <ul class="footer-links">
                        <li><a href="https://chat.whatsapp.com/KG7DBpC0BKv6bFtlzfOr2T" target="_blank" rel="noopener noreferrer"><i class="fa-brands fa-whatsapp" style="margin-right:8px;"></i>WhatsApp Channel</a></li>
                        <li><a href="https://t.me/+XyKdBR9chQpjM2I9" target="_blank" rel="noopener noreferrer"><i class="fa-brands fa-telegram" style="margin-right:8px;"></i>Telegram</a></li>
                    </ul>
                </div>
            </div>
            <div class="footer-bottom">
                <p>&copy; 2026 Foot Holics. All rights reserved.</p>
            </div>
        </div>
    </footer>

    <script src="../assets/js/main.js" defer></script>
    <script>
    (function () {{
        async function loadRelated() {{
            const grid = document.getElementById('relatedArticles');
            if (!grid) return;
            try {{
                const res = await fetch('/api/articles');
                if (!res.ok) throw new Error();
                const all = await res.json();
                const others = all.filter(a => !a.url.includes('{slug_filter}')).slice(0, 3);
                if (!others.length) {{ grid.innerHTML = ''; return; }}
                function esc(s) {{ return s ? s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') : ''; }}
                function catGradient(cat) {{
                  var c = (cat || '').toLowerCase();
                  if (c.includes('la liga')) return 'linear-gradient(135deg,#b83217 0%,#e0633a 100%)';
                  if (c.includes('champions') || c.includes('ucl')) return 'linear-gradient(135deg,#0b1560 0%,#2340c8 100%)';
                  if (c.includes('premier')) return 'linear-gradient(135deg,#2b003a 0%,#5e0fa8 100%)';
                  if (c.includes('bundesliga')) return 'linear-gradient(135deg,#7a0000 0%,#cc2200 100%)';
                  if (c.includes('serie a')) return 'linear-gradient(135deg,#002f70 0%,#0055b3 100%)';
                  if (c.includes('ligue')) return 'linear-gradient(135deg,#002580 0%,#0088d4 100%)';
                  if (c.includes('europa')) return 'linear-gradient(135deg,#b34a00 0%,#e87020 100%)';
                  return 'linear-gradient(135deg,#0a1628 0%,#1c3a54 100%)';
                }}
                grid.innerHTML = others.map(function(a) {{
                  return '<a href="' + esc(a.url) + '" class="rel-card">' +
                    (a.image
                      ? '<div class="rel-card-thumb"><img src="' + esc(a.image) + '" alt="' + esc(a.title) + '" loading="lazy"></div>'
                      : '<div class="rel-card-thumb" style="background:' + catGradient(a.category) + '"><span class="rel-card-thumb-icon">&#x26BD;</span></div>') +
                    '<div class="rel-card-body">' +
                      '<span class="rel-card-badge">' + esc(a.category || 'Football') + '</span>' +
                      '<h3 class="rel-card-title">' + esc(a.title) + '</h3>' +
                      (a.excerpt ? '<p class="rel-card-excerpt">' + esc(a.excerpt) + '</p>' : '') +
                      '<div class="rel-card-footer">' +
                        '<time class="rel-card-date">' + esc(a.date) + '</time>' +
                        '<span class="rel-card-read">Read &#x2192;</span>' +
                      '</div>' +
                    '</div>' +
                  '</a>';
                }}).join('');
            }} catch (e) {{ grid.innerHTML = ''; }}
        }}
        loadRelated();
    }})();
    </script>

</body>
</html>"""


async def article_title_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 1 — collect article title."""
    title = update.message.text.strip()
    if len(title) < 5:
        await update.message.reply_text(
            "❌ Title is too short. Please send a proper article title.",
            parse_mode="Markdown"
        )
        return ARTICLE_TITLE

    context.user_data["art_title"] = title

    keyboard = [
        [InlineKeyboardButton("Premier League", callback_data="art_cat_Premier League"),
         InlineKeyboardButton("Champions League", callback_data="art_cat_Champions League")],
        [InlineKeyboardButton("La Liga", callback_data="art_cat_La Liga"),
         InlineKeyboardButton("Bundesliga", callback_data="art_cat_Bundesliga")],
        [InlineKeyboardButton("Serie A", callback_data="art_cat_Serie A"),
         InlineKeyboardButton("Ligue 1", callback_data="art_cat_Ligue 1")],
        [InlineKeyboardButton("World Football", callback_data="art_cat_World Football"),
         InlineKeyboardButton("Guide", callback_data="art_cat_Guide")],
    ]
    await update.message.reply_text(
        f"✅ Title saved: *{_html.escape(title)}*\n\n"
        "Step 2 of 5: Choose a *category*:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ARTICLE_CATEGORY


async def article_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 2 — collect category via inline button."""
    query = update.callback_query
    await query.answer()
    category = query.data.replace("art_cat_", "")
    context.user_data["art_category"] = category

    await query.edit_message_text(
        f"✅ Category: *{category}*\n\n"
        "Step 3 of 5: Send the *excerpt* (1-2 sentences shown in article cards).\n\n"
        "_Type /cancel to abort_",
        parse_mode="Markdown"
    )
    return ARTICLE_EXCERPT


async def article_excerpt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 3 — collect excerpt."""
    excerpt = update.message.text.strip()
    if len(excerpt) < 10:
        await update.message.reply_text(
            "❌ Excerpt is too short. Write 1-2 sentences summarising the article."
        )
        return ARTICLE_EXCERPT

    context.user_data["art_excerpt"] = excerpt

    await update.message.reply_text(
        "✅ Excerpt saved.\n\n"
        "Step 4 of 5: Send a *cover image* for this article.\n\n"
        "• Send a photo (or send as file for full quality)\n"
        "• Or type `skip` to publish without a cover image\n\n"
        "_Type /cancel to abort_",
        parse_mode="Markdown"
    )
    return ARTICLE_COVER_IMAGE


async def article_cover_image_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 4 — collect optional cover image, then ask for body."""
    date_str = datetime.now(IST).strftime("%Y-%m-%d")
    title = context.user_data.get("art_title", "article")
    provisional_slug = f"{date_str}-{slugify(title)}"

    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document and (update.message.document.mime_type or "").startswith("image/"):
        file_id = update.message.document.file_id

    cover_image_url = None

    if file_id:
        try:
            tg_file = await context.bot.get_file(file_id)
            _, ext = os.path.splitext(tg_file.file_path)
            ext = ext.lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
                ext = '.jpg'

            img_filename = f"{provisional_slug}-cover{ext}"
            root_dir = get_project_root()
            img_dir = os.path.join(root_dir, "assets", "img", "articles")
            os.makedirs(img_dir, exist_ok=True)
            save_path = os.path.join(img_dir, img_filename)
            await tg_file.download_to_drive(save_path)

            cover_image_url = f"https://footholics.in/assets/img/articles/{img_filename}"
            await update.message.reply_text(
                f"✅ Cover image saved as `assets/img/articles/{img_filename}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ Could not save image: {e}\nContinuing without cover image.")
    else:
        # "skip" or any text — no cover image
        await update.message.reply_text("⏭️ Skipping cover image.")

    context.user_data["art_cover_image"] = cover_image_url
    context.user_data["art_parts"] = []   # ordered list of text/image parts
    context.user_data["art_img_count"] = 0

    await update.message.reply_text(
        "Step 5 of 5: *Compose your article.*\n\n"
        "Send your content in the exact order you want it to appear:\n"
        "• Send a *text block* → becomes paragraph(s)\n"
        "• Send a *photo or file* → saved and placed at that position\n"
        "• Use `## Heading` / `### Heading` for section headings\n\n"
        "Type `done` when you're finished.\n\n"
        "_Example: send intro text → send image → send next section → done_",
        parse_mode="Markdown"
    )
    return ARTICLE_CONTENT


async def article_content_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 5 — compose body by interleaving text blocks and image uploads; 'done' finishes."""
    parts     = context.user_data.setdefault("art_parts", [])
    img_count = context.user_data.get("art_img_count", 0)

    # ── Photo / document image ────────────────────────────────────────────────
    file_id = None
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif update.message.document and (update.message.document.mime_type or "").startswith("image/"):
        file_id = update.message.document.file_id

    if file_id:
        try:
            date_str  = datetime.now(IST).strftime("%Y-%m-%d")
            base_slug = f"{date_str}-{slugify(context.user_data.get('art_title', 'article'))}"
            img_count += 1
            context.user_data["art_img_count"] = img_count

            tg_file = await context.bot.get_file(file_id)
            _, ext = os.path.splitext(tg_file.file_path)
            ext = ext.lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
                ext = '.jpg'

            img_filename = f"{base_slug}-img{img_count}{ext}"
            root_dir = get_project_root()
            img_dir  = os.path.join(root_dir, "assets", "img", "articles")
            os.makedirs(img_dir, exist_ok=True)
            await tg_file.download_to_drive(os.path.join(img_dir, img_filename))

            img_url = f"https://footholics.in/assets/img/articles/{img_filename}"
            caption = (update.message.caption or "").strip()
            parts.append(f"![{caption}]({img_url})")

            await update.message.reply_text(
                f"✅ Image {img_count} placed at this position.\n"
                f"`{img_url}`\n\n"
                "Send the next text block, another image, or type `done`.",
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text(f"⚠️ Could not save image: {e}\nTry again or continue.")
        return ARTICLE_CONTENT

    # ── Text message ──────────────────────────────────────────────────────────
    text = (update.message.text or "").strip()

    if text.lower() == "done":
        content = "\n\n".join(parts)
        if len(content.replace("\n", "").replace("!", "").replace("[", "").replace("]", "").replace("(", "").replace(")", "")) < 50:
            await update.message.reply_text(
                "❌ Article body is too short. Send more text and then type `done`.",
                parse_mode="Markdown"
            )
            return ARTICLE_CONTENT

        context.user_data["art_content"] = content

        title    = context.user_data["art_title"]
        category = context.user_data["art_category"]
        excerpt  = context.user_data["art_excerpt"]
        cover_image = context.user_data.get("art_cover_image")

        text_parts   = [p for p in parts if not p.startswith("![")]
        image_count  = img_count
        word_count   = sum(len(p.split()) for p in text_parts)
        cover_line   = "\n*Cover image:* ✅ uploaded" if cover_image else "\n*Cover image:* _(none)_"
        body_preview = content[:300] + ("…" if len(content) > 300 else "")

        keyboard = [
            [InlineKeyboardButton("✅ Publish", callback_data="art_confirm"),
             InlineKeyboardButton("❌ Cancel", callback_data="art_cancel")],
        ]
        await update.message.reply_text(
            f"📋 *Preview — confirm before publishing:*\n\n"
            f"*Title:* {_html.escape(title)}\n"
            f"*Category:* {category}"
            f"{cover_line}\n"
            f"*Parts:* {len(parts)} ({word_count} words, {image_count} image(s))\n"
            f"*Excerpt:* {_html.escape(excerpt[:120])}\n\n"
            f"*Body preview:*\n_{_html.escape(body_preview)}_",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ARTICLE_CONFIRM

    if not text:
        await update.message.reply_text("Send a text block, a photo, or type `done`.", parse_mode="Markdown")
        return ARTICLE_CONTENT

    parts.append(text)
    await update.message.reply_text(
        f"✅ Block {len(parts)} added. Send the next block, an image, or type `done`.",
        parse_mode="Markdown"
    )
    return ARTICLE_CONTENT


async def article_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Step 6 — publish or cancel."""
    query = update.callback_query
    await query.answer()

    if query.data == "art_cancel":
        _keep = {k: context.user_data[k] for k in ('git_username', 'git_token', 'pending_push') if k in context.user_data}
        context.user_data.clear()
        context.user_data.update(_keep)
        await query.edit_message_text("❌ Article cancelled.")
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    # Publish
    title       = context.user_data["art_title"]
    category    = context.user_data["art_category"]
    excerpt     = context.user_data["art_excerpt"]
    content     = context.user_data["art_content"]
    cover_image = context.user_data.get("art_cover_image")  # may be None

    await query.edit_message_text("⏳ Publishing article…")

    try:
        root_dir = get_project_root()
        date_str = datetime.now(IST).strftime("%Y-%m-%d")
        slug = f"{date_str}-{slugify(title)}"

        # Generate HTML
        html_content = generate_article_html(title, slug, category, excerpt, content, date_str, cover_image)

        # Write HTML file
        articles_dir = os.path.join(root_dir, "articles")
        os.makedirs(articles_dir, exist_ok=True)
        html_path = os.path.join(articles_dir, f"{slug}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Save source meta JSON (enables editing later)
        meta_dir = os.path.join(articles_dir, "meta")
        os.makedirs(meta_dir, exist_ok=True)
        meta = {
            "title": title,
            "slug": slug,
            "category": category,
            "excerpt": excerpt,
            "content": content,
            "cover_image": cover_image,
            "date": date_str,
        }
        with open(os.path.join(meta_dir, f"{slug}.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        # Update articles/index.json
        index_path = os.path.join(articles_dir, "index.json")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                articles = json.load(f)
        else:
            articles = []

        index_image = cover_image if cover_image else "https://footholics.in/assets/img/og-image.jpg"
        new_entry = {
            "slug": slug,
            "title": title,
            "excerpt": excerpt,
            "image": index_image,
            "date": date_str,
            "author": "OnixWhite",
            "category": category,
            "url": f"/articles/{slug}.html",
        }
        articles.insert(0, new_entry)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(articles, f, indent=2, ensure_ascii=False)

        # Update sitemap.xml
        sitemap_path = os.path.join(root_dir, "sitemap.xml")
        if os.path.exists(sitemap_path):
            with open(sitemap_path, "r", encoding="utf-8") as f:
                sitemap = f.read()
            new_url_entry = (
                f"    <url>\n"
                f"        <loc>https://footholics.in/articles/{slug}.html</loc>\n"
                f"        <lastmod>{date_str}</lastmod>\n"
                f"        <changefreq>weekly</changefreq>\n"
                f"        <priority>0.8</priority>\n"
                f"    </url>\n\n"
            )
            # Bump lastmod on homepage and articles listing
            sitemap = re.sub(
                r'(<loc>https://footholics\.in/</loc>\s*\n\s*<lastmod>)[^<]+(</lastmod>)',
                rf'\g<1>{date_str}\g<2>',
                sitemap
            )
            sitemap = re.sub(
                r'(<loc>https://footholics\.in/articles/index\.html</loc>\s*\n\s*<lastmod>)[^<]+(</lastmod>)',
                rf'\g<1>{date_str}\g<2>',
                sitemap
            )
            # Insert new article immediately after articles/index.html entry (newest first)
            sitemap = re.sub(
                r'(<loc>https://footholics\.in/articles/index\.html</loc>.*?</url>\s*\n)',
                lambda m: m.group(0) + "\n" + new_url_entry,
                sitemap,
                count=1,
                flags=re.DOTALL
            )
            with open(sitemap_path, "w", encoding="utf-8") as f:
                f.write(sitemap)

        cover_line = f"\n• assets/img/articles/{slug}-cover (uploaded)" if cover_image else ""
        git_user = context.user_data.get('git_username', '')
        git_token = context.user_data.get('git_token', '')
        _art_commit = f"Add article: {title[:50]}"
        push_ok, push_status = await asyncio.to_thread(
            git_auto_push, get_project_root(), _art_commit, git_user, git_token
        )
        set_pending_push(context, [(get_project_root(), _art_commit)], [(push_ok, push_status)])
        success_msg = (
            f"✅ *Article Published!*\n\n"
            f"*File:* `articles/{slug}.html`\n"
            f"*URL:* `https://footholics.in/articles/{slug}.html`\n\n"
            f"*Saved to:*\n"
            f"• articles/{slug}.html\n"
            f"• articles/meta/{slug}.json\n"
            f"• articles/index.json\n"
            f"• sitemap.xml"
            f"{cover_line}\n\n"
            f"{push_summary(('foot-holics', push_ok, push_status))}\n\n"
            f"{'🚀 Live in ~60 seconds!' if push_ok else ''}"
        )
        try:
            await query.edit_message_text(success_msg, parse_mode="Markdown")
        except Exception:
            await query.edit_message_text(success_msg.replace("*", "").replace("`", "").replace("_", ""))

    except Exception as e:
        logger.error(f"Error publishing article: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Error publishing article: {e}")

    _keep = {k: context.user_data[k] for k in ('git_username', 'git_token', 'pending_push') if k in context.user_data}
    context.user_data.clear()
    context.user_data.update(_keep)
    await show_main_menu(update, context, edit_message=False)
    return MAIN_MENU


# ── Article Editing ────────────────────────────────────────────────────────────

async def edit_article_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show list of articles that have a meta file (published via bot)."""
    query = update.callback_query
    root_dir = get_project_root()
    articles_dir = os.path.join(root_dir, "articles")
    index_path = os.path.join(articles_dir, "index.json")

    if not os.path.exists(index_path):
        await query.edit_message_text("❌ No articles found.")
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    with open(index_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    meta_dir = os.path.join(articles_dir, "meta")

    # Only show articles that have a meta file (bot-published)
    editable = [a for a in articles if os.path.exists(os.path.join(meta_dir, f"{a['slug']}.json"))]

    if not editable:
        await query.edit_message_text(
            "❌ No editable articles found.\n\n"
            "Only articles published via the bot can be edited here."
        )
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    # Store list so select handler can look up by index (avoids 64-byte callback_data limit)
    context.user_data["edit_article_list"] = editable[:10]

    keyboard = [
        [InlineKeyboardButton(
            f"{a['date']} — {a['title'][:40]}",
            callback_data=f"edit_art_{i}"
        )]
        for i, a in enumerate(editable[:10])
    ]
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_back")])

    await query.edit_message_text(
        "✏️ *Edit Article*\n\nSelect an article to edit:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_ARTICLE_SELECT


async def edit_article_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User picked an article — show field selection menu."""
    query = update.callback_query
    await query.answer()

    idx      = int(query.data.replace("edit_art_", ""))
    listing  = context.user_data.get("edit_article_list", [])
    if idx >= len(listing):
        await query.edit_message_text("❌ Selection expired. Please try again.")
        return await edit_article_start(update, context)

    slug     = listing[idx]["slug"]
    root_dir = get_project_root()
    meta_path = os.path.join(root_dir, "articles", "meta", f"{slug}.json")

    if not os.path.exists(meta_path):
        await query.edit_message_text("❌ Meta file not found for this article.")
        return await edit_article_start(update, context)

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    context.user_data["edit_slug"] = slug
    context.user_data["edit_meta"] = meta

    cover_status = "✅ has image" if meta.get("cover_image") else "_(none)_"
    keyboard = [
        [InlineKeyboardButton("📝 Title", callback_data="edit_field_title"),
         InlineKeyboardButton("🏷️ Category", callback_data="edit_field_category")],
        [InlineKeyboardButton("💬 Excerpt", callback_data="edit_field_excerpt"),
         InlineKeyboardButton("🖼️ Cover Image", callback_data="edit_field_cover_image")],
        [InlineKeyboardButton("📄 Body", callback_data="edit_field_content")],
        [InlineKeyboardButton("🔙 Back to list", callback_data="edit_field_back")],
    ]

    await query.edit_message_text(
        f"✏️ *Editing:* {_html.escape(meta['title'])}\n\n"
        f"*Category:* {meta['category']}\n"
        f"*Cover image:* {cover_status}\n\n"
        f"Which field would you like to edit?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_ARTICLE_FIELD


async def edit_article_field_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User picked a field — ask for new value."""
    query = update.callback_query
    await query.answer()

    field = query.data.replace("edit_field_", "")

    if field == "back":
        return await edit_article_start(update, context)

    context.user_data["edit_field"] = field

    if field == "category":
        keyboard = [
            [InlineKeyboardButton("Premier League", callback_data="edit_cat_Premier League"),
             InlineKeyboardButton("Champions League", callback_data="edit_cat_Champions League")],
            [InlineKeyboardButton("La Liga", callback_data="edit_cat_La Liga"),
             InlineKeyboardButton("Bundesliga", callback_data="edit_cat_Bundesliga")],
            [InlineKeyboardButton("Serie A", callback_data="edit_cat_Serie A"),
             InlineKeyboardButton("Ligue 1", callback_data="edit_cat_Ligue 1")],
            [InlineKeyboardButton("World Football", callback_data="edit_cat_World Football"),
             InlineKeyboardButton("Guide", callback_data="edit_cat_Guide")],
        ]
        await query.edit_message_text(
            "Choose the new *category*:",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return EDIT_ARTICLE_INPUT

    elif field == "cover_image":
        await query.edit_message_text(
            "🖼️ Send a new *cover image* (photo or file).\n\n"
            "Type `remove` to remove the existing cover image.\n"
            "Type `skip` to keep the current image.",
            parse_mode="Markdown"
        )
        return EDIT_ARTICLE_INPUT

    elif field == "content":
        # Show blocks list so user can pick one to replace
        meta   = context.user_data.get("edit_meta", {})
        blocks = [b for b in meta.get("content", "").split("\n\n") if b.strip()]

        if not blocks:
            await query.edit_message_text("❌ No content blocks found.")
            return EDIT_ARTICLE_FIELD

        lines = []
        for i, b in enumerate(blocks):
            icon    = "🖼️" if b.startswith("![") else "📝"
            preview = b[:70].replace("\n", " ") + ("…" if len(b) > 70 else "")
            lines.append(f"{icon} <b>Block {i + 1}:</b> {_html.escape(preview)}")

        keyboard = []
        row = []
        for i in range(len(blocks)):
            row.append(InlineKeyboardButton(f"Block {i + 1}", callback_data=f"edit_block_{i}"))
            if len(row) == 3:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("➕ Add Block at End", callback_data="edit_block_new")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="edit_field_back")])

        await query.edit_message_text(
            "<b>Select a block to replace or delete:</b>\n\n" + "\n".join(lines),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return EDIT_ARTICLE_INPUT

    else:
        field_labels = {"title": "Title", "excerpt": "Excerpt"}
        label = field_labels.get(field, field.capitalize())
        await query.edit_message_text(
            f"Send the new *{label}*:\n\n_Type /cancel to abort_",
            parse_mode="Markdown"
        )
        return EDIT_ARTICLE_INPUT


async def edit_block_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User tapped a block number — show it and ask for replacement."""
    query = update.callback_query
    await query.answer()

    target = query.data.replace("edit_block_", "")
    meta   = context.user_data.get("edit_meta", {})
    blocks = [b for b in meta.get("content", "").split("\n\n") if b.strip()]

    if target == "new":
        context.user_data["edit_block_index"] = len(blocks)  # append
        await query.edit_message_text(
            "➕ *Add a new block at the end.*\n\n"
            "Send a text block or a photo.\n\n"
            "_Type /cancel to abort_",
            parse_mode="Markdown"
        )
        return EDIT_ARTICLE_INPUT

    idx = int(target)
    context.user_data["edit_block_index"] = idx

    if idx >= len(blocks):
        await query.edit_message_text("❌ Block not found.")
        return EDIT_ARTICLE_FIELD

    current  = blocks[idx]
    is_image = current.strip().startswith("![")
    icon     = "🖼️ image" if is_image else "📝 text"
    preview  = current[:300].replace("\n", " ") + ("…" if len(current) > 300 else "")

    await query.edit_message_text(
        f"<b>Block {idx + 1}</b> ({icon}):\n\n<i>{_html.escape(preview)}</i>\n\n"
        "Send the <b>replacement</b>:\n"
        "• Text block → replaces this block\n"
        "• Photo / file → replaces with an image\n"
        "• Type <code>delete</code> → removes this block\n\n"
        "<i>Type /cancel to abort</i>",
        parse_mode="HTML"
    )
    return EDIT_ARTICLE_INPUT


async def edit_article_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive new value for the chosen field (text or photo), show confirm."""
    field      = context.user_data.get("edit_field")
    meta       = context.user_data.get("edit_meta", {})
    slug       = context.user_data.get("edit_slug")
    block_idx  = context.user_data.get("edit_block_index")  # set when editing a block

    # ── Block-level replacement ──────────────────────────────────────────────
    if field == "content" and block_idx is not None:
        blocks = [b for b in meta.get("content", "").split("\n\n") if b.strip()]

        file_id = None
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        elif update.message.document and (update.message.document.mime_type or "").startswith("image/"):
            file_id = update.message.document.file_id

        if file_id:
            try:
                tg_file  = await context.bot.get_file(file_id)
                _, ext   = os.path.splitext(tg_file.file_path)
                ext = ext.lower() if ext.lower() in ('.jpg', '.jpeg', '.png', '.webp') else '.jpg'
                img_n    = block_idx + 1
                fname    = f"{slug}-edit-img{img_n}{ext}"
                root_dir = get_project_root()
                img_dir  = os.path.join(root_dir, "assets", "img", "articles")
                os.makedirs(img_dir, exist_ok=True)
                await tg_file.download_to_drive(os.path.join(img_dir, fname))
                caption  = (update.message.caption or "").strip()
                new_block = f"![{caption}](https://footholics.in/assets/img/articles/{fname})"
                await update.message.reply_text(f"✅ Image saved: `assets/img/articles/{fname}`", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"❌ Could not save image: {e}")
                return EDIT_ARTICLE_INPUT

            if block_idx >= len(blocks):
                blocks.append(new_block)
            else:
                blocks[block_idx] = new_block

        elif update.message.text:
            text = update.message.text.strip()
            if text.lower() == "delete":
                if block_idx < len(blocks):
                    blocks.pop(block_idx)
                new_block = "_(deleted)_"
            else:
                if block_idx >= len(blocks):
                    blocks.append(text)
                else:
                    blocks[block_idx] = text
                new_block = text
        else:
            await update.message.reply_text("Send a text block or photo, or type `delete`.", parse_mode="Markdown")
            return EDIT_ARTICLE_INPUT

        context.user_data.pop("edit_block_index")
        new_content = "\n\n".join(blocks)
        context.user_data["edit_new_value"] = new_content
        return await _show_edit_confirm(update, context, "content", new_content)

    new_value = None

    # Handle photo uploads for cover_image
    if field == "cover_image":
        file_id = None
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
        elif update.message.document and (update.message.document.mime_type or "").startswith("image/"):
            file_id = update.message.document.file_id

        if file_id:
            try:
                tg_file = await context.bot.get_file(file_id)
                _, ext = os.path.splitext(tg_file.file_path)
                ext = ext.lower()
                if ext not in ('.jpg', '.jpeg', '.png', '.webp'):
                    ext = '.jpg'
                img_filename = f"{slug}-cover{ext}"
                root_dir = get_project_root()
                img_dir = os.path.join(root_dir, "assets", "img", "articles")
                os.makedirs(img_dir, exist_ok=True)
                await tg_file.download_to_drive(os.path.join(img_dir, img_filename))
                new_value = f"https://footholics.in/assets/img/articles/{img_filename}"
                await update.message.reply_text(f"✅ Image saved as `assets/img/articles/{img_filename}`", parse_mode="Markdown")
            except Exception as e:
                await update.message.reply_text(f"❌ Could not save image: {e}")
                return EDIT_ARTICLE_INPUT
        else:
            text = update.message.text.strip().lower()
            if text == "remove":
                new_value = None
            elif text == "skip":
                await update.message.reply_text("⏭️ Cover image unchanged.")
                return await _show_edit_confirm(update, context, field, meta.get("cover_image"), unchanged=True)
            else:
                await update.message.reply_text("❌ Send a photo/file, type `remove`, or type `skip`.", parse_mode="Markdown")
                return EDIT_ARTICLE_INPUT
    else:
        if not update.message.text:
            await update.message.reply_text("❌ Please send a text value.")
            return EDIT_ARTICLE_INPUT
        new_value = update.message.text.strip()
        if not new_value:
            await update.message.reply_text("❌ Value cannot be empty.")
            return EDIT_ARTICLE_INPUT

    context.user_data["edit_new_value"] = new_value
    return await _show_edit_confirm(update, context, field, new_value)


async def edit_article_cat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle category button selection during edit."""
    query = update.callback_query
    await query.answer()
    new_value = query.data.replace("edit_cat_", "")
    context.user_data["edit_new_value"] = new_value

    keyboard = [
        [InlineKeyboardButton("✅ Save", callback_data="edit_confirm_yes"),
         InlineKeyboardButton("❌ Cancel", callback_data="edit_confirm_no")],
    ]
    await query.edit_message_text(
        f"Update category to *{_html.escape(new_value)}*?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_ARTICLE_CONFIRM


async def _show_edit_confirm(update, context, field, new_value, unchanged=False):
    """Helper — show confirm keyboard after collecting new value."""
    if unchanged:
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    field_labels = {
        "title": "Title", "excerpt": "Excerpt", "content": "Body",
        "category": "Category", "cover_image": "Cover Image",
    }
    label = field_labels.get(field, field.capitalize())
    preview = str(new_value)[:200] + ("…" if new_value and len(str(new_value)) > 200 else "") if new_value else "_(removed)_"

    keyboard = [
        [InlineKeyboardButton("✅ Save", callback_data="edit_confirm_yes"),
         InlineKeyboardButton("❌ Cancel", callback_data="edit_confirm_no")],
    ]
    await update.message.reply_text(
        f"<b>Save changes?</b>\n\n<b>Field:</b> {_html.escape(label)}\n<b>New value:</b> {_html.escape(preview)}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return EDIT_ARTICLE_CONFIRM


async def edit_article_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save the edit or cancel."""
    query = update.callback_query
    await query.answer()

    if query.data == "edit_confirm_no":
        context.user_data.pop("edit_field", None)
        context.user_data.pop("edit_new_value", None)
        await query.edit_message_text("❌ Edit cancelled.")
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    field     = context.user_data.get("edit_field")
    new_value = context.user_data.get("edit_new_value")
    slug      = context.user_data.get("edit_slug")
    meta      = context.user_data.get("edit_meta", {})

    await query.edit_message_text("⏳ Saving changes…")

    try:
        root_dir    = get_project_root()
        articles_dir = os.path.join(root_dir, "articles")
        meta_path   = os.path.join(articles_dir, "meta", f"{slug}.json")

        # Update the meta dict
        meta[field] = new_value
        context.user_data["edit_meta"] = meta

        # Regenerate HTML from updated meta
        html_content = generate_article_html(
            title=meta["title"],
            slug=meta["slug"],
            category=meta["category"],
            excerpt=meta["excerpt"],
            content=meta["content"],
            date=meta["date"],
            cover_image=meta.get("cover_image"),
        )
        with open(os.path.join(articles_dir, f"{slug}.html"), "w", encoding="utf-8") as f:
            f.write(html_content)

        # Save updated meta JSON
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)

        # Update articles/index.json entry
        index_path = os.path.join(articles_dir, "index.json")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                articles = json.load(f)
            for entry in articles:
                if entry["slug"] == slug:
                    if field == "title":
                        entry["title"] = new_value
                    elif field == "excerpt":
                        entry["excerpt"] = new_value
                    elif field == "category":
                        entry["category"] = new_value
                    elif field == "cover_image":
                        entry["image"] = new_value if new_value else "https://footholics.in/assets/img/og-image.jpg"
                    break
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(articles, f, indent=2, ensure_ascii=False)

        git_user = context.user_data.get('git_username', '')
        git_token = context.user_data.get('git_token', '')
        _art_commit = f"Update article: {meta['title'][:50]}"
        push_ok, push_status = await asyncio.to_thread(
            git_auto_push, get_project_root(), _art_commit, git_user, git_token
        )
        set_pending_push(context, [(get_project_root(), _art_commit)], [(push_ok, push_status)])
        _art_update_msg = (
            f"✅ *Article updated!*\n\n"
            f"*Field:* {field.replace('_', ' ').capitalize()}\n"
            f"*Article:* {_html.escape(meta['title'])}\n\n"
            f"{push_summary(('foot-holics', push_ok, push_status))}"
        )
        try:
            await query.edit_message_text(_art_update_msg, parse_mode="Markdown")
        except Exception:
            await query.edit_message_text(_art_update_msg.replace("*", "").replace("`", "").replace("_", ""))

    except Exception as e:
        logger.error(f"Error editing article: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Error saving edit: {e}")

    context.user_data.pop("edit_field", None)
    context.user_data.pop("edit_new_value", None)
    await show_main_menu(update, context, edit_message=False)
    return MAIN_MENU


# ── Article Deletion ───────────────────────────────────────────────────────────

async def delete_article_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show all published articles for deletion selection."""
    query = update.callback_query
    root_dir = get_project_root()
    index_path = os.path.join(root_dir, "articles", "index.json")

    if not os.path.exists(index_path):
        await query.edit_message_text("❌ No articles found.")
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    with open(index_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    if not articles:
        await query.edit_message_text("❌ No articles to delete.")
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    # Store list so select handler can look up by index (avoids 64-byte callback_data limit)
    context.user_data["del_article_list"] = articles[:15]

    keyboard = [
        [InlineKeyboardButton(
            f"{a['date']} — {a['title'][:40]}",
            callback_data=f"del_art_{i}"
        )]
        for i, a in enumerate(articles[:15])
    ]
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu_back")])

    await query.edit_message_text(
        "🗑️ *Delete Article*\n\nSelect an article to delete:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DELETE_ARTICLE_SELECT


async def delete_article_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """User selected an article — show confirm prompt."""
    query = update.callback_query
    await query.answer()

    idx     = int(query.data.replace("del_art_", ""))
    listing = context.user_data.get("del_article_list", [])
    if idx >= len(listing):
        await query.edit_message_text("❌ Selection expired. Please try again.")
        return await delete_article_start(update, context)

    entry = listing[idx]
    if not entry:
        await query.edit_message_text("❌ Article not found.")
        return await delete_article_start(update, context)

    context.user_data["del_slug"]  = entry["slug"]
    context.user_data["del_title"] = entry["title"]

    keyboard = [
        [InlineKeyboardButton("✅ Yes, delete it", callback_data="del_confirm_yes"),
         InlineKeyboardButton("❌ Cancel", callback_data="del_confirm_no")],
    ]
    await query.edit_message_text(
        f"🗑️ *Confirm Deletion*\n\n"
        f"Are you sure you want to delete:\n\n"
        f"*{_html.escape(entry['title'])}*\n\n"
        f"This will remove the HTML file, meta JSON, and sitemap entry.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DELETE_ARTICLE_CONFIRM


async def delete_article_confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Execute deletion or cancel."""
    query = update.callback_query
    await query.answer()

    if query.data == "del_confirm_no":
        context.user_data.pop("del_slug", None)
        context.user_data.pop("del_title", None)
        await query.edit_message_text("❌ Deletion cancelled.")
        await show_main_menu(update, context, edit_message=False)
        return MAIN_MENU

    slug  = context.user_data.pop("del_slug", None)
    title = context.user_data.pop("del_title", "")

    await query.edit_message_text("⏳ Deleting article…")

    try:
        root_dir     = get_project_root()
        articles_dir = os.path.join(root_dir, "articles")
        removed      = []

        # 1. Delete HTML file
        html_path = os.path.join(articles_dir, f"{slug}.html")
        if os.path.exists(html_path):
            os.remove(html_path)
            removed.append(f"articles/{slug}.html")

        # 2. Delete meta JSON
        meta_path = os.path.join(articles_dir, "meta", f"{slug}.json")
        if os.path.exists(meta_path):
            os.remove(meta_path)
            removed.append(f"articles/meta/{slug}.json")

        # 3. Remove from index.json
        index_path = os.path.join(articles_dir, "index.json")
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                articles = json.load(f)
            articles = [a for a in articles if a["slug"] != slug]
            with open(index_path, "w", encoding="utf-8") as f:
                json.dump(articles, f, indent=2, ensure_ascii=False)
            removed.append("articles/index.json")

        # 4. Remove from sitemap.xml
        sitemap_path = os.path.join(root_dir, "sitemap.xml")
        if os.path.exists(sitemap_path):
            with open(sitemap_path, "r", encoding="utf-8") as f:
                sitemap = f.read()
            # Remove the <url> block for this article
            sitemap = re.sub(
                r'\n\s*<url>\s*\n\s*<loc>https://footholics\.in/articles/' + re.escape(slug) + r'\.html</loc>.*?</url>',
                '',
                sitemap,
                flags=re.DOTALL
            )
            with open(sitemap_path, "w", encoding="utf-8") as f:
                f.write(sitemap)
            removed.append("sitemap.xml")

        removed_list = "\n".join(f"• {r}" for r in removed)
        git_user = context.user_data.get('git_username', '')
        git_token = context.user_data.get('git_token', '')
        _art_commit = f"Delete article: {title[:40]}"
        push_ok, push_status = await asyncio.to_thread(
            git_auto_push, get_project_root(), _art_commit, git_user, git_token
        )
        set_pending_push(context, [(get_project_root(), _art_commit)], [(push_ok, push_status)])
        _art_del_msg = (
            f"✅ *Article Deleted!*\n\n"
            f"*Title:* {_html.escape(title)}\n\n"
            f"*Removed:*\n{removed_list}\n\n"
            f"{push_summary(('foot-holics', push_ok, push_status))}"
        )
        try:
            await query.edit_message_text(_art_del_msg, parse_mode="Markdown")
        except Exception:
            await query.edit_message_text(_art_del_msg.replace("*", "").replace("`", "").replace("_", ""))

    except Exception as e:
        logger.error(f"Error deleting article: {e}", exc_info=True)
        await query.edit_message_text(f"❌ Error deleting article: {e}")

    await show_main_menu(update, context, edit_message=False)
    return MAIN_MENU


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
            POSTER_IMAGE: [
                MessageHandler(filters.PHOTO, poster_image),
                MessageHandler(filters.Document.IMAGE, poster_image),
                MessageHandler(filters.TEXT & ~filters.COMMAND, poster_image),
            ],
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
            ARTICLE_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, article_title_handler)],
            ARTICLE_CATEGORY: [CallbackQueryHandler(article_category_handler, pattern="^art_cat_")],
            ARTICLE_EXCERPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, article_excerpt_handler)],
            ARTICLE_COVER_IMAGE: [
                MessageHandler(filters.PHOTO, article_cover_image_handler),
                MessageHandler(filters.Document.IMAGE, article_cover_image_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, article_cover_image_handler),
            ],
            ARTICLE_CONTENT: [
                MessageHandler(filters.PHOTO, article_content_handler),
                MessageHandler(filters.Document.IMAGE, article_content_handler),
                MessageHandler(filters.TEXT & ~filters.COMMAND, article_content_handler),
            ],
            ARTICLE_CONFIRM: [
                CallbackQueryHandler(article_confirm_handler, pattern="^art_confirm"),
                CallbackQueryHandler(article_confirm_handler, pattern="^art_cancel"),
            ],
            EDIT_ARTICLE_SELECT: [
                CallbackQueryHandler(edit_article_select_handler, pattern="^edit_art_"),
                CallbackQueryHandler(main_menu_handler, pattern="^menu_"),
            ],
            EDIT_ARTICLE_FIELD: [
                CallbackQueryHandler(edit_article_field_handler, pattern="^edit_field_"),
                CallbackQueryHandler(main_menu_handler, pattern="^menu_"),
            ],
            EDIT_ARTICLE_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_article_input_handler),
                MessageHandler(filters.PHOTO, edit_article_input_handler),
                MessageHandler(filters.Document.IMAGE, edit_article_input_handler),
                CallbackQueryHandler(edit_article_cat_handler, pattern="^edit_cat_"),
                CallbackQueryHandler(edit_block_select_handler, pattern="^edit_block_"),
                CallbackQueryHandler(edit_article_field_handler, pattern="^edit_field_"),
            ],
            EDIT_ARTICLE_CONFIRM: [
                CallbackQueryHandler(edit_article_confirm_handler, pattern="^edit_confirm_"),
            ],
            DELETE_ARTICLE_SELECT: [
                CallbackQueryHandler(delete_article_select_handler, pattern="^del_art_"),
                CallbackQueryHandler(main_menu_handler, pattern="^menu_"),
            ],
            DELETE_ARTICLE_CONFIRM: [
                CallbackQueryHandler(delete_article_confirm_handler, pattern="^del_confirm_"),
            ],
            SET_GIT_CREDS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_git_creds),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),   # /start always restarts from any state
        ],
        allow_reentry=True,
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
