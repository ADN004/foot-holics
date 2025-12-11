#!/usr/bin/env python3
"""Regenerate match HTML files from events.json with raw URLs"""

import json
import os
import re
from datetime import datetime
from urllib.parse import quote

def get_project_root():
    """Get the project root directory."""
    bot_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(bot_dir)

def find_team_logo(team_name, league_slug):
    """Find team logo path."""
    # Simplified - just return placeholder
    return "assets/img/logos/teams/laliga/placeholder.png"

def slugify(text):
    """Convert text to URL-friendly slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text

def get_inline_event_template():
    """Get the HTML template for event pages."""
    # Import bot.py functions directly
    import sys
    bot_dir = os.path.dirname(__file__)
    sys.path.insert(0, bot_dir)
    
    try:
        from bot import get_inline_event_template as get_template
        return get_template()
    except Exception as e:
        print(f"⚠️ Could not import template from bot.py: {e}")
        # Fallback: read from TEMPLATE-event.html if exists
        template_path = os.path.join(get_project_root(), "TEMPLATE-event.html")
        if os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                return f.read()
        return ""

def generate_html_from_event(event):
    """Generate HTML for a match from event JSON."""
    # Get template
    html = get_inline_event_template()
    if not html:
        print(f"⚠️ Could not load template for {event['slug']}")
        return None
    
    # Parse date
    date_obj = datetime.strptime(event["date"], "%Y-%m-%d")
    iso_date = date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")
    match_name_encoded = quote(event["title"])
    
    # Find team logos
    home_logo = find_team_logo(event["homeTeam"], event["leagueSlug"])
    away_logo = find_team_logo(event["awayTeam"], event["leagueSlug"])
    
    # Get stream URLs from broadcast array
    stream_urls = [b["url"] for b in event.get("broadcast", [])]
    while len(stream_urls) < 4:
        stream_urls.append("#")
    
    # Generate filename
    filename = f"{event['slug']}.html"
    home_slug = slugify(event["homeTeam"])
    away_slug = slugify(event["awayTeam"])
    
    # Replace placeholders
    html = html.replace("{{MATCH_NAME}}", event["title"])
    html = html.replace("{{HOME_TEAM}}", event["homeTeam"])
    html = html.replace("{{AWAY_TEAM}}", event["awayTeam"])
    html = html.replace("{{HOME_TEAM_LOGO}}", home_logo)
    html = html.replace("{{AWAY_TEAM_LOGO}}", away_logo)
    html = html.replace("{{DATE}}", date_obj.strftime("%B %d, %Y"))
    html = html.replace("{{DATE_SHORT}}", date_obj.strftime("%b %d, %Y"))
    html = html.replace("{{ISO_DATE}}", iso_date)
    html = html.replace("{{TIME}}", event["time"])
    html = html.replace("{{LEAGUE}}", event["league"])
    html = html.replace("{{LEAGUE_SLUG}}", event["leagueSlug"])
    html = html.replace("{{STADIUM}}", event["stadium"])
    html = html.replace("{{PREVIEW}}", event["excerpt"])
    html = html.replace("{{IMAGE_FILE}}", event["poster"].replace("assets/img/", ""))
    html = html.replace("{{FILE_NAME}}", filename)
    html = html.replace("{{SLUG}}", f"{home_slug}-vs-{away_slug}")
    html = html.replace("{{MATCH_NAME_ENCODED}}", match_name_encoded)
    
    # Generate player URLs with raw stream URLs
    player_urls = []

    for i in range(4):
        stream_num = i + 1
        url = stream_urls[i] if i < len(stream_urls) else "#"

        # Only generate player URL if stream is valid
        if url and url != "#" and not url.startswith("https://t.me/"):
            # Use raw URL with player
            player_url = f"p/{stream_num}-live.html?url={quote(url)}"
        else:
            player_url = "#"

        player_urls.append(player_url)

    # Replace stream URLs with player URLs
    html = html.replace("{{STREAM_URL_1}}", player_urls[0])
    html = html.replace("{{STREAM_URL_2}}", player_urls[1])
    html = html.replace("{{STREAM_URL_3}}", player_urls[2])
    html = html.replace("{{STREAM_URL_4}}", player_urls[3])
    
    return html

def regenerate_match_files():
    """Regenerate all match HTML files from events.json."""
    root_dir = get_project_root()
    events_path = os.path.join(root_dir, "data", "events.json")
    
    # Read events.json
    with open(events_path, "r", encoding="utf-8") as f:
        events = json.load(f)
    
    regenerated = 0
    for event in events:
        html = generate_html_from_event(event)
        if html:
            filename = f"{event['slug']}.html"
            filepath = os.path.join(root_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html)
            
            print(f"✅ Regenerated {filename}")
            regenerated += 1
        else:
            print(f"❌ Failed to regenerate {event['slug']}.html")
    
    print(f"\n✅ Successfully regenerated {regenerated}/{len(events)} match files")
    return regenerated == len(events)

if __name__ == "__main__":
    regenerate_match_files()

