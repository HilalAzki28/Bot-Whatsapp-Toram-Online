import urllib.request
import ssl
import re
from bs4 import BeautifulSoup
import json
import os
import time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

EVENT_KEYWORDS = [
    "anniv", "festive", "xmas", "christmas", "valentine", "white day", 
    "summer", "halloween", "hanami", "sakura", "easter", "collab", "alchemia", 
    "stardust", "sunflower", "snow", "autumn", "moonlight", "maple",
    "cherry pink", "gold potum", "silver potum", "potum", "mycodian",
    "treat", "love", "cacao", "candy", "spring", "zarth", "amalgam", "mimesia", "chocolate",
    "megiston", "event"
]

def scrape_all_arrows():
    print("Scraping all arrow pages from Coryn Club...")
    all_arrows = []
    
    # 8 pages: p=0 to p=7
    for page in range(8):
        url = f"https://coryn.club/item.php?&show=11&type=7&order=id%20DESC&p={page}"
        print(f"Fetching page {page}...")
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=20) as r:
                html = r.read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            continue

        soup = BeautifulSoup(html, 'html.parser')
        titles = soup.find_all('div', class_='card-title')

        for t in titles:
            a_tag = t.find('a')
            span_tag = t.find('span')
            if not a_tag:
                continue
            item_name = a_tag.text.strip()
            item_type = span_tag.text.strip() if span_tag else ""
            if "[Arrow]" not in item_type:
                continue

            card = t.parent
            
            # Badges (span or div)
            badges = [b.text.strip() for b in card.find_all(class_='item-meta-badge')]
            
            # Note
            note_el = card.find(class_='item-meta-note-body')
            note_text = note_el.text.strip() if note_el else ""

            # Check stats
            element = "Normal (Tanpa Elemen)"
            atk = ""
            stats_list = []
            stat_grid = card.find('div', class_='table-grid')
            if stat_grid:
                for row in stat_grid.find_all('div', recursive=False):
                    cols = [c.text.strip().replace('\n', ' ') for c in row.find_all('div', recursive=False) if c.text.strip()]
                    if len(cols) >= 2 and cols[0] != "Stat/Effect":
                        stat_line = f"{cols[0]}: {cols[1]}"
                        stats_list.append(stat_line)
                        if "base atk" in cols[0].lower():
                            atk = cols[1]
                        if "element" in cols[0].lower():
                            element = cols[0].replace("Element", "").strip()

            # Drops and Obtains
            drops = []
            accordions = card.find_all('ul', class_='accordion')
            for acc in accordions:
                for li in acc.find_all('li'):
                    hdr = li.find('div')
                    hdr_txt = hdr.text.strip().lower() if hdr else ""
                    if "obtain" in hdr_txt:
                        pag_items = li.find_all('div', class_='pagination-js-item')
                        if pag_items:
                            for p_item in pag_items:
                                cols = [c.get_text(separator=' ', strip=True) for c in p_item.find_all('div', recursive=False) if c.get_text(strip=True)]
                                cols = [c for c in cols if c != "-"]
                                if cols:
                                    drops.append(cols)
                        else:
                            grid = li.find('div', class_='table-grid')
                            if grid:
                                for row in grid.find_all('div', recursive=False):
                                    cols = [c.get_text(separator=' ', strip=True) for c in row.find_all('div', recursive=False) if c.get_text(strip=True)]
                                    if cols and cols[0] not in ["Monster", "Dye", "Map", "Monster | Dye | Map"]:
                                        clean_cols = [c for c in cols if c not in ["Monster", "Dye", "Map", "-"]]
                                        if clean_cols:
                                            drops.append(clean_cols)
                    elif "recipe" in hdr_txt:
                        r_txt = li.get_text(separator=' ', strip=True).replace("Recipe", "").strip()
                        if r_txt:
                            drops.append(["Craft Blacksmith", r_txt])

            # If no drops found in accordion, check note_text
            if not drops and note_text:
                m_drop = re.search(r'Dropped by (.*?)(?:\.|\n|$)', note_text)
                if m_drop:
                    drops.append([f"Drop: {m_drop.group(1)}", "Event Map / Boss"])

            # Determine event status
            is_event = False
            event_name = ""
            for b in badges:
                b_clean = b.replace("Event:", "").strip()
                if "event" in b.lower() or any(ev in b.lower() for ev in EVENT_KEYWORDS):
                    is_event = True
                    event_name = b_clean
            
            name_lower = item_name.lower()
            if not is_event:
                for kw in EVENT_KEYWORDS:
                    if kw in name_lower:
                        is_event = True
                        event_name = f"Event ({kw.title()})"
                        break

            if not is_event and note_text:
                if any(ev in note_text.lower() for ev in ["event", "limited", "collab", "anniv", "season"]):
                    is_event = True
                    event_name = "Event / Limited"

            # Parse drop list into formatted objects: monster & map
            parsed_drops = []
            for d in drops:
                if len(d) == 1:
                    parsed_drops.append({"monster": d[0], "map": "-"})
                elif len(d) >= 2:
                    m_name = d[0]
                    map_name = d[-1]
                    parsed_drops.append({"monster": m_name, "map": map_name})

            if not is_event:
                for d in parsed_drops:
                    dm = (d['monster'] + ' ' + d['map']).lower()
                    for kw in EVENT_KEYWORDS:
                        if kw in dm:
                            is_event = True
                            event_name = f"Event ({kw.title()})"
                            break
                    if is_event:
                        break

            if not parsed_drops:
                if is_event:
                    parsed_drops.append({"monster": "Craft Blacksmith (Event Limited)", "map": "Event Venue"})
                else:
                    parsed_drops.append({"monster": "Craft Blacksmith / NPC", "map": "Blacksmith / Pandai Besi"})

            arrow_entry = {
                "name": item_name,
                "atk": atk,
                "element": element,
                "is_event": is_event,
                "event_badge": event_name,
                "note": note_text,
                "stats": stats_list,
                "drops": parsed_drops
            }
            all_arrows.append(arrow_entry)

        time.sleep(0.3)

    print(f"Total arrows scraped: {len(all_arrows)}")
    
    # Save to data/arrows_db.json
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    out_path = os.path.join(PROJECT_ROOT, "data", "arrows_db.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_arrows, f, indent=2, ensure_ascii=False)
    print(f"Saved to {out_path}")

if __name__ == "__main__":
    scrape_all_arrows()
