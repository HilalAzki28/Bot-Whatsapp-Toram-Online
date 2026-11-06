import os
import urllib.request
import urllib.parse
import ssl
import json
import time
from bs4 import BeautifulSoup

trees = [
    # Weapon
    "Blade", "Shot", "Magic", "Martial", "Halberd", "Mononofu", "DualSword", "Crusher", "Sprite",
    # Buff
    "Shield", "Dagger", "Knight", "Priest", "Hunter", "Assassin", "Wizard", "Guard", "DarkPower", "MagicBlade", "Barehand", "Ninja", "Partisan", "Necromancer",
    # Assist
    "Survival", "Support", "Battle", "Minstrel", "Dancer", "Golem",
    # Other
    "Smith", "Alchemy", "Tamer", "Scroll"
]

def scrape_tree(tree_name):
    url = f"https://coryn.club/skill.php?tree={urllib.parse.quote(tree_name)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error scraping tree {tree_name}: {e}")
        return []

    soup = BeautifulSoup(html, 'html.parser')
    container = soup.find('div', class_='card-container-1')
    if not container:
        print(f"No card-container-1 found for tree {tree_name}")
        return []

    skills = container.find_all('div', recursive=False)
    results = []
    
    for skill in skills:
        title_p = skill.find('p', class_='card-title')
        if not title_p:
            continue
        name = title_p.get_text(strip=True)
        
        medium_p = skill.find('p', class_='medium')
        level_info = medium_p.get_text(strip=True) if medium_p else ""
        
        req_div = skill.find('div', style=lambda s: s and 'justify-self:end' in s.replace(' ', ''))
        req_text = req_div.get_text(" ", strip=True) if req_div else ""
        
        props = {}
        prop_container = skill.find('div', class_='monster-prop')
        if prop_container:
            for div in prop_container.find_all('div', recursive=False):
                lbl_p = div.find('p', class_='accent-bold')
                if lbl_p:
                    lbl = lbl_p.get_text(strip=True)
                    val_p = div.find(lambda tag: tag.name == 'p' and 'accent-bold' not in tag.get('class', []))
                    if val_p:
                        val = val_p.get_text(" ", strip=True)
                        props[lbl] = val
                    else:
                        p_elements = div.find_all('p')
                        if len(p_elements) > 1:
                            props[lbl] = " ".join([p.get_text(" ", strip=True) for p in p_elements[1:]])
        
        skill_data = {
            "name": name,
            "tree": tree_name,
            "level_info": level_info,
            "weapon_req": req_text,
            "type": props.get("Type", ""),
            "element": props.get("Element", ""),
            "mp": props.get("MP", ""),
            "combo_start": props.get("Combo start", ""),
            "combo_middle": props.get("Combo middle", ""),
            "range": props.get("Range", ""),
            "description": props.get("Description", "")
        }
        results.append(skill_data)
        
    return results

def main():
    all_skills = []
    print("Starting Toram Online skills scraping from Coryn Club...")
    for idx, tree in enumerate(trees):
        print(f"[{idx+1}/{len(trees)}] Scraping {tree} skills...")
        skills = scrape_tree(tree)
        print(f"Found {len(skills)} skills in {tree} tree.")
        all_skills.extend(skills)
        time.sleep(0.5)  # Sleep to be polite to the server
        
    # Save results to skills_db.json
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    output_file = os.path.join(PROJECT_ROOT, "data", "skills_db.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_skills, f, indent=4, ensure_ascii=False)
        
    print(f"Scraping completed! Total skills parsed: {len(all_skills)}")
    print(f"Database saved to {output_file}")

if __name__ == "__main__":
    main()
