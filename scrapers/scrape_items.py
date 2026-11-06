import os
import sys
import urllib.request
import urllib.parse
import ssl
import json
import time

def fetch_items_chunk(offset, limit=100):
    url = f"https://coryn.club/api/v1/items.php?limit={limit}&offset={offset}"
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
    print("Starting download of full items database from Coryn/Raffy Data API...")
    
    initial_res = fetch_items_chunk(0, limit=5)
    if not initial_res or not initial_res.get("success"):
        print("Failed to initialize API request.")
        return
        
    meta = initial_res.get("meta", {})
    total_items = meta.get("total", 8500)
    print(f"Total items in database: {total_items}")
    
    all_items = []
    limit = 100
    offset = 0
    
    while offset < total_items:
        print(f"Fetching items {offset} to {min(offset + limit, total_items)} / {total_items}...")
        res = fetch_items_chunk(offset, limit)
        if res and res.get("success") and res.get("data"):
            data = res["data"]
            all_items.extend(data)
            offset += limit
        else:
            print(f"Retrying offset {offset} in 2 seconds...")
            time.sleep(2)
            
        time.sleep(0.1)  # Fast & polite
        
    print(f"Finished fetching. Total items collected: {len(all_items)}")
    
    # Save to data/raffy_items.json
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)
    output_file = os.path.join(PROJECT_ROOT, "data", "raffy_items.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_items, f, indent=2, ensure_ascii=False)
        
    print(f"Items database successfully saved to {output_file}")

if __name__ == "__main__":
    main()
