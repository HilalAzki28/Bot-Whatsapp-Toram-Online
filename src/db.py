import os
import json
import urllib.request
import urllib.parse
import ssl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Cache variables to avoid loading JSON files on every command call
_crysta_upgrades = None
_skills_db = None
_monsters_db = None
_registlets_db = None
_items_db = None
_arrows_db = None
_item_translations = None
_item_trans_en_to_id = None
_item_trans_id_to_en = None

def get_item_translations():
    """Memuat kamus terjemahan nama item Toram Online (Inggris <-> Indonesia)"""
    global _item_translations, _item_trans_en_to_id, _item_trans_id_to_en
    if _item_translations is None:
        file_path = os.path.join(DATA_DIR, "item_translations.json")
        _item_trans_en_to_id = {}
        _item_trans_id_to_en = {}
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    _item_translations = json.load(f)
                    if isinstance(_item_translations, dict):
                        for en_k, id_v in _item_translations.items():
                            if en_k and id_v:
                                en_clean = en_k.strip()
                                id_clean = id_v.strip()
                                _item_trans_en_to_id[en_clean.lower()] = id_clean
                                _item_trans_id_to_en[id_clean.lower()] = en_clean
            else:
                _item_translations = {}
        except Exception as e:
            print(f"Error loading item_translations.json: {e}")
            _item_translations = {}
    return _item_translations

import re

HEAD_NOUNS = {
    "Sword": "Pedang", "Greatsword": "Pedang Besar", "Katana": "Katana",
    "Bow": "Busur", "Bowgun": "Pistol Busur", "Staff": "Tongkat",
    "Knuckles": "Tinju", "Knuckle": "Tinju", "Halberd": "Tombak Halberd", "Arrow": "Panah",
    "Shield": "Perisai", "Dagger": "Belati", "Blade": "Pedang", "Scythe": "Sabit",
    "Lance": "Tombak Kavaleri", "Spear": "Tombak", "Glaive": "Glaive",
    "Mace": "Gada", "Hammer": "Palu", "Axe": "Kapak", "Rod": "Tongkat", "Cane": "Tongkat",
    "Bat": "Tongkat Pemukul", "Tonfa": "Tonfa", "Gun": "Pistol", "Whip": "Cambuk",
    
    "Garb": "Zirah", "Armor": "Zirah", "Mail": "Zirah", "Coat": "Mantel",
    "Suit": "Jas", "Robe": "Jubah", "Dress": "Gaun", "Costume": "Kostum",
    "Outfit": "Pakaian", "Uniform": "Seragam", "Vest": "Rompi", "Kimono": "Kimono",
    "Cloak": "Jubah", "Cape": "Jubah Pendek",
    
    "Ring": "Cincin", "Talisman": "Jimat", "Charm": "Jimat", "Bangle": "Gelang",
    "Bracelet": "Gelang", "Earring": "Anting", "Necklace": "Kalung", "Strap": "Tali Kulit",
    "Amulet": "Jimat", "Pendant": "Liontin", "Brooch": "Bros", "Belt": "Sabuk",
    "Sash": "Selendang Pinggang", "Band": "Pita Ikat",
    
    "Hat": "Topi", "Cap": "Topi", "Mask": "Topeng", "Helm": "Helm",
    "Helmet": "Helm", "Crown": "Mahkota", "Tiara": "Tiara", "Halo": "Halo",
    "Wings": "Sayap", "Ribbon": "Pita", "Headband": "Bando", "Hairpin": "Jepit Rambut",
    "Circlet": "Mahkota Lingkar", "Beret": "Baret", "Bandana": "Bandana",
    "Scarf": "Selendang", "Eyepatch": "Penutup Mata", "Glasses": "Kacamata",
    
    "Horn": "Tanduk", "Horns": "Tanduk", "Tail": "Ekor", "Eye": "Mata",
    "Eyes": "Mata", "Skin": "Kulit", "Hide": "Kulit", "Fur": "Bulu",
    "Claw": "Cakar", "Claws": "Cakar", "Tooth": "Gigi", "Teeth": "Gigi",
    "Fang": "Taring", "Fangs": "Taring", "Tusk": "Taring", "Tusks": "Taring",
    "Bone": "Tulang", "Bones": "Tulang", "Face": "Wajah", "Hand": "Tangan",
    "Fist": "Tinju", "Fists": "Tinju", "Hair": "Rambut", "Beard": "Janggut",
    "Moustache": "Kumis", "Heart": "Jantung", "Soul": "Jiwa", "Blood": "Darah",
    "Tear": "Air Mata", "Tears": "Air Mata", "Feather": "Bulu", "Feathers": "Bulu",
    "Scale": "Sisik", "Scales": "Sisik", "Shell": "Tempurung",
    
    "Ore": "Bijih", "Wood": "Kayu", "Cloth": "Kain", "Stone": "Batu",
    "Crystal": "Kristal", "Potion": "Ramuan", "Ticket": "Tiket", "Bottle": "Botol",
    "Box": "Kotak", "Scroll": "Gulungan", "Meat": "Daging", "Fluid": "Cairan",
    "Liquid": "Cairan", "Fragment": "Serpihan", "Piece": "Potongan", "Shard": "Pecahan",
    "Root": "Akar", "Seed": "Benih", "Flower": "Bunga", "Leaf": "Daun",
    "Branch": "Ranting", "Bark": "Kulit Kayu", "Jerky": "Dendeng",
    "Apple": "Apel", "Candy": "Permen", "Cookie": "Kue", "Cake": "Kue", "Soup": "Sup",
    "Card": "Kartu", "Book": "Buku", "Grimoire": "Kitab Sihir", "Tome": "Kitab",
    "Rune": "Rune", "Emblem": "Lambang", "Badge": "Lencana", "Coin": "Koin", "Medal": "Medali",
    "Pouch": "Kantung", "Bag": "Tas", "Sack": "Karung", "Basket": "Keranjang",
    "Mirror": "Cermin", "Key": "Kunci", "Bell": "Lonceng", "Orb": "Bola Kristal",
    "Boots": "Sepatu Bot", "Shoes": "Sepatu", "Sandals": "Sandal",
    "Gloves": "Sarung Tangan", "Gauntlet": "Sarung Tangan Besi", "Bracer": "Pelindung Lengan",
    
    "Rattle": "Kerincingan", "Wisp": "Gumpalan Roh", "Clown": "Badut", "Titan": "Titan",
    "Octopus": "Gurita", "Passion": "Gairah", "Shaman": "Dukun", "Scarecrow": "Orang-orangan Sawah",
    "Rat": "Tikus", "Manifest": "Manifestasi", "Grace": "Karunia", "Blessing": "Berkat",
    "Remnant": "Sisa", "Shadow": "Bayangan", "Cavalier": "Ksatria", "Fairy": "Peri", "Doll": "Boneka"
}

MODIFIERS = {
    "Fire": "Api", "Flame": "Api", "Water": "Air", "Aqua": "Air", "Wind": "Angin",
    "Earth": "Bumi", "Light": "Cahaya", "Dark": "Gelap", "Ice": "Es",
    "Thunder": "Petir", "Lightning": "Kilat", "Holy": "Suci", "Sacred": "Keramat",
    "Evil": "Jahat", "Cursed": "Terkutuk", "Ancient": "Kuno", "Iron": "Besi",
    "Steel": "Baja", "Gold": "Emas", "Golden": "Emas", "Silver": "Perak",
    "Bronze": "Perunggu", "Copper": "Tembaga", "Platinum": "Platina", "Mithril": "Mitril",
    "Mythril": "Mitril", "Red": "Merah", "Crimson": "Merah Tua", "Scarlet": "Merah Menyala",
    "Blue": "Biru", "Azure": "Biru Langit", "Green": "Hijau", "Black": "Hitam",
    "White": "Putih", "Yellow": "Kuning", "Purple": "Ungu", "Violet": "Ungu",
    "Forest": "Hutan", "Mountain": "Gunung", "Sea": "Laut", "Ocean": "Samudra",
    "Moon": "Bulan", "Sun": "Matahari", "Solar": "Matahari", "Star": "Bintang",
    "Stardust": "Debu Bintang", "Dragon": "Naga", "Beast": "Binatang",
    "Demon": "Iblis", "Devil": "Iblis", "Angel": "Malaikat", "Ghost": "Hantu",
    "Spirit": "Roh", "Phantom": "Fantasma", "Knight": "Ksatria", "Mage": "Penyihir",
    "Wizard": "Penyihir", "Witch": "Penyihir", "Hunter": "Pemburu",
    "Queen": "Ratu", "Empress": "Ratu", "King": "Raja", "Emperor": "Kaisar",
    "Lord": "Tuan", "Warrior": "Pendekar", "Soldier": "Prajurit",
    "Broken": "Rusak", "Old": "Tua", "Rusty": "Berkarat", "Sharp": "Tajam",
    "Pointed": "Runcing", "Heavy": "Berat", "Lightweight": "Ringan",
    "Short": "Pendek", "Long": "Panjang", "Great": "Besar", "Giant": "Raksasa",
    "Little": "Kecil", "Small": "Kecil", "Wild": "Liar", "Magic": "Sihir",
    "Magical": "Gaib", "Mysterious": "Misterius", "Toxic": "Racun", "Poison": "Racun",
    "Wooden": "Kayu", "Nailed": "Berpaku", "Mystic": "Mistis", "Chaos": "Kekacauan",
    "Abyssal": "Jurang Maut", "Fallen": "Jatuh", "Shining": "Bercahaya",
    "Brutal": "Brutal", "Furious": "Murka", "Silent": "Sunyi", "Deep": "Dalam",
    "Rough": "Kasar", "Tough": "Keras", "Soft": "Lembut", "Sweet": "Manis",
    "Bitter": "Pahit", "Spicy": "Pedas", "Hot": "Panas", "Cold": "Dingin"
}

PAREN_TYPES = {
    "(Staff)": "(Tongkat)",
    "(Knuckle)": "(Tinju)",
    "(Knuckles)": "(Tinju)",
    "(Sword)": "(Pedang)",
    "(1 Handed Sword)": "(Pedang 1 Tangan)",
    "(2 Handed Sword)": "(Pedang 2 Tangan)",
    "(Bow)": "(Busur)",
    "(Bowgun)": "(Pistol Busur)",
    "(Halberd)": "(Tombak Halberd)",
    "(Katana)": "(Katana)",
    "(Magic Device)": "(Alat Sihir)",
    "(Shield)": "(Perisai)",
    "(Dagger)": "(Belati)",
    "(Arrow)": "(Panah)",
    "(Armor)": "(Zirah)",
    "(Additional)": "(Tambahan)",
    "(Special)": "(Khusus)"
}

def smart_toram_translation(en_name: str) -> str:
    name = en_name.strip()
    if not name:
        return name
        
    # 1. Cek akhiran dalam tanda kurung seperti (Staff) -> (Tongkat)
    paren_suffix = ""
    work_name = name
    for p_en, p_id in PAREN_TYPES.items():
        if work_name.endswith(p_en):
            paren_suffix = " " + p_id
            work_name = work_name[:-len(p_en)].strip()
            break
            
    # 2. Cek possessive 's (misal Aba's Face -> Wajah Aba, Lucia's Cane -> Tongkat Lucia)
    m_poss = re.match(r"^([A-Za-z0-9\s]+)'s\s+(.+)$", work_name)
    if m_poss:
        owner = m_poss.group(1).strip()
        item_part = m_poss.group(2).strip()
        translated_item = smart_toram_translation(item_part)
        return f"{translated_item} {owner}{paren_suffix}"
        
    words = work_name.split()
    if not words:
        return name
    
    has_suffix = re.match(r'^[IVX0-9]+$', words[-1]) or words[-1].startswith("(")
    if has_suffix and len(words) >= 2:
        suffix_part = words[-1]
        base_words = words[:-1]
    else:
        suffix_part = ""
        base_words = words
        
    last_w = base_words[-1]
    clean_last = last_w.strip("()[],.'")
    
    if len(base_words) >= 2 and f"{base_words[-2]} {base_words[-1]}" in HEAD_NOUNS:
        head_en = f"{base_words[-2]} {base_words[-1]}"
        head_id = HEAD_NOUNS[head_en]
        mod_words = base_words[:-2]
    elif clean_last in HEAD_NOUNS:
        head_id = HEAD_NOUNS[clean_last]
        mod_words = base_words[:-1]
    else:
        if paren_suffix:
            return f"{work_name}{paren_suffix}"
        return name
        
    if mod_words:
        translated_mods = [MODIFIERS.get(m.strip("()[],.'"), m) for m in mod_words]
        res = f"{head_id} {' '.join(translated_mods)}"
    else:
        res = head_id
        
    if suffix_part:
        res = f"{res} {suffix_part}"
    if paren_suffix:
        res = f"{res}{paren_suffix}"
    return res

def get_item_bilingual_name(name: str) -> str:
    """Mengembalikan format nama dua bahasa: 'Nama Inggris / Nama Indonesia' (misal: 'Mycodian / Sanmurbon')"""
    if not name:
        return ""
    name_clean = name.strip()
    name_low = name_clean.lower()
    get_item_translations()
    
    # 1. Cek jika name adalah Inggris di kamus eksplisit
    if name_low in _item_trans_en_to_id:
        id_name = _item_trans_en_to_id[name_low]
        if id_name.lower() != name_low:
            return f"{name_clean} / {id_name}"
        return name_clean
        
    # 2. Cek jika name adalah Indonesia di kamus eksplisit
    if name_low in _item_trans_id_to_en:
        en_name = _item_trans_id_to_en[name_low]
        if en_name.lower() != name_low:
            return f"{en_name} / {name_clean}"
        return name_clean

    # 3. Smart translator berbasis pola istilah Toram Online untuk seluruh item raffy.club
    smart_id = smart_toram_translation(name_clean)
    if smart_id and smart_id.lower() != name_low:
        return f"{name_clean} / {smart_id}"
        
    return name_clean

def get_translation_search_terms(query: str) -> list[str]:
    """Mengembalikan variasi query dalam bahasa Inggris dan Indonesia untuk pencarian dua arah"""
    q_low = query.strip().lower()
    terms = [q_low]
    get_item_translations()
    
    if q_low in _item_trans_id_to_en:
        en_equiv = _item_trans_id_to_en[q_low].lower()
        if en_equiv not in terms:
            terms.append(en_equiv)
            
    if q_low in _item_trans_en_to_id:
        id_equiv = _item_trans_en_to_id[q_low].lower()
        if id_equiv not in terms:
            terms.append(id_equiv)
            
    # Cari juga partial match di kamus
    for id_k, en_v in _item_trans_id_to_en.items():
        if q_low == id_k or (len(q_low) >= 4 and q_low in id_k):
            if en_v.lower() not in terms:
                terms.append(en_v.lower())
    for en_k, id_v in _item_trans_en_to_id.items():
        if q_low == en_k or (len(q_low) >= 4 and q_low in en_k):
            if id_v.lower() not in terms:
                terms.append(id_v.lower())

    smart_term = smart_toram_translation(q_low)
    if smart_term and smart_term.lower() not in terms:
        terms.append(smart_term.lower())
                
    return terms

def get_items_db():
    """Load and cache raffy_items.json"""
    global _items_db
    if _items_db is None:
        file_path = os.path.join(DATA_DIR, "raffy_items.json")
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    _items_db = json.load(f)
            else:
                _items_db = []
        except Exception as e:
            print(f"Error loading raffy_items.json: {e}")
            _items_db = []
    return _items_db

def get_item_category_key(type_label: str) -> str:
    lbl = (type_label or "").lower().replace("[", "").replace("]", "").strip()
    if any(w in lbl for w in ["crysta", "xtall"]):
        return "xtall"
    elif any(w in lbl for w in ["sword", "katana", "halberd", "bow", "staff", "magic device", "knuckle", "weapon", "senjata", "bowgun", "shield", "arrow", "dagger"]):
        return "wp"
    elif "armor" in lbl or "zirah" in lbl:
        return "armor"
    elif "additional" in lbl or "tambahan" in lbl:
        return "add"
    elif "special" in lbl or "ring" in lbl or "cincin" in lbl:
        return "ring"
    elif "material" in lbl or "bahan" in lbl:
        return "mats"
    elif any(w in lbl for w in ["use", "item", "konsumsi", "usable", "potion", "box"]):
        return "use"
    return "item"

def fetch_online_items_by_name(query: str) -> list:
    """Fetch items from Coryn/Raffy API online when query is not found locally"""
    url = f"https://coryn.club/api/v1/items.php?name={urllib.parse.quote(query)}&limit=20"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            res = json.loads(resp.read().decode('utf-8', errors='ignore'))
            if res.get("success") and res.get("data"):
                return res["data"]
    except Exception as e:
        print(f"Error fetching online items: {e}")
    return []

def get_item_detail_from_api(item_id: int | str) -> dict | None:
    """Fetch complete detail (stats, obtains) for a single item by ID"""
    url = f"https://coryn.club/api/v1/items.php?id={item_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            res = json.loads(resp.read().decode('utf-8', errors='ignore'))
            if res.get("success") and res.get("data"):
                return res["data"]
    except Exception as e:
        print(f"Error fetching item detail #{item_id}: {e}")
    return None

def search_local_items(query: str, category_key: str = "item"):
    """Cari item secara instan dari database lokal raffy_items.json & crysta_upgrades.json (dengan fallback online)"""
    items = get_items_db() or []
    crystas_db = get_crysta_upgrades() or {}

    q = query.lower().strip()
    search_terms = get_translation_search_terms(q)
    results = []
    seen_ids = set()

    # 1. Cek pencarian ID (#10182)
    if q.startswith("#"):
        item_id = q[1:].strip()
        for item in items:
            if str(item.get("id", "")) == item_id:
                return [item]
        if item_id in crystas_db:
            c_info = crystas_db[item_id]
            return [{
                "id": int(item_id),
                "name": c_info["name"],
                "type_label": "Crysta",
                "stats": f"Crysta Item (Ketik `,rute #{item_id}` untuk melihat rute upgrade).",
                "obtaining": "Drop Boss / Upgrade",
                "upgrades_id": c_info.get("upgrades_id")
            }]
        # Fallback query ID online jika tidak ada di lokal
        if item_id.isdigit():
            online_item = get_item_detail_from_api(int(item_id))
            if online_item:
                return [online_item]

    # 2. Pencarian Nama di raffy_items.json
    for item in items:
        raw_name = item.get("name", "")
        name = raw_name.lower()
        t_label = item.get("type_label", "")

        if category_key != "item" and get_item_category_key(t_label) != category_key:
            continue

        bilingual = get_item_bilingual_name(raw_name).lower()
        if any(term in name or term in bilingual for term in search_terms) or q == str(item.get("id", "")):
            results.append(item)
            if "id" in item:
                seen_ids.add(str(item["id"]))

    # 3. Pencarian Nama di crysta_upgrades.json jika kategori 'item' atau 'xtall'
    if category_key in ("item", "xtall"):
        for cid, c_info in crystas_db.items():
            if cid in seen_ids:
                continue
            c_name = c_info.get("name", "")
            c_bilingual = get_item_bilingual_name(c_name).lower()
            if any(term in c_name.lower() or term in c_bilingual for term in search_terms) or q == cid:
                results.append({
                    "id": int(cid),
                    "name": c_name,
                    "type_label": "Crysta",
                    "stats": f"Crysta Item (Ketik `,rute #{cid}` untuk melihat rute upgrade).",
                    "obtaining": "Drop Boss / Upgrade",
                    "upgrades_id": c_info.get("upgrades_id")
                })
                seen_ids.add(cid)

    # 4. Fallback online jika tidak ada hasil lokal sama sekali
    if not results and not q.startswith("#"):
        online_items = fetch_online_items_by_name(q)
        for item in online_items:
            t_label = item.get("type_label", "")
            if category_key != "item" and get_item_category_key(t_label) != category_key:
                continue
            results.append(item)

    return results

def search_local_monsters(query: str, m_type_filter: str | None = None):
    """Cari monster secara instan dari database lokal monsters_db.json"""
    monsters = get_monsters_db()
    if not monsters:
        return []

    q = query.lower().strip()
    search_terms = get_translation_search_terms(q)
    results = []

    # 1. Cek ID
    if q.startswith("#"):
        mon_id = q[1:].strip()
        for mon in monsters:
            if str(mon.get("id", "")) == mon_id:
                return [mon]

    # 2. Nama & Filter Tipe
    for mon in monsters:
        name = mon.get("name", "").lower()
        m_type = str(mon.get("type", "")).lower()

        if m_type_filter == "boss" and m_type != "boss":
            continue
        elif m_type_filter in ("mboss", "miniboss") and m_type != "mini boss":
            continue
        elif m_type_filter in ("mob", "normal") and m_type in ("boss", "mini boss"):
            continue

        if any(term in name for term in search_terms) or q == str(mon.get("id", "")):
            results.append(mon)

    return results

def get_crysta_upgrades():
    """Load and cache crysta_upgrades.json"""
    global _crysta_upgrades
    if _crysta_upgrades is None:
        file_path = os.path.join(DATA_DIR, "crysta_upgrades.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                _crysta_upgrades = json.load(f)
        except Exception as e:
            print(f"Error loading crysta_upgrades.json: {e}")
            _crysta_upgrades = {}
    return _crysta_upgrades

def get_skills_db():
    """Load and cache skills_db.json"""
    global _skills_db
    if _skills_db is None:
        file_path = os.path.join(DATA_DIR, "skills_db.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                _skills_db = json.load(f)
        except Exception as e:
            print(f"Error loading skills_db.json: {e}")
            _skills_db = []
    return _skills_db

def get_monsters_db():
    """Load and cache monsters_db.json"""
    global _monsters_db
    if _monsters_db is None:
        file_path = os.path.join(DATA_DIR, "monsters_db.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                _monsters_db = json.load(f)
        except Exception as e:
            print(f"Error loading monsters_db.json: {e}")
            _monsters_db = []
    return _monsters_db

def get_registlets_db():
    """Load and cache registlets_db.json"""
    global _registlets_db
    if _registlets_db is None:
        file_path = os.path.join(DATA_DIR, "registlets_db.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                _registlets_db = json.load(f)
        except Exception as e:
            print(f"Error loading registlets_db.json: {e}")
            _registlets_db = []
    return _registlets_db

def get_arrows_db() -> list:
    """Load and cache arrows_db.json"""
    global _arrows_db
    if _arrows_db is None:
        file_path = os.path.join(DATA_DIR, "arrows_db.json")
        try:
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    _arrows_db = json.load(f)
            else:
                _arrows_db = []
        except Exception as e:
            print(f"Error loading arrows_db.json: {e}")
            _arrows_db = []
    return _arrows_db

def clean_arrow_drops(drops: list) -> list:
    """Format and deduplicate monster drops and locations"""
    import re
    seen = set()
    cleaned = []
    for d in drops:
        m = d.get('monster', '').strip()
        loc = d.get('map', '').strip()
        if 'craft' in m.lower():
            key = 'Craft Blacksmith'
            if key not in seen:
                seen.add(key)
                cleaned.append("Craft Blacksmith (NPC/Player)")
            continue
        # Simplify monster name: remove (Lv ...) and difficulty
        base_m = re.sub(r'\s*\(Lv\s*\d+\)', '', m).strip()
        base_m = re.sub(r'\s*\(Easy\)|\s*\(Normal\)|\s*\(Hard\)|\s*\(Nightmare\)|\s*\(Ultimate\)', '', base_m).strip()
        key = f"{base_m} @ {loc}"
        if key not in seen:
            seen.add(key)
            cleaned.append(f"{base_m} ({loc})" if loc and loc != "-" else base_m)
    return cleaned

def format_arrows_list(is_event: bool, element_filter: str | None = None) -> str:
    """Format daftar arrow (Event atau Non-Event) dikelompokkan berdasarkan Elemen"""
    arrows = get_arrows_db()
    filtered = [a for a in arrows if bool(a.get("is_event")) == is_event]
    
    if element_filter:
        filtered = [a for a in filtered if element_filter.lower() in a.get("element", "").lower()]

    title = "DAFTAR ARROW EVENT" if is_event else "DAFTAR ARROW NON-EVENT"
    if element_filter:
        title += f" [ELEMEN {element_filter.upper()}]"

    elements_order = ["Fire", "Water", "Wind", "Earth", "Light", "Dark", "Normal"]
    groups = {el: [] for el in elements_order}
    groups["Other"] = []

    for a in filtered:
        el_key = "Other"
        for el in elements_order:
            if el.lower() in a.get("element", "").lower():
                el_key = el
                break
        groups[el_key].append(a)

    icons = {
        "Fire": "*ELEMEN FIRE (API)*",
        "Water": "*ELEMEN WATER (AIR)*",
        "Wind": "*ELEMEN WIND (ANGIN)*",
        "Earth": "*ELEMEN EARTH (TANAH)*",
        "Light": "*ELEMEN LIGHT (CAHAYA)*",
        "Dark": "*ELEMEN DARK (GELAP)*",
        "Normal": "*NORMAL (NON-ELEMEN)*",
        "Other": "*LAIN-LAIN*"
    }

    out = f"*{title} TORAM ONLINE*\n"
    out += f"Total: {len(filtered)} Arrow\n\n"

    for el in elements_order + ["Other"]:
        items = groups[el]
        if not items:
            continue
        out += f"{icons[el]}\n"
        for a in items:
            dr = clean_arrow_drops(a.get("drops", []))
            dr_str = ", ".join(dr) if dr else "Craft Blacksmith"
            badge = f" [{a['event_badge']}]" if a.get('event_badge') else ""
            watk = a.get('atk', '-')
            out += f"• *{a['name']}* (WATK: {watk}){badge}\n  └ Drop: {dr_str}\n"
        out += "\n"

    sample_name = filtered[0]['name'] if filtered else 'stardust'
    out += f"Tips: Ketik `,arrow [nama panah]` (contoh: `,arrow {sample_name}`) untuk melihat detail stats panah."
    return out.strip()

def search_arrows(query: str) -> list:
    """Cari arrow berdasarkan nama atau elemen dari database lokal arrows_db.json"""
    arrows = get_arrows_db()
    q = query.lower().strip()
    search_terms = get_translation_search_terms(q)
    
    # 1. Exact match
    exact = [a for a in arrows if any(a.get('name', '').lower() == t for t in search_terms)]
    if exact:
        return exact

    # 2. Substring match
    matches = [a for a in arrows if any(t in a.get('name', '').lower() for t in search_terms)]
    if matches:
        return matches

    # 3. Element match
    el_matches = [a for a in arrows if q in a.get('element', '').lower()]
    return el_matches

def format_arrow_detail(arrow: dict) -> str:
    """Format detail lengkap satu arrow"""
    raw_name = arrow.get("name", "Unknown")
    disp_name = get_item_bilingual_name(raw_name)
    element = arrow.get("element", "Normal")
    atk = arrow.get("atk", "-")
    is_event = arrow.get("is_event", False)
    badge = arrow.get("event_badge", "")
    stats = arrow.get("stats", [])
    drops = arrow.get("drops", [])
    note = arrow.get("note", "")

    status_str = f"Event ({badge})" if is_event else "Non-Event"
    stats_lines = "\n".join([f"- {s}" for s in stats]) if stats else "Tidak ada data stats"
    
    dr = clean_arrow_drops(drops)
    dr_lines = "\n".join([f"- {d}" for d in dr]) if dr else "- Craft Blacksmith"

    note_str = f"\n*Catatan:* {note}\n" if note else ""

    return (
        f"*DETAIL ARROW: {disp_name.upper()}*\n\n"
        f"• *Nama:* {disp_name}\n"
        f"• *Elemen:* {element}\n"
        f"• *WATK:* {atk}\n"
        f"• *Kategori:* {status_str}\n"
        f"{note_str}\n"
        f"*Stats / Efek:*\n{stats_lines}\n\n"
        f"*Drop Monster & Lokasi:*\n{dr_lines}"
    )

def load_warnings():
    """Load group warnings from warnings.json (no caching since it is updated frequently)"""
    file_path = os.path.join(DATA_DIR, "warnings.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading warnings.json: {e}")
    return {}

def save_warnings(warnings_data):
    """Save group warnings to warnings.json"""
    file_path = os.path.join(DATA_DIR, "warnings.json")
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(warnings_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving warnings.json: {e}")
        return False

def get_group_warnings_data(warnings_data: dict, chat_jid) -> dict:
    """Mengambil dict peringatan grup dengan normalisasi key JID standar"""
    std_jid = f"{chat_jid.User}@{chat_jid.Server}" if hasattr(chat_jid, 'User') else str(chat_jid)
    if std_jid in warnings_data:
        return warnings_data[std_jid]

    raw_str = str(chat_jid)
    if raw_str in warnings_data:
        data = warnings_data.pop(raw_str)
        warnings_data[std_jid] = data
        save_warnings(warnings_data)
        return data

    user_part = getattr(chat_jid, 'User', None)
    if user_part:
        for k in list(warnings_data.keys()):
            if user_part in k:
                data = warnings_data.pop(k)
                warnings_data[std_jid] = data
                save_warnings(warnings_data)
                return data

    warnings_data[std_jid] = {}
    return warnings_data[std_jid]


# Static Databases
pet_natures = {
    "steady": {
        "name": "Steady (Rajin/Tenang)",
        "behavior": "Sangat memprioritaskan penggunaan skill bantuan (seperti First Aid/Heal) pada pemiliknya (Master). Pet akan mengabaikan serangan musuh jika Master terluka demi memulihkannya.",
        "aoe_avoid": "Sangat Tinggi (Hampir selalu mendodge/menghindari lingkaran area AoE merah).",
        "recom": "Sangat direkomendasikan untuk Pet tipe Support atau Healer."
    },
    "sturdy": {
        "name": "Sturdy (Tangguh)",
        "behavior": "Hampir mirip dengan Steady, memprioritaskan First Aid/Heal pada Master. Kadang menghentikan aksi serangannya untuk fokus memulihkan Master.",
        "aoe_avoid": "Sangat Tinggi (Sangat aktif menghindari lingkaran area AoE merah).",
        "recom": "Sangat bagus untuk Pet tipe Support atau Tanker defensif karena pertahanannya yang kokoh."
    },
    "sly": {
        "name": "Sly (Licik)",
        "behavior": "Fokus pada serangan jarak jauh dan menjaga jarak dari musuh. Menghindari pertarungan jarak dekat secara langsung.",
        "aoe_avoid": "Sangat Tinggi (Paling aktif menghindar dari lingkaran area AoE merah).",
        "recom": "Sangat direkomendasikan untuk Pet tipe Range DPS (seperti Bow/Staff)."
    },
    "justice": {
        "name": "Justice (Keadilan)",
        "behavior": "Secually memprioritaskan menyerang musuh dengan HP tertinggi atau Bos di area pertempuran.",
        "aoe_avoid": "Tinggi (Sering menghindari lingkaran area AoE merah).",
        "recom": "Sangat cocok untuk Pet tipe Attacker / DPS (baik Fisik maupun Magic)."
    },
    "devoted": {
        "name": "Devoted (Setia/Berkorban)",
        "behavior": "Menarik perhatian musuh (Aggro) ke dirinya sendiri untuk melindungi Master. Sangat sering menggunakan skill taunt jika diajarkan.",
        "aoe_avoid": "Rendah (Sengaja menahan serangan dan jarang menghindar demi melindungi Master).",
        "recom": "Sifat / Nature wajib bagi Pet tipe Tanker utama grup."
    },
    "brave": {
        "name": "Brave (Pemberani)",
        "behavior": "Aktif menyerang musuh dari jarak dekat secara ofensif. Pet memiliki frekuensi serangan yang konstan.",
        "aoe_avoid": "Sedang (Kadang menghindar, kadang tidak).",
        "recom": "Cocok untuk Pet tipe Melee Attacker (seperti 1H Sword/Knuckles)."
    },
    "intelligent": {
        "name": "Intelligent (Pintar)",
        "behavior": "Meningkatkan efektivitas serangan sihir (Magic Attack) dan lebih cerdas menggunakan skill-skill berbasis MP.",
        "aoe_avoid": "Sedang (Cenderung menjaga jarak aman).",
        "recom": "Sangat cocok untuk Pet tipe Magic DPS / Mage."
    },
    "agile": {
        "name": "Agile (Tangkas)",
        "behavior": "Meningkatkan kecepatan gerak pet (Movement Speed) dan kecepatan animasi serangannya (Motion Speed).",
        "aoe_avoid": "Sedang - Tinggi (Bergerak lincah di sekitar target).",
        "recom": "Bagus untuk Pet tipe Speed Attacker / DPS cepat."
    },
    "timid": {
        "name": "Timid (Penakut)",
        "behavior": "Menghindari musuh sebisa mungkin dan menjaga jarak yang sangat jauh. Hanya menyerang secara pasif saat musuh lengah.",
        "aoe_avoid": "Tinggi (Menjauh dari semua area bahaya).",
        "recom": "Bisa digunakan untuk Pet murni Support/Buff jarak jauh agar tidak mudah mati."
    },
    "gentle": {
        "name": "Gentle (Lembut)",
        "behavior": "Lebih fokus mendampingi Master dan memberikan dukungan tidak langsung. Tidak agresif dan menghindari pertempuran langsung.",
        "aoe_avoid": "Tinggi (Mengutamakan keselamatan diri dan Master).",
        "recom": "Bagus untuk Pet tipe Healer / Buffer murni."
    }
}

traits_db = {
    "str": "STR\nDeskripsi: Meningkatkan status STR.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 STR\n• Lvl 2: +2 STR\n• Lvl 3: +3 STR\n• Lvl 4: +4 STR\n• Lvl 5: +5 STR",
    "int": "INT\nDeskripsi: Meningkatkan status INT.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 INT\n• Lvl 2: +2 INT\n• Lvl 3: +3 INT\n• Lvl 4: +4 INT\n• Lvl 5: +5 INT",
    "vit": "VIT\nDeskripsi: Meningkatkan status VIT.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 VIT\n• Lvl 2: +2 VIT\n• Lvl 3: +3 VIT\n• Lvl 4: +4 VIT\n• Lvl 5: +5 VIT",
    "agi": "AGI\nDeskripsi: Meningkatkan status AGI.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 AGI\n• Lvl 2: +2 AGI\n• Lvl 3: +3 AGI\n• Lvl 4: +4 AGI\n• Lvl 5: +5 AGI",
    "dex": "DEX\nDeskripsi: Meningkatkan status DEX.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 DEX\n• Lvl 2: +2 DEX\n• Lvl 3: +3 DEX\n• Lvl 4: +4 DEX\n• Lvl 5: +5 DEX",
    "maxhp": "MaxHP\nDeskripsi: Meningkatkan status MaxHP.\n*Efek per Level (Tier)*:\n• Lvl 1: +200 MaxHP\n• Lvl 2: +400 MaxHP\n• Lvl 3: +600 MaxHP\n• Lvl 4: +800 MaxHP\n• Lvl 5: +1000 MaxHP",
    "maxmp": "MaxMP\nDeskripsi: Meningkatkan status MaxMP.\n*Efek per Level (Tier)*:\n• Lvl 1: +10 MaxMP\n• Lvl 2: +20 MaxMP\n• Lvl 3: +30 MaxMP\n• Lvl 4: +40 MaxMP\n• Lvl 5: +50 MaxMP",
    "atk": "ATK\nDeskripsi: Meningkatkan status ATK.\n*Efek per Level (Tier)*:\n• Lvl 1: +5 ATK\n• Lvl 2: +10 ATK\n• Lvl 3: +15 ATK\n• Lvl 4: +20 ATK\n• Lvl 5: +25 ATK",
    "matk": "MATK\nDeskripsi: Meningkatkan status MATK.\n*Efek per Level (Tier)*:\n• Lvl 1: +5 MATK\n• Lvl 2: +10 MATK\n• Lvl 3: +15 MATK\n• Lvl 4: +20 MATK\n• Lvl 5: +25 MATK",
    "def": "DEF\nDeskripsi: Meningkatkan status DEF.\n*Efek per Level (Tier)*:\n• Lvl 1: +10 DEF\n• Lvl 2: +20 DEF\n• Lvl 3: +30 DEF\n• Lvl 4: +40 DEF\n• Lvl 5: +50 DEF",
    "mdef": "MDEF\nDeskripsi: Meningkatkan status MDEF.\n*Efek per Level (Tier)*:\n• Lvl 1: +10 MDEF\n• Lvl 2: +20 MDEF\n• Lvl 3: +30 MDEF\n• Lvl 4: +40 MDEF\n• Lvl 5: +50 MDEF",
    "accuracy": "Accuracy\nDeskripsi: Meningkatkan status Akurasi.\n*Efek per Level (Tier)*:\n• Lvl 1: +3 Akurasi\n• Lvl 2: +6 Akurasi\n• Lvl 3: +9 Akurasi\n• Lvl 4: +12 Akurasi\n• Lvl 5: +15 Akurasi",
    "dodge": "Dodge\nDeskripsi: Meningkatkan status Dodge.\n*Efek per Level (Tier)*:\n• Lvl 1: +3 Dodge\n• Lvl 2: +6 Dodge\n• Lvl 3: +9 Dodge\n• Lvl 4: +12 Dodge\n• Lvl 5: +15 Dodge",
    "aspd": "ASPD\nDeskripsi: Meningkatkan status ASPD.\n*Efek per Level (Tier)*:\n• Lvl 1: +50 ASPD\n• Lvl 2: +100 ASPD\n• Lvl 3: +150 ASPD\n• Lvl 4: +200 ASPD\n• Lvl 5: +250 ASPD",
    "cspd": "CSPD\nDeskripsi: Meningkatkan status CSPD.\n*Efek per Level (Tier)*:\n• Lvl 1: +50 CSPD\n• Lvl 2: +100 CSPD\n• Lvl 3: +150 CSPD\n• Lvl 4: +200 CSPD\n• Lvl 5: +250 CSPD",
    "natural hp regen": "Natural HP Regen\nDeskripsi: Meningkatkan pemulihan HP alami (Natural HP Regen).\n*Efek per Level (Tier)*:\n• Lvl 1: +15 HP Regen\n• Lvl 2: +30 HP Regen\n• Lvl 3: +45 HP Regen\n• Lvl 4: +60 HP Regen\n• Lvl 5: +75 HP Regen",
    "natural mp regen": "Natural MP Regen\nDeskripsi: Meningkatkan pemulihan MP alami (Natural MP Regen).\n*Efek per Level (Tier)*:\n• Lvl 1: +5 MP Regen\n• Lvl 2: +10 MP Regen\n• Lvl 3: +15 MP Regen\n• Lvl 4: +20 MP Regen\n• Lvl 5: +25 MP Regen",
    "critical rate": "Critical Rate\nDeskripsi: Meningkatkan status Critical Rate.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 Critical Rate\n• Lvl 2: +2 Critical Rate\n• Lvl 3: +3 Critical Rate\n• Lvl 4: +4 Critical Rate\n• Lvl 5: +5 Critical Rate",
    "critical damage": "Critical Damage\nDeskripsi: Meningkatkan status Critical Damage.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 Critical Damage\n• Lvl 2: +2 Critical Damage\n• Lvl 3: +3 Critical Damage\n• Lvl 4: +4 Critical Damage\n• Lvl 5: +5 Critical Damage",
    "exp gain": "Exp Gain\nDeskripsi: Meningkatkan EXP yang didapat dari mengalahkan monster.\n*Efek per Level (Tier)*:\n• Lvl 1: +3% EXP Gain\n• Lvl 2: +6% EXP Gain\n• Lvl 3: +9% EXP Gain\n• Lvl 4: +12% EXP Gain\n• Lvl 5: +15% EXP Gain",
    "pet exp gain": "Pet Exp Gain\nDeskripsi: Meningkatkan EXP yang diperoleh Pet.\n*Efek per Level (Tier)*:\n• Lvl 1: +6% Pet EXP Gain\n• Lvl 2: +12% Pet EXP Gain\n• Lvl 3: +18% Pet EXP Gain\n• Lvl 4: +24% Pet EXP Gain\n• Lvl 5: +30% Pet EXP Gain",
    "battlecast": "Battlecast\nDeskripsi: Memberikan damage ke target meningkatkan CSPD selama 6 detik. Maks 20 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: +20 CSPD per stack (Maks +400)\n• Lvl 2: +40 CSPD per stack (Maks +800)\n• Lvl 3: +60 CSPD per stack (Maks +1200)\n• Lvl 4: +80 CSPD per stack (Maks +1600)\n• Lvl 5: +100 CSPD per stack (Maks +2000)",
    "blood regen": "Blood Regen\nDeskripsi: Memberikan damage ke target memulihkan HP. Aktif setiap 3 detik sekali.\nPeningkatan STR: +Total STR ke HP yang dipulihkan.\n*Efek per Level (Tier)*:\n• Lvl 1: Memulihkan 200 HP\n• Lvl 2: Memulihkan 400 HP\n• Lvl 3: Memulihkan 600 HP\n• Lvl 4: Memulihkan 800 HP\n• Lvl 5: Memulihkan 1000 HP",
    "blood spell": "Blood Spell\nDeskripsi: Memberikan damage ke target memulihkan HP. Aktif setiap 3 detik sekali.\nPeningkatan INT: +Total INT ke HP yang dipulihkan.\n*Efek per Level (Tier)*:\n• Lvl 1: Memulihkan 200 HP\n• Lvl 2: Memulihkan 400 HP\n• Lvl 3: Memulihkan 600 HP\n• Lvl 4: Memulihkan 800 HP\n• Lvl 5: Memulihkan 1000 HP",
    "bunker edge": "Bunker Edge\nDeskripsi: Memberikan damage ke target meningkatkan Physical Pierce sebesar 1% selama 5 detik. Maks 10 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: Activation Power 20\n• Lvl 2: Activation Power 40\n• Lvl 3: Activation Power 60\n• Lvl 4: Activation Power 80\n• Lvl 5: Activation Power 100",
    "bunker magica": "Bunker Magica\nDeskripsi: Memberikan damage ke target meningkatkan Magic Pierce sebesar 1% selama 5 detik. Maks 10 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: Activation Power 20\n• Lvl 2: Activation Power 40\n• Lvl 3: Activation Power 60\n• Lvl 4: Activation Power 80\n• Lvl 5: Activation Power 100",
    "counter evasion mana": "Counter Evasion Mana\nDeskripsi: Memulihkan MP saat target berhasil melakukan Evasion (kecuali event). Aktif setiap 6 detik sekali.\nPeningkatan INT: +Base INT / (20 - 3 * Tier).\n*Efek per Level (Tier)*:\n• Lvl 1: Memulihkan 20 MP (INT scaling: +Base INT/17)\n• Lvl 2: Memulihkan 40 MP (INT scaling: +Base INT/14)\n• Lvl 3: Memulihkan 60 MP (INT scaling: +Base INT/11)\n• Lvl 4: Memulihkan 80 MP (INT scaling: +Base INT/8)\n• Lvl 5: Memulihkan 100 MP (INT scaling: +Base INT/5)",
    "counter evasion power": "Counter Evasion Power\nDeskripsi: Saat target berhasil melakukan Evasion (kecuali event), ATK meningkat selama (5 + 5 * Tier) detik. Aktif setiap 20 detik sekali.\nPeningkatan DEX: +Base DEX / 5 ke peningkatan ATK.\n*Efek per Level (Tier)*:\n• Lvl 1: Meningkatkan ATK sebesar 100 selama 10 detik\n• Lvl 2: Meningkatkan ATK sebesar 100 selama 15 detik\n• Lvl 3: Meningkatkan ATK sebesar 100 selama 20 detik\n• Lvl 4: Meningkatkan ATK sebesar 100 selama 25 detik\n• Lvl 5: Meningkatkan ATK sebesar 100 selama 30 detik",
    "counter rage": "Counter Rage\nDeskripsi: Saat menerima damage dari target, Aggro meningkat selama 12 detik.\n*Efek per Level (Tier)*:\n• Lvl 1: +10% Aggro\n• Lvl 2: +20% Aggro\n• Lvl 3: +30% Aggro\n• Lvl 4: +40% Aggro\n• Lvl 5: +50% Aggro",
    "counter speed": "Counter Speed\nDeskripsi: Saat menerima damage dari target, ASPD, CSPD, dan Action Speed meningkat selama 3 detik.\n*Efek per Level (Tier)*:\n• Lvl 1: +2% ASPD, CSPD, & Action Speed\n• Lvl 2: +4% ASPD, CSPD, & Action Speed\n• Lvl 3: +6% ASPD, CSPD, & Action Speed\n• Lvl 4: +8% ASPD, CSPD, & Action Speed\n• Lvl 5: +10% ASPD, CSPD, & Action Speed",
    "critical": "Critical\nDeskripsi: Memberikan damage ke target meningkatkan Critical Rate selama 3 detik.\nPeningkatan CRT: +CRT / 15 ke durasi efek.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 Critical Rate per stack (Maks 10 stack)\n• Lvl 2: +1 Critical Rate per stack (Maks 20 stack)\n• Lvl 3: +1 Critical Rate per stack (Maks 30 stack)\n• Lvl 4: +1 Critical Rate per stack (Maks 40 stack)\n• Lvl 5: +1 Critical Rate per stack (Maks 50 stack)",
    "critical rebound": "Critical Rebound\nDeskripsi: Jika serangan Anda MISS, Critical Rate meningkat selama 60 detik. Maks 5 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: +4 Critical Rate per stack (Maks +20)\n• Lvl 2: +8 Critical Rate per stack (Maks +40)\n• Lvl 3: +12 Critical Rate per stack (Maks +60)\n• Lvl 4: +16 Critical Rate per stack (Maks +80)\n• Lvl 5: +20 Critical Rate per stack (Maks +100)",
    "cursed weapon": "Cursed Weapon\nDeskripsi: Memberikan damage ke target mengurangi Max HP sebesar 1% selama 3 detik, tetapi meningkatkan ATK dan MATK. Maks 99 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 ATK & MATK per stack (Maks +99)\n• Lvl 2: +2 ATK & MATK per stack (Maks +198)\n• Lvl 3: +3 ATK & MATK per stack (Maks +297)\n• Lvl 4: +4 ATK & MATK per stack (Maks +396)\n• Lvl 5: +5 ATK & MATK per stack (Maks +495)",
    "dash defence": "Dash Defence\nDeskripsi: Saat menggunakan Evasion, selama 3 detik, Physical dan Magical Resistance meningkat. Maks 3 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: +2% Physical & Magical Resistance per stack\n• Lvl 2: +4% Physical & Magical Resistance per stack\n• Lvl 3: +6% Physical & Magical Resistance per stack\n• Lvl 4: +8% Physical & Magical Resistance per stack\n• Lvl 5: +10% Physical & Magical Resistance per stack",
    "dash power": "Dash Power\nDeskripsi: Saat menggunakan Evasion, selama 3 detik, meningkatkan ATK dan ASPD. Maks 3 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: +10 ATK & +100 ASPD per stack\n• Lvl 2: +20 ATK & +150 ASPD per stack\n• Lvl 3: +30 ATK & +200 ASPD per stack\n• Lvl 4: +40 ATK & +250 ASPD per stack\n• Lvl 5: +50 ATK & +300 ASPD per stack",
    "engineer": "Engineer\nDeskripsi: Memberikan damage ke target meningkatkan ATK, MATK, dan CSPD selama 20 detik. Aktif setiap 10 detik sekali.\nPeningkatan TEC: ATK/MATK +TEC / (6 - Tier), CSPD +TEC * 5 / (6 - Tier).\n*Efek per Level (Tier)*:\n• Lvl 1: +10 ATK/MATK, +10 CSPD (TEC scaling: ATK/MATK +TEC/5, CSPD +TEC)\n• Lvl 2: +15 ATK/MATK, +10 CSPD (TEC scaling: ATK/MATK +TEC/4, CSPD +TEC*1.25)\n• Lvl 3: +20 ATK/MATK, +10 CSPD (TEC scaling: ATK/MATK +TEC/3, CSPD +TEC*1.67)\n• Lvl 4: +25 ATK/MATK, +10 CSPD (TEC scaling: ATK/MATK +TEC/2, CSPD +TEC*2.5)\n• Lvl 5: +30 ATK/MATK, +10 CSPD (TEC scaling: ATK/MATK +TEC/1, CSPD +TEC*5)",
    "fighting magica": "Fighting Magica\nDeskripsi: Memberikan damage ke target meningkatkan MATK selama 4 detik.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 MATK per stack (Maks 300 stack -> +300 MATK)\n• Lvl 2: +2 MATK per stack (Maks 150 stack -> +300 MATK)\n• Lvl 3: +3 MATK per stack (Maks 100 stack -> +300 MATK)\n• Lvl 4: +4 MATK per stack (Maks 75 stack -> +300 MATK)\n• Lvl 5: +5 MATK per stack (Maks 60 stack -> +300 MATK)",
    "fighting power": "Fighting Power\nDeskripsi: Memberikan damage ke target meningkatkan ATK selama 2 detik.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 ATK per stack (Maks 300 stack -> +300 ATK)\n• Lvl 2: +2 ATK per stack (Maks 150 stack -> +300 ATK)\n• Lvl 3: +3 ATK per stack (Maks 100 stack -> +300 ATK)\n• Lvl 4: +4 ATK per stack (Maks 75 stack -> +300 ATK)\n• Lvl 5: +5 ATK per stack (Maks 60 stack -> +300 ATK)",
    "foreseen evasion": "Foreseen Evasion\nDeskripsi: Saat target berhasil melakukan Evasion (kecuali event), Anticipate meningkat selama 12 detik.\n*Efek per Level (Tier)*:\n• Lvl 1: +5% Anticipate\n• Lvl 2: +10% Anticipate\n• Lvl 3: +15% Anticipate\n• Lvl 4: +20% Anticipate\n• Lvl 5: +25% Anticipate",
    "gearshift": "Gearshift\nDeskripsi: Memberikan damage ke target meningkatkan ASPD selama 3 detik. Maks 20 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: +20 ASPD per stack (Maks +400)\n• Lvl 2: +40 ASPD per stack (Maks +800)\n• Lvl 3: +60 ASPD per stack (Maks +1200)\n• Lvl 4: +80 ASPD per stack (Maks +1600)\n• Lvl 5: +100 ASPD per stack (Maks +2000)",
    "graze mana": "Graze Mana\nDeskripsi: Memulihkan 10 MP jika serangan Anda menghasilkan efek Graze.\n*Efek per Level (Tier)*:\n• Lvl 1: Peluang Aktif (Activation Power) 10%\n• Lvl 2: Peluang Aktif (Activation Power) 20%\n• Lvl 3: Peluang Aktif (Activation Power) 30%\n• Lvl 4: Peluang Aktif (Activation Power) 40%\n• Lvl 5: Peluang Aktif (Activation Power) 50%",
    "graze mana boost": "Graze Mana Boost\nDeskripsi: Jika serangan Anda Graze, selama 15 detik MaxMP berkurang, tetapi Short & Long Range Damage meningkat 1%, dan Akurasi meningkat. Maks 3 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: -300 MaxMP & +60 Akurasi per stack\n• Lvl 2: -250 MaxMP & +120 Akurasi per stack\n• Lvl 3: -200 MaxMP & +180 Akurasi per stack\n• Lvl 4: -150 MaxMP & +240 Akurasi per stack\n• Lvl 5: -100 MaxMP & +300 Akurasi per stack",
    "graze precision": "Graze Precision\nDeskripsi: Jika serangan Anda Graze, Akurasi meningkat selama 30 detik. Maks 5 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: +20 Akurasi per stack (Maks +100)\n• Lvl 2: +40 Akurasi per stack (Maks +200)\n• Lvl 3: +60 Akurasi per stack (Maks +300)\n• Lvl 4: +80 Akurasi per stack (Maks +400)\n• Lvl 5: +100 Akurasi per stack (Maks +500)",
    "guarded advantage": "Guarded Advantage\nDeskripsi: Saat target berhasil melakukan Guard (kecuali event), Guard Break meningkat selama 12 detik.\n*Efek per Level (Tier)*:\n• Lvl 1: +5% Guard Break\n• Lvl 2: +10% Guard Break\n• Lvl 3: +15% Guard Break\n• Lvl 4: +20% Guard Break\n• Lvl 5: +25% Guard Break",
    "guarded magica": "Guarded Magica\nDeskripsi: Saat target berhasil melakukan Guard (kecuali event), meningkatkan MATK selama (5 + 5 * Tier) detik. Aktif setiap 20 detik sekali.\nPeningkatan DEX: +Base DEX / 10 ke peningkatan MATK.\n*Efek per Level (Tier)*:\n• Lvl 1: MATK +50 selama 10 detik\n• Lvl 2: MATK +50 selama 15 detik\n• Lvl 3: MATK +50 selama 20 detik\n• Lvl 4: MATK +50 selama 25 detik\n• Lvl 5: MATK +50 selama 30 detik",
    "guarded recovery": "Guarded Recovery\nDeskripsi: Memulihkan HP saat target berhasil melakukan Guard (kecuali event). Aktif setiap 6 detik sekali.\nPeningkatan STR: +Base STR * 2^(Tier-1) / 2.\n*Efek per Level (Tier)*:\n• Lvl 1: Memulihkan 1000 HP (STR scaling: +Base STR/2)\n• Lvl 2: Memulihkan 1500 HP (STR scaling: +Base STR)\n• Lvl 3: Memulihkan 2000 HP (STR scaling: +Base STR*2)\n• Lvl 4: Memulihkan 2500 HP (STR scaling: +Base STR*4)\n• Lvl 5: Memulihkan 3000 HP (STR scaling: +Base STR*8)",
    "health barrier": "Health Barrier\nDeskripsi: Memberikan damage ke target meningkatkan Physical & Magic Barrier selama 6 detik. Maks 100 stack.\nPeningkatan MTL: +MTL / (6 - Tier) per stack.\n*Efek per Level (Tier)*:\n• Lvl 1: +2 Barrier per stack (MTL scaling: +MTL/5)\n• Lvl 2: +4 Barrier per stack (MTL scaling: +MTL/4)\n• Lvl 3: +6 Barrier per stack (MTL scaling: +MTL/3)\n• Lvl 4: +8 Barrier per stack (MTL scaling: +MTL/2)\n• Lvl 5: +10 Barrier per stack (MTL scaling: +MTL/1)",
    "life purge": "Life Purge\nDeskripsi: Saat menerima damage dari target, selama 20 detik MaxHP berkurang, tetapi ASPD meningkat. Maks 5 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: -1% MaxHP & +50 ASPD per stack\n• Lvl 2: -2% MaxHP & +100 ASPD per stack\n• Lvl 3: -4% MaxHP & +200 ASPD per stack\n• Lvl 4: -8% MaxHP & +400 ASPD per stack\n• Lvl 5: -16% MaxHP & +800 ASPD per stack",
    "lucky experience": "Lucky Experience\nDeskripsi: Memberikan damage ke target meningkatkan EXP Gain selama 77 detik. Maks 10 stack.\nPeningkatan LUK: Maksimal stack bertambah berdasarkan status LUK.\n*Efek per Level (Tier)*:\n• Lvl 1: +1% EXP Gain per stack\n• Lvl 2: +2% EXP Gain per stack\n• Lvl 3: +3% EXP Gain per stack\n• Lvl 4: +4% EXP Gain per stack\n• Lvl 5: +5% EXP Gain per stack",
    "magica rebound": "Magica Rebound\nDeskripsi: Jika serangan Anda MISS, MATK meningkat selama 30 detik. Maks 10 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: +10 MATK per stack (Maks +100)\n• Lvl 2: +20 MATK per stack (Maks +200)\n• Lvl 3: +30 MATK per stack (Maks +300)\n• Lvl 4: +40 MATK per stack (Maks +400)\n• Lvl 5: +50 MATK per stack (Maks +500)",
    "mana combat": "Mana Combat\nDeskripsi: Memulihkan MP saat menerima damage dari target.\nPeningkatan VIT: +Base VIT / (20 * (6 - Tier)) ke pemulihan MP.\n*Efek per Level (Tier)*:\n• Lvl 1: Memulihkan 1 MP (VIT scaling: +Base VIT/100)\n• Lvl 2: Memulihkan 2 MP (VIT scaling: +Base VIT/80)\n• Lvl 3: Memulihkan 3 MP (VIT scaling: +Base VIT/60)\n• Lvl 4: Memulihkan 4 MP (VIT scaling: +Base VIT/40)\n• Lvl 5: Memulihkan 5 MP (VIT scaling: +Base VIT/20)",
    "mana rebound": "Mana Rebound\nDeskripsi: Memulihkan 100 MP jika serangan Anda menghasilkan efek MISS.\n*Efek per Level (Tier)*:\n• Lvl 1: Peluang Aktif (Activation Power) 10%\n• Lvl 2: Peluang Aktif (Activation Power) 20%\n• Lvl 3: Peluang Aktif (Activation Power) 30%\n• Lvl 4: Peluang Aktif (Activation Power) 50%\n• Lvl 5: Peluang Aktif (Activation Power) 100%",
    "mega power rebound": "Mega Power Rebound\nDeskripsi: Jika serangan Anda MISS, selama 90 detik meningkatkan ATK & Critical Rate, tetapi mengurangi Akurasi sebesar 9999.\n*Efek per Level (Tier)*:\n• Lvl 1: +100 ATK & +50 Critical Rate\n• Lvl 2: +200 ATK & +75 Critical Rate\n• Lvl 3: +300 ATK & +100 Critical Rate\n• Lvl 4: +400 ATK & +125 Critical Rate\n• Lvl 5: +500 ATK & +150 Critical Rate",
    "nimble": "Nimble\nDeskripsi: Memberikan damage ke target meningkatkan Dodge selama 6 detik. Maks 30 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 Dodge per stack (Maks +30)\n• Lvl 2: +2 Dodge per stack (Maks +60)\n• Lvl 3: +3 Dodge per stack (Maks +90)\n• Lvl 4: +4 Dodge per stack (Maks +120)\n• Lvl 5: +5 Dodge per stack (Maks +150)",
    "power rebound": "Power Rebound\nDeskripsi: Jika serangan Anda MISS, ATK meningkat selama 30 detik. Maks 10 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: +10 ATK per stack (Maks +100)\n• Lvl 2: +20 ATK per stack (Maks +200)\n• Lvl 3: +30 ATK per stack (Maks +300)\n• Lvl 4: +40 ATK per stack (Maks +400)\n• Lvl 5: +50 ATK per stack (Maks +500)",
    "precision": "Precision\nDeskripsi: Memberikan damage ke target meningkatkan Akurasi selama 6 detik. Maks 30 stack.\n*Efek per Level (Tier)*:\n• Lvl 1: +1 Akurasi per stack (Maks +30)\n• Lvl 2: +2 Akurasi per stack (Maks +60)\n• Lvl 3: +3 Akurasi per stack (Maks +90)\n• Lvl 4: +4 Akurasi per stack (Maks +120)\n• Lvl 5: +5 Akurasi per stack (Maks +150)",
    "spirit blow": "Spirit Blow\nDeskripsi: Memberikan damage ke target memulihkan MP. Aktif setiap 6 detik sekali.\nPeningkatan AGI: +Total AGI / (90 - 15 * Tier) ke pemulihan MP.\n*Efek per Level (Tier)*:\n• Lvl 1: Memulihkan 2 MP (AGI scaling: +Total AGI/75)\n• Lvl 2: Memulihkan 4 MP (AGI scaling: +Total AGI/60)\n• Lvl 3: Memulihkan 6 MP (AGI scaling: +Total AGI/45)\n• Lvl 4: Memulihkan 8 MP (AGI scaling: +Total AGI/30)\n• Lvl 5: Memulihkan 10 MP (AGI scaling: +Total AGI/15)",
    "spirit shot": "Spirit Shot\nDeskripsi: Memberikan damage ke target memulihkan MP. Aktif setiap 6 detik sekali.\nPeningkatan DEX: +Total DEX / (90 - 15 * Tier) ke pemulihan MP.\n*Efek per Level (Tier)*:\n• Lvl 1: Memulihkan 2 MP (DEX scaling: +Total DEX/75)\n• Lvl 2: Memulihkan 4 MP (DEX scaling: +Total DEX/60)\n• Lvl 3: Memulihkan 6 MP (DEX scaling: +Total DEX/45)\n• Lvl 4: Memulihkan 8 MP (DEX scaling: +Total DEX/30)\n• Lvl 5: Memulihkan 10 MP (DEX scaling: +Total DEX/15)",
    "vengeful life": "Vengeful Life\nDeskripsi: Saat menerima damage dari target, meningkatkan MaxHP selama 180 detik.\n*Efek per Level (Tier)*:\n• Lvl 1: +50 MaxHP per stack (Maks 120 stack -> +6000 HP)\n• Lvl 2: +100 MaxHP per stack (Maks 100 stack -> +10000 HP)\n• Lvl 3: +200 MaxHP per stack (Maks 80 stack -> +16000 HP)\n• Lvl 4: +400 MaxHP per stack (Maks 60 stack -> +24000 HP)\n• Lvl 5: +800 MaxHP per stack (Maks 40 stack -> +32000 HP)",
    "vengeful magica": "Vengeful Magica\nDeskripsi: Saat menerima damage dari target, meningkatkan MATK selama 30 detik.\n*Efek per Level (Tier)*:\n• Lvl 1: +10 MATK per stack (Maks 90 stack -> +900 MATK)\n• Lvl 2: +15 MATK per stack (Maks 60 stack -> +900 MATK)\n• Lvl 3: +30 MATK per stack (Maks 30 stack -> +900 MATK)\n• Lvl 4: +60 MATK per stack (Maks 15 stack -> +900 MATK)\n• Lvl 5: +90 MATK per stack (Maks 10 stack -> +900 MATK)",
    "vengeful mana": "Vengeful Mana\nDeskripsi: Saat menerima damage dari target, meningkatkan Max MP selama 180 detik.\n*Efek per Level (Tier)*:\n• Lvl 1: +5 MaxMP per stack (Maks 30 stack -> +150 MaxMP)\n• Lvl 2: +10 MaxMP per stack (Maks 25 stack -> +250 MaxMP)\n• Lvl 3: +20 MaxMP per stack (Maks 20 stack -> +400 MaxMP)\n• Lvl 4: +40 MaxMP per stack (Maks 15 stack -> +600 MaxMP)\n• Lvl 5: +80 MaxMP per stack (Maks 10 stack -> +800 MaxMP)",
    "vengeful power": "Vengeful Power\nDeskripsi: Saat menerima damage dari target, meningkatkan ATK selama 30 detik.\n*Efek per Level (Tier)*:\n• Lvl 1: +10 ATK per stack (Maks 90 stack -> +900 ATK)\n• Lvl 2: +15 ATK per stack (Maks 60 stack -> +900 ATK)\n• Lvl 3: +30 ATK per stack (Maks 30 stack -> +900 ATK)\n• Lvl 4: +60 ATK per stack (Maks 15 stack -> +900 ATK)\n• Lvl 5: +90 ATK per stack (Maks 10 stack -> +900 ATK)",
    "vengeful samurai": "Vengeful Samurai\nDeskripsi: Saat menerima damage dari target, Unsheathe Power meningkat sebesar 100 selama 9 detik.\n*Efek per Level (Tier)*:\n• Lvl 1: Maksimal 1 stack (+100 Unsheathe Power)\n• Lvl 2: Maksimal 2 stack (+200 Unsheathe Power)\n• Lvl 3: Maksimal 3 stack (+300 Unsheathe Power)\n• Lvl 4: Maksimal 4 stack (+400 Unsheathe Power)\n• Lvl 5: Maksimal 5 stack (+500 Unsheathe Power)",
    "flinch unavailable": "Flinch Unavailable\nDeskripsi: Karakter tidak dapat lagi mengakibatkan status [Flinch] (Gemetar/Flinch) kepada musuh.\n*Efek per Level (Tier)*:\n• Lvl 1 s/d 5: Efek Flinch dinonaktifkan sepenuhnya.",
    "stun unavailable": "Stun Unavailable\nDeskripsi: Karakter tidak dapat lagi mengakibatkan status [Stun] (Pusing/Pingsan) kepada musuh.\n*Efek per Level (Tier)*:\n• Lvl 1 s/d 5: Efek Stun dinonaktifkan sepenuhnya.",
    "tumble unavailable": "Tumble Unavailable\nDeskripsi: Karakter tidak dapat lagi mengakibatkan status [Tumble] (Jatuh) kepada musuh.\n*Efek per Level (Tier)*:\n• Lvl 1 s/d 5: Efek Tumble dinonaktifkan sepenuhnya.",
    "immobilization unavailable": "Immobilization Unavailable\nDeskripsi: Karakter tidak dapat lagi mengakibatkan status [Immobilization] (Imobilitas) kepada musuh.\n*Efek per Level (Tier)*:\n• Lvl 1 s/d 5: Efek Immobilization dinonaktifkan sepenuhnya."
}


TRAIT_TRANSLATIONS = {
    "accuracy": "Akurasi (Ketepatan)",
    "agi": "AGI",
    "aspd": "Kecepatan Serangan (ASPD)",
    "atk": "Daya Serang Fisik (ATK)",
    "battlecast": "Mantra Tempur",
    "blood regen": "Pemulihan Darah",
    "blood spell": "Sihir Darah",
    "bunker edge": "Pertahanan Ujung",
    "bunker magica": "Magika Bunker",
    "counter evasion mana": "Mana Tangkal Hindaran",
    "counter evasion power": "Daya Tangkal Hindaran",
    "counter rage": "Murka Tangkal",
    "counter speed": "Kecepatan Tangkal",
    "critical": "Kritikal",
    "critical damage": "Kerusakan Kritikal",
    "critical rate": "Peluang Kritikal",
    "critical rebound": "Pantulan Kritikal",
    "cspd": "Kecepatan Merapal (CSPD)",
    "cursed weapon": "Senjata Terkutuk",
    "dash defence": "Pertahanan Terjang",
    "dash power": "Daya Terjang",
    "def": "Pertahanan Fisik (DEF)",
    "dex": "DEX",
    "dodge": "Menghindar (Dodge)",
    "engineer": "Insinyur",
    "exp gain": "Perolehan EXP",
    "fighting magica": "Magika Tempur",
    "fighting power": "Daya Tempur",
    "flinch unavailable": "Flinch (Gemetar) Nonaktif",
    "foreseen evasion": "Hindaran Terduga",
    "gearshift": "Oper Gigi",
    "graze mana": "Mana Serempet",
    "graze mana boost": "Pendorong Mana Serempet",
    "graze precision": "Ketepatan Serempet",
    "guarded advantage": "Keuntungan Tangkisan",
    "guarded magica": "Magika Tangkisan",
    "guarded recovery": "Pemulihan Tangkisan",
    "health barrier": "Penghalang Darah (HP)",
    "immobilization unavailable": "Imobilitas Nonaktif",
    "int": "INT",
    "life purge": "Pembersihan Hayat",
    "lucky experience": "Pengalaman Beruntung",
    "magica rebound": "Pantulan Magika",
    "mana combat": "Pertempuran Mana",
    "mana rebound": "Pantulan Mana",
    "matk": "Daya Serang Sihir (MATK)",
    "maxhp": "HP Maksimal",
    "maxmp": "MP Maksimal",
    "mdef": "Pertahanan Sihir (MDEF)",
    "mega power rebound": "Pantulan Daya Mega",
    "natural hp regen": "Pemulihan HP Alami",
    "natural mp regen": "Pemulihan MP Alami",
    "nimble": "Lincah (Dodge)",
    "pet exp gain": "Perolehan EXP Pet",
    "power rebound": "Pantulan Daya",
    "precision": "Presisi (Akurasi)",
    "spirit blow": "Pukulan Roh",
    "spirit shot": "Tembakan Roh",
    "str": "STR",
    "stun unavailable": "Pingsan (Stun) Nonaktif",
    "tumble unavailable": "Jatuh (Tumble) Nonaktif",
    "vengeful life": "Hayat Pendendam",
    "vengeful magica": "Magika Pendendam",
    "vengeful mana": "Mana Pendendam",
    "vengeful power": "Daya Pendendam",
    "vengeful samurai": "Samurai Pendendam",
    "vit": "VIT"
}

def format_trait_detail(key: str) -> str:
    key_low = key.strip().lower()
    raw = traits_db.get(key_low, "")
    if not raw:
        return ""
    en_title = key_low.title() if key_low not in ["str", "int", "vit", "agi", "dex", "atk", "matk", "def", "mdef", "aspd", "cspd", "maxhp", "maxmp"] else key_low.upper()
    lines = raw.splitlines()
    body = "\n".join(lines[1:]) if len(lines) > 1 and lines[0].strip().lower() == key_low else raw
    return f"*DETAIL TRAIT: {en_title.upper()}*\n\n• *Nama:* {en_title}\n{body}".strip()
