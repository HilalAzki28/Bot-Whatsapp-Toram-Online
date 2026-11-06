import os
import urllib.request
import urllib.parse
import ssl
import json
import time

def fetch_monsters_chunk(offset, limit=100):
    url = f"https://coryn.club/api/v1/monsters.php?limit={limit}&offset={offset}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            return json.loads(response.read().decode('utf-8', errors='ignore'))
    except Exception as e:
        print(f"Error fetching offset {offset}: {e}")
        return None

def main():
    print("Starting download of monsters database from Coryn Club API...")
    
    # Run once to get total count
    initial_res = fetch_monsters_chunk(0, limit=5)
    if not initial_res or not initial_res.get("success"):
        print("Failed to initialize API request.")
        return
        
    meta = initial_res.get("meta", {})
    total_monsters = meta.get("total", 3500)
    print(f"Total monsters in Coryn Club database: {total_monsters}")
    
    all_bosses_minibosses = []
    limit = 100
    offset = 0
    
    while offset < total_monsters:
        print(f"Fetching monsters {offset} to {offset + limit}...")
        res = fetch_monsters_chunk(offset, limit)
        if res and res.get("success") and res.get("data"):
            data = res["data"]
            for monster in data:
                t_label = monster.get("type_label", "")
                # We only need Bosses and Mini Bosses
                if t_label in ["Boss", "Mini Boss"]:
                    all_bosses_minibosses.append({
                        "id": monster.get("id"),
                        "name": monster.get("name"),
                        "level": monster.get("level"),
                        "type": t_label,
                        "mode": monster.get("mode"),
                        "hp": monster.get("hp"),
                        "exp": monster.get("exp"),
                        "element": monster.get("element_label"),
                        "map": monster.get("map_name"),
                        "limited": monster.get("limited", False)
                    })
            offset += limit
        else:
            print(f"Retrying offset {offset} in 3 seconds...")
            time.sleep(3)
            
        time.sleep(0.3)  # Be polite to the server
        
    print(f"Finished fetching. Found {len(all_bosses_minibosses)} Bosses and Mini Bosses.")
    
    # Save to monsters_db.json
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    output_file = os.path.join(PROJECT_ROOT, "data", "monsters_db.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_bosses_minibosses, f, indent=4, ensure_ascii=False)
        
    print(f"Database successfully saved to {output_file}")

if __name__ == "__main__":
    main()
