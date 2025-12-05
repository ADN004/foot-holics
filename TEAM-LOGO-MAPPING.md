# Team Logo Mapping Guide

## For Bot.py Implementation

This file contains the complete mapping of team names to their logo paths. Use this in your bot.py to automatically populate team logos.

---

## Python Dictionary for bot.py

```python
# Add this to your bot.py file

TEAM_LOGO_MAPPING = {
    # Premier League
    'arsenal': 'assets/img/logos/teams/premier-league/arsenal.png',
    'aston-villa': 'assets/img/logos/teams/premier-league/aston-villa.png',
    'brentford': 'assets/img/logos/teams/premier-league/brentford.png',
    'brighton': 'assets/img/logos/teams/premier-league/brighton.png',
    'chelsea': 'assets/img/logos/teams/premier-league/chelsea.png',
    'everton': 'assets/img/logos/teams/premier-league/everton.png',
    'fulham': 'assets/img/logos/teams/premier-league/fulham.png',
    'leicester': 'assets/img/logos/teams/premier-league/leicester.png',
    'leicester-city': 'assets/img/logos/teams/premier-league/leicester.png',
    'liverpool': 'assets/img/logos/teams/premier-league/liverpool.png',
    'manchester-city': 'assets/img/logos/teams/premier-league/manchester-city.png',
    'man-city': 'assets/img/logos/teams/premier-league/manchester-city.png',
    'manchester-united': 'assets/img/logos/teams/premier-league/manchester-united.png',
    'man-united': 'assets/img/logos/teams/premier-league/manchester-united.png',
    'newcastle': 'assets/img/logos/teams/premier-league/newcastle.png',
    'newcastle-united': 'assets/img/logos/teams/premier-league/newcastle.png',
    'nottingham-forest': 'assets/img/logos/teams/premier-league/nottingham-forest.png',
    'tottenham': 'assets/img/logos/teams/premier-league/tottenham.png',
    'west-ham': 'assets/img/logos/teams/premier-league/west-ham.png',

    # La Liga
    'athletic-bilbao': 'assets/img/logos/teams/la-liga/athletic-bilbao.png',
    'atletico-madrid': 'assets/img/logos/teams/la-liga/atletico-madrid.png',
    'atletico': 'assets/img/logos/teams/la-liga/atletico-madrid.png',
    'barcelona': 'assets/img/logos/teams/la-liga/barcelona.png',
    'getafe': 'assets/img/logos/teams/la-liga/getafe.png',
    'girona': 'assets/img/logos/teams/la-liga/girona.png',
    'osasuna': 'assets/img/logos/teams/la-liga/osasuna.png',
    'real-betis': 'assets/img/logos/teams/la-liga/real-betis.png',
    'betis': 'assets/img/logos/teams/la-liga/real-betis.png',
    'real-madrid': 'assets/img/logos/teams/la-liga/real-madrid.png',
    'real-sociedad': 'assets/img/logos/teams/la-liga/real-sociedad.png',
    'sevilla': 'assets/img/logos/teams/la-liga/sevilla.png',
    'valencia': 'assets/img/logos/teams/la-liga/valencia.png',
    'villarreal': 'assets/img/logos/teams/la-liga/villarreal.png',

    # Serie A
    'ac-milan': 'assets/img/logos/teams/serie-a/ac-milan.png',
    'milan': 'assets/img/logos/teams/serie-a/ac-milan.png',
    'atalanta': 'assets/img/logos/teams/serie-a/atalanta.png',
    'bologna': 'assets/img/logos/teams/serie-a/bologna.png',
    'fiorentina': 'assets/img/logos/teams/serie-a/fiorentina.png',
    'inter-milan': 'assets/img/logos/teams/serie-a/inter-milan.png',
    'inter': 'assets/img/logos/teams/serie-a/inter-milan.png',
    'juventus': 'assets/img/logos/teams/serie-a/juventus.png',
    'lazio': 'assets/img/logos/teams/serie-a/lazio.png',
    'napoli': 'assets/img/logos/teams/serie-a/napoli.png',
    'roma': 'assets/img/logos/teams/serie-a/roma.png',
    'sassuolo': 'assets/img/logos/teams/serie-a/sassuolo.png',
    'torino': 'assets/img/logos/teams/serie-a/torino.png',
    'udinese': 'assets/img/logos/teams/serie-a/udinese.png',

    # Bundesliga
    'bayer-leverkusen': 'assets/img/logos/teams/bundesliga/bayer-leverkusen.png',
    'leverkusen': 'assets/img/logos/teams/bundesliga/bayer-leverkusen.png',
    'bayern-munich': 'assets/img/logos/teams/bundesliga/bayern-munich.png',
    'bayern': 'assets/img/logos/teams/bundesliga/bayern-munich.png',
    'borussia-dortmund': 'assets/img/logos/teams/bundesliga/borussia-dortmund.png',
    'dortmund': 'assets/img/logos/teams/bundesliga/borussia-dortmund.png',
    'borussia-monchengladbach': 'assets/img/logos/teams/bundesliga/borussia-monchengladbach.png',
    'eintracht-frankfurt': 'assets/img/logos/teams/bundesliga/eintracht-frankfurt.png',
    'frankfurt': 'assets/img/logos/teams/bundesliga/eintracht-frankfurt.png',
    'rb-leipzig': 'assets/img/logos/teams/bundesliga/rb-leipzig.png',
    'leipzig': 'assets/img/logos/teams/bundesliga/rb-leipzig.png',
    'schalke': 'assets/img/logos/teams/bundesliga/schalke.png',
    'vfb-stuttgart': 'assets/img/logos/teams/bundesliga/vfb-stuttgart.png',
    'stuttgart': 'assets/img/logos/teams/bundesliga/vfb-stuttgart.png',
    'werder-bremen': 'assets/img/logos/teams/bundesliga/werder-bremen.png',
    'wolfsburg': 'assets/img/logos/teams/bundesliga/wolfsburg.png',

    # Champions League / European Teams
    'ajax': 'assets/img/logos/teams/champions-league/ajax.png',
    'benfica': 'assets/img/logos/teams/champions-league/benfica.png',
    'celtic': 'assets/img/logos/teams/champions-league/celtic.png',
    'lyon': 'assets/img/logos/teams/champions-league/lyon.png',
    'marseille': 'assets/img/logos/teams/champions-league/marseille.png',
    'monaco': 'assets/img/logos/teams/champions-league/monaco.png',
    'porto': 'assets/img/logos/teams/champions-league/porto.png',
    'psg': 'assets/img/logos/teams/champions-league/psg.png',
    'paris-saint-germain': 'assets/img/logos/teams/champions-league/psg.png',
    'psv': 'assets/img/logos/teams/champions-league/psv.png',
    'rangers': 'assets/img/logos/teams/champions-league/rangers.png',
    'sporting-cp': 'assets/img/logos/teams/champions-league/sporting-cp.png',
    'sporting': 'assets/img/logos/teams/champions-league/sporting-cp.png',
}

def get_team_logo(team_name):
    """
    Get the logo path for a team name.
    Automatically converts team name to slug format.
    Returns default fallback if team not found.
    """
    # Convert to slug
    team_slug = slugify(team_name)

    # Try to find in mapping
    logo_path = TEAM_LOGO_MAPPING.get(team_slug)

    if logo_path:
        return logo_path

    # Fallback: return None (template will show emoji instead)
    return None

def replace_team_logos_in_template(html_content, home_team, away_team):
    """
    Replace [HOME_TEAM_LOGO_PATH] and [AWAY_TEAM_LOGO_PATH] in template.
    """
    home_logo = get_team_logo(home_team)
    away_logo = get_team_logo(away_team)

    # Default fallback
    default_logo = 'assets/img/logos/default-team.png'

    html_content = html_content.replace(
        '[HOME_TEAM_LOGO_PATH]',
        home_logo if home_logo else default_logo
    )

    html_content = html_content.replace(
        '[AWAY_TEAM_LOGO_PATH]',
        away_logo if away_logo else default_logo
    )

    return html_content
```

---

## Usage Example in bot.py

```python
# When generating a match page:

def generate_match_page(home_team, away_team, ...):
    # Read template
    with open('TEMPLATE-event.html', 'r') as f:
        html_template = f.read()

    # Replace team logos
    html_content = replace_team_logos_in_template(html_template, home_team, away_team)

    # Replace other placeholders
    html_content = html_content.replace('[HOME TEAM FULL NAME]', home_team)
    html_content = html_content.replace('[AWAY TEAM FULL NAME]', away_team)
    # ... other replacements

    # Save to file
    with open(f'{match_slug}.html', 'w') as f:
        f.write(html_content)
```

---

## Logo Folder Structure

```
assets/img/logos/teams/
├── premier-league/
│   ├── arsenal.png
│   ├── chelsea.png
│   ├── liverpool.png
│   ├── manchester-city.png
│   ├── manchester-united.png
│   └── ... (15 teams total)
├── la-liga/
│   ├── real-madrid.png
│   ├── barcelona.png
│   ├── atletico-madrid.png
│   └── ... (12 teams total)
├── serie-a/
│   ├── ac-milan.png
│   ├── inter-milan.png
│   ├── juventus.png
│   └── ... (12 teams total)
├── bundesliga/
│   ├── bayern-munich.png
│   ├── borussia-dortmund.png
│   └── ... (10 teams total)
└── champions-league/
    ├── ajax.png
    ├── psg.png
    └── ... (11 teams total)
```

---

## Template Placeholders

In `TEMPLATE-event.html`, use these placeholders:

- `[HOME_TEAM_LOGO_PATH]` - Will be replaced with home team logo path
- `[AWAY_TEAM_LOGO_PATH]` - Will be replaced with away team logo path
- `[HOME TEAM NAME]` - Team name for alt text
- `[AWAY TEAM NAME]` - Team name for alt text

---

## Automatic Fallback

The template now includes automatic fallback:
- If logo image fails to load (`onerror`), it shows a default gradient circle with ⚽ emoji
- This ensures the page never looks broken even if a logo is missing

---

## Testing

To test if logos work:
1. Generate a match with Real Madrid vs Manchester City
2. Check that logos appear in the Teams Block section
3. If logo doesn't load, the fallback emoji should appear

---

**Last Updated:** December 2025
