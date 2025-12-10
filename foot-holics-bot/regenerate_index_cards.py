#!/usr/bin/env python3
"""Regenerate index.html match cards from events.json"""

import json
import os
import re
from datetime import datetime

def get_project_root():
    """Get the project root directory."""
    bot_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(bot_dir)

def regenerate_index_cards():
    """Regenerate all match cards in index.html from events.json"""
    root_dir = get_project_root()
    events_path = os.path.join(root_dir, "data", "events.json")
    index_path = os.path.join(root_dir, "index.html")
    
    # Read events.json
    with open(events_path, "r", encoding="utf-8") as f:
        events = json.load(f)
    
    # Generate cards HTML
    cards_html = []
    for event in events:
        date_obj = datetime.strptime(event["date"], "%Y-%m-%d")
        date_formatted = date_obj.strftime("%B %d, %Y")
        excerpt = event["excerpt"][:120] + "..." if len(event["excerpt"]) > 120 else event["excerpt"]
        filename = f"{event['slug']}.html"
        
        card = f"""                    <article class="glass-card match-card">
                        <img src="{event['poster']}" alt="{event['title']}" class="match-poster" loading="lazy">
                        <div class="match-header">
                            <h3 class="match-title">{event['title']}</h3>
                            <span class="league-badge {event['leagueSlug']}">{event['league']}</span>
                        </div>
                        <div class="match-meta">
                            <div class="match-meta-item">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
                                    <line x1="16" y1="2" x2="16" y2="6"></line>
                                    <line x1="8" y1="2" x2="8" y2="6"></line>
                                    <line x1="3" y1="10" x2="21" y2="10"></line>
                                </svg>
                                <span>{date_formatted}</span>
                            </div>
                            <div class="match-meta-item">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <circle cx="12" cy="12" r="10"></circle>
                                    <polyline points="12 6 12 12 16 14"></polyline>
                                </svg>
                                <span>{event['time']} GMT</span>
                            </div>
                            <div class="match-meta-item">
                                <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                    <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
                                    <circle cx="12" cy="10" r="3"></circle>
                                </svg>
                                <span>{event['stadium']}</span>
                            </div>
                        </div>
                        <p class="match-excerpt">{excerpt}</p>
                        <a href="{filename}" class="match-link">
                            Read More & Watch Live
                            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
                                <line x1="5" y1="12" x2="19" y2="12"></line>
                                <polyline points="12 5 19 12 12 19"></polyline>
                            </svg>
                        </a>
                    </article>"""
        cards_html.append(card)
    
    # Read index.html
    with open(index_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Find matches-grid and replace content
    # Find the opening tag
    grid_start = content.find('<div class="matches-grid"')
    if grid_start == -1:
        print("❌ Could not find matches-grid in index.html")
        return False
    
    # Find the closing </div> before <!-- Pagination
    pagination_start = content.find('<!-- Pagination', grid_start)
    if pagination_start == -1:
        print("❌ Could not find Pagination comment in index.html")
        return False
    
    # Find the last </div> before pagination
    grid_end = content.rfind('</div>', grid_start, pagination_start)
    if grid_end == -1:
        print("❌ Could not find closing </div> for matches-grid")
        return False
    
    # Extract the opening tag
    grid_opening_end = content.find('>', grid_start)
    grid_opening = content[grid_start:grid_opening_end + 1]
    
    # Build new content - remove all existing cards and empty placeholders
    new_content = grid_opening + "\n" + "\n".join(cards_html) + "\n                </div>"
    content = content[:grid_start] + new_content + content[grid_end + 6:]  # +6 for "</div>"
    
    # Write back
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"✅ Successfully regenerated {len(cards_html)} match cards in index.html")
    return True

if __name__ == "__main__":
    regenerate_index_cards()
