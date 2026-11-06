import re

READ_MORE = chr(0x200e) * 4000

def get_menu_text(sender_name: str) -> str:
    """Generate dynamic menu text with the sender's name"""
    return (
        f"*ditdut toram*\n"
        f"Yoo , {sender_name}!\n"
        f"Berikut list command yang baru bisa digunakan, gausah muluk muluk dulu baru di buat ini!!!\n"
        f"{READ_MORE}\n"
        f"==Menu Umum==\n"
        f"- ,menu -> list menu\n"
        f"- ,help -> list menu\n"
        f"- ,tt <link> -> unduh video TikTok (No WM)\n"
        f"- ,fb <link> -> unduh video Facebook / Reels\n"
        f"- ,ig <link> -> unduh video Instagram Reels\n"

        f"- ,music <judul> -> cari & unduh musik/lagu\n"
        f"- ,s / ,sticker -> buat stiker dari gambar\n"
        f"- ,setmeme <teks> -> buat stiker meme berteks\n"
        f"- ,ai <tanya> -> Gemini AI Assistant\n"
        f"- ,gemini <tanya> -> Gemini AI Assistant\n"
        f"- ,ping -> ping bot\n"
        f"- ,about -> info bot\n"
        f"- ,quote -> random quotes\n"
        f"- ,waifu -> random waifu\n"
        f"- ,husbu -> random husbu\n"
        f"- ,calc -> kalkulator\n"
        f"- ,a -> hidetag all\n"
        f"- ,kick -> kick member\n"
        f"- ,view -> view viewonce\n"
        f"- ,warn -> warn member\n"
        f"- ,reset -> reset warn\n"
        f"- ,listwarn -> list warn member\n\n"
        f"==Toram Search==\n"
        f"- ,item -> cari item\n"
        f"- ,arrow -> list & cari arrow (non-event / event)\n"
        f"- ,wp -> cari weapon\n"
        f"- ,armor -> cari armor\n"
        f"- ,add -> cari additional\n"
        f"- ,ring -> cari special\n"
        f"- ,xtall -> cari crysta\n"
        f"- ,mats -> cari material\n"
        f"- ,use -> cari konsumsi\n"
        f"- ,mob -> cari monster\n"
        f"- ,boss -> cari boss monster\n"
        f"- ,mboss -> cari mini boss\n"
        f"- ,rute -> rute crysta\n"
        f"- ,skill -> detail skill\n"
        f"- ,regis -> detail registlet\n"
        f"- ,pet -> sifat pet\n"
        f"- ,trait -> detail trait\n"
        f"- ,lvling -> rekomendasi leveling\n"
        f"- ,buff [kategori] -> list food buff (contoh: ,buff dex)\n"
        f"- ,bahanmq -> list bahan mq\n"
        f"- ,bag -> list bahan bag\n"
        f"- ,statlist -> list stat\n"
        f"- ,mt / ,maintenance -> info update & maintenance (realtime)\n"
        f"- ,ava / ,avatar -> info avatar chest (realtime)\n"
        f"- ,boost -> info boss boost (realtime)\n\n"
        f"==Toram Tools==\n"
        f"- ,fillwp -> weapon statting\n"
        f"- ,fillarm -> armor statting\n"
        f"- ,mq <lvl> [%] <bab> -> kalkulator exp MQ (contoh: ,mq 150 60% 9)\n"
        f"- ,mqspam<N> -> simulasi spam ulang MQ N-kali (contoh: ,mqspam2 150 60% 9)\n\n"
        f"==Game Interaktif==\n"
        f"- ,family100 / ,f100 -> main game Family 100\n"
        f"- ,kuistoram -> main kuis Toram Online\n"
        f"- ,susunkata -> main game susun kata\n"
        f"- ,skor -> lihat klasemen poin game grup\n"
        f"- ,nyerah -> menyerah di sesi game aktif\n\n"
        f"==Info Bot==\n"
        f"- ,cekbot -> cek sisa masa aktif sewa bot di grup\n\n"
        f"Kasih saran langsung tag aja !"
    )

def get_pet_menu_text(natures_list: str) -> str:
    """Generate dynamic pet nature list text"""
    return (
        f"*Sifat/Nature Pet Toram Online* \n\n"
        f"Berikut adalah daftar Sifat Pet yang tersedia:\n"
        f"{natures_list}\n\n"
        f"Tips: Ketik *,pet <nama sifat>* untuk melihat detail perilaku dan rekomendasi tipe pet.\n"
        f"Contoh: *,pet steady* atau *,pet devoted*\n\n"
        f"*STATUS PET* \n"
        f"Tipe : STR, INT, VIT, AGI, DEX\n"
        f"• Awam : 40, 40, 40, 40, 40\n"
        f"• Penguat Skill : 50, 50, 50, 50, 50\n"
        f"• Serba Bisa : 60, 60, 60, 60, 60\n"
        f"• Genius : 80, 80, 80, 80, 80\n"
        f"• Serangan Fisik : 120, 10, 40, 80, 50\n"
        f"• Serangan Sihir : 10, 120, 40, 60, 70\n"
        f"• Penghindar : 40, 40, 40, 120, 80\n"
        f"• Akurat : 40, 40, 40, 60, 120\n"
        f"• Tahan Fisik : 60, 30, 110, 50, 50\n"
        f"• Tahan Sihir : 30, 70, 80, 50, 70\n\n"
        f"*SIFAT & BONUS* \n"
        f"• Antusias (ATK +30%)\n"
        f"• Intelek (MATK +30%)\n"
        f"• Kokoh (ATK & MATK +15%, P&M Resist +15%)\n"
        f"• Heroik (Critical Damage +30)\n"
        f"• Mantap (Critical Rate -100%, HIT +30)\n"
        f"• Proaktif (ASPD +1000, CSPD +500)\n"
        f"• Lincah (Motion Speed Up)\n"
        f"• Adil (AMPR x2)\n"
        f"• Licik (Aggro -30%)\n"
        f"• Setia (P&M Rest +30%, Aggro +400%)\n"
        f"• Kalem (Max HP +30%)\n"
        f"• Penakut (Range Attack Only, MP Regen)\n"
        f"• Lembut (Can't Attack, MP Regen)\n"
        f"• Nekat (Bergerak Di Area Kecil)\n\n"
        f"*LEVELING PET* \n"
        f"• 1-40 = Pendekar Bertopeng (Normal)\n"
        f"• 40-46 = Pendekar Bertopeng (Hard)\n"
        f"• 46-72 = Pendekar Bertopeng (Nightmare)\n"
        f"• 72-102 = Pendekar Bertopeng (Ultimate)\n"
        f"• 102-160 = Cerberus (Ultimate)\n"
        f"• 160-210 = Venena Coenubia (Ultimate) / Finstern (Ultimate)\n"
        f"• 210-230 = Kuzto (Ultimate)\n"
        f"• 230-260 = Ferzen (Ultimate)\n\n"
        f" *Estimasi Leveling Level Terbatas (Limit):*\n"
        f"• Lvl +1 = 300 kill mob (±10 Menit)\n"
        f"• Lvl +2 = 600 kill mob (±20 Menit)\n"
        f"• Lvl +3 = 1.200 kill mob (±40 Menit)\n"
        f"• Lvl +4 = 2.400 kill mob (±80 Menit)\n"
        f"• Lvl +5 = 4.800 kill mob (±160 Menit)\n"
        f"• Lvl +6 = 9.600 kill mob (±320 Menit)\n"
        f"• Lvl +7 = 19.200 kill mob (±640 Menit)\n"
        f"• Lvl +8 = 38.400 kill mob (±1280 Menit)\n"
        f"• Lvl +9 = 76.800 kill mob (±2560 Menit)"
    )

def format_pet_detail(matched_nature: dict) -> str:
    """Format detailed information of a pet nature"""
    return (
        f"*Sifat Pet: {matched_nature['name']}* \n\n"
        f"- *Perilaku Tempur*:\n{matched_nature['behavior']}\n\n"
        f"- *Menghindar AoE Merah*:\n{matched_nature['aoe_avoid']}\n\n"
        f"- *Rekomendasi Tipe Pet*:\n{matched_nature['recom']}"
    )

ABOUT_TEXT = (
    "*ditdut toram* untuk memudahkan pencarian informasi toram online!\n\n"
    "Jika request atau keperluan project dll bisa hubungi owner!"
)

PING_TEXT = "Pong! "

QUOTE_TEXT = "Gausah quote quote ini bot bukan Mario Teguh!!!"

UNKNOWN_COMMAND_TEXT = "Peringatan: Commandnya kagak ada. Ketik yang bener dlu liat list make command ,menu gausah make command yang belum author SunKSenK Bot tambahin ngerti kagak?"

SUNK_TEXT = (
    " *SunKSenK* \n\n"
    "Sosok King Dual Sword yang menduduki takhta tertinggi dari segala king, apa itu THS? apa itu KETAN? apa itu HB MURTAD? apalagi BOWGUN cuihhh job dibawah King Dual Sword semua itu "
    "*SunKSenK King Dual Sword*, yang sekaligus merupakan Owner dari SunKSenK Bot!"
)

EXP_BUFF_LINES = [
    "Level 1  = 1 EXP",
    "Level 2  = 3 EXP",
    "Level 3  = 9 EXP",
    "Level 4  = 21 EXP",
    "Level 5  = 45 EXP",
    "Level 6  = 93 EXP",
    "Level 7  = 189 EXP",
    "Level 8  = 381 EXP",
    "Level 9  = 765 EXP",
    "Level 10 = 1.533 EXP",
]

BUFF_DATA = {
    "exp": {
        "title": "EXP COOKING FOOD BUFF",
        "aliases": ["exp", "level", "cooking", "masak", "cook"],
        "lines": EXP_BUFF_LINES,
    },
    "acc": {
        "title": "ACCURACY",
        "aliases": ["acc", "accuracy", "hit"],
        "lines": [
            "• 4261111 (+ AMPR)",
            "• 1018215 (Lv 9 + ATK)",
            "• 2010308",
        ],
    },
    "-aggro": {
        "title": "-AGGRO",
        "aliases": ["-aggro", "min aggro", "minaggro", "minus aggro", "aggro-"],
        "lines": [
            "• 1010261 (+ DEX)",
            "• 6213303 (+ M.Resist)",
            "• 3190038 (+ Fractional Barrier)",
            "• 2020808",
            "• 1010147",
        ],
    },
    "+aggro": {
        "title": "+AGGRO",
        "aliases": ["+aggro", "plus aggro", "plusaggro", "aggro+"],
        "lines": [
            "• 3040005 (+ HP)",
            "• 2020606 (+ RTE Water)",
            "• 2010136 (+ Weapon ATK)",
            "• 3204544 (+ Max MP)",
            "• 3010069 (+ Max MP)",
            "• 53010043",
            "• 3158668",
            "• 7171717",
            "• 1011340",
            "• 5261002",
        ],
    },
    "agi": {
        "title": "AGI",
        "aliases": ["agi", "agility"],
        "lines": [
            "• 4262222 (+ HP)",
            "• 3100301 (+ HP)",
            "• 7162029 (+ Critical Rate)",
            "• 1110033 (+ STR)",
            "• 2010750 (+ Critical Rate)",
            "• 2020037",
            "• 4027777",
        ],
    },
    "ampr": {
        "title": "AMPR",
        "aliases": ["ampr", "amp"],
        "lines": [
            "• 2011234 (+ Max MP)",
            "• 6030603 (+ Max MP)",
            "• 1010017 (+ Max MP)",
            "• 1010596 (+ Max MP)",
            "• 4261111 (+ Accuracy)",
            "• 1010058 (+ DEX)",
            "• 1047777 (+ INT)",
            "• 4040088 (+ INT)",
            "• 2020909 (+ RTE Light)",
            "• 2210000 (+ M.Resist)",
            "• 8077777 (+ Critical Rate)",
            "• 4233333",
            "• 7257777",
            "• 9060000",
            "• 1019696",
            "• 1022900",
            "• 4083005",
            "• 7220777",
            "• 4040404",
            "• 1010036",
            "• 3201003",
            "• 5236969",
            "• 3226325",
            "• 3063101",
            "• 2223330",
            "• 3020777",
        ],
    },
    "atk": {
        "title": "ATK",
        "aliases": ["atk", "attack"],
        "lines": [
            "• 1018215 (Lv 9 + Accuracy)",
            "• 6100000",
            "• 5110834",
            "• 1018215",
        ],
    },
    "fbarrier": {
        "title": "FRACTIONAL BARRIER",
        "aliases": ["fbarrier", "fbarier", "fractional barrier", "fractional barier", "fractional"],
        "lines": [
            "• 1012222",
            "• 53190003",
            "• 1074649 (+ DEX)",
            "• 4010024 (+ STR)",
            "• 6150029 (+ RTE Earth)",
            "• 3190038 (+ -Aggro)",
            "• 5261919 (Lv 9 + STR)",
            "• 3010003 (Lv 9)",
        ],
    },
    "pbarrier": {
        "title": "PHYSICAL BARRIER",
        "aliases": ["pbarrier", "pbarier", "physical barrier", "physical barier"],
        "lines": [
            "• 2020111",
        ],
    },
    "mbarrier": {
        "title": "MAGIC BARRIER",
        "aliases": ["mbarrier", "mbarier", "magic barrier", "magic barier"],
        "lines": [
            "• 2020505 (Lv 8)",
        ],
    },
    "cr": {
        "title": "CRITICAL RATE",
        "aliases": ["cr", "crit", "critical", "critical rate"],
        "lines": [
            "• 7162029 (+ AGI)",
            "• 1100000 (+ P.Resist)",
            "• 5119105 (+ INT)",
            "• 2010750 (+ AGI)",
            "• 3149696 (Lv 6 + DTE Wind)",
            "• 8077777 (+ AMPR)",
            "• 1240124",
            "• 1037777",
            "• 8020000",
            "• 6241210",
            "• 5010098",
            "• 1181140",
            "• 2022020",
            "• 6181111",
            "• 1200069",
            "• 1201021",
            "• 2010044",
            "• 3061206",
        ],
    },
    "dex": {
        "title": "DEX",
        "aliases": ["dex", "dexterity"],
        "lines": [
            "• 1107777 (+ HP)",
            "• 5010031 (+ AMPR)",
            "• 1010261 (+ -Aggro)",
            "• 5010092 (+ DTE Dark)",
            "• 1074649 (+ Fractional Barrier)",
            "• 3111999 (Lv 9 + DTE Light)",
            "• 2010079 (+ Max MP)",
            "• 2020222",
            "• 1160000",
            "• 1112220",
            "• 6010313",
            "• 1010058 (+ AMPR)",
        ],
    },
    "drop": {
        "title": "DROP RATE",
        "aliases": ["drop", "droprate", "drop rate", "dr"],
        "lines": [
            "• 4196969 (Lv 6)",
            "• 1010085 (Lv 6)",
            "• 1235980 (Lv 5)",
            "• 1010018 (Lv 5)",
            "• 1067777 (Lv 4)",
            "• 3112005 (Lv 4)",
            "• 2020096 (Lv 3)",
            "• 1240124 (Lv 3)",
            "• 1212121 (Lv 3)",
        ],
    },
    "dte neutral": {
        "title": "DTE NEUTRAL",
        "aliases": ["dte neutral", "dte netral", "dteneutral"],
        "lines": [
            "• 7012828 (Lv 7 + Max MP)",
            "• 1230500",
        ],
    },
    "dte dark": {
        "title": "DTE DARK",
        "aliases": ["dte dark", "dte kegelapan", "dte hitam", "dtedark"],
        "lines": [
            "• 1190020",
            "• 5010092 (+ DEX)",
            "• 1190020 (+ INT)",
            "• 6116116",
            "• 2130776",
            "• 1230600",
        ],
    },
    "dte light": {
        "title": "DTE LIGHT",
        "aliases": ["dte light", "dte cahaya", "dte putih", "dtelight"],
        "lines": [
            "• 1240000",
            "• 3111999",
            "• 1240000 (Lv 9 + Max MP)",
            "• 3111999 (Lv 9 + DEX)",
            "• 1019696 (Lv 8 + AMPR)",
            "• 2260333 (Lv 9)",
            "• 3111999 (Lv 9)",
            "• 4010090 (Lv 8)",
            "• 1230700 (Lv 10)",
        ],
    },
    "dte earth": {
        "title": "DTE EARTH",
        "aliases": ["dte earth", "dte tanah", "dte bumi", "dteearth"],
        "lines": [
            "• 1230100",
            "• 2020202",
            "• 4111113",
            "• 4233333 (+ AMPR)",
            "• 1011001 (Lv 9 + Max MP)",
            "• 4083005 (Lv 8 + AMPR)",
            "• 1010216 (Lv 8 + Max MP)",
            "• 7100666",
            "• 1010002 (Lv 8)",
        ],
    },
    "dte fire": {
        "title": "DTE FIRE",
        "aliases": ["dte fire", "dte api", "dtefire"],
        "lines": [
            "• 6098888",
            "• 3210106",
            "• 1230200",
            "• 1121212 (Lv 9)",
        ],
    },
    "dte water": {
        "title": "DTE WATER",
        "aliases": ["dte water", "dte air", "dtewater"],
        "lines": [
            "• 1230300",
            "• 7150030",
            "• 1110111",
            "• 7150029 (Lv 8 + Max MP)",
            "• 1010810 (Lv 6 + Weapon ATK)",
        ],
    },
    "dte wind": {
        "title": "DTE WIND",
        "aliases": ["dte wind", "dte angin", "dtewind"],
        "lines": [
            "• 1230400",
            "• 2210101 (Lv 10)",
            "• 3149696 (Lv 6 + Critical Rate)",
        ],
    },
    "hp": {
        "title": "MAX HP",
        "aliases": ["hp", "max hp", "maxhp"],
        "lines": [
            "• 2020096",
            "• 1107777 (+ DEX)",
            "• 4262222 (+ AGI)",
            "• 3100301 (+ AGI)",
            "• 3040005 (+ Aggro)",
            "• 1250015",
            "• 1180755",
            "• 8080000",
            "• 1010417",
            "• 1010356",
            "• 54154629",
        ],
    },
    "int": {
        "title": "INT",
        "aliases": ["int", "intelligence"],
        "lines": [
            "• 1032222 (+ Max MP)",
            "• 1047777 (+ AMPR)",
            "• 6010701 (+ P.Resist)",
            "• 5119105 (+ Critical Rate)",
            "• 4040088 (+ AMPR)",
            "• 1190020 (+ DTE Dark)",
            "• 2020707",
            "• 6061294",
            "• 1010140",
            "• 7130001",
        ],
    },
    "matk": {
        "title": "MATK",
        "aliases": ["matk", "magic atk", "magic attack"],
        "lines": [
            "• 1024649",
            "• 1021684 (Lv 9)",
        ],
    },
    "mp": {
        "title": "MAX MP",
        "aliases": ["mp", "max mp", "maxmp"],
        "lines": [
            "• 2011234 (+ AMPR)",
            "• 6030603 (+ AMPR)",
            "• 1010017 (+ AMPR)",
            "• 1010596 (+ AMPR)",
            "• 2010079 (+ DEX)",
            "• 1032222 (+ INT)",
            "• 3204544 (+ Aggro)",
            "• 3010069 (+ Aggro)",
            "• 6061616",
            "• 7012828",
            "• 8080000",
            "• 2232002",
            "• 1014999",
            "• 7150029",
            "• 3022048",
            "• 1010216",
            "• 2020101",
            "• 51110000",
            "• 1240000",
            "• 4120003",
            "• 3017676",
            "• 1025436",
            "• 1010143",
            "• 6053838",
            "• 1091111",
            "• 7010130",
            "• 6066666",
            "• 1011001",
            "• 1100017",
            "• 6052000",
            "• 3010037",
        ],
    },
    "pres": {
        "title": "PHYSICAL RESISTANCE",
        "aliases": ["pres", "presist", "physical resist", "physical resistance", "p.resist"],
        "lines": [
            "• 1100000 (+ Critical Rate)",
            "• 6010701 (+ INT)",
            "• 1020001 (+ RTE Light)",
            "• 7010014",
            "• 2020345",
            "• 9040000",
            "• 2020111",
            "• 1010081",
            "• 4010051",
        ],
    },
    "mres": {
        "title": "MAGIC RESISTANCE",
        "aliases": ["mres", "mresist", "magic resist", "magic resistance", "m.resist"],
        "lines": [
            "• 6213303 (+ Aggro)",
            "• 2210000 (+ AMPR)",
            "• 7010016",
            "• 2020505",
            "• 3041975",
            "• 7190000",
            "• 1111575",
            "• 6190007",
        ],
    },
    "rte dark": {
        "title": "RTE DARK",
        "aliases": ["rte dark", "rte kegelapan", "rte hitam", "rtedark"],
        "lines": [
            "• 2020707 (Lv 9 + INT)",
        ],
    },
    "rte light": {
        "title": "RTE LIGHT",
        "aliases": ["rte light", "rte cahaya", "rte putih", "rtelight"],
        "lines": [
            "• 2020909 (+ AMPR)",
            "• 1023040 (Lv 9 + AMPR)",
            "• 1020001 (Lv 7 + P.Resist)",
            "• 1112220 (Lv 7 + DEX)",
            "• 4220777 (Lv 4)",
        ],
    },
    "rte fire": {
        "title": "RTE FIRE",
        "aliases": ["rte fire", "rte api", "rtefire"],
        "lines": [
            "• 2020101 (Lv 9 + Max MP)",
        ],
    },
    "rte water": {
        "title": "RTE WATER",
        "aliases": ["rte water", "rte air", "rtewater"],
        "lines": [
            "• 2020606 (Lv 8 + Aggro)",
        ],
    },
    "rte wind": {
        "title": "RTE WIND",
        "aliases": ["rte wind", "rte angin", "rtewind"],
        "lines": [
            "• 2020222 (Lv 9)",
        ],
    },
    "rte earth": {
        "title": "RTE EARTH",
        "aliases": ["rte earth", "rte tanah", "rte bumi", "rteearth"],
        "lines": [
            "• 6150029 (+ Fractional Barrier)",
            "• 2020404 (Lv 9)",
        ],
    },
    "rte neutral": {
        "title": "RTE NEUTRAL",
        "aliases": ["rte neutral", "rte netral", "rteneutral"],
        "lines": [
            "• 2020303 (+ STR)",
            "• 7220777 (Lv 9)",
        ],
    },
    "str": {
        "title": "STR",
        "aliases": ["str", "strength"],
        "lines": [
            "• 1110033 (+ AGI)",
            "• 4010024 (+ Fractional Barrier)",
            "• 2020303 (+ RTE Neutral)",
            "• 2202202",
            "• 1150001",
            "• 1026234",
            "• 5261919",
            "• 5050888",
        ],
    },
    "vit": {
        "title": "VIT",
        "aliases": ["vit", "vitality"],
        "lines": [
            "• 5130123",
            "• 4032850",
        ],
    },
    "watk": {
        "title": "WEAPON ATK",
        "aliases": ["watk", "weapon atk", "weapon attack", "w.atk", "watak"],
        "lines": [
            "• 3010777 (+ Critical Rate)",
            "• 2010136 (+ Aggro)",
            "• 6100000",
            "• 9070000",
            "• 1011126",
            "• 8080080",
            "• 1067777",
            "• 4240242",
            "• 5110834",
            "• 6269999",
            "• 6010024",
            "• 1010810",
            "• 53010014",
        ],
    },
}

BUFF_GROUPS = {
    "aggro": {
        "title": "AGGRO",
        "aliases": ["aggro"],
        "keys": ["-aggro", "+aggro"],
    },
    "barrier": {
        "title": "BARRIER",
        "aliases": ["barrier", "barier"],
        "keys": ["fbarrier", "pbarrier", "mbarrier"],
    },
    "resist": {
        "title": "RESISTANCE",
        "aliases": ["resist", "resistance"],
        "keys": ["pres", "mres"],
    },
    "dte": {
        "title": "DTE (DAMAGE TO ELEMENT)",
        "aliases": ["dte"],
        "keys": ["dte neutral", "dte dark", "dte light", "dte earth", "dte fire", "dte water", "dte wind"],
    },
    "rte": {
        "title": "RTE (RESIST TO ELEMENT)",
        "aliases": ["rte"],
        "keys": ["rte dark", "rte light", "rte fire", "rte water", "rte wind", "rte earth", "rte neutral"],
    },
    "fire": {
        "title": "ELEMENT: FIRE",
        "aliases": ["fire", "api"],
        "keys": ["dte fire", "rte fire"],
    },
    "water": {
        "title": "ELEMENT: WATER",
        "aliases": ["water", "air"],
        "keys": ["dte water", "rte water"],
    },
    "wind": {
        "title": "ELEMENT: WIND",
        "aliases": ["wind", "angin"],
        "keys": ["dte wind", "rte wind"],
    },
    "earth": {
        "title": "ELEMENT: EARTH",
        "aliases": ["earth", "tanah", "bumi"],
        "keys": ["dte earth", "rte earth"],
    },
    "light": {
        "title": "ELEMENT: LIGHT",
        "aliases": ["light", "cahaya"],
        "keys": ["dte light", "rte light"],
    },
    "dark": {
        "title": "ELEMENT: DARK",
        "aliases": ["dark", "kegelapan", "hitam"],
        "keys": ["dte dark", "rte dark"],
    },
    "neutral": {
        "title": "ELEMENT: NEUTRAL",
        "aliases": ["neutral", "netral"],
        "keys": ["dte neutral", "rte neutral"],
    },
}

def build_full_buff_text() -> str:
    sections = []
    
    header = (
        "*DAFTAR FOOD BUFF LAND TORAM ONLINE*\n"
        "Gunakan: ,buff <kategori> untuk mencari kategori tertentu.\n"
        "Contoh: ,buff dex, ,buff str, ,buff ampr, ,buff cr\n"
        "──────────────────\n"
        "*EXP COOKING FOOD BUFF*\n" +
        "\n".join(EXP_BUFF_LINES)
    )
    sections.append(header)
    
    full_order = [
        ("acc", None),
        ("-aggro", "+aggro"),
        ("agi", None),
        ("ampr", None),
        ("atk", None),
        ("fbarrier", "pbarrier", "mbarrier"),
        ("cr", None),
        ("dex", None),
        ("drop", None),
        ("dte neutral", "dte dark", "dte light", "dte earth", "dte fire", "dte water", "dte wind"),
        ("hp", None),
        ("int", None),
        ("matk", None),
        ("mp", None),
        ("pres", "mres"),
        ("rte dark", "rte light", "rte fire", "rte water", "rte wind", "rte earth", "rte neutral"),
        ("str", None),
        ("vit", None),
        ("watk", None),
    ]
    
    for item in full_order:
        sec_parts = []
        if isinstance(item, tuple):
            keys = [k for k in item if k is not None]
        else:
            keys = [item]
        
        for k in keys:
            entry = BUFF_DATA[k]
            sec_parts.append(f"*{entry['title']}*\n" + "\n".join(entry["lines"]))
        
        sections.append("\n\n".join(sec_parts))
        
    return "\n──────────────────\n".join(sections)

BUFF_TEXT = build_full_buff_text()

def get_buff_response(query: str = "") -> str:
    clean_q = query.lower().strip()
    if not clean_q:
        return BUFF_TEXT
    
    norm_q = re.sub(r'[\s\-_]+', ' ', clean_q).strip()
    
    # 1. Match single category
    for key, data in BUFF_DATA.items():
        if clean_q == key or norm_q == key or clean_q in data["aliases"] or norm_q in data["aliases"]:
            body = "\n".join(data["lines"])
            return (
                f"*BUFF FOOD: {data['title']}*\n"
                f"──────────────────\n"
                f"{body}\n"
                f"──────────────────\n"
                f"Ketik ,buff untuk melihat semua daftar buff."
            )
            
    # 2. Match group category
    for g_key, g_data in BUFF_GROUPS.items():
        if clean_q == g_key or norm_q == g_key or clean_q in g_data["aliases"] or norm_q in g_data["aliases"]:
            sub_sections = []
            for k in g_data["keys"]:
                entry = BUFF_DATA[k]
                sub_sections.append(f"*{entry['title']}*\n" + "\n".join(entry["lines"]))
            
            body = "\n\n".join(sub_sections)
            return (
                f"*BUFF FOOD: {g_data['title']}*\n"
                f"──────────────────\n"
                f"{body}\n"
                f"──────────────────\n"
                f"Ketik ,buff untuk melihat semua daftar buff."
            )
            
    # 3. Not found
    return (
        f"Kategori buff \"{query}\" tidak ditemukan.\n\n"
        f"Kategori yang tersedia:\n"
        f"- Status: str, agi, vit, int, dex\n"
        f"- Stat Tempur: hp, mp, atk, matk, watk, cr, acc, ampr, drop\n"
        f"- Aggro: aggro, +aggro, -aggro\n"
        f"- Barrier: barrier, fbarrier, pbarrier, mbarrier\n"
        f"- Resistance: resist, pres, mres\n"
        f"- DTE: dte, dte fire, dte water, dte wind, dte earth, dte light, dte dark, dte neutral\n"
        f"- RTE: rte, rte fire, rte water, rte wind, rte earth, rte light, rte dark, rte neutral\n"
        f"- Elemen: fire, water, wind, earth, light, dark, neutral\n"
        f"- Lainnya: exp (kalkulator exp cooking)\n\n"
        f"Contoh penggunaan:\n"
        f"- ,buff dex\n"
        f"- ,buff str\n"
        f"- ,buff cr\n"
        f"- ,buff dte fire"
    )


MQ_TEXT = (
    " *DAFTAR BAHAN MAIN QUEST (MQ) TORAM ONLINE*\n"
    "Untuk awal hingga pertengahan permainan:\n\n"
    "- *Bab 1: The Beginning of Chaos*\n"
    "• 5x Daun Colon (Colon Leaf) – Lokasi: Land Under Development\n"
    "• 2x Sisik Naga (Hard Dragon Skin) – Lokasi: Decel (Boss) atau mobs Naga di Dragon's Den\n"
    "• 1x Daging Domba (Lamb Meat) – Lokasi: Rakau Plains\n"
    "• 3x Sulur (Vine) – Lokasi: Reug Saltou's Suburb\n"
    "• 3x Paruh Tebal (Thick Beak) – Lokasi: Ruined Temple\n"
    "• 3x Sayap Peri (Fairy Feather) – Lokasi: Ruined Temple\n\n"
    "- *Bab 2: Look for Holy Gems!*\n"
    "• 20x Koin Ksatria (Swordsman Stone Coin) – Lokasi: Saham Crater\n\n"
    "- *Bab 3: Battle with the Ancient God*\n"
    "• 1x Daging Tikus Pasir (Sand Mole Meat) – Lokasi: Aulada Tower\n"
    "• 3x Cakar Binatang Buas (Beast Claw) – Lokasi: Singolare Ruins\n"
    "• 5x Kulit Kodok Pasir (Sand Frog Skin) – Lokasi: Akaku Desert\n"
    "• 10x Taring Bergerigi (Jagged Fang) – Lokasi: Ethos Fortress\n"
    "• 5x Kristal Saham (Saham Crystal) – Lokasi: Saham Underground Cave\n"
    "• 1x Permata Jiwa (Spiritual Gemstone) – Lokasi: Ancient Empress Tomb\n\n"
    "- *Bab 8: The Road to Elden*\n"
    "• 5x Anggur Rokoko (Rokoko Grape) – Lokasi: Rokoko Plains\n\n"
    "- *Bab 9: Recapturing El Scaro*\n"
    "• 10x Kayu Labilans (Labilans Wood) – Lokasi: Labilans Gorge\n\n"
    "- *Bab 11: The Altar of Deities*\n"
    "• 20x Tanduk Patah (Broken Horn) – Lokasi: Mt. Mahat\n\n"
    "- *Bab 12: The Choice of the Goddess*\n"
    "• 5x Bijih Berkembang (Growing Ore) – Lokasi: Deepest Part of Mount Elb\n"
    "• 5x Batu Jabali (Jabali Stone) – Lokasi: Jabali Valley\n\n"
    "- *Bab 14 & 15: Cerita Terbaru*\n"
    "• 20x Kulit Tebal Berlendir (Slimy Thick Skin) – Lokasi: Map Bab 14\n"
    "• 10x Akar Melilit (Tangled Roots) – Lokasi: Map Bab 14\n"
    "• 10x Kayu Menabra (Menabra Wood) – Lokasi: Map Bab 15"
)

TAS_TEXT = """ *TAMBAH SLOT TAS KOLEKSI TORAM ONLINE* 

- *50-51*
- Kulit Colon x1 [Colon : Tanah Pembangunan]

- *51-52*
- Kulit Berkualitas x1 [Lavarca : Dataran Rakau]

- *52-53*
- Spina x1.000

- *53-54*
- Kulit Minotaur x1 [Minotaur : Kuil Runtuh: Area Terlarang]
- Pecahan Kristal Jingga x1 [Cobre : Danau Icule]

- *54-55*
- Kulit Anjing Hutan x1 [Anjing Hutan : Hutan Marbabo: Bagian Dalam]
- Lencana Goblin x1 [Boss Goblin : Gua Ribisco: Bagian Dalam]

- *55-56*
- Spina x2.000

- *56-57*
- Bulu Mochelo x1 [Mochelo : Lereng Merapi A3]
- Kain Linen x10 [Crow Killer : Dusun Douce]

- *57-58*
- Bulu Naga Giok x1 [Forestia : Tanah Kaos]
- Tanduk Berkualitas x10 [Bandot : Tanah Tinggi Yorl]

- *58-59*
- Sabuk Bos Roga x1 [Boss Roga : Gua Bawah Tanah Saham: Ujung]
- Kain Beludu x10 [Orc Petarung : Gua Bawah Tanah Saham]

- *59-60*
- Spina x4.000

- *60-61*
- Cakar Beruang x2 [Violaccoon : Padang Darkanon]
- Sheeting Fabric x20 [Cassy : Makam Ratu Kuno: Area 2]

- *61-62*
- Rantai Kukuh x2 [Pendekar Bertopeng : Tanah Tinggi Pertanian]
- Kain Polister x20 [Boneka Pengembara : Kota Hilang]

- *62-63*
- Sisik Naga Sabana x2 [Naga Sabana Yelb : Desa Albatif]
- Kulit Serigala Alien x20 [Serigala Luar : Gerbang Dunia Lain: Area 1]

- *63-64*
- Spina x8.000

- *64-65*
- Jubah Sobek x2 [Goovua : Gurun Akaku: Bukit]
- Kulit Tupai x20 [Rodentail : Maia Diela]

- *65-66*
- Tanduk Elang Zamrud x2 [Elang Zamrud : Teras Kerikil]
- Bulu Kambing x20 [Koza : Jurang Dunkel]

- *66-67*
- Sayap Naga Senja x2 [Naga Senja : Benteng Solfini: Atap]
- Bulu Halus x20 [Little Snow Boar : Lembah Es Polde]

- *67-68*
- Spina x16.000

- *68-69*
- Rantai Penyucian x2 [Cerberus : Mata Air Kelahiran: Puncak]
- Kain Goyah x20 [Jewel Eye : Mata Air Kelahiran: Tengah]

- *69-70*
- Benang Aranea x2 [Aranea : Taman Sublimasi: Pusat]
- Benang Laba-Laba Kecil x20 [Aramia : Taman Sublimasi: Area 2]

- *70-71*
- Kain Dewi Tiruan x3 [Imitacia : Istana Gelap: Aula Besar]
- Kain Apung x10 [Flying Executioner : Buaian Prajurit]
- Tapak Lembut x20 [Bunny Summoner : Sungai Kegelapan]

- *71-72*
- Surai Hewan Iblis x3 [Memecoleous : Istana Gelap: Area2]
- Bantalan Tapak Keras x10 [Manticore : Istana Gelap: Area1]
- Bulu Bayangan Hitam x20 [Shadow Fly : Istana Gelap: Area1]

- *72-73*
- Spina x32.000

- *73-74*
- Bulu Tapir x3 [Tapir : Graben Membara: Permukaan]
- Bulu Kaku x10 [Wooly : Graben Membara: Permukaan]
- Minyak Anti Karat x20 [Ornis Demi Machina : Garis Pertahanan Artileri Otomatis]

- *74-75*
- Kain Kuno x3 [Proto Leon : Reruntuhan Singolaire: Lantai 3]
- Kulit Pohon Lunak x10 [Floral Bee : Situs Simcracker]
- Rambut Potum Kotor x20 [Slum Potum : Klaspe Kumuh]

- *75-76*
- Tulang Raksasa Merah x3 [Dusk Machina : Pabrik Demi Machina Kecil: Area 2]
- Mantel Hitam Sobek x10 [Rugos Demi Machina : Pabrik Demi Machina Kecil: Area 2]
- Rantai Putus x20 [Machina Penyiksa : Pabrik Demi Machina Kecil: Area 2]

- *76-77*
- Sisik Chimera x3 [Mozto Machina : Pabrik Demi Machina Besar: Bagian Terdalam]
- Benda Pendar Aneh x10 [Horn Machina : Pabrik Demi Machina Besar]
- Tentakel Tangguh x20 [Ledon Machina : Pabrik Demi Machina Besar]

- *77-78*
- Spina x64.000

- *78-79*
- Jubah Roh Hutan x3 [Lalvada : Hutan Monster: Bagian Dalam]
- Taring Tanaman x10 [Nepenthe : Hutan Monster]
- Kain Felt x20 [Naga Boneka : Mansion Lufenas]

- *79-80*
- Aloi Lyark x3 [Gwaimol : Penjara Cuervo: Atap]
- Baju Penjaga Robek x10 [Sipir Lyark : Penjara Cuervo: Lantai 2]
- Kain Lembu x20 [Lyark Spesialis : Laboratorium Brahe: Area 2]

- *80-81*
- Kain Bercahaya x4 [Seraph Machina : Menara Penembus Bumi: Sisi Dalam]
- Kulit Sintetis Rusak x20 [Lyark Brawler : Sekitar Alun-Alun Droma]
- Cawat Pengeksekusi x20 [Volo : Sekitar Alun-Alun Droma Area 2]

- *81-82*
- Potongan Baju K. Kecil x4 [Venena : Istana Ultimea: Takhta]
- Pecahan Zirah Keras x20 [High Tigris : Istana Ultimea Gudang Demi Machina]
- Kulit Ular x20 [Ular Kolam : Reservoir Copia]

- *82-83*
- Spina x100.000

- *83-84*
- Kulit Mama Fluck x4 [Mama Fluck : Gua Pelupa]
- Daun Besar Colon x20 [Leedle Colon : Dataran Rokoko]
- Bulu Garis Vertikal x20 [Rakun Tambun : Hutan Curonne]

- *84-85*
- Kain Rohani Mardula x4 [Mardula : Serambi Dewa Berkah]
- Kain Berkilau Misterius x20 [Malaikat Gelembung : Koridor Heresi/Kuil Para Dewa/Serambi Dewa Pembangunan/Serambi Dewa Istimewa]
- Bulu Kelabu x20 [Haliabubo : Reruntuhan G. Mithurna: Koridor Atas]

- *85-86*
- Mantel Carbuncle x4 [Carbuncle : Serambi Dewa Pembangunan]
- Kain Rajut x20 [Malaikat Gelembung : Koridor Heresi/Kuil Para Dewa/Serambi Dewa Pembangunan/Serambi Dewa Istimewa]
- Ekor Beruang Berkantong x20 [Oddy : Kuil Para Dewa: Area 4/Serambi Dewa Pembangunan]

- *86-87*
- Bulu Raja Piton x4 [Raja Piton : Pegunungan Elf: Kuil]
- Bulu Putih Lebat x20 [Bandot : Taman Es & Salju]
- Bulu Abu Kaku x20 [Silveria : Pegunungan Elf]

- *87-88*
- Ingot Kuno x4 [Golem Preman : Kuil Naga Kegelapan: Tengah]
- Taring Serigala Es x20 [Corloup : Pegunungan Elf]
- Kain Gelap x20 [Soul Reaper : Kuil Naga Kegelapan]

- *88-89*
- Spina x200.000

- *89-90*
- Taring Tuscog x4 [Tuscog : Jalan Eryldan: Sekitar Hutan Ein]
- Sutra Ulat x20 [Tikus Lumut : Hutan Ein]
- Bulu Manusia Serigala x20 [Wolfret : Jalan Eryldan]

- *90-91*
- Serpihan Kayu Kuzto x5 [Kuzto : Distrik Labilans: Alun-Alun]
- Bulu Cerpelai x20 [Satwal : Distrik Fabriska]
- Sabuk Pinggang Misterius x30 [Moculus : Distrik Fractum: Area 1]

- *91-92*
- Kantong Kristal x5 [Nemopirania : Distrik Racetacula: Area 1]
- Ekor Lembut x20 [Alpoa : Distrik Labilans: Area 3]
- Papula Kuat x30 [Toksinaria : Distrik Racetacula: Area 1]

- *92-93*
- Sayap Repthon x5 [Repthon : Zona Riset Delzton: Area Terdalam]
- Kancing Polong x20 [Colon Marquis : Reruntuhan Mansion Lufenas Tua]
- Kain Perca Jas Panjang x30 [Gulingkar : Zona Riset Delzton: Area 1]

- *93-94*
- Rambut Kaisar Siluman x5 [Venena Metacoenubia : Neo Plastida]
- Kain Merah Sobek x20 [Potum Bandit Gurun; Gurun Pasir Geist: Area 1]
- Kulit Karatan x30 [Jasman : Reruntuhan Elban Urban]

- *94-95*
- Spina x300.000

- *95-96*
- Tulang Pisteus x5 [Pisteus : Pesisir Ducia: Area Terdalam]
- Kain Fantom x20 [Flooray : Dasar Tebing Lunagent]
- Bulu Berang-Berang Laut x30 [Lutris : Pesisir Ducia: Area 3]

- *96-97*
- Sayap Arachnidemon x5 [Arachnidemon : Lembah Arche: Area Terdalam]
- Belenggu Logam x20 [Besy : Lembah Arche]
- Kulit Ular Aneh x30 [Coofer : Reruntuhan Kota Rokoko]

- *97-98*
- Jangat Berlendir x5 [Datuk Nezim : Lahan Basah Nezim]
- Kain Enty x20 [Enty : Rimba Penyihir]
- Poros Kokoh x30 [Orang2an Sawah Seram : Rimba Penyihir: Area 2]

- *98-99*
- Perca Gendam Geni x5 [Hexter : Rimba Penyihir: Area Terdalam]
- Piring Kappa x20 [Kappadon : Lahan Basah Nezim]
- Bulu Gagak x30 [Orang2an Sawah Seram : Rimba Penyihir: Area 2]

- *99-100*
- Inti Latebra Menggeliat x5 [Trocostida : Nov Diela: Area 1]
- Cairan Lekat x20 [Juvestida : Nov Diela: Area 1]
- Kulit Pelik x30 [Mata Jahat : Padang Morga: Area 1]"""

STATLIST_TEXT = (
    "*TORAM ONLINE STAT LIST (STATTING)* \n\n"
    "*Catatan Penting (NOTE):*\n"
    "• `elematch` dan `elenon` cukup isi *1*\n"
    "• Elemen default adalah *Fire* (karena tidak berpengaruh pada Cost)\n"
    "• `pot`: Potensial equipment (*Wajib diisi*)\n"
    "• `prof`: Level profesi BS (*Opsional*)\n"
    "• Maksimal *6 stats* untuk masing-masing stats positif (+) dan negatif (-)\n\n"
    "──────────────────\n\n"
    " *Enhance Stats:*\n"
    "• `str` : STR\n"
    "• `str%` : STR%\n"
    "• `int` : INT\n"
    "• `int%` : INT%\n"
    "• `vit` : VIT\n"
    "• `vit%` : VIT%\n"
    "• `agi` : AGI\n"
    "• `agi%` : AGI%\n"
    "• `dex` : DEX\n"
    "• `dex%` : DEX%\n\n"
    " *Enhance HP/MP:*\n"
    "• `hpreg` : Natural HP regen\n"
    "• `hpreg%` : Natural HP regen%\n"
    "• `mpreg` : Natural MP regen\n"
    "• `mpreg%` : Natural MP regen%\n"
    "• `hp` : MaxHP\n"
    "• `maxhp%` : MaxHP%\n"
    "• `maxmp` : MaxMP\n\n"
    "*Enhance Attack:*\n"
    "• `atk` : ATK\n"
    "• `atk%` : ATK%\n"
    "• `matk` : MATK\n"
    "• `matk%` : MATK%\n"
    "• `stab%` : Stability%\n"
    "• `pp%` : Physical Pierce %\n"
    "• `mp%` : Magic Pierce %\n\n"
    " *Enhance Defense:*\n"
    "• `def` : DEF\n"
    "• `mdef` : MDEF\n"
    "• `def%` : DEF%\n"
    "• `mdef%` : MDEF%\n"
    "• `pres%` : Physical Resistance %\n"
    "• `mres%` : Magic Resistance %\n"
    "• `foe%` : % Reduce Dmg (Foe Epicenter)\n"
    "• `bow%` : % Reduce Dmg (Bowling)\n"
    "• `bull%` : % Reduce Dmg (Bullet)\n"
    "• `flo%` : % Reduce Dmg (Floor)\n"
    "• `line` : % Reduce Dmg (Straight Line)\n"
    "• `Charge%` : % Reduce Dmg (Charge)\n"
    "• `epic%` : % Reduce Dmg (Player Epicenter)\n"
    "• `mete%` : % Reduce Dmg (Meteor)\n\n"
    " *Enhance Accuracy:*\n"
    "• `acc` : Accuracy\n"
    "• `acc%` : Accuracy %\n\n"
    " *Enhance Dodge:*\n"
    "• `dodge` : Dodge\n"
    "• `dodge%` : Dodge %\n\n"
    " *Enhance Speed:*\n"
    "• `aspd` : ASPD\n"
    "• `aspd%` : ASPD%\n"
    "• `cspd` : CSPD\n"
    "• `cspd%` : CSPD%\n\n"
    " *Enhance Critical:*\n"
    "• `cr` : Critical Rate\n"
    "• `cr%` : Critical Rate%\n"
    "• `cd` : Critical Damage\n"
    "• `cd%` : Critical Damage%\n\n"
    " *Enhance Elements:*\n"
    "• `dte%` : % Stronger Against ele (fire)\n"
    "• `dtefire%` : % Stronger Against Fire\n"
    "• `dtewater%` : % Stronger Against Water\n"
    "• `dtewind%` : % Stronger Against Wind\n"
    "• `dteearth%` : % Stronger Against Earth\n"
    "• `dtelight%` : % Stronger Against Light\n"
    "• `dtedark%` : % Stronger Against Dark\n"
    "• `rte%` : ele Resistance % (fire)\n"
    "• `rtefire%` : Fire Resistance %\n"
    "• `rtewater%` : Water Resistance %\n"
    "• `rtewind%` : Wind Resistance %\n"
    "• `rteearth%` : Earth Resistance %\n"
    "• `rtelight%` : Light Resistance %\n"
    "• `rtedark%` : Dark Resistance %\n\n"
    "*Special Enhancement:*\n"
    "• `ail%` : Ailment Resistance %\n"
    "• `eva%` : Evasion Rate %\n"
    "• `guard` : Guard Power\n"
    "• `guard%` : Guard Rate %\n"
    "• `aggro%` : Aggro %\n\n"
    " *Awaken Elements:*\n"
    "• `elematch` : Element (matching)\n"
    "• `elenon` : Element (not matching)\n"
)

# ==============================================================================
# DATABASE & KALKULATOR EXP MAIN QUEST (MQ) TORAM ONLINE (RAFFY.CLUB / TORAM TOOLS)
# ==============================================================================
MQ_CHAPTERS_DATA = [
    {
        "chapter": 1,
        "title": "The Beginning of Chaos",
        "episodes": [
            (1, "First Time Visit", 30),
            (2, "Straye Brother and Sister", 80),
            (3, "A Golem on a Rampage", 730),
            (4, "The Goddess of Wisdom", 2060),
            (5, "The Dragon's Den", 4700),
            (6, "The Ruined Temple", 9330),
            (7, "The First Magic Stone", 16700),
            (8, "Purification Incense", 27900),
            (9, "The Dragon and Black Crystal", 43000),
        ]
    },
    {
        "chapter": 2,
        "title": "Look for Holy Gems!",
        "episodes": [
            (1, "The Merchant Girl", 64000),
            (2, "Where Are the Gems?", 92000),
            (3, "Who is the Black Knight?!", 118200),
            (4, "Trials in the Palace", 149000),
            (5, "The Moon Wizard", 172000),
            (6, "The Follower and Hater", 227000),
            (7, "The Wizard's Cave", 240000),
            (8, "The Star Wizard", 255000),
        ]
    },
    {
        "chapter": 3,
        "title": "Battle with the Ancient God",
        "episodes": [
            (1, "The Invincible... Enemy??", 270000),
            (2, "The Ancient Empress", 284000),
            (3, "The Culprit", 319000),
            (4, "Fate of the Fortress", 335000),
            (5, "Memory in the Lost Town", 398000),
            (6, "The Stolen Sorcery Gem", 417000),
            (7, "Living with a Dragon", 462300),
            (8, "Monsters from Outerworld", 540000),
        ]
    },
    {
        "chapter": 4,
        "title": "The Creeping Shadows",
        "episodes": [
            (1, "The Mage Diels", 562000),
            (2, "Journey for Reconstruction", 585000),
            (3, "The Sacred Gem in Akaku", 710000),
            (4, "The King of Darkan", 740000),
            (5, "The Lurking Evil", 803000),
            (6, "Find the False Black Knight!", 913000),
            (7, "Technista's Movement", 1000000),
            (8, "The Falling Feather of Death", 1100000),
        ]
    },
    {
        "chapter": 5,
        "title": "The Storm in the Darkness",
        "episodes": [
            (1, "In the Unknown Darkness", 1150000),
            (2, "The Charm", 1310000),
            (3, "Parching Dark Mirror", 1370000),
            (4, "Fierce Battle in the Garden", 1550000),
            (5, "A Light in the Darkness", 1750000),
            (6, "The Ones Nesting in the Manor", 1970000),
            (7, "The Dark Castle", 2210000),
            (8, "To the World of the Living", 2220000),
        ]
    },
    {
        "chapter": 6,
        "title": "The Two Technistas",
        "episodes": [
            (1, "Demi Machina", 2600000),
            (2, "The Town of Pax Faction", 2700000),
            (3, "Mechanical Heart", 2800000),
            (4, "Black Knights of Lyark", 2820000),
            (5, "The Mysterious Artifact", 3030000),
            (6, "Truth of the Artifact", 3099000),
            (7, "The Price of Treachery", 3320000),
            (8, "The Blasphemous Factory", 3640000),
            (9, "Mystery of the Black Knights", 4020000),
        ]
    },
    {
        "chapter": 7,
        "title": "Upheaval in Ultimea",
        "episodes": [
            (1, "Monster's Forest", 4730000),
            (2, "The Underground Town", 4820000),
            (3, "The Elves in Lyark", 5070000),
            (4, "The Mad Laboratory", 5500000),
            (5, "Tragedy in the Jail", 6000000),
            (6, "Calamity in Droma Square", 6400000),
            (7, "Head for Ultimea Palace", 6900000),
            (8, "The Chaotic Truth", 7400000),
        ]
    },
    {
        "chapter": 8,
        "title": "Road to Eldenbaum",
        "episodes": [
            (1, "The Mine Where Monsters Lurk", 8400000),
            (2, "The Mysterious Shadow", 8500000),
            (3, "The New Diel Country", 8600000),
            (4, "The Ruins of the Gods", 8800000),
            (5, "The Former God of Justice", 9100000),
            (6, "The Remaining Thrones in the Shrine", 9700000),
            (7, "Gods' Whereabouts", 10400000),
            (8, "The Wait at Specia's Shrine", 11100000),
            (9, "The Warden of Ice & Snow", 11800000),
            (10, "At Mountains' End", 12500000),
        ]
    },
    {
        "chapter": 9,
        "title": "Recapturing Eldenbaum",
        "episodes": [
            (1, "Deadly Road to Eldenbaum", 15800000),
            (2, "Unforeseen Traps", 17100000),
            (3, "Traces of Technological Progress", 18200000),
            (4, "An Unexpected Acquaintance", 19200000),
            (5, "Front Line Base Operation", 20300000),
            (6, "Strategy to Redeem the Treetop Harbor", 21500000),
            (7, "The Teleporter Left Behind", 22800000),
            (8, "The Man Who Seeks Death", 24100000),
            (9, "The Battle to Recapture Eldenbaum", 25500000),
            (10, "A New Beginning", 12200000),
        ]
    },
    {
        "chapter": 10,
        "title": "The Lost God's Ship",
        "episodes": [
            (1, "Off to the Fateful Land", 26000000),
            (2, "The Inhabitants Under the Cliff", 27400000),
            (3, "The Nightmare Returns", 28800000),
            (4, "The Whereabouts of the Missing Monks", 30200000),
            (5, "The Goddess of Justice and the Squatters", 31600000),
            (6, "Navigator of the Ark", 33100000),
            (7, "The Witch in the Woods", 34600000),
            (8, "The Duel in Nov Diela", 36200000),
        ]
    },
    {
        "chapter": 11,
        "title": "Off to Toram",
        "episodes": [
            (1, "Flying the Ark", 37800000),
            (2, "Land of the Unknown", 49000000),
            (3, "The Strolling Forest", 51000000),
            (4, "Eumanos the Forest Dwellers", 53400000),
            (5, "A Sproutling is Born", 55700000),
            (6, "The Blessing-Bearer", 58100000),
            (7, "Intense Battle in Coenubia's Stronghold", 60500000),
            (8, "The Shadow of a Smoky Mountain", 63000000),
            (9, "The Weredragons & the Underground World", 65500000),
        ]
    },
    {
        "chapter": 12,
        "title": "The Weredragons' Vital Point",
        "episodes": [
            (1, "The Sky with a Ceiling", 73400000),
            (2, "Rivalry Between Dragons and Weredragons", 76300000),
            (3, "Weredragon Couple and a Baby", 79300000),
            (4, "Weredragons' Vital Point", 82300000),
            (5, "Intense Battle in the Propulsion System", 85300000),
            (6, "Discovering a New Technology", 44200000),
            (7, "Ark Repair", 92700000),
            (8, "Weredragon Dispute", 96000000),
            (9, "Cocoon in the Ice Wall", 99300000),
        ]
    },
    {
        "chapter": 13,
        "title": "The Water Tribe and Coenubia",
        "episodes": [
            (1, "Underwater Inhabitants", 112600000),
            (2, "Water Dome", 116500000),
            (3, "Underwater City", 60200000),
            (4, "The Thing in the Abandoned District", 125800000),
            (5, "Shadow from the Abyss", 129900000),
            (6, "The Ruthless Council", 67000000),
            (7, "Mysterious Entity in the Little Shrine", 139900000),
            (8, "The Great Battle Underwater", 144200000),
        ]
    },
    {
        "chapter": 14,
        "title": "Mainland Toram",
        "episodes": [
            (1, "Crisis in the Sky", 159100000),
            (2, "The Surviving Siblings", 164000000),
            (3, "Chaotic Situation", 168900000),
            (4, "The Bitter Truth", 173800000),
            (5, "The Uncouth Rana Prince", 178800000),
            (6, "Mutant Coenubia Village", 183900000),
            (7, "Fierce Battle with Mutant Lixis", 189000000),
        ]
    },
    {
        "chapter": 15,
        "title": "Coenubia's Awakening",
        "episodes": [
            (1, "Ark Crisis", 210500000),
            (2, "Coastal Clash", 216300000),
            (3, "Unda's Rescue Operation", 222200000),
            (4, "Unda's Return", 228100000),
            (5, "The Young Man and the Old Tree", 234000000),
            (6, "The Village of Lixis", 240000000),
            (7, "Visions of a Distant Past", 246000000),
            (8, "As the Roots Come to Light", 252100000),
        ]
    },
    {
        "chapter": 16,
        "title": "The Royal Dragon's Bloodline",
        "episodes": [
            (1, "Freedos's Thoughts", 141700000),
            (2, "Chaos in the Valley", 293700000),
        ]
    }
]


def get_toram_level_exp(lv: int) -> int:
    """Rumus resmi kebutuhan EXP dari Level `lv` ke `lv + 1` di Toram Online: floor(0.025 * lv^4 + 2 * lv)"""
    if lv < 1:
        return 0
    return int(0.025 * (lv ** 4) + 2 * lv)


def simulate_exp_gain(start_lv: int, start_pct: float, gained_exp: int) -> tuple[int, float, int]:
    """Menghitung level baru, persentase baru, dan sisa EXP ke level berikutnya setelah mendapat `gained_exp`."""
    curr_lv = max(1, start_lv)
    curr_pct = max(0.0, min(99.99, start_pct))
    req_curr = get_toram_level_exp(curr_lv)
    rem_exp = int(req_curr * (curr_pct / 100.0)) + gained_exp

    while curr_lv < 500:
        req = get_toram_level_exp(curr_lv)
        if rem_exp >= req:
            rem_exp -= req
            curr_lv += 1
        else:
            break

    final_req = get_toram_level_exp(curr_lv)
    final_pct = (rem_exp / final_req) * 100.0 if final_req > 0 else 0.0
    exp_to_next = max(0, final_req - rem_exp)
    return curr_lv, final_pct, exp_to_next


def calculate_mq_exp(query: str = "", spam_runs: int = 1) -> str:
    """Kalkulator EXP Main Quest (MQ) Toram Online & Perencanaan Adventurer's Diary"""
    flat_episodes = []
    for ch_obj in MQ_CHAPTERS_DATA:
        ch_num = ch_obj["chapter"]
        ch_title = ch_obj["title"]
        for ep_num, ep_title, ep_exp in ch_obj["episodes"]:
            flat_episodes.append({
                "ch": ch_num,
                "ch_title": ch_title,
                "ep": ep_num,
                "ep_title": ep_title,
                "exp": ep_exp,
                "code": f"{ch_num}-{ep_num}"
            })

    total_all_mq = sum(x["exp"] for x in flat_episodes)
    last_ep_obj = flat_episodes[-1]

    q = query.strip()
    q_low = q.lower()

    # 1. Jika meminta daftar total EXP per Bab (,mqexp list)
    if q_low in ["list", "daftar", "bab", "chapter", "chapters", "tabel"]:
        lines = [
            "*TABEL TOTAL EXP MAIN QUEST (MQ) TORAM ONLINE*",
            "_Sumber: Raffy Club / Toram Tools MQ Database_\n"
        ]
        for ch_obj in MQ_CHAPTERS_DATA:
            ch_sum = sum(e[2] for e in ch_obj["episodes"])
            ep_cnt = len(ch_obj["episodes"])
            lines.append(f"• *Bab {ch_obj['chapter']}: {ch_obj['title']}* ({ep_cnt} Ep)\n  └ Total: `{ch_sum:,}` EXP")
        lines.append(f"\n*Total Keseluruhan (Bab 1 - {last_ep_obj['ch']}):* `{total_all_mq:,}` EXP")
        lines.append("\n*Tips:*")
        lines.append("• Ketik `,mq bab 15` untuk melihat rincian EXP tiap episode di Bab 15.")
        lines.append("• Ketik `,mq 150` untuk menghitung naik ke level berapa jika mulai MQ dari Lv 150.")
        return "\n".join(lines)

    # 2. Jika meminta rincian episode pada bab tertentu (,mqexp bab 15 / ,mqexp ch 15)
    m_ch_detail = re.match(r'^(?:bab|ch|chapter)\s*(\d+)$', q_low)
    if m_ch_detail:
        target_ch = int(m_ch_detail.group(1))
        ch_found = next((c for c in MQ_CHAPTERS_DATA if c["chapter"] == target_ch), None)
        if not ch_found:
            return f"Peringatan: Bab {target_ch} tidak ditemukan. Saat ini MQ tersedia dari Bab 1 s/d Bab {last_ep_obj['ch']}."
        ch_sum = sum(e[2] for e in ch_found["episodes"])
        lines = [
            f"*RINCIAN EXP MQ BAB {target_ch}: {ch_found['title'].upper()}*",
            "──────────────────────────"
        ]
        for ep_num, ep_title, ep_exp in ch_found["episodes"]:
            lines.append(f"• *[{target_ch}-{ep_num}] {ep_title}*\n  └ `{ep_exp:,}` EXP")
        lines.append("──────────────────────────")
        lines.append(f"*Total EXP Bab {target_ch}:* `{ch_sum:,}` EXP")
        lines.append(f"\nContoh hitung dari bab ini: `,mq 1 {target_ch}-1 {last_ep_obj['code']}`")
        return "\n".join(lines)

    # 3. Jika tanpa argumen atau help, tampilkan panduan penggunaan
    if not q or q_low in ["help", "panduan", "cara", "info"]:
        lv_def, pct_def, _ = simulate_exp_gain(1, 0.0, total_all_mq)
        return (
            "*PANDUAN KALKULATOR EXP MAIN QUEST (MQ)*\n"
            "_Sumber: Raffy Club / Toram Tools MQ Calculator_\n"
            "──────────────────────────\n"
            f"• Bab MQ Tersedia: Bab 1 s/d Bab {last_ep_obj['ch']} (Tamat)\n"
            f"• Total EXP Full MQ (1x Run): `{total_all_mq:,}` EXP\n"
            f"• Dari Lv 1 (0%) Full MQ: Naik ke *Lv {lv_def} ({pct_def:.1f}%)*\n"
            "──────────────────────────\n"
            "*Format Penggunaan:*\n\n"
            "1. Hitung 1x MQ (dari bab mulai s/d bab terakhir):\n"
            "   `,mq <level> [persen%] [bab_mulai]`\n"
            "   Contoh:\n"
            f"   • `,mq 150 60% 9` (Lv 150 60% mulai Bab 9 s/d Bab {last_ep_obj['ch']})\n"
            f"   • `,mq 150 9`     (Lv 150 0% mulai Bab 9 s/d Bab {last_ep_obj['ch']})\n"
            f"   • `,mq 150`       (Lv 150 mulai Bab 1 s/d Bab {last_ep_obj['ch']})\n\n"
            "2. Pengulangan MQ (Adventurer's Diary):\n"
            "   `,mqspam<jumlah> <level> [persen%] [bab_mulai]`\n"
            "   Contoh:\n"
            f"   • `,mqspam2 150 60% 9` (Spam ulang MQ 2x dari Bab 9)\n"
            f"   • `,mqspam3 200 11`    (Spam ulang MQ 3x dari Bab 11)\n\n"
            "3. Tabel EXP per Bab:\n"
            "   • `,mq list`   (Daftar total EXP tiap bab)\n"
            "   • `,mq bab 15` (Rincian episode Bab 15)"
        )

    # 4. Parsing argumen fleksibel
    start_lv = 1
    start_pct = 0.0
    start_ch, start_ep = 1, 1
    end_ch, end_ep = last_ep_obj["ch"], last_ep_obj["ep"]
    diary_runs = max(1, min(20, spam_runs))
    target_lv = 305

    def parse_ch_ep(token: str, is_end: bool = False) -> tuple[int, int] | None:
        token = token.strip().lower().replace("bab", "").replace("ch", "").strip()
        m_ce = re.match(r'^(\d{1,2})[\-:.](\d{1,2})$', token)
        if m_ce:
            c_v, e_v = int(m_ce.group(1)), int(m_ce.group(2))
            if 1 <= c_v <= last_ep_obj["ch"]:
                return (c_v, e_v)
        if token.isdigit():
            c_v = int(token)
            if 1 <= c_v <= last_ep_obj["ch"]:
                ch_d = next((c for c in MQ_CHAPTERS_DATA if c["chapter"] == c_v), None)
                if ch_d:
                    return (c_v, len(ch_d["episodes"]) if is_end else 1)
        return None

    # Cek key=value terlebih dahulu
    kv_matches = re.findall(r'(lv|lvl|level|exp|pct|dari|start|from|mulai|sampai|end|to|diary|run|runs|target)\s*=\s*([^\s,]+)', q_low)
    cleaned_q = re.sub(r'(lv|lvl|level|exp|pct|dari|start|from|mulai|sampai|end|to|diary|run|runs|target)\s*=\s*[^\s,]+', '', q_low)
    cleaned_q = cleaned_q.replace(',', ' ').strip()

    for k, v in kv_matches:
        v_clean = v.rstrip('%')
        if k in ("lv", "lvl", "level") and v_clean.isdigit():
            start_lv = max(1, min(499, int(v_clean)))
        elif k in ("exp", "pct"):
            try:
                start_pct = max(0.0, min(99.99, float(v_clean)))
            except Exception:
                pass
        elif k in ("dari", "start", "from", "mulai"):
            parsed = parse_ch_ep(v, is_end=False)
            if parsed:
                start_ch, start_ep = parsed
        elif k in ("sampai", "end", "to"):
            parsed = parse_ch_ep(v, is_end=True)
            if parsed:
                end_ch, end_ep = parsed
        elif k in ("diary", "run", "runs") and v_clean.isdigit():
            diary_runs = max(1, min(20, int(v_clean)))
        elif k == "target" and v_clean.isdigit():
            target_lv = max(1, min(500, int(v_clean)))

    # Parse token posisional yang tersisa
    tokens = [t for t in cleaned_q.split() if t]
    pos_nums = []
    for t in tokens:
        if t.endswith('%') and t[:-1].replace('.', '', 1).isdigit():
            start_pct = max(0.0, min(99.99, float(t[:-1])))
        elif re.match(r'^\d{1,2}[\-:.]\d{1,2}$', t):
            pos_nums.append(t)
        elif t.isdigit():
            pos_nums.append(t)

    if pos_nums:
        # Token angka pertama adalah Level Karakter
        if not any(k in ("lv", "lvl", "level") for k, _ in kv_matches):
            first_tok = pos_nums.pop(0)
            if first_tok.isdigit():
                start_lv = max(1, min(499, int(first_tok)))

        # Jika masih ada 1 atau 2 token berikutnya, itu adalah bab_mulai [dan bab_akhir]
        if len(pos_nums) >= 1 and not any(k in ("dari", "start", "from", "mulai") for k, _ in kv_matches):
            p1 = parse_ch_ep(pos_nums[0], is_end=False)
            if p1:
                start_ch, start_ep = p1
        if len(pos_nums) >= 2 and not any(k in ("sampai", "end", "to") for k, _ in kv_matches):
            p2 = parse_ch_ep(pos_nums[1], is_end=True)
            if p2:
                end_ch, end_ep = p2

    # Cari indeks episode awal & akhir
    start_idx = 0
    end_idx = len(flat_episodes) - 1

    for idx, ep_item in enumerate(flat_episodes):
        if ep_item["ch"] == start_ch and ep_item["ep"] == start_ep:
            start_idx = idx
            break
        elif ep_item["ch"] == start_ch and start_ep > ep_item["ep"]:
            start_idx = idx

    for idx, ep_item in enumerate(flat_episodes):
        if ep_item["ch"] == end_ch and ep_item["ep"] == end_ep:
            end_idx = idx
            break
        elif ep_item["ch"] == end_ch:
            end_idx = idx

    if start_idx > end_idx:
        start_idx, end_idx = end_idx, start_idx

    selected_eps = flat_episodes[start_idx:end_idx + 1]
    single_run_exp = sum(x["exp"] for x in selected_eps)
    first_sel = selected_eps[0]
    last_sel = selected_eps[-1]

    # Simulasi per-run (1x Run normal, atau beberapa kali Adventurer's Diary)
    run_details = []
    curr_l, curr_p = start_lv, start_pct
    for r_i in range(1, diary_runs + 1):
        next_l, next_p, rem_next = simulate_exp_gain(curr_l, curr_p, single_run_exp)
        run_details.append((r_i, curr_l, curr_p, next_l, next_p, rem_next))
        curr_l, curr_p = next_l, next_p

    final_lv, final_pct, exp_to_next_lv = run_details[-1][3], run_details[-1][4], run_details[-1][5]

    # Hitung Optimasi Skip Bab Awal (Pre-Skip):
    # Jika mulai dari Bab 1, cari sampai episode berapa bisa di-skip tanpa menurunkan final_lv (pada 1x run)
    one_run_lv = run_details[0][3]
    skip_until_ep = None
    if start_idx == 0 and len(selected_eps) > 5:
        acc_skip = 0
        for idx_s in range(len(selected_eps) - 1):
            cand_skip = acc_skip + selected_eps[idx_s]["exp"]
            test_lv, _, _ = simulate_exp_gain(start_lv, start_pct, single_run_exp - cand_skip)
            if test_lv >= one_run_lv:
                acc_skip = cand_skip
                skip_until_ep = selected_eps[idx_s + 1]
            else:
                break

    # Hitung berapa total run (Adventurer's Diary) untuk mencapai Target Level (default 305)
    runs_needed_for_target = 0
    sim_l, sim_p = start_lv, start_pct
    if single_run_exp > 0 and sim_l < target_lv:
        while sim_l < target_lv and runs_needed_for_target < 30:
            sim_l, sim_p, _ = simulate_exp_gain(sim_l, sim_p, single_run_exp)
            runs_needed_for_target += 1

    # Rangkai output hasil kalkulasi yang ringkas dan jelas
    reply = [
        "*HASIL KALKULASI EXP MAIN QUEST (MQ)*",
        "_Sumber: Raffy Club / Toram Tools MQ Calculator_",
        "──────────────────────────",
        f"• Level Awal: Lv {start_lv} ({start_pct:.1f}%)",
        f"• Rentang MQ: Bab {first_sel['ch']} s/d Bab {last_sel['ch']} (Tamat)",
        f"• EXP per Run: `{single_run_exp:,}` EXP",
    ]
    if diary_runs > 1:
        reply.append(f"• Total EXP ({diary_runs}x Run): `{single_run_exp * diary_runs:,}` EXP")

    reply.append("──────────────────────────")
    reply.append(f"*PROGRES LEVEL ({diary_runs}x Run):*" if diary_runs > 1 else "*PROGRES LEVEL (1x Run):*")
    if diary_runs == 1:
        reply.append(f"• Level Akhir: *Lv {final_lv} ({final_pct:.2f}%)* (+{final_lv - start_lv} Level)")
        reply.append(f"• Kurang EXP ke Lv {final_lv + 1}: `{exp_to_next_lv:,}` EXP")
        clean_arg = q if q else f"{start_lv} {first_sel['ch']}"
        reply.append(f"\n*Tips Pengulangan (Diary):*\nGunakan `,mqspam2 {clean_arg}` untuk simulasi ulang 2x.")
    else:
        for r_i, c_l, c_p, n_l, n_p, _ in run_details:
            lbl = "Run 1 (MQ Awal)" if r_i == 1 else f"Run {r_i} (Diary #{r_i - 1})"
            reply.append(f"• {lbl}: Lv {c_l} ({c_p:.0f}%) -> *Lv {n_l} ({n_p:.1f}%)*")
        reply.append(f"\n• Level Akhir: *Lv {final_lv} ({final_pct:.2f}%)* (+{final_lv - start_lv} Level)")
        reply.append(f"• Kurang EXP ke Lv {final_lv + 1}: `{exp_to_next_lv:,}` EXP")

    return "\n".join(reply)

_UNUSED_STATLIST_END = (
)
