import os
import urllib.request
import urllib.parse
import ssl
import json
import time
from bs4 import BeautifulSoup

def scrape_registlets():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    all_registlets = []
    page = 0
    
    while True:
        url = f"https://coryn.club/registlet.php?&p={page}"
        print(f"Scraping page {page}...")
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
                html = response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"Error loading page {page}: {e}")
            break
            
        soup = BeautifulSoup(html, 'html.parser')
        grid = soup.find('div', class_='registlet-grid')
        if not grid:
            print("No registlet-grid found. Stopping.")
            break
            
        cards = grid.find_all('article', class_='registlet-card')
        if not cards:
            print(f"No cards found on page {page}. Stopping.")
            break
            
        for card in cards:
            # Title
            title_el = card.find('h2', class_='registlet-card__title')
            name = title_el.get_text(strip=True) if title_el else "Unknown"
            
            # Chips
            max_lv = ""
            affects = ""
            chips = card.find_all('span', class_='registlet-chip')
            for chip in chips:
                classes = chip.get('class', [])
                text = chip.get_text(strip=True)
                if 'registlet-chip--accent' in classes:
                    affects = text
                else:
                    max_lv = text
            
            # Effect
            effect_el = card.find('div', class_='registlet-card__effect')
            effect = effect_el.get_text(" ", strip=True) if effect_el else ""
            
            # Obtained From
            obtained_from = []
            sections = card.find_all('div', class_='registlet-card__section')
            for sec in sections:
                title_p = sec.find('p', class_='registlet-card__section-title')
                if title_p and title_p.get_text(strip=True) == 'Obtained From':
                    # Check empty
                    empty_note = sec.find('p', class_='registlet-empty-note')
                    if empty_note:
                        obtained_from.append(empty_note.get_text(strip=True))
                    else:
                        sources = sec.find_all('div', class_='registlet-source')
                        for src in sources:
                            strong_el = src.find('strong')
                            span_el = src.find('span')
                            strong_txt = strong_el.get_text(strip=True) if strong_el else ""
                            span_txt = span_el.get_text(strip=True) if span_el else ""
                            if strong_txt and span_txt:
                                obtained_from.append(f"{strong_txt} ({span_txt})")
                            elif strong_txt:
                                obtained_from.append(strong_txt)
                            elif span_txt:
                                obtained_from.append(span_txt)
            
            obtained_str = ", ".join(obtained_from) if obtained_from else "No drop source recorded yet."
            
            all_registlets.append({
                "name": name,
                "max_lv": max_lv,
                "affects": affects,
                "effect": effect,
                "obtained_from": obtained_str
            })
            
        print(f"Page {page} done. Total registlets: {len(all_registlets)}")
        page += 1
        time.sleep(0.3)
        
    return all_registlets

def main():
    registlets = scrape_registlets()
    print(f"Scraped {len(registlets)} registlets in total.")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    output_file = os.path.join(PROJECT_ROOT, "data", "registlets_db.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(registlets, f, indent=4, ensure_ascii=False)
    print(f"Saved to {output_file} successfully.")

if __name__ == "__main__":
    main()
