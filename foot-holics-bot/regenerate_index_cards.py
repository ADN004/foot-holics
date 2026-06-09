#!/usr/bin/env python3
"""
Maintenance utility for data/events.json.

The homepage now loads match cards dynamically via /api/articles, which
serves events directly from data/events.json.  Static match-card HTML is no
longer injected into index.html, so the old index.html regeneration logic
has been replaced with this JSON maintenance tool.

Operations available:
  --validate   Check all entries for required fields (default)
  --sort       Re-sort entries by date descending and write back
  --report     Print a summary of all events
  --fix        Remove entries that are missing required fields
"""

import json
import os
import re
import sys
import argparse
from datetime import datetime

REQUIRED_FIELDS = [
    "id", "date", "time", "slug", "title",
    "homeTeam", "awayTeam", "league", "leagueSlug",
    "stadium", "poster", "excerpt", "status", "streams",
]


def get_project_root():
    bot_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(bot_dir)


def load_events(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_events(path, events):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)
    print(f"✅ Saved {len(events)} events to {path}")


def validate_events(events):
    errors = []
    for i, ev in enumerate(events):
        missing = [k for k in REQUIRED_FIELDS if k not in ev or ev[k] is None]
        if missing:
            errors.append((i, ev.get("slug", f"<entry {i}>"), missing))
    return errors


def sort_events(events):
    def sort_key(ev):
        try:
            return datetime.strptime(ev.get("date", "1970-01-01"), "%Y-%m-%d")
        except ValueError:
            return datetime.min

    return sorted(events, key=sort_key, reverse=True)


def print_report(events):
    print(f"\n{'='*60}")
    print(f"  events.json — {len(events)} entries")
    print(f"{'='*60}")
    for ev in events:
        status_icon = {"live": "🔴", "upcoming": "🟡", "finished": "⚪"}.get(
            ev.get("status", "").lower(), "❓"
        )
        print(
            f"  {status_icon}  [{ev.get('date','')}] {ev.get('title','(no title)')}"
            f"  ({ev.get('league','')})"
        )
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--validate", action="store_true", help="Validate all entries (default behaviour)")
    parser.add_argument("--sort",     action="store_true", help="Re-sort entries by date descending and save")
    parser.add_argument("--report",   action="store_true", help="Print a summary of all events")
    parser.add_argument("--fix",      action="store_true", help="Remove entries with missing required fields and save")
    args = parser.parse_args()

    root_dir    = get_project_root()
    events_path = os.path.join(root_dir, "data", "events.json")

    if not os.path.exists(events_path):
        print(f"❌ events.json not found at {events_path}")
        sys.exit(1)

    events = load_events(events_path)
    print(f"📂 Loaded {len(events)} events from {events_path}")

    if args.report:
        print_report(events)

    errors = validate_events(events)
    if errors:
        print(f"\n⚠️  {len(errors)} entries have missing required fields:")
        for idx, slug, missing in errors:
            print(f"   [{idx}] {slug}: missing {missing}")
    else:
        print(f"✅ All {len(events)} entries pass validation")

    if args.fix and errors:
        bad_indices = {i for i, _, _ in errors}
        events = [ev for i, ev in enumerate(events) if i not in bad_indices]
        print(f"🗑️  Removed {len(bad_indices)} invalid entries")
        save_events(events_path, events)

    if args.sort:
        sorted_events = sort_events(events)
        save_events(events_path, sorted_events)
        print("📅 Sorted by date descending")

    if not any([args.report, args.sort, args.fix]):
        # Default: just validate (already done above)
        if errors:
            sys.exit(1)


if __name__ == "__main__":
    main()
