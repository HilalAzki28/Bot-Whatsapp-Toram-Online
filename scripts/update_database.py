"""
Script Pembaru Database Mandiri Toram Online (Items, Monsters, Skills, Registlets)
Perintah jalankan: python scripts/update_database.py
"""

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
SCRAPERS_DIR = os.path.join(PROJECT_ROOT, "scrapers")

print("== Memulai pembaruan Database Mandiri Toram Online ==")

def run_scraper(script_name):
    script_path = os.path.join(SCRAPERS_DIR, script_name)
    if os.path.exists(script_path):
        print(f"\n--- Menjalankan {script_name} ---")
        try:
            result = subprocess.run([sys.executable, script_path], check=True)
            print(f"[OK] {script_name} selesai.")
        except Exception as e:
            print(f"[ERROR] Gagal menjalankan {script_name}: {e}")
    else:
        print(f"[WARN] Script {script_name} tidak ditemukan.")

def main():
    # 1. Update Items Database
    run_scraper("scrape_items.py")
    
    # 2. Update Monsters Database
    run_scraper("scrape_monsters.py")
    
    # 3. Update Skills Database
    run_scraper("scrape_skills.py")
    
    # 4. Update Registlets Database
    run_scraper("scrape_registlets.py")
    
    # 5. Update Arrows Database
    run_scraper("scrape_arrows.py")

    print("\n[OK] Pembaruan Seluruh Database Mandiri Toram Online Selesai!")

if __name__ == "__main__":
    main()
