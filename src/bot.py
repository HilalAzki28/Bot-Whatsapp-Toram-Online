import logging
import os
import sys
import random
import re
import segno
import time
import subprocess
import shutil
import tempfile
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import ssl
import json
import io
import socket
import requests
# Force IPv4 socket resolution globally for requests, urllib, and sockets on Cloud VMs with broken IPv6 routes
try:
    import urllib3.util.connection as urllib_conn
    urllib_conn.allowed_gai_family = lambda: socket.AF_INET
except Exception:
    pass

_orig_getaddrinfo = socket.getaddrinfo
def _getaddrinfo_ipv4(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
socket.getaddrinfo = _getaddrinfo_ipv4

# Setup binary ffmpeg dari imageio_ffmpeg ke PATH secara global untuk yt-dlp & thumbnail generator
try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if ffmpeg_exe:
        ffmpeg_dir = os.path.dirname(ffmpeg_exe)
        target_ffmpeg = os.path.join(ffmpeg_dir, 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg')
        if not os.path.exists(target_ffmpeg):
            shutil.copyfile(ffmpeg_exe, target_ffmpeg)
            if os.name != 'nt':
                os.chmod(target_ffmpeg, 0o755)
        if ffmpeg_dir not in os.environ.get('PATH', ''):
            os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
except Exception:
    pass

from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta, timezone
import threading
from contextlib import contextmanager
from bs4 import BeautifulSoup
from neonize.client import NewClient, ParticipantChange, JID
from neonize.events import ConnectedEv, MessageEv, GroupInfoEv
import hashlib
from neonize.utils.enum import ChatPresence, ChatPresenceMedia, MediaType, VoteType, Presence
from neonize.ext.interactive_message import ButtonMessage
import waE2E.WAWebProtobufsE2E_pb2 as pb
from google.protobuf.json_format import MessageToJson, Parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DSGIRL_IMAGE_PATH = os.path.join(ASSETS_DIR, "dsgirl.jpg")
IMPACT_FONT_PATH = os.path.join(ASSETS_DIR, "impact.ttf")
BANNED_GROUPS_FILE = os.path.join(DATA_DIR, "banned_groups.json")

def get_banned_groups() -> set:
    """Membaca daftar ID grup yang dilarang/diblokir menggunakan command bot"""
    try:
        if os.path.exists(BANNED_GROUPS_FILE):
            with open(BANNED_GROUPS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return set(str(x).strip() for x in data if str(x).strip())
    except Exception as e:
        logging.error(f"Gagal membaca banned_groups.json: {e}")
    return set()

GROUP_SUBSCRIPTIONS_FILE = os.path.join(DATA_DIR, "group_subscriptions.json")
GROUP_SUBSCRIPTIONS_BAK = os.path.join(DATA_DIR, "group_subscriptions.json.bak")
OWNERS_FILE = os.path.join(DATA_DIR, "owner_numbers.json")
SUBSCRIPTION_COOLDOWN = {}
DEFAULT_OWNER_NUMBERS = {
    "6287828697399", "087828697399", "205479875735664",
    "6289673563210", "089673563210", "29756254887999",
    "6281291678454", "274251395375109", "628999800123", "135188390633710"
}
BOT_START_TIME = time.time()
WIB_TIMEZONE = timezone(timedelta(hours=7))

def get_owner_numbers() -> set:
    owners = set(DEFAULT_OWNER_NUMBERS)
    if os.path.exists(OWNERS_FILE):
        try:
            with open(OWNERS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for x in data:
                        owners.add(str(x).strip())
        except Exception as e:
            logging.error(f"Gagal membaca owner_numbers.json: {e}")
    return owners

def send_reply_or_message(client: NewClient, text: str, message: MessageEv):
    """Kirim balasan dengan reply_message, jika gagal (misal pesan dari bot sendiri) fallback ke send_message langsung"""
    chat_jid = message.Info.MessageSource.Chat
    try:
        if not message.Info.MessageSource.IsFromMe:
            client.reply_message(text, message)
            return
    except Exception as e:
        logging.warning(f"reply_message gagal ({e}), mencoba send_message...")
    
    try:
        client.send_message(chat_jid, text)
    except Exception as e:
        logging.error(f"send_message juga gagal: {e}")

def load_group_subscriptions() -> dict:
    try:
        if os.path.exists(GROUP_SUBSCRIPTIONS_FILE):
            with open(GROUP_SUBSCRIPTIONS_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, dict) and data:
                    return data
        # Fallback pemulihan otomatis jika file utama kosong / tertimpa tapi ada backup .bak
        if os.path.exists(GROUP_SUBSCRIPTIONS_BAK):
            with open(GROUP_SUBSCRIPTIONS_BAK, "r") as f:
                bak_data = json.load(f)
                if isinstance(bak_data, dict) and bak_data:
                    logging.info("Memulihkan group_subscriptions.json dari file cadangan .bak")
                    save_group_subscriptions(bak_data)
                    return bak_data
    except Exception as e:
        logging.error(f"Gagal membaca group_subscriptions.json: {e}")
    return {}

def save_group_subscriptions(data: dict):
    try:
        with open(GROUP_SUBSCRIPTIONS_FILE, "w") as f:
            json.dump(data, f, indent=2)
        # Buat salinan cadangan otomatis setiap kali ada data aktif
        if data:
            with open(GROUP_SUBSCRIPTIONS_BAK, "w") as f:
                json.dump(data, f, indent=2)
    except Exception as e:
        logging.error(f"Gagal menyimpan group_subscriptions.json: {e}")

def check_group_subscription(group_jid_str: str) -> tuple[bool, str, str]:
    """Mengecek status masa aktif grup: mengembalikan (is_active, expired_str, remaining_str)"""
    subs = load_group_subscriptions()
    group_clean = group_jid_str.split('@')[0]
    info = subs.get(group_jid_str) or subs.get(group_clean) or subs.get(f"{group_clean}@g.us")

    if not info:
        return (False, "Belum diatur", "Masa aktif belum diaktifkan")

    if not info.get("active", False):
        return (False, info.get("expired_at", "-"), "Dinonaktifkan oleh Owner")

    expired_at_str = info.get("expired_at", "")
    if not expired_at_str:
        return (False, "Belum diatur", "Masa aktif belum diaktifkan")

    try:
        exp_dt = datetime.fromisoformat(expired_at_str)
        now = datetime.now()
        if now > exp_dt:
            return (False, exp_dt.strftime("%d-%m-%Y %H:%M WIB"), "Telah kedaluwarsa")

        diff = exp_dt - now
        days = diff.days
        hours = diff.seconds // 3600
        mins = (diff.seconds % 3600) // 60
        remaining_str = f"{days} hari {hours} jam {mins} menit"
        return (True, exp_dt.strftime("%d-%m-%Y %H:%M WIB"), remaining_str)
    except Exception as e:
        logging.error(f"Error parsing expired_at: {e}")
        return (False, "Format tanggal salah", "Error")

def handle_set_subscription(client: NewClient, message: MessageEv, args: str, chat_jid_str: str):
    args_str = args.strip()
    args_lower = args_str.lower()
    if not args_lower:
        send_reply_or_message(client, "Format: `,set [jumlah] hari` (contoh: `,set 30 hari`) atau `,set [id_grup] [jumlah] hari` atau `,set off` untuk menonaktifkan.", message)
        return

    # Cek apakah ada target grup spesifik di dalam args (misal: 120363411640694519@g.us atau ID grup angka panjang)
    target_group_jid = chat_jid_str
    remaining_args = args_lower

    group_match = re.search(r'([0-9a-zA-Z\-_]+@g\.us|\d{15,})', args_str)
    if group_match:
        matched_gid = group_match.group(1)
        target_group_jid = matched_gid if matched_gid.endswith("@g.us") else f"{matched_gid}@g.us"
        remaining_args = args_str.replace(matched_gid, "").strip().lower()

    # Cek apakah dipanggil di private chat tanpa menyertakan ID grup
    is_group = message.Info.MessageSource.IsGroup or chat_jid_str.endswith("@g.us")
    if not is_group and target_group_jid == chat_jid_str:
        send_reply_or_message(
            client, 
            "Gagal: Anda sedang berada di Personal Chat. Harap sertakan ID Grup!\nContoh: `,set 120363xxxxxxxx@g.us 30 hari`\n\nTips: Ketik `,id` di dalam grup untuk melihat ID grup tersebut.", 
            message
        )
        return

    subs = load_group_subscriptions()

    if remaining_args in ["off", "disable", "stop", "mati"]:
        info = subs.get(target_group_jid) or subs.get(target_group_jid.split('@')[0], {})
        info["active"] = False
        subs[target_group_jid] = info
        save_group_subscriptions(subs)
        send_reply_or_message(client, f"Bot di grup `{target_group_jid}` telah dinonaktifkan oleh Owner.", message)
        return

    # Ekstrak angka durasi hari dari remaining_args
    m = re.search(r'(\d+)', remaining_args)
    if not m:
        send_reply_or_message(client, "Gagal: Jumlah hari tidak valid. Contoh penggunaan: `,set 30 hari` atau `,set 120363...@g.us 30 hari`", message)
        return

    days_count = int(m.group(1))
    info = subs.get(target_group_jid) or subs.get(target_group_jid.split('@')[0], {})
    if days_count <= 0:
        info["active"] = False
        subs[target_group_jid] = info
        save_group_subscriptions(subs)
        send_reply_or_message(client, f"Bot di grup `{target_group_jid}` telah dinonaktifkan.", message)
        return

    now = datetime.now()
    base_dt = now
    is_extended = False

    # Jika grup masih aktif dan belum expired, perpanjang dari tanggal expired sebelumnya (akumulasi)
    if info.get("active", False) and "expired_at" in info:
        try:
            curr_exp = datetime.fromisoformat(info["expired_at"])
            if curr_exp > now:
                base_dt = curr_exp
                is_extended = True
        except Exception:
            base_dt = now

    exp_dt = base_dt + timedelta(days=days_count)
    subs[target_group_jid] = {
        "active": True,
        "set_at": now.isoformat(),
        "expired_at": exp_dt.isoformat(),
        "duration_days": days_count
    }
    save_group_subscriptions(subs)

    exp_formatted = exp_dt.strftime("%d-%m-%Y %H:%M WIB")
    if is_extended:
        diff = exp_dt - now
        total_days = diff.days
        total_hours = diff.seconds // 3600
        reply = (
            f"*MASA AKTIF BOT BERHASIL DIPERPANJANG*\n\n"
            f"• *Grup:* `{target_group_jid}`\n"
            f"• *Penambahan:* +{days_count} hari\n"
            f"• *Total Sisa Waktu:* {total_days} hari {total_hours} jam\n"
            f"• *Berlaku sampai:* {exp_formatted}\n\n"
            f"Ketik command `,cekbot` untuk memeriksa sisa waktu kapan saja."
        )
    else:
        reply = (
            f"*MASA AKTIF BOT BERHASIL DIATUR*\n\n"
            f"• *Grup:* `{target_group_jid}`\n"
            f"• *Durasi:* {days_count} hari\n"
            f"• *Berlaku sampai:* {exp_formatted}\n\n"
            f"Ketik command `,cekbot` untuk memeriksa sisa waktu kapan saja."
        )
    send_reply_or_message(client, reply, message)

def handle_ceksewa_command(client: NewClient, message: MessageEv, chat_jid_str: str, args: str = ""):
    target_group = chat_jid_str
    if args.strip():
        group_match = re.search(r'([0-9a-zA-Z\-_]+@g\.us|\d{15,})', args.strip())
        if group_match:
            matched_gid = group_match.group(1)
            target_group = matched_gid if matched_gid.endswith("@g.us") else f"{matched_gid}@g.us"

    is_active, exp_str, remaining = check_group_subscription(target_group)
    if is_active:
        reply = (
            f"*STATUS SEWA BOT TORAM*\n\n"
            f"• *Grup:* `{target_group}`\n"
            f"• *Status:* Aktif\n"
            f"• *Berakhir pada:* {exp_str}\n"
            f"• *Sisa Masa Aktif:* {remaining}\n\n"
            f"Silakan hubungi Owner jika ingin memperpanjang masa aktif bot."
        )
    else:
        reply = (
            f"*STATUS SEWA BOT TORAM*\n\n"
            f"• *Grup:* `{target_group}`\n"
            f"• *Status:* Tidak Aktif / Kedaluwarsa ({remaining})\n"
            f"• *Berakhir pada:* {exp_str}\n\n"
            f"Masa aktif bot telah habis jika ingin mengaktifkan silahkan direct message botnya untuk selesaikan pembayaran lalu infokan nama grupnya.\n\n"
            f"Thanks :*"
        )
    send_reply_or_message(client, reply, message)

def send_image_reply(client: NewClient, message: MessageEv, image_path: str, caption: str):
    """Mengirim balasan berupa gambar (misal: dsgirl.jpg) dengan caption teks, dengan fallback ke reply_message jika gambar tidak ada"""
    try:
        if os.path.exists(image_path):
            with open(image_path, "rb") as f:
                img_bytes = f.read()
            chat_jid = message.Info.MessageSource.Chat
            msg_to_send = client.build_image_message(
                file=img_bytes,
                caption=caption,
                quoted=message
            )
            client.send_message(chat_jid, msg_to_send)
            return
    except Exception as e:
        logging.error(f"Gagal mengirim gambar {image_path}: {e}")

@contextmanager
def typing_indicator(client: NewClient, chat_jid):
    """Context manager untuk menampilkan status typing (sedang mengetik) selama proses berjalan"""
    stop_event = threading.Event()

    def _keep_typing():
        while not stop_event.is_set():
            try:
                client.send_chat_presence(chat_jid, ChatPresence.CHAT_PRESENCE_COMPOSING, ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT)
            except Exception:
                pass
            stop_event.wait(4.0)

    try:
        client.send_chat_presence(chat_jid, ChatPresence.CHAT_PRESENCE_COMPOSING, ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT)
    except Exception as e:
        logging.debug(f"Gagal mengirim chat presence composing: {e}")

    t = threading.Thread(target=_keep_typing, daemon=True)
    t.start()
    try:
        yield
    finally:
        stop_event.set()
        try:
            client.send_chat_presence(chat_jid, ChatPresence.CHAT_PRESENCE_PAUSED, ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT)
        except Exception:
            pass

DEFAULT_BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
    'Pragma': 'no-cache',
    'Connection': 'keep-alive',
}

def get_fallback_urls(url: str) -> list:
    """Membuat daftar URL cadangan termasuk Google Translate mirror & Jina AI proxy untuk bypass Akamai/Cloudflare IP block & SSL reset."""
    urls = [url]
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc and "translate.goog" not in parsed.netloc:
            domain = parsed.netloc
            translated_domain = domain.replace('.', '-').replace(':', '-') + ".translate.goog"
            path_query = parsed.path or "/"
            if parsed.query:
                path_query += "?" + parsed.query + "&_x_tr_sl=auto&_x_tr_tl=id"
            else:
                path_query += "?_x_tr_sl=auto&_x_tr_tl=id"
            goog_domain_url = f"{parsed.scheme or 'https'}://{translated_domain}{path_query}"
            urls.append(goog_domain_url)
    except Exception:
        pass
    
    gt_proxy = f"https://translate.google.com/translate?sl=auto&tl=id&u={urllib.parse.quote(url, safe='')}"
    urls.append(gt_proxy)
    jina_proxy = f"https://r.jina.ai/{url}"
    urls.append(jina_proxy)
    return urls

def fetch_web_page(url: str, headers: dict | None = None, timeout: int = 12, retries: int = 2) -> str:
    """Mengambil HTML/Text dari URL dengan memprioritaskan requests.Session & Google Translate mirror/proxy fallback."""
    req_headers = DEFAULT_BROWSER_HEADERS.copy()
    if headers:
        req_headers.update(headers)

    urls_to_try = get_fallback_urls(url)
    errors = []

    # 1. Coba curl_cffi jika tersedia
    try:
        from curl_cffi import requests as cffi_requests
        for target_url in urls_to_try:
            try:
                resp = cffi_requests.get(target_url, impersonate="chrome120", timeout=timeout, verify=False)
                if resp.status_code == 200 and resp.text and len(resp.text) > 200:
                    return resp.text
            except Exception as e:
                errors.append(f"curl_cffi ({target_url[:50]}...): {e}")
    except Exception as e:
        errors.append(f"curl_cffi import: {e}")

    # 2. Coba requests.Session (Sangat kompatibel di semua versi Python)
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        session = requests.Session()
        session.headers.update(req_headers)
        for target_url in urls_to_try:
            for attempt in range(retries):
                try:
                    resp = session.get(target_url, timeout=timeout, verify=False)
                    if resp.status_code == 200 and resp.text and len(resp.text) > 200:
                        return resp.text
                    else:
                        errors.append(f"requests ({target_url[:50]}...) status {resp.status_code}")
                except Exception as e:
                    errors.append(f"requests ({target_url[:50]}...): {e}")
                    time.sleep(0.3)
    except Exception as e:
        errors.append(f"requests module: {e}")

    # 3. Coba urllib bawaan Python standard library
    try:
        for target_url in urls_to_try:
            try:
                req = urllib.request.Request(target_url, headers=req_headers)
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
                    if resp.status == 200:
                        content = resp.read().decode('utf-8', errors='ignore')
                        if len(content) > 200:
                            return content
            except Exception as e:
                errors.append(f"urllib ({target_url[:50]}...): {e}")
    except Exception as e:
        errors.append(f"urllib module: {e}")

    # 4. Coba curl CLI bawaan OS (dengan -4 untuk force IPv4)
    if shutil.which('curl'):
        for target_url in urls_to_try:
            cmd = [
                'curl', '-4', '-s', '-L',
                '--connect-timeout', str(timeout),
                '-A', req_headers['User-Agent'],
                target_url
            ]
            for attempt in range(retries):
                try:
                    res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore', timeout=timeout)
                    if res.returncode == 0 and res.stdout and len(res.stdout) > 200:
                        return res.stdout
                    else:
                        errors.append(f"curl ({target_url[:50]}...) code {res.returncode}")
                except Exception as e:
                    errors.append(f"curl ({target_url[:50]}...): {e}")
                    time.sleep(0.3)

    raise Exception(f"Gagal mengambil URL {url}. Logs: {'; '.join(errors)}")

def fetch_web_bytes(url: str, headers: dict | None = None, timeout: int = 15, retries: int = 2) -> bytes:
    """Mengambil binary data (gambar/file) dari URL dengan requests.Session & fallback mirror."""
    req_headers = DEFAULT_BROWSER_HEADERS.copy()
    if headers:
        req_headers.update(headers)

    urls_to_try = get_fallback_urls(url)
    errors = []

    try:
        from curl_cffi import requests as cffi_requests
        for target_url in urls_to_try:
            try:
                resp = cffi_requests.get(target_url, impersonate="chrome120", timeout=timeout, verify=False)
                if resp.status_code == 200 and resp.content and len(resp.content) > 100:
                    return resp.content
            except Exception as e:
                errors.append(f"curl_cffi bytes ({target_url[:50]}...): {e}")
    except Exception:
        pass

    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        session = requests.Session()
        session.headers.update(req_headers)
        for target_url in urls_to_try:
            for attempt in range(retries):
                try:
                    resp = session.get(target_url, timeout=timeout, verify=False)
                    if resp.status_code == 200 and resp.content and len(resp.content) > 100:
                        return resp.content
                    else:
                        errors.append(f"requests bytes ({target_url[:50]}...) status {resp.status_code}")
                except Exception as e:
                    errors.append(f"requests bytes ({target_url[:50]}...): {e}")
                    time.sleep(0.3)
    except Exception as e:
        errors.append(f"requests bytes module: {e}")

    if shutil.which('curl'):
        for target_url in urls_to_try:
            cmd = [
                'curl', '-4', '-s', '-L',
                '--connect-timeout', str(timeout),
                '-A', req_headers['User-Agent'],
                target_url
            ]
            for attempt in range(retries):
                try:
                    res = subprocess.run(cmd, capture_output=True, timeout=timeout)
                    if res.returncode == 0 and res.stdout and len(res.stdout) > 100:
                        return res.stdout
                except Exception as e:
                    errors.append(f"curl bytes ({target_url[:50]}...): {e}")
                    time.sleep(0.3)

    raise Exception(f"Gagal mengambil binary URL {url}. Logs: {'; '.join(errors)}")


from db import (
    pet_natures, traits_db, get_crysta_upgrades, get_skills_db, 
    get_monsters_db, get_registlets_db, load_warnings, save_warnings,
    get_group_warnings_data,
    search_local_items, search_local_monsters,
    get_item_detail_from_api, get_arrows_db, format_arrows_list, format_arrow_detail,
    search_arrows, clean_arrow_drops,
    get_item_bilingual_name, get_translation_search_terms,
    TRAIT_TRANSLATIONS, format_trait_detail
)
import games
from respon_bot import get_menu_text, ABOUT_TEXT, PING_TEXT, QUOTE_TEXT, MQ_TEXT, TAS_TEXT, SUNK_TEXT, get_pet_menu_text, format_pet_detail, STATLIST_TEXT, get_buff_response, calculate_mq_exp


# Atur logging untuk melihat status koneksi dan aktivitas bot
logging.basicConfig(level=logging.INFO)

# Inisialisasi klien Neonize dengan database lokal untuk persistence sesi
client = NewClient(os.path.join(PROJECT_ROOT, "whatsapp_session.sqlite3"))

# Cache lokal untuk menyimpan data anggota & admin grup (durasi 10 menit)
GROUP_CACHE = {}

# Cache pesan grup terbaru untuk mendukung deteksi multi-gambar (album/2 gambar) pada command ,a
MAX_GROUP_CACHE_SIZE = 100
GROUP_MESSAGES_CACHE_FILE = os.path.join(DATA_DIR, "group_messages_cache.json")

def load_group_messages_cache() -> dict:
    """Membaca cache riwayat pesan grup dari file JSON agar tidak hilang saat bot restart"""
    if os.path.exists(GROUP_MESSAGES_CACHE_FILE):
        try:
            with open(GROUP_MESSAGES_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    for gid, entries in data.items():
                        for item in entries:
                            item["all_senders"] = set(item.get("all_senders", []))
                            if item.get("raw_json"):
                                try:
                                    msg_obj = pb.Message()
                                    Parse(item["raw_json"], msg_obj)
                                    item["raw_message"] = msg_obj
                                except Exception:
                                    pass
                    return data
        except Exception as e:
            logging.error(f"Gagal membaca group_messages_cache.json: {e}")
    return {}

def save_group_messages_cache(cache_dict: dict):
    """Menyimpan cache riwayat pesan grup ke file JSON"""
    try:
        serializable = {}
        for gid, entries in cache_dict.items():
            s_list = []
            for item in entries:
                s_item = {
                    "id": item.get("id", ""),
                    "parent_id": item.get("parent_id", ""),
                    "message_index": item.get("message_index", 0),
                    "sender": item.get("sender", ""),
                    "sender_raw": item.get("sender_raw", ""),
                    "sender_alt": item.get("sender_alt", ""),
                    "all_senders": list(item.get("all_senders", [])),
                    "timestamp": item.get("timestamp", 0),
                    "is_image": item.get("is_image", False),
                    "is_album": item.get("is_album", False),
                    "expected_count": item.get("expected_count", 0),
                    "caption": item.get("caption", ""),
                    "text": item.get("text", ""),
                    "raw_json": item.get("raw_json", "")
                }
                s_list.append(s_item)
            serializable[gid] = s_list[-MAX_GROUP_CACHE_SIZE:]
        with open(GROUP_MESSAGES_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Gagal menyimpan group_messages_cache.json: {e}")

GROUP_MESSAGE_CACHE = load_group_messages_cache()

def clear_chat_history_cache():
    """Menghapus memory cache dan file cache riwayat pesan grup (group_messages_cache.json) pada sisi bot"""
    try:
        GROUP_MESSAGE_CACHE.clear()
        GROUP_CACHE.clear()
        SUBSCRIPTION_COOLDOWN.clear()
        save_group_messages_cache({})
        print(" [00:00 WIB] Riwayat chat & cache pesan di sisi bot berhasil dibersihkan.")
        logging.info("Riwayat chat cache grup di sisi bot berhasil dibersihkan.")
        return True
    except Exception as e:
        logging.error(f"Gagal membersihkan riwayat chat cache grup: {e}")
        return False

def daily_midnight_cleanup_scheduler():
    """Background thread untuk membersihkan riwayat pesan grup dan mereset limit setiap jam 00:00 WIB"""
    while True:
        try:
            now_wib = datetime.now(WIB_TIMEZONE)
            tomorrow_wib = (now_wib + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            seconds_until_midnight = (tomorrow_wib - now_wib).total_seconds()
            
            if seconds_until_midnight > 0:
                time.sleep(seconds_until_midnight)
            else:
                time.sleep(60)

            logging.info("[00:00 WIB] Menjalankan pembersihan harian riwayat chat & reset limit...")
            clear_chat_history_cache()
            
            try:
                check_and_reset_waifu_limit()
            except Exception as e:
                logging.error(f"Error reset waifu limit pada 00:00 WIB: {e}")
            try:
                check_and_reset_husbu_limit()
            except Exception as e:
                logging.error(f"Error reset husbu limit pada 00:00 WIB: {e}")

            time.sleep(5)
        except Exception as e:
            logging.error(f"Error pada daily_midnight_cleanup_scheduler: {e}")
            time.sleep(60)

# Jalankan scheduler pembersihan riwayat chat harian di background
cleanup_worker = threading.Thread(target=daily_midnight_cleanup_scheduler, daemon=True)
cleanup_worker.start()

def keepalive_presence_worker():
    """Mengirim sinyal online (Presence.AVAILABLE) ke server WhatsApp secara berkala (setiap 10 menit) agar sesi tidak dianggap idle/logout otomatis."""
    time.sleep(20)
    while True:
        try:
            if client:
                client.send_presence(Presence.AVAILABLE)
                logging.debug("Keep-alive presence sent to WhatsApp server.")
        except Exception as e:
            logging.debug(f"Keep-alive presence note: {e}")
        time.sleep(600)

presence_worker = threading.Thread(target=keepalive_presence_worker, daemon=True)
presence_worker.start()

# --- GEMINI AI INTEGRATION WITH AUTOMATIC MODEL FALLBACK ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-3.5-flash",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash",
    "gemini-robotics-er-2-preview",
    "gemini-1.5-flash-8b"
]

def ask_gemini_with_fallback(prompt: str) -> str:
    headers = {"Content-Type": "application/json"}
    payload = json.dumps({
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }).encode("utf-8")

    last_error = ""

    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            context = ssl._create_unverified_context()
            with urllib.request.urlopen(req, context=context, timeout=25) as resp:
                if resp.status == 200:
                    res_body = json.loads(resp.read().decode("utf-8"))
                    candidates = res_body.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            text = parts[0].get("text", "").strip()
                            if text:
                                logging.info(f"Berhasil merespon menggunakan model Gemini: {model}")
                                return text
        except urllib.error.HTTPError as err:
            err_msg = err.read().decode('utf-8', errors='ignore')
            logging.warning(f"Model {model} limit/error {err.code}: {err_msg}")
            last_error = f"HTTP {err.code}"
        except Exception as err:
            logging.warning(f"Model {model} error: {err}")
            last_error = str(err)

    return f"Gagal: Maaf, seluruh model Gemini AI sedang mengalami limit/gangguan saat ini. Detail: {last_error}"

def handle_gemini_ai_command(client, message, prompt: str):
    prompt = prompt.strip()
    if not prompt:
        client.reply_message(" *Gemini AI Assistant*\n\nFormat Perintah:\n`,ai <pertanyaan>` atau `,gemini <pertanyaan>`\n\nContoh:\n`,ai apa rekomendasi combo dual sword di Toram Online?`", message)
        return

    answer = ask_gemini_with_fallback(prompt)
    client.reply_message(answer, message)


def handle_sticker_command(client: NewClient, message: MessageEv):
    """Membuat dan mengirimkan stiker WhatsApp dari gambar langsung atau gambar yang di-reply"""
    target_msg = None
    
    # 1. Cek jika pesan saat ini langsung berisi gambar
    if message.Message.HasField("imageMessage"):
        target_msg = message.Message
    # 2. Cek jika pesan balasan (reply) berisi gambar/stiker/viewonce
    elif message.Message.HasField("extendedTextMessage") and message.Message.extendedTextMessage.HasField("contextInfo"):
        ctx_info = message.Message.extendedTextMessage.contextInfo
        if ctx_info.HasField("quotedMessage"):
            q_msg = ctx_info.quotedMessage
            if q_msg.HasField("imageMessage"):
                target_msg = q_msg
            elif q_msg.HasField("stickerMessage"):
                target_msg = q_msg
            elif q_msg.HasField("viewOnceMessage"):
                target_msg = q_msg.viewOnceMessage.message
            elif q_msg.HasField("viewOnceMessageV2"):
                target_msg = q_msg.viewOnceMessageV2.message

    if not target_msg:
        client.reply_message("Peringatan: *Cara Membuat Stiker:*\n\n1. Kirim gambar dengan caption `,s` atau `,sticker`\n2. Atau *reply/balas* pesan gambar dengan ketik `,s` atau `,sticker`", message)
        return

    try:
        media_bytes = client.download_any(target_msg)
        if not media_bytes:
            client.reply_message("Gagal: Gagal mengunduh gambar. Silakan coba kirim ulang gambarnya.", message)
            return

        # Konversi gambar ke WebP 512x512 transparan untuk stiker WhatsApp
        img = Image.open(io.BytesIO(media_bytes)).convert("RGBA")
        img.thumbnail((512, 512), Image.Resampling.LANCZOS)
        
        canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        offset = ((512 - img.width) // 2, (512 - img.height) // 2)
        canvas.paste(img, offset)

        output = io.BytesIO()
        canvas.save(output, format="WEBP")
        sticker_bytes = output.getvalue()

        # Kirim stiker ke chat
        client.send_sticker(
            to=message.Info.MessageSource.Chat,
            file=sticker_bytes,
            quoted=message,
            packname="SunKSenK Bot",
            name="Toram Online WA Bot"
        )
    except Exception as e:
        logging.error(f"Error saat membuat sticker: {e}")
        client.reply_message(f"Gagal: Gagal membuat stiker. Detail: {e}", message)


def _wrap_meme_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Membagi kalimat menjadi beberapa baris agar pas di dalam batas lebar kanvas"""
    words = text.split()
    if not words:
        return []
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
    if current_line:
        lines.append(" ".join(current_line))
    return lines


def _get_best_meme_font(text: str, max_w: int, max_h: int) -> tuple[ImageFont.FreeTypeFont, list[str]]:
    """Mencari ukuran font Impact terbesar yang muat rapi di area stiker (58pt s/d 24pt)"""
    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)

    candidate_fonts = [
        IMPACT_FONT_PATH,
        "impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "arialbd.ttf",
        "arial.ttf"
    ]

    # Iterasi dari ukuran besar ke kecil agar teks tampil sebesar dan sejelas mungkin
    for size in range(58, 23, -2):
        font = None
        for cf in candidate_fonts:
            try:
                font = ImageFont.truetype(cf, size)
                break
            except Exception:
                continue
        if not font:
            font = ImageFont.load_default()
            return font, [text]

        lines = _wrap_meme_text(text, font, max_w, draw)
        if not lines:
            return font, []

        line_heights = [draw.textbbox((0, 0), l, font=font)[3] - draw.textbbox((0, 0), l, font=font)[1] for l in lines]
        total_h = sum(line_heights) + int(size * 0.15) * (len(lines) - 1)

        # Maksimal 2 baris per blok agar komposisi stiker seimbang dan teks tetap besar
        if len(lines) <= 2 and total_h <= max_h:
            return font, lines

    # Fallback ukuran minimum 24pt
    for cf in candidate_fonts:
        try:
            font = ImageFont.truetype(cf, 24)
            break
        except Exception:
            continue
    lines = _wrap_meme_text(text, font, max_w, draw) if font else [text]
    return font or ImageFont.load_default(), lines


def draw_meme_text(image: Image.Image, top_text: str, bottom_text: str) -> Image.Image:
    """
    Menggambar teks meme bergaya Impact (teks putih dengan outline hitam tebal)
    pada gambar yang telah disesuaikan ke kanvas stiker 512x512 sehingga teks selalu besar dan jelas terbaca.
    """
    # 1. Resize gambar utama agar pas di dalam batas 512x512 terlebih dahulu
    img = image.convert("RGBA")
    img.thumbnail((512, 512), Image.Resampling.LANCZOS)
    width, height = img.size
    draw = ImageDraw.Draw(img)

    max_w = int(width * 0.94)
    max_h = int(height * 0.35)

    def render_block(text: str, is_top: bool):
        if not text:
            return
        text_upper = text.strip().upper()
        font, lines = _get_best_meme_font(text_upper, max_w, max_h)
        if not lines:
            return

        f_size = getattr(font, 'size', 32)
        outline_w = max(2, int(f_size * 0.08))
        line_spacing = int(f_size * 0.15)

        line_metrics = []
        for l in lines:
            bbox = draw.textbbox((0, 0), l, font=font)
            lw = bbox[2] - bbox[0]
            lh = bbox[3] - bbox[1]
            line_metrics.append((l, lw, lh))

        total_block_h = sum(m[2] for m in line_metrics) + line_spacing * (len(lines) - 1)

        if is_top:
            curr_y = int(height * 0.03)
        else:
            curr_y = height - total_block_h - int(height * 0.05)

        for l, lw, lh in line_metrics:
            x_pos = (width - lw) // 2

            # Gambar outline hitam tebal di sekeliling teks
            for dx in range(-outline_w, outline_w + 1):
                for dy in range(-outline_w, outline_w + 1):
                    if dx != 0 or dy != 0:
                        draw.text((x_pos + dx, curr_y + dy), l, font=font, fill="black")

            # Gambar teks putih utama
            draw.text((x_pos, curr_y), l, font=font, fill="white")
            curr_y += lh + line_spacing

    if top_text:
        render_block(top_text, is_top=True)
    if bottom_text:
        render_block(bottom_text, is_top=False)

    # 2. Tempelkan gambar berteks ke tengah kanvas transparan 512x512 stiker WhatsApp
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    offset = ((512 - img.width) // 2, (512 - img.height) // 2)
    canvas.paste(img, offset)
    return canvas


def handle_setmeme_command(client: NewClient, message: MessageEv, text_prompt: str):
    """Membuat stiker meme berteks dari gambar langsung atau gambar yang di-reply"""
    text_prompt = text_prompt.strip()
    if not text_prompt:
        client.reply_message(
            "Peringatan: *Cara Membuat Stiker Meme:*\n\n"
            "Format: `,setmeme <teks>` atau `,setmeme <teks atas>|<teks bawah>`\n\n"
            "Contoh 1: `,setmeme ah sial ini` (teks di bawah)\n"
            "Contoh 2: `,setmeme ketika kamu|lupa leveling` (teks atas & bawah)\n\n"
            "Tips: Kirim gambar dengan caption di atas ATAU balas (reply) gambar dengan perintah di atas!", 
            message
        )
        return

    # Parse top text vs bottom text
    if "|" in text_prompt:
        parts = text_prompt.split("|", 1)
        top_text = parts[0].strip()
        bottom_text = parts[1].strip()
    else:
        top_text = ""
        bottom_text = text_prompt

    target_msg = None
    if message.Message.HasField("imageMessage"):
        target_msg = message.Message
    elif message.Message.HasField("extendedTextMessage") and message.Message.extendedTextMessage.HasField("contextInfo"):
        ctx_info = message.Message.extendedTextMessage.contextInfo
        if ctx_info.HasField("quotedMessage"):
            q_msg = ctx_info.quotedMessage
            if q_msg.HasField("imageMessage"):
                target_msg = q_msg
            elif q_msg.HasField("stickerMessage"):
                target_msg = q_msg
            elif q_msg.HasField("viewOnceMessage"):
                target_msg = q_msg.viewOnceMessage.message
            elif q_msg.HasField("viewOnceMessageV2"):
                target_msg = q_msg.viewOnceMessageV2.message

    if not target_msg:
        client.reply_message("Peringatan: Silakan kirim gambar dengan caption perintah `,setmeme <teks>` ATAU balas (reply) gambar yang ingin dijadikan stiker meme!", message)
        return

    try:
        media_bytes = client.download_any(target_msg)
        if not media_bytes:
            client.reply_message("Gagal: Gagal mengunduh gambar. Silakan coba kirim ulang gambarnya.", message)
            return

        # Buka gambar dan lukis teks meme langsung ke kanvas stiker 512x512
        base_img = Image.open(io.BytesIO(media_bytes))
        canvas = draw_meme_text(base_img, top_text, bottom_text)

        output = io.BytesIO()
        canvas.save(output, format="WEBP")
        sticker_bytes = output.getvalue()

        # Kirim stiker meme ke chat
        client.send_sticker(
            to=message.Info.MessageSource.Chat,
            file=sticker_bytes,
            quoted=message,
            packname="SunKSenK Bot",
            name="Meme Sticker"
        )
    except Exception as e:
        logging.error(f"Error saat membuat meme sticker: {e}")
        client.reply_message(f"Gagal: Gagal membuat stiker meme. Detail: {e}", message)


def _extract_media_duration(data: bytes) -> int:
    """Mengekstrak durasi media (dalam detik) dari header MP4/M4A/MP3 secara murni di Python atau via ffmpeg."""
    # 1. Parsing cepat murni Python
    try:
        idx = data.find(b'mvhd')
        if idx != -1 and len(data) >= idx + 36:
            box_data = data[idx + 4:]
            version = box_data[0]
            import struct
            if version == 0 and len(box_data) >= 20:
                timescale, duration = struct.unpack('>II', box_data[12:20])
                if timescale:
                    return int(duration / timescale)
            elif version == 1 and len(box_data) >= 32:
                timescale, duration = struct.unpack('>IQ', box_data[20:32])
                if timescale:
                    return int(duration / timescale)
        for tag in [b'Xing', b'Info']:
            t_idx = data.find(tag)
            if t_idx != -1 and len(data) >= t_idx + 12:
                import struct
                flags = struct.unpack('>I', data[t_idx + 4 : t_idx + 8])[0]
                if flags & 0x0001:
                    frames = struct.unpack('>I', data[t_idx + 8 : t_idx + 12])[0]
                    return int((frames * 1152) / 44100)
    except Exception:
        pass

    # 2. Parsing via ffmpeg jika tersedia
    try:
        f_exe = shutil.which("ffmpeg")
        if f_exe and len(data) > 1024:
            with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tf:
                tf.write(data)
                t_name = tf.name
            try:
                p = subprocess.run([f_exe, '-i', t_name], stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=4)
                err = p.stderr.decode('utf-8', errors='ignore')
                m = re.search(r'Duration:\s*(\d{2}):(\d{2}):(\d{2}(?:\.\d+)?)', err)
                if m:
                    h, m_val, s = m.groups()
                    return int(float(h) * 3600 + float(m_val) * 60 + float(s))
            finally:
                try:
                    os.remove(t_name)
                except Exception:
                    pass
    except Exception:
        pass
    return 0

def _extract_video_thumbnail(data: bytes) -> bytes | None:
    """Mengekstrak 1 frame JPEG thumbnail dari video menggunakan ffmpeg untuk preview di WhatsApp."""
    try:
        f_exe = shutil.which("ffmpeg")
        if not f_exe or len(data) < 1024:
            return None
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(data)
            t_name = tf.name
        try:
            cmd = [
                f_exe,
                '-ss', '00:00:01',
                '-i', t_name,
                '-vframes', '1',
                '-vf', 'scale=320:-1',
                '-q:v', '3',
                '-f', 'image2pipe',
                '-vcodec', 'mjpeg',
                '-'
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=5)
            if res.returncode == 0 and res.stdout and len(res.stdout) > 100:
                return res.stdout
        finally:
            try:
                os.remove(t_name)
            except Exception:
                pass
    except Exception:
        pass
    return None


def _ensure_whatsapp_playable_video(data: bytes) -> bytes:
    """Memastikan video berformat MP4 (H.264 + AAC + yuv420p + faststart) agar 100% dapat diputar langsung di WhatsApp."""
    try:
        f_exe = shutil.which("ffmpeg")
        if not f_exe or len(data) < 1024:
            return data
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf_in:
            tf_in.write(data)
            in_path = tf_in.name
        out_path = in_path + "_wa.mp4"
        try:
            probe = subprocess.run([f_exe, '-i', in_path], stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=8)
            info_str = probe.stderr.decode('utf-8', errors='ignore').lower()
            has_h264 = 'video: h264' in info_str
            has_aac_or_mp3 = ('audio: aac' in info_str) or ('audio: mp3' in info_str) or ('audio:' not in info_str)

            if has_h264 and has_aac_or_mp3:
                cmd = [
                    f_exe, '-y', '-i', in_path,
                    '-c', 'copy',
                    '-movflags', '+faststart',
                    out_path
                ]
                res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=20)
                if res.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                    with open(out_path, 'rb') as f_out:
                        return f_out.read()
                return data

            cmd = [
                f_exe, '-y', '-i', in_path,
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-crf', '26',
                '-pix_fmt', 'yuv420p',
                '-vf', 'scale=trunc(iw/2)*2:trunc(ih/2)*2',
                '-c:a', 'aac',
                '-b:a', '128k',
                '-movflags', '+faststart',
                out_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=90)
            if res.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                with open(out_path, 'rb') as f_out:
                    return f_out.read()
        finally:
            for p in [in_path, out_path]:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
    except Exception:
        pass
    return data


def _ensure_whatsapp_playable_audio(data: bytes) -> bytes:
    """Memastikan audio dikonversi menjadi MP3 standar (44100Hz, stereo, 128kbps) agar langsung dapat di-play di WhatsApp."""
    try:
        f_exe = shutil.which("ffmpeg")
        if not f_exe or len(data) < 1024:
            return data
        is_mp4_or_webm = (b'ftyp' in data[:32]) or data[:4] == b'\x1a\x45\xdf\xa3' or data[:4] == b'OggS'
        if not is_mp4_or_webm and (data[:3] == b'ID3' or (len(data) > 2 and data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)):
            return data

        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as tf_in:
            tf_in.write(data)
            in_path = tf_in.name
        out_path = in_path + ".mp3"
        try:
            cmd = [
                f_exe, '-y', '-i', in_path,
                '-vn',
                '-acodec', 'libmp3lame',
                '-ar', '44100',
                '-ac', '2',
                '-b:a', '128k',
                out_path
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, timeout=60)
            if res.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                with open(out_path, 'rb') as f_out:
                    return f_out.read()
        finally:
            for p in [in_path, out_path]:
                try:
                    if os.path.exists(p):
                        os.remove(p)
                except Exception:
                    pass
    except Exception:
        pass
    return data


def extract_quoted_text_from_message(message: MessageEv) -> str:
    """Mengekstrak teks atau caption dari pesan yang di-reply/quoted jika ada"""
    try:
        if not message or not message.Message:
            return ""
        unwrapped = deep_unwrap_message(message.Message)
        if not unwrapped:
            return ""

        ctx_info = None
        for field_name in ['extendedTextMessage', 'imageMessage', 'videoMessage', 'documentMessage', 'buttonsResponseMessage', 'templateButtonReplyMessage']:
            if unwrapped.HasField(field_name):
                sub = getattr(unwrapped, field_name)
                if hasattr(sub, 'HasField') and sub.HasField('contextInfo'):
                    ctx_info = sub.contextInfo
                    break

        if ctx_info and ctx_info.HasField('quotedMessage'):
            return extract_text_from_message_pb(ctx_info.quotedMessage)
    except Exception:
        pass
    return ""


def handle_media_download_command(client: NewClient, message: MessageEv, query: str, platform_key: str | None = None, cmd_used: str = ",dl"):
    """Mengunduh video/media dari external link (TikTok, Facebook, Instagram, YouTube, dll.) dan dikirim sebagai file dokumen."""
    chat_jid = message.Info.MessageSource.Chat

    target_url = None
    if query:
        url_match = re.search(r'https?://[^\s]+', query)
        if url_match:
            target_url = url_match.group(0).rstrip('>')

    # Jika tidak ada link di teks perintah, coba cek pesan yang di-reply (quoted message)
    if not target_url:
        quoted_text = extract_quoted_text_from_message(message)
        if quoted_text:
            url_match = re.search(r'https?://[^\s]+', quoted_text)
            if url_match:
                target_url = url_match.group(0).rstrip('>')

    if not target_url and platform_key == "youtube" and query and query.strip():
        try:
            import downloader
            s_info = downloader.search_youtube_music_info(query.strip())
            if s_info.get("url"):
                target_url = s_info["url"]
        except Exception:
            pass

    if not target_url:
        plat_guides = {
            "youtube": ("YouTube", ",yt", "https://youtu.be/xxxx"),
            "tiktok": ("TikTok", ",tt", "https://vt.tiktok.com/xxxx/"),
            "facebook": ("Facebook", ",fb", "https://www.facebook.com/share/v/xxxx/"),
            "instagram": ("Instagram", ",ig", "https://www.instagram.com/reel/xxxx/"),
            "twitter": ("Twitter / X", ",tw", "https://x.com/user/status/xxxx"),
            "pinterest": ("Pinterest", ",pin", "https://pin.it/xxxx"),
            "threads": ("Threads", ",th", "https://www.threads.net/@user/post/xxxx"),
            "capcut": ("CapCut", ",cc", "https://www.capcut.com/t/xxxx/"),
            "snackvideo": ("SnackVideo", ",sv", "https://s.snackvideo.com/p/xxxx"),
            "spotify": ("Spotify", ",sp", "https://open.spotify.com/track/xxxx"),
            "soundcloud": ("SoundCloud", ",sc", "https://soundcloud.com/artist/track"),
        }
        if platform_key and platform_key in plat_guides:
            p_label, p_cmd, p_ex = plat_guides[platform_key]
            usage_msg = (
                f"❌ *Format Perintah {p_label} Downloader*\n\n"
                f"Penggunaan:\n"
                f"1. `{p_cmd} <link {p_label}>`\n"
                f"2. Atau *balas/reply* pesan yang memuat link {p_label} dengan `{p_cmd}`\n\n"
                f"💡 *Contoh:*\n"
                f"`{p_cmd} {p_ex}`"
            )
            send_reply_or_message(client, usage_msg, message)
            return

        usage_msg = (
            "*DAFTAR COMMAND DOWNLOADER PLATFORM*\n\n"
            "Gunakan command sesuai singkatan platform:\n"
            "• *,tt <link>* -> TikTok Video (No Watermark)\n"
            "• *,fb <link>* -> Facebook Video / Reels\n"
            "• *,ig <link>* -> Instagram Reels / Post\n"
            "• *,music <judul>* -> Cari & Putar Lagu/Musik\n\n"
            "*Tips:* Anda juga bisa langsung *reply* pesan berisi link dengan singkatan platformnya (`,tt`, `,fb`, `,ig`)."
        )
        send_reply_or_message(client, usage_msg, message)
        return
    if False:
        usage_msg = (
            "*Format Perintah Kurang Lengkap*\n\n"
            "Penggunaan:\n"
            "1. `,dl <link media/video>`\n"
            "2. Atau *balas/reply* pesan yang memuat link dengan `,dl`\n\n"
            "*Platform didukung:*\n"
            "• TikTok (Video No-Watermark)\n"
            "• Facebook (HD/SD Video)\n"
            "• Instagram (Reels / Video)\n"
            "• YouTube (Video MP4)\n"
            "• Twitter/X, dll.\n\n"
            "*Contoh:*\n"
            "`,dl https://vt.tiktok.com/xxxx/`"
        )
        send_reply_or_message(client, usage_msg, message)
        return

    # Kirim status memproses
    send_reply_or_message(client, "Sedang memproses dan mengunduh media dari link...", message)

    try:
        import downloader
        res = downloader.get_media(target_url, is_audio=(platform_key in ["spotify", "soundcloud"]), forced_platform=platform_key)
        if not res.get("status"):
            err_msg = res.get("error", "Gagal mengekstrak media dari link tersebut.")
            send_reply_or_message(client, f"*Gagal Mengunduh:*\n{err_msg}", message)
            return

        title = res.get("title") or "Video"
        clean_title = re.sub(r'[^\w\s-]', '', title).strip()[:50] or "video"
        ext = res.get("filename", "").split(".")[-1] if "." in res.get("filename", "") else "mp4"
        filename = f"{clean_title}.{ext}"
        mimetype = res.get("mimetype") or "video/mp4"

        # Batas maksimal unduhan 45 MB agar aman pada VPS low-RAM dan batas WA
        MAX_SIZE = 45 * 1024 * 1024
        media_bytes = res.get("media_bytes")

        if not media_bytes:
            stream_url = res.get("url")
            if not stream_url:
                send_reply_or_message(client, "*Gagal Mengunduh:*\nLink stream media tidak ditemukan.", message)
                return

            req_headers = res.get("headers") or {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Origin': 'https://en1.savefrom.net',
                'Referer': 'https://en1.savefrom.net/'
            }

            resp = requests.get(stream_url, headers=req_headers, stream=True, timeout=60, allow_redirects=True)
            if resp.status_code != 200:
                if resp.status_code == 403 and ("youtube.com" in target_url or "youtu.be" in target_url):
                    send_reply_or_message(client, "*Gagal Mengunduh (403 Forbidden):*\nServer YouTube membatasi link stream luar ke IP VPS Anda.\n\n*Solusi:* Jalankan perintah `pip install yt-dlp` di terminal VPS Anda agar bot dapat mengunduh langsung dari YouTube tanpa pembatasan IP.", message)
                else:
                    send_reply_or_message(client, f"*Gagal Mengunduh:*\nServer media mengembalikan kode status {resp.status_code}.", message)
                return

            resp_content_type = resp.headers.get('Content-Type', '').lower()
            if 'text/html' in resp_content_type:
                send_reply_or_message(client, "*Gagal Mengunduh:*\nServer media mengembalikan halaman web HTML (link tidak valid atau kedaluwarsa).", message)
                return

            content_len = resp.headers.get('Content-Length')
            if content_len and int(content_len) > MAX_SIZE:
                size_mb = round(int(content_len) / (1024 * 1024), 1)
                send_reply_or_message(client, f"*Ukuran Melebihi Batas:*\nUkuran file ({size_mb} MB) terlalu besar untuk dikirim lewat WhatsApp (maks 45 MB).", message)
                return

            chunks = []
            downloaded_bytes = 0
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    chunks.append(chunk)
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > MAX_SIZE:
                        send_reply_or_message(client, "*Gagal:*\nUkuran file melebihi batas maksimal 45 MB.", message)
                        return

            media_bytes = b"".join(chunks)
            del chunks

        # Validasi bahwa konten bukan halaman HTML atau data kosong/rusak
        if len(media_bytes) < 10240 or media_bytes.startswith(b'<!doctype') or media_bytes.startswith(b'<html'):
            send_reply_or_message(client, "*Gagal Mengunduh:*\nData media yang diterima tidak valid atau rusak (halaman web/error).", message)
            del media_bytes
            return

        caption = f"*{title}*\nUnduhan Berhasil"
        file_size = len(media_bytes)
        size_mb = round(file_size / (1024 * 1024), 1)

        msg_to_send = None
        is_audio_result = res.get("type") == "audio" or filename.lower().endswith((".mp3", ".m4a", ".aac", ".ogg", ".opus")) or (mimetype and mimetype.startswith("audio/"))

        if not is_audio_result:
            media_bytes = _ensure_whatsapp_playable_video(media_bytes)
        else:
            media_bytes = _ensure_whatsapp_playable_audio(media_bytes)

        if is_audio_result:
            try:
                upload = client.upload(media_bytes, MediaType.MediaAudio)
                ctx_info = pb.ContextInfo()
                if message:
                    ctx_info.MergeFrom(client._make_quoted_message(message))

                dur = int(res.get("duration") or 0) or _extract_media_duration(media_bytes)
                ext = filename.split('.')[-1].lower() if '.' in filename else 'mp3'
                audio_mimetype = 'audio/mp4' if ext in ['m4a', 'aac'] else ('audio/ogg; codecs=opus' if ext in ['ogg', 'opus'] else 'audio/mpeg')

                audio_msg = pb.AudioMessage(
                    URL=upload.url,
                    directPath=upload.DirectPath,
                    fileEncSHA256=upload.FileEncSHA256,
                    fileLength=upload.FileLength,
                    fileSHA256=upload.FileSHA256,
                    mediaKey=upload.MediaKey,
                    mimetype=audio_mimetype,
                    PTT=False,
                    seconds=dur or 1,
                    contextInfo=ctx_info
                )
                msg_to_send = pb.Message(audioMessage=audio_msg)
            except Exception as e_a:
                logging.warning(f"Gagal upload audioMessage ({e_a}), kirim sebagai dokumen...")
                doc_caption = f"{caption}\nFile: {filename} ({size_mb} MB)"
                msg_to_send = client.build_document_message(
                    file=media_bytes,
                    filename=filename,
                    mimetype=mimetype or "audio/mpeg",
                    caption=doc_caption,
                    quoted=message
                )
        else:
            # Video: Kirim sebagai VideoMessage agar langsung dapat diputar (playable video) di WhatsApp
            try:
                upload = client.upload(media_bytes, MediaType.MediaVideo)
                ctx_info = pb.ContextInfo()
                if message:
                    ctx_info.MergeFrom(client._make_quoted_message(message))

                dur = int(res.get("duration") or 0) or _extract_media_duration(media_bytes)
                thumb = _extract_video_thumbnail(media_bytes)

                video_kwargs = {
                    "URL": upload.url,
                    "directPath": upload.DirectPath,
                    "fileEncSHA256": upload.FileEncSHA256,
                    "fileLength": upload.FileLength,
                    "fileSHA256": upload.FileSHA256,
                    "mediaKey": upload.MediaKey,
                    "mimetype": "video/mp4",
                    "caption": caption,
                    "seconds": dur or 1,
                    "contextInfo": ctx_info
                }
                if thumb:
                    video_kwargs["JPEGThumbnail"] = thumb

                video_msg = pb.VideoMessage(**video_kwargs)
                msg_to_send = pb.Message(videoMessage=video_msg)
            except Exception as e_vid:
                logging.warning(f"Gagal upload VideoMessage langsung ({e_vid}), mencoba client.build_video_message...")
                try:
                    msg_to_send = client.build_video_message(file=media_bytes, caption=caption, quoted=message)
                except Exception as e_bvid:
                    logging.error(f"Fallback build_video_message gagal ({e_bvid}), fallback ke document: {e_bvid}")
                    doc_caption = f"{caption}\nFile: {filename} ({size_mb} MB)"
                    msg_to_send = client.build_document_message(
                        file=media_bytes,
                        filename=filename,
                        mimetype=mimetype or "video/mp4",
                        caption=doc_caption,
                        quoted=message
                    )

        if msg_to_send:
            client.send_message(chat_jid, msg_to_send)
        else:
            send_reply_or_message(client, "Gagal mengemas pesan media untuk dikirim.", message)

        del media_bytes
    except Exception as e:
        logging.error(f"Error pada handle_media_download_command: {e}", exc_info=True)
        send_reply_or_message(client, f"*Terjadi Kesalahan:*\n{e}", message)


def handle_music_command(client: NewClient, message: MessageEv, query: str):
    """Mencari dan mengunduh musik/lagu berdasarkan judul lagu atau link media."""
    chat_jid = message.Info.MessageSource.Chat

    # Jika tidak ada judul di query, periksa apakah user me-reply pesan teks
    if not query:
        quoted_text = extract_quoted_text_from_message(message)
        if quoted_text:
            query = quoted_text.strip()

    if not query:
        usage_msg = (
            "*Format Perintah Kurang Lengkap*\n\n"
            "Penggunaan:\n"
            "1. `,music <judul lagu / nama musik>`\n"
            "2. Atau *balas/reply* pesan teks dengan `,music`\n\n"
            "*Contoh:*\n"
            "• `,music Komang - Raim Laode`\n"
            "• `,music Bohemian Rhapsody`\n"
            "• `,music Nadin Amizah Rayuan Perempuan Gila`"
        )
        send_reply_or_message(client, usage_msg, message)
        return

    # Kirim status memproses
    send_reply_or_message(client, f"Sedang mencari musik *\"{query}\"* dan mengunduh audio...", message)

    try:
        import downloader
        res = downloader.search_and_download_music(query)
        if not res.get("status"):
            err_msg = res.get("error", "Musik tidak ditemukan.")
            send_reply_or_message(client, f"*Gagal Mengunduh Musik:*\n{err_msg}", message)
            return

        title = res.get("title") or query
        clean_title = re.sub(r'[^\w\s-]', '', title).strip()[:50] or "music"
        ext = res.get("filename", "").split(".")[-1] if "." in res.get("filename", "") else "mp3"
        filename = f"{clean_title}.{ext}"
        mimetype = res.get("mimetype") or "audio/mpeg"

        # Batas maksimal unduhan 45 MB agar aman pada VPS low-RAM dan batas WA
        MAX_SIZE = 45 * 1024 * 1024
        media_bytes = res.get("media_bytes")

        if not media_bytes:
            stream_url = res.get("url")
            if not stream_url:
                send_reply_or_message(client, "*Gagal Mengunduh:*\nLink stream audio tidak ditemukan.", message)
                return

            req_headers = res.get("headers") or {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Origin': 'https://en1.savefrom.net',
                'Referer': 'https://en1.savefrom.net/'
            }

            resp = requests.get(stream_url, headers=req_headers, stream=True, timeout=60, allow_redirects=True)
            if resp.status_code != 200:
                send_reply_or_message(client, f"*Gagal Mengunduh:*\nServer audio mengembalikan kode status {resp.status_code}.", message)
                return

            chunks = []
            downloaded_bytes = 0
            for chunk in resp.iter_content(chunk_size=64 * 1024):
                if chunk:
                    chunks.append(chunk)
                    downloaded_bytes += len(chunk)
                    if downloaded_bytes > MAX_SIZE:
                        send_reply_or_message(client, "*Gagal:*\nUkuran file audio melebihi batas maksimal 45 MB.", message)
                        return

            media_bytes = b"".join(chunks)
            del chunks

        # Validasi bahwa konten bukan halaman HTML atau data kosong/rusak
        if len(media_bytes) < 10240 or media_bytes.startswith(b'<!doctype') or media_bytes.startswith(b'<html'):
            send_reply_or_message(client, "*Gagal Mengunduh:*\nData audio yang diterima tidak valid atau rusak.", message)
            del media_bytes
            return

        file_size = len(media_bytes)
        size_mb = round(file_size / (1024 * 1024), 1)
        caption = f"*{title}*\nUkuran: {size_mb} MB\nUnduhan Berhasil"

        msg_to_send = None
        media_bytes = _ensure_whatsapp_playable_audio(media_bytes)
        filename = f"{clean_title}.mp3"
        mimetype = "audio/mpeg"
        dur = int(res.get("duration") or 0) or _extract_media_duration(media_bytes)

        try:
            # 1. Upload langsung sebagai MediaAudio ke WhatsApp agar tampil sebagai player audio yang bisa diputar langsung di WhatsApp
            upload = client.upload(media_bytes, MediaType.MediaAudio)
            ctx_info = pb.ContextInfo()
            if message:
                ctx_info.MergeFrom(client._make_quoted_message(message))

            ext = filename.split('.')[-1].lower() if '.' in filename else 'mp3'
            if ext in ['m4a', 'aac']:
                audio_mimetype = 'audio/mp4'
            elif ext in ['ogg', 'opus']:
                audio_mimetype = 'audio/ogg; codecs=opus'
            else:
                audio_mimetype = 'audio/mpeg'

            audio_msg = pb.AudioMessage(
                URL=upload.url,
                directPath=upload.DirectPath,
                fileEncSHA256=upload.FileEncSHA256,
                fileLength=upload.FileLength,
                fileSHA256=upload.FileSHA256,
                mediaKey=upload.MediaKey,
                mimetype=audio_mimetype,
                PTT=False,
                seconds=dur or 1,
                contextInfo=ctx_info
            )
            msg_to_send = pb.Message(audioMessage=audio_msg)
        except Exception as ex_audio:
            logging.warning(f"Upload pb.AudioMessage langsung gagal ({ex_audio}), mencoba client.build_audio_message...")
            try:
                msg_to_send = client.build_audio_message(file=media_bytes, ptt=False, quoted=message)
            except Exception as e_audio:
                logging.error(f"build_audio_message gagal ({e_audio}), fallback ke document file: {e_audio}")
                msg_to_send = client.build_document_message(
                    file=media_bytes,
                    filename=filename,
                    mimetype=mimetype or "audio/mpeg",
                    caption=caption,
                    quoted=message
                )

        if msg_to_send:
            client.send_message(chat_jid, msg_to_send)
        else:
            send_reply_or_message(client, "Gagal mengemas pesan musik untuk dikirim.", message)

        del media_bytes
    except Exception as e:
        logging.error(f"Error pada handle_music_command: {e}", exc_info=True)
        send_reply_or_message(client, f"*Terjadi Kesalahan:*\n{e}", message)


def get_group_members_info(client: NewClient, chat_jid: JID) -> dict:
    """Mengambil informasi anggota grup dengan caching (10 menit)"""
    chat_jid_str = str(chat_jid)
    now = time.time()
    
    if chat_jid_str in GROUP_CACHE and (now - GROUP_CACHE[chat_jid_str]['timestamp'] < 600):
        return GROUP_CACHE[chat_jid_str]
        
    try:
        group_info = client.get_group_info(chat_jid)
        jids_list = []
        admins_list = []
        jids_raw = []
        for participant in group_info.Participants:
            jids_list.append(f"{participant.JID.User}@{participant.JID.Server}")
            jids_raw.append(participant.JID)
            if participant.IsAdmin or participant.IsSuperAdmin:
                admins_list.append(participant.JID.User)
        
        data = {
            'jids': jids_list,
            'admins': admins_list,
            'jids_raw': jids_raw,
            'timestamp': now
        }
        GROUP_CACHE[chat_jid_str] = data
        return data
    except Exception as e:
        logging.error(f"Gagal mengambil informasi anggota grup: {e}")
        if chat_jid_str in GROUP_CACHE:
            return GROUP_CACHE[chat_jid_str]
        return {
            'jids': [],
            'admins': [],
            'jids_raw': [],
            'timestamp': 0
        }

# Handler kustom untuk QR Code agar disimpan sebagai file gambar
def on_qr(client: NewClient, data_qr: bytes):
    # Tampilkan di terminal seperti bawaan
    print("\n" + "="*50)
    print(" QR CODE WHATSAPP BARU DIHASILKAN")
    print("="*50)
    try:
        segno.make_qr(data_qr).terminal(compact=True)
    except Exception:
        # Fallback jika encoding terminal Windows (CP1252) tidak mendukung karakter block QR
        try:
            segno.make_qr(data_qr).terminal(compact=False)
        except Exception:
            print("[QR Code tidak dapat ditampilkan langsung di terminal ini]")
    
    # Simpan sebagai file gambar PNG di folder proyek
    qr_file = os.path.join(PROJECT_ROOT, "whatsapp_qr.png")
    segno.make_qr(data_qr).save(qr_file, scale=10)
    print(f"\n QR Code sukses disimpan sebagai gambar: '{qr_file}'")
    print("Silakan buka gambar tersebut di komputer Anda dan lakukan pemindaian (scan) menggunakan WhatsApp HP Anda.")
    print("="*50 + "\n")

client.event.qr(on_qr)



def deep_unwrap_message(msg: pb.Message) -> pb.Message:
    """Membuka semua pembungkus pesan secara mendalam (ephemeral, viewOnce, associatedChild, botForwarded, dll.)"""
    if not msg:
        return msg
    curr = msg
    wrapper_fields = [
        'ephemeralMessage', 'viewOnceMessage', 'viewOnceMessageV2',
        'viewOnceMessageV2Extension', 'documentWithCaptionMessage',
        'associatedChildMessage', 'botForwardedMessage', 'editedMessage',
        'groupMentionedMessage', 'deviceSentMessage', 'spoilerMessage',
        'commentMessage', 'botInvokeMessage'
    ]
    for _ in range(10):
        unwrapped = False
        for wf in wrapper_fields:
            if curr.HasField(wf):
                sub = getattr(curr, wf)
                if hasattr(sub, 'message') and sub.HasField('message'):
                    curr = sub.message
                    unwrapped = True
                    break
        if not unwrapped:
            break
    return curr

def unwrap_message_obj(msg: pb.Message) -> pb.Message:
    """Alias kompatibilitas untuk deep_unwrap_message"""
    return deep_unwrap_message(msg)

def extract_media_submessage(msg: pb.Message) -> tuple[pb.Message | None, bool, str]:
    """
    Mengekstrak (target_msg, is_image, caption) dari Message protobuf.
    Mendukung direct imageMessage, document (image), buttonsMessage, interactiveMessage.header.
    Mengembalikan target_msg (pb.Message) yang siap diunduh oleh client.download_any.
    """
    if not msg:
        return None, False, ""
    unwrapped = deep_unwrap_message(msg)
    if not unwrapped:
        return None, False, ""

    if unwrapped.HasField('imageMessage'):
        caption = unwrapped.imageMessage.caption or ""
        return unwrapped, True, caption

    if unwrapped.HasField('documentMessage') and unwrapped.documentMessage.mimetype and unwrapped.documentMessage.mimetype.startswith('image/'):
        caption = unwrapped.documentMessage.caption or ""
        return unwrapped, True, caption

    if unwrapped.HasField('buttonsMessage') and unwrapped.buttonsMessage.HasField('imageMessage'):
        caption = unwrapped.buttonsMessage.imageMessage.caption or unwrapped.buttonsMessage.contentText or ""
        m = pb.Message(imageMessage=unwrapped.buttonsMessage.imageMessage)
        return m, True, caption

    if unwrapped.HasField('interactiveMessage') and unwrapped.interactiveMessage.HasField('header') and unwrapped.interactiveMessage.header.HasField('imageMessage'):
        caption = unwrapped.interactiveMessage.header.imageMessage.caption or ""
        m = pb.Message(imageMessage=unwrapped.interactiveMessage.header.imageMessage)
        return m, True, caption

    return None, False, ""

def extract_text_from_message_pb(msg: pb.Message) -> str:
    """Ekstraksi teks pesan secara aman dari Message protobuf (termasuk media caption & wrappers)"""
    if not msg:
        return ""
    unwrapped = deep_unwrap_message(msg)
    if not unwrapped:
        return ""
    if unwrapped.conversation:
        return unwrapped.conversation
    if unwrapped.extendedTextMessage and unwrapped.extendedTextMessage.text:
        return unwrapped.extendedTextMessage.text
    if unwrapped.imageMessage and unwrapped.imageMessage.caption:
        return unwrapped.imageMessage.caption
    if unwrapped.videoMessage and unwrapped.videoMessage.caption:
        return unwrapped.videoMessage.caption
    if unwrapped.documentMessage and unwrapped.documentMessage.caption:
        return unwrapped.documentMessage.caption
    if unwrapped.buttonsMessage and unwrapped.buttonsMessage.contentText:
        return unwrapped.buttonsMessage.contentText
    if unwrapped.interactiveMessage and unwrapped.interactiveMessage.HasField('body') and unwrapped.interactiveMessage.body.text:
        return unwrapped.interactiveMessage.body.text
    if unwrapped.templateMessage:
        tm = unwrapped.templateMessage
        if tm.HasField('hydratedTemplate') and tm.hydratedTemplate.hydratedContentText:
            return tm.hydratedTemplate.hydratedContentText
        if tm.HasField('fourRowTemplate') and tm.fourRowTemplate.HasField('content') and tm.fourRowTemplate.content.text:
            return tm.fourRowTemplate.content.text
    if unwrapped.HasField('interactiveResponseMessage'):
        irm = unwrapped.interactiveResponseMessage
        if irm.HasField('nativeFlowResponseMessage') and irm.nativeFlowResponseMessage.paramsJSON:
            try:
                params = json.loads(irm.nativeFlowResponseMessage.paramsJSON)
                if params.get("id"):
                    return str(params["id"])
            except Exception:
                pass
        if irm.HasField('body') and irm.body.text:
            return irm.body.text
    if unwrapped.HasField('buttonsResponseMessage'):
        brm = unwrapped.buttonsResponseMessage
        return brm.selectedButtonID or brm.selectedDisplayText or ""
    if unwrapped.HasField('listResponseMessage'):
        lrm = unwrapped.listResponseMessage
        if lrm.HasField('singleSelectReply') and lrm.singleSelectReply.selectedRowID:
            return lrm.singleSelectReply.selectedRowID
        return lrm.title or lrm.description or ""
    if unwrapped.HasField('templateButtonReplyMessage'):
        tbrm = unwrapped.templateButtonReplyMessage
        return tbrm.selectedID or tbrm.selectedDisplayText or ""
    return ""

def extract_text(message: MessageEv) -> str:
    """Ekstraksi teks pesan secara aman dari MessageEv protobuf (termasuk media caption & wrappers)"""
    if not message or not message.Message:
        return ""
    return extract_text_from_message_pb(message.Message)

def cache_group_message(message: MessageEv):
    """Menyimpan pesan grup terbaru ke memory cache untuk mendukung command ,a pada multi-gambar / 2 gambar"""
    try:
        if not message.Info or not message.Info.MessageSource or not message.Info.MessageSource.IsGroup:
            return
        chat_jid = message.Info.MessageSource.Chat
        if not chat_jid:
            return
        chat_jid_str = f"{chat_jid.User}@{chat_jid.Server}"

        # Cek apakah ini adalah pembaruan pesan yang diedit (protocolMessage MESSAGE_EDIT)
        cand_proto = message.Message
        if cand_proto and hasattr(cand_proto, 'HasField') and cand_proto.HasField('protocolMessage'):
            pm = cand_proto.protocolMessage
            target_key_id = pm.key.ID if pm.HasField('key') and pm.key.ID else ""
            if target_key_id and pm.HasField('editedMessage'):
                edited_pb = pm.editedMessage
                edited_unwrapped = deep_unwrap_message(edited_pb)
                media_msg, is_img, img_caption = extract_media_submessage(edited_pb)
                if not is_img and edited_unwrapped:
                    media_msg, is_img, img_caption = extract_media_submessage(edited_unwrapped)
                text_content = extract_text_from_message_pb(edited_unwrapped or edited_pb)

                cached_list = GROUP_MESSAGE_CACHE.get(chat_jid_str, [])
                for existing in cached_list:
                    if existing["id"] == target_key_id:
                        if is_img:
                            existing["is_image"] = True
                            existing["media_msg"] = media_msg
                            existing["raw_message"] = edited_pb
                        if img_caption:
                            existing["caption"] = img_caption
                        if text_content:
                            existing["text"] = text_content
                        save_group_messages_cache(GROUP_MESSAGE_CACHE)
                        break
                return

        msg_id = message.Info.ID
        if not msg_id:
            return
        
        sender_user = ""
        sender_alt = ""
        if message.Info and message.Info.MessageSource:
            if message.Info.MessageSource.Sender and message.Info.MessageSource.Sender.User:
                sender_user = message.Info.MessageSource.Sender.User
            if message.Info.MessageSource.SenderAlt and message.Info.MessageSource.SenderAlt.User:
                sender_alt = message.Info.MessageSource.SenderAlt.User
            if not sender_user and message.Info.MessageSource.Chat and message.Info.MessageSource.Chat.User:
                sender_user = message.Info.MessageSource.Chat.User

        clean_sender = sender_user.split('.')[0].split(':')[0].split('@')[0] if sender_user else ""
        clean_sender_alt = sender_alt.split('.')[0].split(':')[0].split('@')[0] if sender_alt else ""

        all_senders = set()
        for s in [sender_user, clean_sender, sender_alt, clean_sender_alt]:
            if s:
                all_senders.add(s.lower())

        unwrapped = deep_unwrap_message(message.Message) if message.Message else None

        # Deteksi parent_id dan messageIndex dari messageContextInfo.messageAssociation
        parent_id = ""
        message_index = 0
        for cand_m in [message.Message, unwrapped]:
            if cand_m and hasattr(cand_m, 'HasField') and cand_m.HasField('messageContextInfo'):
                mci = cand_m.messageContextInfo
                if mci.HasField('messageAssociation'):
                    assoc = mci.messageAssociation
                    if assoc.HasField('parentMessageKey') and assoc.parentMessageKey.ID:
                        parent_id = assoc.parentMessageKey.ID
                    if assoc.messageIndex:
                        message_index = assoc.messageIndex
                    break

        # Deteksi jika ini adalah albumMessage
        is_album = False
        expected_count = 0
        for cand_m in [unwrapped, message.Message]:
            if cand_m and hasattr(cand_m, 'HasField') and cand_m.HasField('albumMessage'):
                is_album = True
                expected_count = cand_m.albumMessage.expectedImageCount or 0
                break

        media_msg, is_img, img_caption = extract_media_submessage(message.Message)
        if not is_img and unwrapped:
            media_msg, is_img, img_caption = extract_media_submessage(unwrapped)

        ts = time.time()
        if hasattr(message.Info, 'Timestamp') and message.Info.Timestamp:
            ts_raw = message.Info.Timestamp
            if hasattr(ts_raw, 'seconds'):
                ts = float(getattr(ts_raw, 'seconds'))
            elif isinstance(ts_raw, (int, float)):
                ts = float(ts_raw)

        # Jika parent_id kosong tapi ada album baru dari pengirim yang sama dalam 20 detik terakhir
        if not parent_id and is_img:
            cached_list = GROUP_MESSAGE_CACHE.get(chat_jid_str, [])
            for past_item in reversed(cached_list[-8:]):
                p_senders = set(past_item.get("all_senders", [])) or {past_item.get("sender", "").lower()}
                if past_item.get("is_album") and (not p_senders or bool(p_senders & all_senders)):
                    if abs(ts - past_item.get("timestamp", 0)) <= 25:
                        parent_id = past_item.get("id")
                        break

        raw_json = ""
        try:
            raw_json = MessageToJson(message.Message)
        except Exception:
            pass

        text_content = extract_text_from_message_pb(unwrapped or message.Message)

        entry = {
            "id": msg_id,
            "parent_id": parent_id,
            "message_index": message_index,
            "sender": clean_sender,
            "sender_raw": sender_user,
            "sender_alt": sender_alt,
            "all_senders": list(all_senders),
            "timestamp": ts,
            "is_image": is_img,
            "is_album": is_album,
            "expected_count": expected_count,
            "caption": img_caption,
            "text": text_content,
            "media_msg": media_msg,
            "raw_message": message.Message,
            "raw_json": raw_json
        }

        if chat_jid_str not in GROUP_MESSAGE_CACHE:
            GROUP_MESSAGE_CACHE[chat_jid_str] = []

        q = GROUP_MESSAGE_CACHE[chat_jid_str]
        replaced = False
        for i, existing in enumerate(q):
            if existing["id"] == msg_id:
                q[i] = entry
                replaced = True
                break

        if not replaced:
            q.append(entry)
            if len(q) > MAX_GROUP_CACHE_SIZE:
                q.pop(0)

        # Simpan cache ke file jika berupa media atau album
        if is_img or is_album:
            save_group_messages_cache(GROUP_MESSAGE_CACHE)
    except Exception as e:
        logging.debug(f"Error caching group message: {e}")


def safe_calc(expression: str) -> str:
    """Evaluasi matematis sederhana secara aman"""
    # Bersihkan spasi
    expr_clean = expression.strip()
    # Regex untuk memvalidasi hanya angka, operator matematika dasar, titik desimal, kurung, dan spasi
    if re.match(r"^[0-9+\-*/().\s]+$", expr_clean):
        try:
            # Gunakan dict kosong untuk __builtins__ demi keamanan
            result = eval(expr_clean, {"__builtins__": None}, {})
            return f"*Kalkulator*\n\nEkspresi: `{expr_clean}`\nHasil: *{result}*"
        except Exception as e:
            return f"Gagal: *Kalkulator Error*: Gagal menghitung ekspresi. Detail: {e}"
    else:
        return "Gagal: *Kalkulator Error*: Karakter tidak valid. Hanya angka dan operator (+, -, *, /, tanda kurung) yang diperbolehkan."



def categorize_item_type(type_label: str) -> str:
    """Mengelompokkan tipe item ke kategori yang lebih besar (Weapon, Armor, Crysta, dll.)"""
    tl = type_label.lower().replace("[", "").replace("]", "").strip()
    if any(w in tl for w in ["sword", "bow", "staff", "magic device", "knuckles", "halberd", "katana", "arrow", "shield"]):
        return "*Weapon / Sub-Weapon / Shield*"
    elif "crysta" in tl:
        return "*Crysta*"
    elif "armor" in tl:
        return " *Armor*"
    elif "material" in tl:
        return " *Material*"
    elif "additional" in tl:
        return " *Additional Gear*"
    elif "special" in tl:
        return " *Special Gear*"
    elif "usable" in tl:
        return " *Usable*"
    else:
        return "*Lain-lain*"

def fetch_coryn_item_variants(query_or_id) -> dict | None:
    """Mengambil data varian lengkap (Drop Boss & Craft Blacksmith) dari Coryn Club HTML"""
    query_str = str(query_or_id).strip()
    if query_str.startswith("#") or query_str.isdigit():
        item_id = query_str.replace("#", "").strip()
        url = f"https://coryn.club/item.php?id={item_id}"
    else:
        url = f"https://coryn.club/item.php?name={urllib.parse.quote(query_str)}"

    try:
        html = fetch_web_page(url)
        soup = BeautifulSoup(html, 'html.parser')

        cards = soup.find_all('div', class_='card-container')
        if not cards:
            return None

        first_card = cards[0]
        title_el = first_card.find('div', class_='card-title')
        name = title_el.find('a').text.strip() if title_el and title_el.find('a') else "Unknown Item"
        type_label = title_el.find('span').text.strip() if title_el and title_el.find('span') else "[Equipment]"

        # Jika query berupa ID dan hanya dapat 1 kartu, coba cari berdasarkan nama untuk mendapatkan semua varian
        if (query_str.startswith("#") or query_str.isdigit()) and name and len(cards) == 1:
            name_url = f"https://coryn.club/item.php?name={urllib.parse.quote(name)}"
            try:
                name_html = fetch_web_page(name_url, timeout=5)
                name_soup = BeautifulSoup(name_html, 'html.parser')
                name_cards = name_soup.find_all('div', class_='card-container')
                if name_cards:
                    cards = name_cards
            except Exception:
                pass

        sell_info = "0 Spina"
        process_info = "0"
        prop_div = cards[0].find('div', class_='item-prop')
        if prop_div:
            prop_txt = prop_div.get_text(separator=' ', strip=True)
            m_sell = re.search(r'Sell\s*([\d,]+\s*Spina)', prop_txt, re.IGNORECASE)
            if m_sell:
                sell_info = m_sell.group(1)
            m_proc = re.search(r'Process\s*(.*?)(?=$|Sell)', prop_txt, re.IGNORECASE)
            if m_proc:
                process_info = m_proc.group(1).strip()

        drop_sections = []
        craft_sections = []

        for card in cards:
            card_title_el = card.find('div', class_='card-title')
            card_name = card_title_el.find('a').text.strip() if card_title_el and card_title_el.find('a') else ""
            
            if name and card_name and name.lower() not in card_name.lower() and card_name.lower() not in name.lower():
                continue

            accordions = card.find_all('ul', class_='accordion')
            for acc in accordions:
                lis = acc.find_all('li')
                stats_list = []
                obtained_list = []
                recipe_info = ""

                for li in lis:
                    hdr = li.find('div')
                    hdr_txt = hdr.text.strip().lower() if hdr else ""

                    if "stat" in hdr_txt:
                        grid = li.find('div', class_='table-grid')
                        if grid:
                            for row in grid.find_all('div', recursive=False):
                                cols = [c.text.strip().replace('\n', ' ') for c in row.find_all('div', recursive=False) if c.text.strip()]
                                if len(cols) >= 2 and cols[0] != "Stat/Effect":
                                    stats_list.append(f"- {cols[0]}: {cols[1]}")
                    elif "obtained" in hdr_txt:
                        pag_items = li.find_all('div', class_='pagination-js-item')
                        if pag_items:
                            for item_el in pag_items:
                                cols = [c.get_text(separator=' ', strip=True) for c in item_el.find_all('div', recursive=False) if c.get_text(strip=True)]
                                cols = [c for c in cols if c != "-"]
                                if cols:
                                    obtained_list.append(" | ".join(cols))
                        else:
                            grid = li.find('div', class_='table-grid')
                            if grid:
                                for row in grid.find_all('div', recursive=False):
                                    cols = [c.get_text(separator=' ', strip=True) for c in row.find_all('div', recursive=False) if c.get_text(strip=True)]
                                    if cols and cols[0] not in ["Monster", "Dye", "Map", "Monster | Dye | Map"]:
                                        clean_cols = [c for c in cols if c not in ["Monster", "Dye", "Map", "-"]]
                                        if clean_cols:
                                            obtained_list.append(" | ".join(clean_cols))
                        if not obtained_list:
                            txt = li.get_text(separator=' ', strip=True).replace("Obtained From", "").strip()
                            if txt and not txt.startswith("Monster"):
                                obtained_list.append(txt)
                    elif "recipe" in hdr_txt:
                        recipe_info = li.get_text(separator='\n', strip=True).replace("Recipe\n", "").strip()

                is_craft = recipe_info or any("smith" in o.lower() for o in obtained_list)
                if is_craft:
                    craft_sections.append({
                        "stats": stats_list,
                        "recipe": recipe_info,
                        "obtained": obtained_list
                    })
                elif stats_list or obtained_list:
                    drop_sections.append({
                        "stats": stats_list,
                        "obtained": obtained_list
                    })

        return {
            "name": name,
            "type_label": type_label,
            "sell": sell_info,
            "process": process_info,
            "drop_sections": drop_sections,
            "craft_sections": craft_sections
        }
    except Exception as e:
        logging.error(f"Gagal mengambil varian item {query_or_id}: {e}")
        return None

def format_item_detail(item: dict) -> str:
    """Memformat data item equipment/armor/weapon menjadi 2 jenis output (Drop Boss vs Craft Blacksmith)"""
    item_id = item.get("id")
    item_name = item.get("name", "")

    # Coba ambil data varian lengkap dari web
    coryn_data = None
    if item_id:
        if item.get("is_custom_local"):
            coryn_data = {
                "name": item_name,
                "type_label": item.get("type_label", "[Normal Crysta]"),
                "sell": f"{item.get('sell', 67)} Spina",
                "process": f"{item.get('process_amount', 100)} Mana",
                "drop_sections": [
                    {
                        "stats": item.get("custom_stats_list") or [
                            "- Short Range Damage: +10%",
                            "- Stability: +5%",
                            "- Evasion Recharge: +5%",
                            "- Long Range Damage: -15%",
                            "- Upgrade dari Crysta: Kuffania"
                        ],
                        "obtained": item.get("custom_obtained_list") or [
                            "Blanc | Normal Crysta (Upgrade dari Crysta Kuffania)"
                        ]
                    }
                ],
                "craft_sections": []
            }
        else:
            coryn_data = fetch_coryn_item_variants(item_id)
            if coryn_data and item_name:
                c_low = coryn_data.get("name", "").strip().lower()
                i_low = item_name.strip().lower()
                if c_low != i_low and i_low not in c_low:
                    coryn_data = None
    if not coryn_data and item_name:
        if not item.get("is_custom_local"):
            cand_coryn = fetch_coryn_item_variants(item_name)
            if cand_coryn and cand_coryn.get("name", "").strip().lower() == item_name.strip().lower():
                coryn_data = cand_coryn

    if coryn_data:
        name = coryn_data.get("name", item_name)
        type_label = coryn_data.get("type_label", item.get("type_label", "[Equipment]"))
        sell = coryn_data.get("sell", f"{item.get('sell', 0)} Spina")
        process = coryn_data.get("process", f"{item.get('process', 0)}")

        reply = []
        display_name = get_item_bilingual_name(name)
        reply.append(f"*DETAIL ITEM: {display_name.upper()}*")
        reply.append(f"- *Nama:* {display_name}")
        reply.append(f"- *Tipe:* {type_label}")
        reply.append(f"- *Harga Jual:* {sell} | *Proses:* {process}")
        reply.append("")

        # 1. DROP FROM BOSS / MONSTER
        reply.append("──────────────────")
        reply.append("1. *[DROP FROM BOSS / MONSTER]*")
        reply.append("──────────────────")

        drops = coryn_data.get("drop_sections", [])
        if drops:
            for idx, d in enumerate(drops[:2]):
                if len(drops) > 1:
                    reply.append(f"*Varian Drop {idx+1}:*")
                if d.get("stats"):
                    reply.append("*Status & Stats (Drop):*")
                    for s in d["stats"]:
                        m_upg = re.match(r"^-\s*Upgrade for:\s*(.+)$", s, re.IGNORECASE)
                        if m_upg:
                            target_c = m_upg.group(1).strip()
                            reply.append(f"- Upgrade dari Crysta: {get_item_bilingual_name(target_c)}")
                        else:
                            reply.append(s)
                else:
                    reply.append("*Status & Stats (Drop):* Tidak ada data statistik khusus")

                if d.get("obtained"):
                    reply.append("\n*Lokasi Drop & Monster/Boss:*")
                    for ob in d["obtained"]:
                        reply.append(f"- {ob}")
                else:
                    reply.append("\n*Lokasi Drop:* Boss / Monster Toram World")
                reply.append("")
        else:
            reply.append("_Item ini tidak memiliki drop dari monster/boss (Murni Crafting)._\n")

        # 2. CRAFT FROM BLACKSMITH / PLAYER
        reply.append("──────────────────")
        reply.append("2. *[CRAFT FROM BLACKSMITH]*")
        reply.append("──────────────────")

        crafts = coryn_data.get("craft_sections", [])
        if crafts:
            for idx, c in enumerate(crafts[:2]):
                if len(crafts) > 1:
                    reply.append(f"*Varian Craft {idx+1}:*")
                if c.get("stats"):
                    reply.append("*Status & Stats Crafting (BS):*")
                    reply.extend(c["stats"])
                else:
                    reply.append("*Status & Stats Crafting (BS):* Memiliki Potential Point untuk Statting BS")

                if c.get("recipe"):
                    reply.append("\n*Resep & Bahan Crafting Blacksmith:*")
                    lines = c["recipe"].split("\n")
                    for line in lines:
                        line_s = line.strip()
                        if line_s:
                            if line_s in ["Fee", "Set", "Level", "Difficulty", "Materials"]:
                                reply.append(f"- *{line_s}:*")
                            elif line_s.startswith("-"):
                                reply.append(f"  {line_s}")
                            else:
                                reply.append(f"  {line_s}")
                else:
                    reply.append("\n*Resep Crafting:* Dapat dibuat di NPC Blacksmith / Player Smith Skill.")
                reply.append("")
        else:
            reply.append("_Item ini tidak dapat dibuat di NPC Blacksmith / Smith Skill (Murni Drop)._\n")

        return "\n".join(reply).strip()

    # Fallback jika scraper web tidak mendapatkan data
    if item.get("id") and ("stats" not in item or not item.get("stats")):
        api_detail = get_item_detail_from_api(item["id"])
        if api_detail:
            item = api_detail

    stats_text = ""
    if "stats" in item and item["stats"]:
        if isinstance(item["stats"], list):
            stats_text = "\n*Stats/Effects:*\n"
            for stat in item["stats"]:
                val = stat.get("amount", 0)
                sign = "+" if val > 0 else ""
                stats_text += f"- {stat.get('effect_name', 'Unknown')}: {sign}{val}\n"
        else:
            stats_text = f"\n*Stats/Effects:*\n{item['stats']}\n"
    else:
        stats_text = "\n*Stats/Effects:* Tidak ada data/efek\n"

    obtains_text = ""
    if "obtains" in item and item["obtains"]:
        obtains_text = "\n*Cara Mendapatkan (Drop/Craft):*\n"
        for ob in item["obtains"]:
            m_name = ob.get("name", "")
            m_type = ob.get("type_label", "")
            m_map = ob.get("map_name", "")
            loc = f" ({m_map})" if m_map else ""
            obtains_text += f"- {m_name} [{m_type}]{loc}\n"
    elif "obtaining" in item and item["obtaining"]:
        obtains_text = f"\n*Cara Mendapatkan:*\n{item['obtaining']}\n"

    badge = item.get("meta", {}).get("badge", "")
    note = item.get("meta", {}).get("note", "")
    meta_info = ""
    if badge:
        meta_info += f"*Badge:* {badge}\n"
    if note:
        meta_info += f"*Note:* {note}\n"

    raw_n = item.get('name', 'Unknown')
    disp_n = get_item_bilingual_name(raw_n)
    text = (
        f"*DETAIL ITEM: {disp_n.upper()}*\n\n"
        f"- *Nama:* {disp_n}\n"
        f"- *Tipe:* {item.get('type_label', 'Unknown')}\n"
        f"- *Harga Jual:* {item.get('sell', 0)} Spina\n"
        f"- *Proses Poin:* {item.get('process', 0)} (x{item.get('process_amount', 1)})\n"
        f"{meta_info}"
        f"{stats_text}"
        f"{obtains_text}"
    )
    return text.strip()



def handle_fillwp_command(client, message, query: str):
    """Memproses command ,fillwp dengan melakukan form POST ke tanaka0.work"""
    if not query:
        guide_msg = (
            "*PANDUAN STATTING SIMULATOR WEAPON* \n"
            "_Sumber: https://tanaka0.work/_\n\n"
            "*Aturan Penggunaan:*\n"
            "• List stats ketik *,statlist*\n"
            "• Maksimal positif & negatif stats = *7*\n"
            "• Untuk stats positif isi dengan *angka / max*\n"
            "• Untuk stats negatif isi dengan *min*\n"
            "• *dte, rte, elematch, elenon* default adalah *fire* (elemen lain silakan cek list)\n"
            "• *elematch* dan *elenon* cukup diisi dengan nilai *1*\n\n"
            "Tips: *Contoh Format Perintah:*\n"
            "`,fillwp elenon=1, dte%=20, cd=max, atk%=10, cr=max, hpreg=min, dodge=min, def%=min, pot=113, prof=260`"
        )
        client.reply_message(guide_msg, message)
        return

    try:
        # Parse query into key-value pairs
        pairs = [p.strip() for p in query.split(',')]
        params = {}
        for pair in pairs:
            if '=' in pair:
                k, v = pair.split('=', 1)
                params[k.strip().lower()] = v.strip().lower()

        # Shorthand mapping
        shorthand_map = {
            "atk%": "ATK %", "atk": "ATK",
            "matk%": "MATK %", "matk": "MATK",
            "cd%": "Critical Damage %", "cd": "Critical Damage",
            "cr%": "Critical Rate %", "cr": "Critical Rate",
            "str%": "STR %", "str": "STR",
            "int%": "INT %", "int": "INT",
            "vit%": "VIT %", "vit": "VIT",
            "agi%": "AGI %", "agi": "AGI",
            "dex%": "DEX %", "dex": "DEX",
            "hpreg%": "Natural HP Regen %", "hpreg": "Natural HP Regen",
            "mpreg%": "Natural MP Regen %", "mpreg": "Natural MP Regen",
            "dodge%": "Dodge %", "dodge": "Dodge",
            "def%": "DEF %", "def": "DEF",
            "mdef%": "MDEF %", "mdef": "MDEF",
            "accuracy%": "Accuracy %", "accuracy": "Accuracy",
            "acc%": "Accuracy %", "acc": "Accuracy",
            "hp%": "MaxHP %", "hp": "MaxHP",
            "maxhp%": "MaxHP %", "maxhp": "MaxHP",
            "mp": "MaxMP", "maxmp": "MaxMP",
            "mp%": "Magic Pierce %",
            "pp%": "Penetrasi Fisik %",
            "stability%": "Stability %", "stab%": "Stability %",
            "physpierce%": "Penetrasi Fisik %", "physpierce": "Penetrasi Fisik %",
            "magicpierce%": "Magic Pierce %", "magicpierce": "Magic Pierce %",
            "atkspd%": "Kecepatan Serangan %", "atkspd": "Kecepatan Serangan",
            "castspd%": "Kecepatan Merapal %", "castspd": "Kecepatan Merapal",
        }
        
        def parse_element_stat(key):
            ele_map = {
                "api": "Api", "fire": "Api",
                "air": "Air", "water": "Air", "aqua": "Air",
                "angin": "Angin", "wind": "Angin",
                "bumi": "Bumi", "earth": "Bumi",
                "cahaya": "Cahaya", "light": "Cahaya",
                "gelap": "Gelap", "dark": "Gelap"
            }
            if key.startswith("dte"):
                ele_part = key[3:].replace("%", "").strip()
                ele = ele_map.get(ele_part, "Api")
                return f"% luka ke {ele}"
            if key.startswith("rte"):
                ele_part = key[3:].replace("%", "").strip()
                ele = ele_map.get(ele_part, "Api")
                return f"kebal {ele} %"
            if key.startswith("elenon") or key.startswith("nonmatch"):
                ele_part = key[6:] if key.startswith("elenon") else key[8:]
                ele = ele_map.get(ele_part, "Api")
                return f"Unsur {ele} (no matching)"
            if key.startswith("elematch") or key.startswith("ele"):
                ele_part = key[8:] if key.startswith("elematch") else key[3:]
                ele = ele_map.get(ele_part, "Api")
                return f"Unsur {ele} (matching)"
            return None

        plus_list = []
        minus_list = []
        
        pot = int(params.get("pot", 113))
        prof = int(params.get("prof", params.get("proff", 260)))
        chara_lv = int(params.get("lvl", params.get("lv", params.get("level", 320))))
        
        for k, v in params.items():
            if k in ["pot", "prof", "lvl", "lv", "level"]:
                continue
                
            stat_name = shorthand_map.get(k)
            if not stat_name:
                stat_name = parse_element_stat(k)
                
            if not stat_name:
                continue
                
            if v == "max" or (v.isdigit() and int(v) > 0):
                lv_val = "MAX" if v == "max" else v
                plus_list.append((stat_name, lv_val))
            elif v == "min" or (v.startswith("-") and v[1:].isdigit()) or (v.isdigit() and int(v) < 0):
                lv_val = "MAX" if v == "min" else str(abs(int(v)))
                minus_list.append((stat_name, lv_val))

        # Batasi maksimal 7 item masing-masing
        plus_list = plus_list[:7]
        minus_list = minus_list[:7]

        cookie_jar = http.cookiejar.CookieJar()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar),
            urllib.request.HTTPSHandler(context=ctx)
        )
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # 1. Ambil halaman utama untuk inisialisasi cookies & CSRF
        req = urllib.request.Request("https://tanaka0.work/id/BukiProper", headers=headers)
        with opener.open(req, timeout=10) as res:
            html = res.read().decode('utf-8', errors='ignore')
            
        soup = BeautifulSoup(html, 'html.parser')
        csrf_el = soup.find('input', attrs={'name': 'csrf_token'})
        csrf_token = csrf_el.get('value') if csrf_el else ''
        send_token_el = soup.find('input', attrs={'name': 'send_token'})
        send_token = send_token_el.get('value') if send_token_el else ''
        
        # 2. Siapkan data POST
        post_data = {
            'csrf_token': csrf_token,
            'send_token': send_token,
            'properBui': 'Weapon',
            'paramLevel': str(chara_lv),
            'shokiSenzai': str(pot),
            'kisoSenzai': '15',
            'jukurendo': str(prof),
            'rikaiKinzoku': '10',
            'rikaiNunoti': '10',
            'rikaiKemono': '10',
            'rikaiMokuzai': '10',
            'rikaiYakuhin': '10',
            'rikaiMaso': '10',
        }
        
        for i in range(7):
            name_key = f"plusProperList[{i}].properName"
            lv_key = f"plusProperList[{i}].properLvHyoji"
            if i < len(plus_list):
                post_data[name_key] = plus_list[i][0]
                post_data[lv_key] = plus_list[i][1]
            else:
                post_data[name_key] = ''
                post_data[lv_key] = 'MAX'
                
        for i in range(7):
            name_key = f"minusProperList[{i}].properName"
            lv_key = f"minusProperList[{i}].properLvHyoji"
            if i < len(minus_list):
                post_data[name_key] = minus_list[i][0]
                post_data[lv_key] = minus_list[i][1]
            else:
                post_data[name_key] = ''
                post_data[lv_key] = 'MAX'
                
        post_data['sendData'] = 'Submit'
        
        encoded_data = urllib.parse.urlencode(post_data).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        post_req = urllib.request.Request(
            "https://tanaka0.work/id/BukiProper",
            data=encoded_data,
            headers=headers,
            method="POST"
        )
        
        with opener.open(post_req, timeout=15) as res:
            res_html = res.read().decode('utf-8', errors='ignore')
            
        res_soup = BeautifulSoup(res_html, 'html.parser')
        app_div = res_soup.find(id='app')
        if not app_div:
            client.reply_message("Gagal: Gagal memproses hasil perhitungan. div #app tidak ditemukan.", message)
            return

        div55 = None
        div57 = None
        div59 = None
        
        for div in app_div.find_all('div', recursive=False):
            txt = div.get_text()
            if "Statting of" in txt:
                div55 = div
            elif "Mat cost pt" in txt or "reduction of material cost" in txt or "PROF LV" in txt:
                div57 = div
            elif "Starting Pot" in txt or "Sisa Pot" in txt or "Steps" in txt:
                div59 = div

        pos_stats = ""
        neg_stats = ""
        if div55:
            text_nodes = [str(c).strip() for c in div55.children if getattr(c, 'name', None) is None and str(c).strip()]
            if len(text_nodes) >= 1:
                pos_stats = text_nodes[0]
            if len(text_nodes) >= 2:
                neg_stats = text_nodes[1]

        mat_cost_reduction = ""
        compassion_info = ""
        mats_detail = {}
        highest_mats = ""
        if div57:
            font_tag = div57.find('font')
            if font_tag:
                font_text = font_tag.get_text()
                if "(Compassion" in font_text:
                    parts = font_text.split("(Compassion", 1)
                    mat_cost_reduction = parts[0].strip()
                    compassion_info = "(Compassion" + parts[1].strip()
                else:
                    mat_cost_reduction = font_text.strip()
                    
            text_nodes = [str(c).strip() for c in div57.children if getattr(c, 'name', None) is None and str(c).strip()]
            for tn in text_nodes:
                if "Metal:" in tn:
                    matches = re.findall(r'(\w+):([\d,]+)pt', tn)
                    for k, v in matches:
                        mats_detail[k.lower()] = v
                elif "Highest mats" in tn:
                    highest_mats = tn

        success_rate = ""
        starting_pot = ""
        steps = []
        if div59:
            span = div59.find('span')
            if span:
                success_rate = span.get_text().strip()
            b_tag = div59.find('b')
            if b_tag:
                starting_pot = b_tag.get_text().strip()
                
            text_nodes = [str(c).strip() for c in div59.children if getattr(c, 'name', None) is None and str(c).strip()]
            for tn in text_nodes:
                if re.match(r'^\d+\.', tn):
                    steps.append(tn)

        formatted_reply = []
        formatted_reply.append("*HASIL SIMULASI STATTING WEAPON* ")
        formatted_reply.append("_Sumber: https://tanaka0.work/_")
        formatted_reply.append("")
        
        formatted_reply.append("*Target Stats:*")
        if pos_stats:
            formatted_reply.append(" *Positif:*")
            for s in pos_stats.split(','):
                s_strip = s.strip()
                if s_strip:
                    formatted_reply.append(f"   • {s_strip}")
        if neg_stats:
            formatted_reply.append(" *Negatif:*")
            for s in neg_stats.split(','):
                s_strip = s.strip()
                if s_strip:
                    formatted_reply.append(f"   • {s_strip}")
                    
        formatted_reply.append("")
        if success_rate:
            formatted_reply.append(f"*{success_rate}*")
            
        pot_val = starting_pot.replace("Starting Pot：", "").replace("pt", "").strip() if starting_pot else str(pot)
        formatted_reply.append(f"*Starting Potential:* {pot_val} pt")
        formatted_reply.append(f" *Proficiency Level (PROF):* {prof}")
        formatted_reply.append("")
        
        formatted_reply.append("*Langkah-Langkah (Steps):*")
        for step in steps:
            m = re.match(r'^(\d+)\.\s*(.*)', step)
            if m:
                step_num = int(m.group(1))
                step_text = m.group(2)
                emojis = {1: "1⃣", 2: "2⃣", 3: "3⃣", 4: "4⃣", 5: "5⃣", 6: "6⃣", 7: "7⃣", 8: "8⃣", 9: "9⃣", 10: ""}
                num_prefix = emojis.get(step_num, f"[{step_num}]")
                step_text_cleaned = step_text.replace("（", " (").replace("）", ")").replace("：", ": ")
                formatted_reply.append(f"{num_prefix} {step_text_cleaned}")
            else:
                formatted_reply.append(step)
                
        formatted_reply.append("")
        formatted_reply.append(" *Estimasi Biaya Material (Material Cost):*")
        formatted_reply.append(f"• Metal : {mats_detail.get('metal', '0')} pt")
        formatted_reply.append(f"• Cloth : {mats_detail.get('cloth', '0')} pt")
        formatted_reply.append(f"• Beast : {mats_detail.get('beast', '0')} pt")
        formatted_reply.append(f"• Wood  : {mats_detail.get('wood', '0')} pt")
        formatted_reply.append(f"• Medi  : {mats_detail.get('medicine', '0')} pt")
        formatted_reply.append(f"• Mana  : {mats_detail.get('mana', '0')} pt")
        
        if highest_mats:
            highest_mats_clean = highest_mats.replace("Highest mats per step", "Highest mats/step").replace("：", ": ").strip("()")
            formatted_reply.append(f"*{highest_mats_clean}*")
            
        formatted_reply.append("")
        formatted_reply.append("ℹ *_Efisiensi Biaya:_*")
        if mat_cost_reduction:
            formatted_reply.append(f"• {mat_cost_reduction}")
        if compassion_info:
            comp_formatted = compassion_info.replace("CompassionLv", "Compassion Lv").replace(',', ', ').replace(':', ': ').strip("()")
            formatted_reply.append(f"• {comp_formatted}")
            
        formatted_reply.append("")
        formatted_reply.append("Peringatan: *Catatan Penting:*")
        formatted_reply.append("- Cek kembali di Stating Simulator, rumus menggunakan *level stats* bukan *nilai stats*.")
        formatted_reply.append("- Dodge lv-16 = Dodge -22 dan Accuracy lv-16 = Accuracy -22")

        client.reply_message("\n".join(formatted_reply), message)
    except Exception as e:
        client.reply_message(f"Gagal: Terjadi kesalahan saat memproses statting weapon. Detail: {e}", message)

def handle_fillarm_command(client, message, query: str):
    """Memproses command ,fillarm dengan melakukan form POST ke tanaka0.work"""
    if not query:
        guide_msg = (
            " *PANDUAN STATTING SIMULATOR ARMOR* \n"
            "_Sumber: https://tanaka0.work/_\n\n"
            "*Aturan Penggunaan:*\n"
            "• List stats ketik *,statlist*\n"
            "• Maksimal positif & negatif stats = *7*\n"
            "• Untuk stats positif isi dengan *angka / max*\n"
            "• Untuk stats negatif isi dengan *min*\n"
            "• *dte, rte, elematch, elenon* default adalah *fire* (elemen lain silakan cek list)\n"
            "• *elematch* dan *elenon* cukup diisi dengan nilai *1*\n\n"
            "Tips: *Contoh Format Perintah:*\n"
            "`,fillarm str%=10, cd=max, cr=max, hpreg=min, dodge=min, pot=90, prof=260`"
        )
        client.reply_message(guide_msg, message)
        return

    try:
        # Parse query into key-value pairs
        pairs = [p.strip() for p in query.split(',')]
        params = {}
        for pair in pairs:
            if '=' in pair:
                k, v = pair.split('=', 1)
                params[k.strip().lower()] = v.strip().lower()

        # Shorthand mapping
        shorthand_map = {
            "atk%": "ATK %", "atk": "ATK",
            "matk%": "MATK %", "matk": "MATK",
            "cd%": "Critical Damage %", "cd": "Critical Damage",
            "cr%": "Critical Rate %", "cr": "Critical Rate",
            "str%": "STR %", "str": "STR",
            "int%": "INT %", "int": "INT",
            "vit%": "VIT %", "vit": "VIT",
            "agi%": "AGI %", "agi": "AGI",
            "dex%": "DEX %", "dex": "DEX",
            "hpreg%": "Natural HP Regen %", "hpreg": "Natural HP Regen",
            "mpreg%": "Natural MP Regen %", "mpreg": "Natural MP Regen",
            "dodge%": "Dodge %", "dodge": "Dodge",
            "def%": "DEF %", "def": "DEF",
            "mdef%": "MDEF %", "mdef": "MDEF",
            "accuracy%": "Accuracy %", "accuracy": "Accuracy",
            "acc%": "Accuracy %", "acc": "Accuracy",
            "hp%": "MaxHP %", "hp": "MaxHP",
            "maxhp%": "MaxHP %", "maxhp": "MaxHP",
            "mp": "MaxMP", "maxmp": "MaxMP",
            "mp%": "Magic Pierce %",
            "pp%": "Penetrasi Fisik %",
            "stability%": "Stability %", "stab%": "Stability %",
            "physpierce%": "Penetrasi Fisik %", "physpierce": "Penetrasi Fisik %",
            "magicpierce%": "Magic Pierce %", "magicpierce": "Magic Pierce %",
            "atkspd%": "Kecepatan Serangan %", "atkspd": "Kecepatan Serangan",
            "castspd%": "Kecepatan Merapal %", "castspd": "Kecepatan Merapal",
        }
        
        def parse_element_stat(key):
            ele_map = {
                "api": "Api", "fire": "Api",
                "air": "Air", "water": "Air", "aqua": "Air",
                "angin": "Angin", "wind": "Angin",
                "bumi": "Bumi", "earth": "Bumi",
                "cahaya": "Cahaya", "light": "Cahaya",
                "gelap": "Gelap", "dark": "Gelap"
            }
            if key.startswith("dte"):
                ele_part = key[3:].replace("%", "").strip()
                ele = ele_map.get(ele_part, "Api")
                return f"% luka ke {ele}"
            if key.startswith("rte"):
                ele_part = key[3:].replace("%", "").strip()
                ele = ele_map.get(ele_part, "Api")
                return f"kebal {ele} %"
            if key.startswith("elenon") or key.startswith("nonmatch"):
                ele_part = key[6:] if key.startswith("elenon") else key[8:]
                ele = ele_map.get(ele_part, "Api")
                return f"Unsur {ele} (no matching)"
            if key.startswith("elematch") or key.startswith("ele"):
                ele_part = key[8:] if key.startswith("elematch") else key[3:]
                ele = ele_map.get(ele_part, "Api")
                return f"Unsur {ele} (matching)"
            return None

        plus_list = []
        minus_list = []
        
        pot = int(params.get("pot", 90))
        prof = int(params.get("prof", params.get("proff", 260)))
        chara_lv = int(params.get("lvl", params.get("lv", params.get("level", 320))))
        
        for k, v in params.items():
            if k in ["pot", "prof", "lvl", "lv", "level"]:
                continue
                
            stat_name = shorthand_map.get(k)
            if not stat_name:
                stat_name = parse_element_stat(k)
                
            if not stat_name:
                continue
                
            if v == "max" or (v.isdigit() and int(v) > 0):
                lv_val = "MAX" if v == "max" else v
                plus_list.append((stat_name, lv_val))
            elif v == "min" or (v.startswith("-") and v[1:].isdigit()) or (v.isdigit() and int(v) < 0):
                lv_val = "MAX" if v == "min" else str(abs(int(v)))
                minus_list.append((stat_name, lv_val))

        # Batasi maksimal 7 item masing-masing
        plus_list = plus_list[:7]
        minus_list = minus_list[:7]

        cookie_jar = http.cookiejar.CookieJar()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar),
            urllib.request.HTTPSHandler(context=ctx)
        )
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        # 1. Ambil halaman utama untuk inisialisasi cookies & CSRF
        req = urllib.request.Request("https://tanaka0.work/id/BouguProper", headers=headers)
        with opener.open(req, timeout=10) as res:
            html = res.read().decode('utf-8', errors='ignore')
            
        soup = BeautifulSoup(html, 'html.parser')
        csrf_el = soup.find('input', attrs={'name': 'csrf_token'})
        csrf_token = csrf_el.get('value') if csrf_el else ''
        send_token_el = soup.find('input', attrs={'name': 'send_token'})
        send_token = send_token_el.get('value') if send_token_el else ''
        
        # 2. Siapkan data POST
        post_data = {
            'csrf_token': csrf_token,
            'send_token': send_token,
            'properBui': 'Armor',
            'paramLevel': str(chara_lv),
            'shokiSenzai': str(pot),
            'kisoSenzai': '15',
            'jukurendo': str(prof),
            'rikaiKinzoku': '10',
            'rikaiNunoti': '10',
            'rikaiKemono': '10',
            'rikaiMokuzai': '10',
            'rikaiYakuhin': '10',
            'rikaiMaso': '10',
        }
        
        for i in range(7):
            name_key = f"plusProperList[{i}].properName"
            lv_key = f"plusProperList[{i}].properLvHyoji"
            if i < len(plus_list):
                post_data[name_key] = plus_list[i][0]
                post_data[lv_key] = plus_list[i][1]
            else:
                post_data[name_key] = ''
                post_data[lv_key] = 'MAX'
                
        for i in range(7):
            name_key = f"minusProperList[{i}].properName"
            lv_key = f"minusProperList[{i}].properLvHyoji"
            if i < len(minus_list):
                post_data[name_key] = minus_list[i][0]
                post_data[lv_key] = minus_list[i][1]
            else:
                post_data[name_key] = ''
                post_data[lv_key] = 'MAX'
                
        post_data['sendData'] = 'Submit'
        
        encoded_data = urllib.parse.urlencode(post_data).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        post_req = urllib.request.Request(
            "https://tanaka0.work/id/BouguProper",
            data=encoded_data,
            headers=headers,
            method="POST"
        )
        
        with opener.open(post_req, timeout=15) as res:
            res_html = res.read().decode('utf-8', errors='ignore')
            
        res_soup = BeautifulSoup(res_html, 'html.parser')
        app_div = res_soup.find(id='app')
        if not app_div:
            client.reply_message("Gagal: Gagal memproses hasil perhitungan. div #app tidak ditemukan.", message)
            return

        div55 = None
        div57 = None
        div59 = None
        
        for div in app_div.find_all('div', recursive=False):
            txt = div.get_text()
            if "Statting of" in txt:
                div55 = div
            elif "Mat cost pt" in txt or "reduction of material cost" in txt or "PROF LV" in txt:
                div57 = div
            elif "Starting Pot" in txt or "Sisa Pot" in txt or "Steps" in txt:
                div59 = div

        pos_stats = ""
        neg_stats = ""
        if div55:
            text_nodes = [str(c).strip() for c in div55.children if getattr(c, 'name', None) is None and str(c).strip()]
            if len(text_nodes) >= 1:
                pos_stats = text_nodes[0]
            if len(text_nodes) >= 2:
                neg_stats = text_nodes[1]

        mat_cost_reduction = ""
        compassion_info = ""
        mats_detail = {}
        highest_mats = ""
        if div57:
            font_tag = div57.find('font')
            if font_tag:
                font_text = font_tag.get_text()
                if "(Compassion" in font_text:
                    parts = font_text.split("(Compassion", 1)
                    mat_cost_reduction = parts[0].strip()
                    compassion_info = "(Compassion" + parts[1].strip()
                else:
                    mat_cost_reduction = font_text.strip()
                    
            text_nodes = [str(c).strip() for c in div57.children if getattr(c, 'name', None) is None and str(c).strip()]
            for tn in text_nodes:
                if "Metal:" in tn:
                    matches = re.findall(r'(\w+):([\d,]+)pt', tn)
                    for k, v in matches:
                        mats_detail[k.lower()] = v
                elif "Highest mats" in tn:
                    highest_mats = tn

        success_rate = ""
        starting_pot = ""
        steps = []
        if div59:
            span = div59.find('span')
            if span:
                success_rate = span.get_text().strip()
            b_tag = div59.find('b')
            if b_tag:
                starting_pot = b_tag.get_text().strip()
                
            text_nodes = [str(c).strip() for c in div59.children if getattr(c, 'name', None) is None and str(c).strip()]
            for tn in text_nodes:
                if re.match(r'^\d+\.', tn):
                    steps.append(tn)

        formatted_reply = []
        formatted_reply.append(" *HASIL SIMULASI STATTING ARMOR* ")
        formatted_reply.append("_Sumber: https://tanaka0.work/_")
        formatted_reply.append("")
        
        formatted_reply.append("*Target Stats:*")
        if pos_stats:
            formatted_reply.append(" *Positif:*")
            for s in pos_stats.split(','):
                s_strip = s.strip()
                if s_strip:
                    formatted_reply.append(f"   • {s_strip}")
        if neg_stats:
            formatted_reply.append(" *Negatif:*")
            for s in neg_stats.split(','):
                s_strip = s.strip()
                if s_strip:
                    formatted_reply.append(f"   • {s_strip}")
                    
        formatted_reply.append("")
        if success_rate:
            formatted_reply.append(f"*{success_rate}*")
            
        pot_val = starting_pot.replace("Starting Pot：", "").replace("pt", "").strip() if starting_pot else str(pot)
        formatted_reply.append(f"*Starting Potential:* {pot_val} pt")
        formatted_reply.append(f" *Proficiency Level (PROF):* {prof}")
        formatted_reply.append("")
        
        formatted_reply.append("*Langkah-Langkah (Steps):*")
        for step in steps:
            m = re.match(r'^(\d+)\.\s*(.*)', step)
            if m:
                step_num = int(m.group(1))
                step_text = m.group(2)
                emojis = {1: "1⃣", 2: "2⃣", 3: "3⃣", 4: "4⃣", 5: "5⃣", 6: "6⃣", 7: "7⃣", 8: "8⃣", 9: "9⃣", 10: ""}
                num_prefix = emojis.get(step_num, f"[{step_num}]")
                step_text_cleaned = step_text.replace("（", " (").replace("）", ")").replace("：", ": ")
                formatted_reply.append(f"{num_prefix} {step_text_cleaned}")
            else:
                formatted_reply.append(step)
                
        formatted_reply.append("")
        formatted_reply.append(" *Estimasi Biaya Material (Material Cost):*")
        formatted_reply.append(f"• Metal : {mats_detail.get('metal', '0')} pt")
        formatted_reply.append(f"• Cloth : {mats_detail.get('cloth', '0')} pt")
        formatted_reply.append(f"• Beast : {mats_detail.get('beast', '0')} pt")
        formatted_reply.append(f"• Wood  : {mats_detail.get('wood', '0')} pt")
        formatted_reply.append(f"• Medi  : {mats_detail.get('medicine', '0')} pt")
        formatted_reply.append(f"• Mana  : {mats_detail.get('mana', '0')} pt")
        
        if highest_mats:
            highest_mats_clean = highest_mats.replace("Highest mats per step", "Highest mats/step").replace("：", ": ").strip("()")
            formatted_reply.append(f"*{highest_mats_clean}*")
            
        formatted_reply.append("")
        formatted_reply.append("ℹ *_Efisiensi Biaya:_*")
        if mat_cost_reduction:
            formatted_reply.append(f"• {mat_cost_reduction}")
        if compassion_info:
            comp_formatted = compassion_info.replace("CompassionLv", "Compassion Lv").replace(',', ', ').replace(':', ': ').strip("()")
            formatted_reply.append(f"• {comp_formatted}")
            
        formatted_reply.append("")
        formatted_reply.append("Peringatan: *Catatan Penting:*")
        formatted_reply.append("- Cek kembali di Stating Simulator, rumus menggunakan *level stats* bukan *nilai stats*.")
        formatted_reply.append("- Dodge lv-16 = Dodge -22 dan Accuracy lv-16 = Accuracy -22")

        client.reply_message("\n".join(formatted_reply), message)
    except Exception as e:
        client.reply_message(f"Gagal: Terjadi kesalahan saat memproses statting armor. Detail: {e}", message)


def format_monster_detail(monster: dict) -> str:
    """Format detail monster untuk balasan WhatsApp"""
    name = monster.get("name", "Unknown Monster")
    level = monster.get("level", "-")
    element = monster.get("element", "-")
    m_type = monster.get("type", "Monster")
    m_map = monster.get("map", "Toram World")
    hp = monster.get("hp", "-")
    exp = monster.get("exp", "-")

    reply = f"*{name}* (Lv {level})\n"
    reply += f"• Tipe: {m_type}\n"
    reply += f"• Elemen: {element}\n"
    if isinstance(hp, int):
        reply += f"• HP: {hp:,}\n"
    else:
        reply += f"• HP: {hp}\n"
    if isinstance(exp, int):
        reply += f"• EXP: {exp:,}\n"
    else:
        reply += f"• EXP: {exp}\n"
    reply += f"• Lokasi: {m_map}"
    return reply.strip()

def format_monster_group_detail(monster_list: list) -> str:
    """Memformat seluruh variasi level/difficulty/map suatu Monster biasa atau Boss menjadi 1 pesan WhatsApp yang rapi"""
    if not monster_list:
        return ""
    if len(monster_list) == 1:
        return format_monster_detail(monster_list[0])
    
    first = monster_list[0]
    raw_name = first.get("name", "Unknown Monster")
    base_name = raw_name.split(" (")[0].strip() if " (" in raw_name else raw_name
    
    element = first.get("element", "-")
    m_type = first.get("type", "Monster")
    maps_set = set(m.get("map") for m in monster_list if m.get("map"))
    single_map = maps_set.pop() if len(maps_set) == 1 else None
    
    mode_order = {"easy": 1, "normal": 2, "hard": 3, "nightmare": 4, "ultimate": 5}
    sorted_mobs = sorted(monster_list, key=lambda m: (m.get("level", 0), mode_order.get(str(m.get("mode", "")).lower(), 99)))
    
    reply = f"*{base_name}* ({m_type})\n"
    reply += f"• Elemen: {element}\n"
    if single_map:
        reply += f"• Lokasi: {single_map}\n\n"
    else:
        reply += "\n"
        
    reply += f"*Variasi Level & Difficulty ({len(sorted_mobs)} entries):*\n"
    
    for mon in sorted_mobs:
        b_name = mon.get("name", "")
        bracket = ""
        if " (" in b_name:
            bracket = " [" + b_name.split(" (")[1].rstrip(")") + "]"
        
        mode = mon.get("mode", "Normal")
        level = mon.get("level", "-")
        hp = mon.get("hp", "-")
        exp = mon.get("exp", "-")
        loc = mon.get("map", "")
        
        hp_str = f"{hp:,}" if isinstance(hp, int) and hp >= 0 else str(hp)
        exp_str = f"{exp:,}" if isinstance(exp, int) and exp >= 0 else str(exp)
        loc_str = f" | Map: {loc}" if loc and not single_map else ""
        
        reply += f"• *{mode}*{bracket} (Lv {level}) | HP: {hp_str} | EXP: {exp_str}{loc_str}\n"
        
    return reply.strip()

# Penyimpanan sementara untuk opsi pilihan interaktif (Option Button/List Tap & Nomor/Nama Pilihan)
POLL_OPTION_HASH_MAP: dict[bytes, dict] = {}
POLL_BY_MSG_ID: dict[str, dict] = {}
PENDING_SEARCH_CHOICES: dict[tuple[str, str], dict] = {}

def send_interactive_choice_options(
    client: NewClient,
    message: MessageEv,
    poll_title: str,
    choices: list[dict],
    fallback_text: str
):
    """
    Mengirim daftar pilihan (option) interaktif yang bisa langsung di-tap / diklik
    oleh pengguna di WhatsApp menggunakan Interactive ButtonMessage (Selection Option List + Quick Reply Buttons)
    serta menyimpan mapping untuk tap langsung maupun balasan angka/nama.
    """
    try:
        chat_jid = message.Info.MessageSource.Chat
        chat_jid_str = f"{chat_jid.User}@{chat_jid.Server}"
        sender_user = ""
        if message.Info.MessageSource.Sender and message.Info.MessageSource.Sender.User:
            sender_user = message.Info.MessageSource.Sender.User
        elif chat_jid and chat_jid.User:
            sender_user = chat_jid.User
        clean_sender = sender_user.split('.')[0].split(':')[0].split('@')[0]
        now = time.time()

        # Bersihkan entri lama (> 30 menit) agar memori tetap ringan
        for k_p in list(PENDING_SEARCH_CHOICES.keys()):
            if now - PENDING_SEARCH_CHOICES[k_p].get("timestamp", 0) > 1800:
                del PENDING_SEARCH_CHOICES[k_p]

        num_choices_map = {}

        for idx, ch in enumerate(choices[:10], start=1):
            cmd_str = str(ch["command"]).strip()
            name_str = str(ch.get("name") or ch.get("label") or f"Option {idx}").strip()
            label_str = str(ch.get("label") or name_str).strip()
            num_choices_map[str(idx)] = cmd_str
            num_choices_map[cmd_str.lower()] = cmd_str
            if name_str:
                num_choices_map[name_str.lower()] = cmd_str
                num_choices_map[name_str[:24].strip().lower()] = cmd_str
                num_choices_map[f"{idx}. {name_str}".strip().lower()] = cmd_str
                num_choices_map[f"{idx}. {name_str[:20]}".strip().lower()] = cmd_str
            if label_str:
                num_choices_map[label_str.lower()] = cmd_str
                num_choices_map[f"{idx}. {label_str}".strip().lower()] = cmd_str

        PENDING_SEARCH_CHOICES[(chat_jid_str, clean_sender)] = {
            "choices": num_choices_map,
            "orig_message": message,
            "timestamp": now
        }
        PENDING_SEARCH_CHOICES[(chat_jid_str, "*")] = {
            "choices": num_choices_map,
            "orig_message": message,
            "timestamp": now
        }

        if len(choices) >= 2:
            title_lines = [ln.strip() for ln in poll_title.splitlines() if ln.strip()]
            header_title = title_lines[0] if title_lines else "Pilih Option"
            btn_msg = (
                ButtonMessage()
                .set_title(header_title)
                .set_body(fallback_text.strip())
                .set_footer("Tap/klik salah satu option di bawah")
                .set_context_info(client._make_quoted_message(message))
            )
            btn_msg.add_selection("Pilih Option")
            btn_msg.add_section("Daftar Pilihan")
            for idx, ch in enumerate(choices[:10], start=1):
                row_title = str(ch.get("name") or ch.get("label") or f"Option {idx}").strip()
                row_desc = str(ch.get("label") or row_title).strip()
                btn_msg.add_row(
                    title=row_title[:24],
                    description=row_desc[:72],
                    id=str(ch["command"]).strip(),
                    header=f"Option {idx}",
                )
            for idx, ch in enumerate(choices[:3], start=1):
                row_title = str(ch.get("name") or ch.get("label") or f"Option {idx}").strip()
                btn_msg.add_reply(f"{idx}. {row_title[:20]}", str(ch["command"]).strip())

            client.send_interactive_message(chat_jid, btn_msg)
            return
    except Exception as e:
        logging.warning(f"Gagal mengirim interactive button options, menggunakan fallback teks: {e}")

    client.reply_message(fallback_text, message)


def resolve_interactive_or_poll_command(client: NewClient, message: MessageEv) -> tuple[str, MessageEv | None, bool]:
    """
    Mendeteksi apakah pesan masuk adalah tap/klik pada Interactive Option (ButtonMessage / Selection List / Quick Reply)
    atau balasan nomor/nama pilihan, lalu mengembalikan (command_str, orig_message, is_interactive).
    """
    try:
        if not message or not message.Message:
            return "", None, False

        chat_jid = message.Info.MessageSource.Chat
        chat_jid_str = f"{chat_jid.User}@{chat_jid.Server}" if chat_jid else ""
        sender_user = ""
        if message.Info.MessageSource.Sender and message.Info.MessageSource.Sender.User:
            sender_user = message.Info.MessageSource.Sender.User
        elif chat_jid and chat_jid.User:
            sender_user = chat_jid.User
        clean_sender = sender_user.split('.')[0].split(':')[0].split('@')[0]
        now = time.time()

        orig_msg = None
        active_choices_map = {}
        for lookup_key in [(chat_jid_str, clean_sender), (chat_jid_str, "*")]:
            pending = PENDING_SEARCH_CHOICES.get(lookup_key)
            if pending and (now - pending.get("timestamp", 0) <= 1800):
                if orig_msg is None:
                    orig_msg = pending.get("orig_message")
                if not active_choices_map:
                    active_choices_map = pending.get("choices", {})

        unwrapped = deep_unwrap_message(message.Message)
        target_pb = unwrapped if unwrapped else message.Message

        # 1. Cek respons dari Interactive Option (ButtonMessage: single_select / quick_reply / list / buttons / template)
        interactive_candidates = []
        is_interactive_pb = False

        if target_pb.HasField('interactiveResponseMessage'):
            is_interactive_pb = True
            irm = target_pb.interactiveResponseMessage
            if irm.HasField('nativeFlowResponseMessage') and irm.nativeFlowResponseMessage.paramsJSON:
                try:
                    params = json.loads(irm.nativeFlowResponseMessage.paramsJSON)
                    for k in ("id", "selectedId", "selectedRowId", "selectedButtonId", "title", "display_text", "description"):
                        val = params.get(k)
                        if val and isinstance(val, str):
                            interactive_candidates.append(val.strip())
                except Exception:
                    pass
            if irm.HasField('body') and irm.body.text:
                interactive_candidates.append(irm.body.text.strip())

        if target_pb.HasField('buttonsResponseMessage'):
            is_interactive_pb = True
            brm = target_pb.buttonsResponseMessage
            if brm.selectedButtonID:
                interactive_candidates.append(brm.selectedButtonID.strip())
            if brm.selectedDisplayText:
                interactive_candidates.append(brm.selectedDisplayText.strip())

        if target_pb.HasField('listResponseMessage'):
            is_interactive_pb = True
            lrm = target_pb.listResponseMessage
            if lrm.HasField('singleSelectReply') and lrm.singleSelectReply.selectedRowID:
                interactive_candidates.append(lrm.singleSelectReply.selectedRowID.strip())
            if lrm.title:
                interactive_candidates.append(lrm.title.strip())
            if lrm.description:
                interactive_candidates.append(lrm.description.strip())

        if target_pb.HasField('templateButtonReplyMessage'):
            is_interactive_pb = True
            tbrm = target_pb.templateButtonReplyMessage
            if tbrm.selectedID:
                interactive_candidates.append(tbrm.selectedID.strip())
            if tbrm.selectedDisplayText:
                interactive_candidates.append(tbrm.selectedDisplayText.strip())

        if is_interactive_pb:
            for cand in interactive_candidates:
                if cand.startswith(","):
                    return cand, (orig_msg or message), True
            for cand in interactive_candidates:
                c_low = cand.lower()
                c_clean = cand.lstrip(",").strip().lower()
                if c_low in active_choices_map:
                    return active_choices_map[c_low], (orig_msg or message), True
                if c_clean in active_choices_map:
                    return active_choices_map[c_clean], (orig_msg or message), True

        # 2. Cek apakah user mengetik angka/nama pilihan (misal "1", "2", "1. Blanc", atau "Blanc") setelah option muncul
        raw_txt = extract_text_from_message_pb(message.Message).strip()
        if not raw_txt:
            return "", None, False

        low_txt = raw_txt.lower()
        clean_key = raw_txt.lstrip(",").strip().lower()

        for lookup_key in [(chat_jid_str, clean_sender), (chat_jid_str, "*")]:
            pending = PENDING_SEARCH_CHOICES.get(lookup_key)
            if pending and (now - pending.get("timestamp", 0) <= 300):
                choices_map = pending.get("choices", {})
                saved_orig = pending.get("orig_message") or message
                if low_txt in choices_map:
                    return choices_map[low_txt], saved_orig, True
                if clean_key.isdigit() and clean_key in choices_map:
                    return choices_map[clean_key], saved_orig, True
                if not raw_txt.startswith(",") and clean_key in choices_map:
                    return choices_map[clean_key], saved_orig, True
    except Exception as e:
        logging.debug(f"Gagal memeriksa opsi interaktif: {e}")

    return "", None, False


def handle_item_search_command(client: NewClient, message: MessageEv, query: str, cmd_key: str = "item", cmd_label: str = "Item"):
    """Pencarian item dari database mandiri lokal (0 latency)"""
    query = query.strip()
    if not query:
        client.reply_message(f"Peringatan: Format salah. Gunakan `,{cmd_key} [nama]`", message)
        return

    try:
        force_exact = query.startswith("=")
        if force_exact:
            query = query[1:].strip()
        results = search_local_items(query, cmd_key)
        if not results:
            client.reply_message("Tidak ditemukan coba cari menggunakan bahasa inggris", message)
            return

        # Cek apakah ada exact match atau hanya ada 1 nama item unik (misal varian-varian dengan nama persis sama)
        q_lower = query.lower()
        search_terms = get_translation_search_terms(q_lower)
        results.sort(key=lambda x: (0 if any(x.get("name", "").strip().lower() == t for t in search_terms) else (1 if any(x.get("name", "").strip().lower().startswith(t) for t in search_terms) else 2), x.get("name", "").strip().lower()))
        unique_names_low = set(i.get("name", "").strip().lower() for i in results if i.get("name", "").strip())
        exact_matches = [i for i in results if any(i.get("name", "").strip().lower() == t for t in search_terms)] if (force_exact or len(unique_names_low) == 1) else []
        unique_names = set(i.get("name", "").strip() for i in results)

        if exact_matches:
            client.reply_message(format_item_detail(exact_matches[0]), message)
        elif len(unique_names) == 1 or len(results) == 1:
            client.reply_message(format_item_detail(results[0]), message)
        else:
            reply = f" *Hasil Pencarian {cmd_label}:*\n\n"
            seen_item_names = set()
            choice_options = []
            count = 0
            for item in results:
                name_str = item.get("name", "").strip()
                if name_str not in seen_item_names:
                    seen_item_names.add(name_str)
                    t_lbl = item.get('type_label', '').strip()
                    item_id = item.get('id')
                    target_cmd = f",{cmd_key} #{item_id}" if item_id else f",{cmd_key} ={name_str}"
                    bilingual_name = get_item_bilingual_name(name_str)
                    choice_options.append({
                        "label": f"{bilingual_name} {t_lbl}".strip()[:50],
                        "name": name_str,
                        "command": target_cmd
                    })
                    reply += f"{count + 1}. *{bilingual_name}* {t_lbl}\n"
                    count += 1
                    if count >= 10:
                        break
            if len(unique_names) > 10:
                reply += f"\n_...dan {len(unique_names) - 10} {cmd_label.lower()} lainnya._\n"
            reply += f"\nTips: Tap/klik salah satu opsi atau balas dengan angka `1`-{count}."
            poll_title = f"Pilih {cmd_label} untuk \"{query}\"\n(Tap/klik salah satu {cmd_label.lower()} di bawah):"
            send_interactive_choice_options(client, message, poll_title, choice_options, reply)
            return
            client.reply_message(reply, message)
    except Exception as e:
        client.reply_message(f"Gagal: Terjadi kesalahan saat mencari {cmd_label.lower()}. Detail: {e}", message)

def handle_arrow_command(client: NewClient, message: MessageEv, query: str):
    """Menangani command ,arrow untuk menampilkan daftar (non-event & event) dan detail panah Toram Online"""
    q = query.strip().lower()

    # 1. Bantuan / menu jika query kosong atau help
    if not q or q in ["help", "menu", "list", "info"]:
        help_text = (
            "*PANDUAN COMMAND ARROW TORAM ONLINE*\n\n"
            "Gunakan opsi berikut untuk melihat daftar atau info panah:\n"
            "- `,arrow nonevent` -> Daftar lengkap Arrow Non-Event (WATK, Monster & Lokasi)\n"
            "- `,arrow event` -> Daftar lengkap Arrow Event (WATK, Monster & Lokasi)\n"
            "- `,arrow [nama panah]` -> Detail stats, WATK & drop suatu panah (Contoh: `,arrow sakura` atau `,arrow stardust`)\n"
            "- `,arrow [elemen]` -> Filter panah berdasarkan elemen (Contoh: `,arrow fire`, `,arrow water`, `,arrow dark`, dll.)"
        )
        client.reply_message(help_text, message)
        return

    # 2. Permintaan daftar non-event
    if q in ["nonevent", "non-event", "non event", "normal"]:
        res = format_arrows_list(is_event=False)
        client.reply_message(res, message)
        return

    # 3. Permintaan daftar event
    if q in ["event", "limited"]:
        res = format_arrows_list(is_event=True)
        client.reply_message(res, message)
        return

    # 4. Filter elemen spesifik
    element_map = {
        "fire": "Fire", "api": "Fire",
        "water": "Water", "air": "Water",
        "wind": "Wind", "angin": "Wind",
        "earth": "Earth", "tanah": "Earth",
        "light": "Light", "cahaya": "Light",
        "dark": "Dark", "gelap": "Dark",
        "neutral": "Normal", "no element": "Normal"
    }
    if q in element_map:
        target_el = element_map[q]
        arrows = get_arrows_db()
        matching = [a for a in arrows if target_el.lower() in a.get("element", "").lower()]
        if matching:
            reply = f"*DAFTAR ARROW ELEMEN {target_el.upper()}*\n"
            reply += f"Total: {len(matching)} Arrow\n\n"
            for a in matching:
                ev_tag = f" [Event: {a['event_badge']}]" if a.get("is_event") else " [Non-Event]"
                dr = clean_arrow_drops(a.get("drops", []))
                dr_str = ", ".join(dr) if dr else "Craft Blacksmith"
                watk = a.get('atk', '-')
                reply += f"• *{a['name']}* (WATK: {watk}){ev_tag}\n  └ Drop: {dr_str}\n"
            reply += "\nTips: Ketik `,arrow [nama panah]` untuk melihat detail stats panah."
            client.reply_message(reply.strip(), message)
            return

    # 5. Pencarian nama arrow
    results = search_arrows(query)
    if not results:
        client.reply_message(f"Peringatan: Arrow '{query}' tidak ditemukan.\n\nTips:\n- Gunakan nama panah dalam bahasa Inggris (contoh: `,arrow sakura`)\n- Atau ketik `,arrow nonevent` / `,arrow event` untuk melihat daftar lengkap.", message)
        return

    # Jika hanya 1 hasil atau exact match
    if len(results) == 1 or results[0].get("name", "").lower() == q:
        client.reply_message(format_arrow_detail(results[0]), message)
        return

    # Jika ada beberapa hasil (maks 8 ditampilkan ringkas)
    reply = f"*Hasil Pencarian Arrow: '{query}'*\n\n"
    for a in results[:8]:
        ev_tag = f" [Event: {a['event_badge']}]" if a.get("is_event") else " [Non-Event]"
        dr = clean_arrow_drops(a.get("drops", []))
        dr_str = ", ".join(dr) if dr else "Craft Blacksmith"
        watk = a.get('atk', '-')
        disp_a = get_item_bilingual_name(a['name'])
        reply += f"• *{disp_a}* [{a.get('element', 'Normal')}] (WATK: {watk}){ev_tag}\n  └ Drop: {dr_str}\n"

    if len(results) > 8:
        reply += f"\n_...dan {len(results) - 8} arrow lainnya._\n"
    reply += "\nTips: Ketik `,arrow [nama lengkap]` untuk melihat detail stats lengkap."
    client.reply_message(reply.strip(), message)

def handle_monster_search_command(client: NewClient, message: MessageEv, query: str, cmd_key: str = "mob", cmd_label: str = "Monster", m_type_filter: str | None = None):
    """Pencarian monster/boss/miniboss dari database mandiri lokal (0 latency)"""
    query = query.strip()
    if not query:
        client.reply_message(f"Peringatan: Format salah. Gunakan `,{cmd_key} [nama]`", message)
        return

    try:
        results = search_local_monsters(query, m_type_filter)
        if not results:
            client.reply_message("Tidak ditemukan coba cari menggunakan bahasa inggris", message)
            return

        # Utamakan exact match pada nama monster (misal 'raffy' mengabaikan 'Hyper Raffy')
        exact_matches = [m for m in results if m.get("name", "").split(" (")[0].strip().lower() == query.lower()]
        target_list = exact_matches if exact_matches else results

        # Jika hasil merujuk ke 1 nama monster (semua variasi level/difficulty bernama sama),
        # langsung tampilkan gabungan variasi level/lokasi-nya dalam 1 pesan!
        base_names = set(r.get("name", "").split(" (")[0].strip() for r in target_list)
        if len(base_names) == 1:
            client.reply_message(format_monster_group_detail(target_list), message)
            return

        if len(target_list) == 1:
            client.reply_message(format_monster_detail(target_list[0]), message)
        else:
            reply = f" *Hasil Pencarian {cmd_label}:*\n\n"
            for mon in target_list[:10]:
                reply += f"- *{mon['name']}* (Lv {mon.get('level', '-')})\n"
            if len(target_list) > 10:
                reply += f"\n_...dan {len(target_list) - 10} {cmd_label.lower()} lainnya._\n"
            reply += f"\nTips: Ketik `,{cmd_key} [nama_spesifik]` untuk melihat detail spesifik."
            client.reply_message(reply, message)
    except Exception as e:
        client.reply_message(f"Gagal: Terjadi kesalahan saat mencari {cmd_label.lower()}. Detail: {e}", message)


def handle_crysta_route_command(client, message, query: str):
    """Mencari dan menampilkan rute upgrade untuk Crysta dari Database Lokal"""
    if not query:
        client.reply_message("Peringatan: Format salah. Gunakan `,rute [nama_crysta]`", message)
        return
        
    try:
        # Load database lokal upgrade
        upgrades_data = get_crysta_upgrades()
        if not upgrades_data:
            client.reply_message("Gagal: Database rute upgrade tidak ditemukan atau rusak. Silakan hubungi admin.", message)
            return

        curr_id = None
        target_name = ""

        if query.startswith("#"):
            item_id = query[1:].strip()
            if item_id in upgrades_data:
                curr_id = item_id
                target_name = upgrades_data[item_id]["name"]
        else:
            search_terms = get_translation_search_terms(query)
            matches = []
            for k, v in upgrades_data.items():
                v_name_lower = v["name"].lower()
                bilingual = get_item_bilingual_name(v["name"]).lower()
                if any(t in v_name_lower or t in bilingual for t in search_terms):
                    if not any(m[1].strip().lower() == v["name"].strip().lower() for m in matches):
                        matches.append((k, v["name"]))
            matches.sort(key=lambda x: (0 if any(x[1].strip().lower() == t for t in search_terms) else (1 if any(x[1].strip().lower().startswith(t) for t in search_terms) else 2), x[1].strip().lower()))
            
            if len(matches) == 1:
                curr_id = matches[0][0]
                target_name = matches[0][1]
            elif len(matches) > 1:
                reply = " *Hasil Pencarian Rute Crysta (Pilih salah satu):*\n\n"
                choice_options = []
                for idx_c, (cid, name) in enumerate(matches[:10], start=1):
                    bilingual = get_item_bilingual_name(name)
                    choice_options.append({
                        "label": f"{bilingual} [Rute]"[:50],
                        "name": name,
                        "command": f",rute #{cid}"
                    })
                    reply += f"{idx_c}. *{bilingual}*\n"
                if len(matches) > 10:
                    reply += f"\n_...dan {len(matches) - 10} lainnya._\n"
                reply += f"\nTips: Tap/klik salah satu opsi atau balas dengan angka `1`-{len(choice_options)}."
                poll_title = f"🔍 Pilih Rute Crysta untuk \"{query}\"\n(Tap/klik salah satu Crysta di bawah):"
                send_interactive_choice_options(client, message, poll_title, choice_options, reply)
                return

        if not curr_id:
            client.reply_message("Tidak ditemukan coba cari menggunakan bahasa inggris", message)
            return

        # Telusuri ke belakang (ke root)
        chain = []
        cid = curr_id
        visited = set()
        while cid:
            if cid in visited:
                break
            visited.add(cid)
            name = upgrades_data.get(cid, {}).get("name", f"Crysta #{cid}")
            chain.insert(0, (cid, name))
            parent_id = upgrades_data.get(cid, {}).get("upgrades_id")
            cid = str(parent_id) if parent_id else None

        # Base / Root ID adalah elemen pertama di chain
        base_id = chain[0][0]

        # Fungsi pembantu rekursif untuk mencari semua cabang upgrade ke depan
        def get_paths_forward(cid, visited):
            children = []
            for k, v in upgrades_data.items():
                if str(v.get("upgrades_id")) == cid and k not in visited:
                    children.append((k, v["name"]))
            
            if not children:
                return [[(cid, upgrades_data.get(cid, {}).get("name", "Unknown"))]]
                
            paths = []
            for child_id, child_name in children:
                child_paths = get_paths_forward(child_id, visited | {child_id})
                for path in child_paths:
                    paths.append([(cid, upgrades_data.get(cid, {}).get("name", "Unknown"))] + path)
            return paths

        # Dapatkan semua rute lengkap dari base_id
        all_routes = get_paths_forward(base_id, {base_id})

        # Format pesan balasan rute
        disp_target = get_item_bilingual_name(target_name)
        reply = "*RUTE UPGRADE CRYSTA*\n\n"
        reply += f"Menampilkan rute upgrade untuk *{disp_target}*:\n\n"
        
        if len(all_routes) == 1:
            for idx, (cid, name) in enumerate(all_routes[0]):
                marker = " (Target)" if cid == str(curr_id) else ""
                base_lbl = " (Base)" if idx == 0 else ""
                disp_cname = get_item_bilingual_name(name)
                reply += f"{idx + 1}. *{disp_cname}*{base_lbl}{marker}\n"
                if idx < len(all_routes[0]) - 1:
                    reply += "     ↓ (Upgrade)\n"
        else:
            for r_idx, route in enumerate(all_routes):
                reply += f"*Alternatif Rute {r_idx + 1}:*\n"
                for idx, (cid, name) in enumerate(route):
                    marker = " (Target)" if cid == str(curr_id) else ""
                    base_lbl = " (Base)" if idx == 0 else ""
                    disp_cname = get_item_bilingual_name(name)
                    reply += f"{idx + 1}. *{disp_cname}*{base_lbl}{marker}\n"
                    if idx < len(route) - 1:
                        reply += "     ↓ (Upgrade)\n"
                if r_idx < len(all_routes) - 1:
                    reply += "\n"

        client.reply_message(reply, message)
    except Exception as e:
        client.reply_message(f"Gagal: Terjadi kesalahan saat mencari rute upgrade. Detail: {e}", message)

def format_skill_detail(skill: dict) -> str:
    """Memformat data skill menjadi teks WhatsApp yang rapi"""
    name = skill.get("name", "Unknown")
    tree = skill.get("tree", "Unknown")
    lvl = skill.get("level_info", "")
    req = skill.get("weapon_req", "") or "Available with all weapons"
    stype = skill.get("type", "-")
    elem = skill.get("element", "-")
    mp = skill.get("mp", "-")
    c_start = skill.get("combo_start", "-")
    c_mid = skill.get("combo_middle", "-")
    srange = skill.get("range", "-")
    desc = skill.get("description", "Tidak ada deskripsi.")
    
    text = (
        f" *DETAIL SKILL: {name.upper()}*\n\n"
        f" *Skill Tree:* {tree} Skills" + (f" ({lvl})" if lvl else "") + f"\n"
        f"*Persyaratan:* {req}\n\n"
        f"- *Tipe:* {stype}\n"
        f"- *Elemen:* {elem}\n"
        f"- *MP:* {mp}\n"
        f"- *Combo:* Start: {c_start} | Middle: {c_mid}\n"
        f"- *Jangkauan (Range):* {srange}\n\n"
        f"*Deskripsi:*\n{desc}"
    )
    return text.strip()

def handle_skill_search_command(client, message, query: str):
    """Mencari dan menampilkan informasi detail tentang skill Toram Online"""
    if not query:
        client.reply_message("Peringatan: Format salah. Gunakan `,skill [nama_skill]`", message)
        return
        
    try:
        # Load database lokal skill
        skills_data = get_skills_db()
        if not skills_data:
            client.reply_message("Gagal: Database skill tidak ditemukan. Silakan hubungi admin.", message)
            return

        query_lower = query.strip().lower()
        matches = []
        for s in skills_data:
            if query_lower in s.get("name", "").lower():
                matches.append(s)
                
        if len(matches) == 0:
            client.reply_message("Tidak ditemukan coba cari menggunakan bahasa inggris", message)
        elif len(matches) == 1:
            reply = format_skill_detail(matches[0])
            client.reply_message(reply, message)
        else:
            # Cari apakah ada kecocokan yang persis sama (exact match)
            exact_match = None
            for s in matches:
                if s.get("name", "").lower() == query_lower:
                    exact_match = s
                    break
            
            if exact_match:
                reply = format_skill_detail(exact_match)
                client.reply_message(reply, message)
            else:
                # Tampilkan daftar kecocokan (maks 10)
                reply = " *Hasil Pencarian Skill:*\n\n"
                for s in matches[:10]:
                    reply += f"- *{s['name']}* [{s.get('tree', 'Unknown')}]\n"
                if len(matches) > 10:
                    reply += f"\n_...dan {len(matches) - 10} skill lainnya._\n"
                reply += "\nTips: Ketik `,skill [nama_spesifik]` untuk melihat detail skill secara spesifik."
                client.reply_message(reply, message)
                
    except Exception as e:
        client.reply_message(f"Gagal: Terjadi kesalahan saat mencari skill. Detail: {e}", message)

def format_registlet_detail(r: dict) -> str:
    """Memformat data registlet menjadi teks WhatsApp yang rapi"""
    reply = (
        f" *DETAIL REGISTLET* \n\n"
        f"- *Nama:* {r['name']}\n"
        f"- *Max Lvl:* {r['max_lv']}\n"
    )
    if r.get('affects'):
        reply += f"- *Mempengaruhi:* {r['affects']}\n"
    reply += (
        f"- *Efek:* {r['effect']}\n"
        f"- *Didapatkan Dari:* {r['obtained_from']}"
    )
    return reply

def handle_registlet_search_command(client, message, query: str):
    """Mencari dan menampilkan informasi detail tentang Registlet Toram Online"""
    if not query:
        client.reply_message("Peringatan: Format salah. Gunakan `,regis [nama_registlet]`", message)
        return
        
    try:
        registlets_data = get_registlets_db()
        if not registlets_data:
            client.reply_message("Gagal: Database registlet tidak ditemukan. Silakan hubungi admin.", message)
            return

        query_lower = query.strip().lower()
        matches = []
        for r in registlets_data:
            if query_lower in r.get("name", "").lower():
                matches.append(r)
                
        if len(matches) == 0:
            client.reply_message("Tidak ditemukan coba cari menggunakan bahasa inggris", message)
        elif len(matches) == 1:
            reply = format_registlet_detail(matches[0])
            client.reply_message(reply, message)
        else:
            # Cari apakah ada kecocokan yang persis sama (exact match)
            exact_match = None
            for r in matches:
                if r.get("name", "").lower() == query_lower:
                    exact_match = r
                    break
            
            if exact_match:
                reply = format_registlet_detail(exact_match)
                client.reply_message(reply, message)
            else:
                # Tampilkan daftar kecocokan (maks 10)
                reply = " *Hasil Pencarian Registlet:*\n\n"
                for r in matches[:10]:
                    aff_str = f" ({r['affects']})" if r.get('affects') else ""
                    reply += f"- *{r['name']}*{aff_str} - {r['max_lv']}\n"
                if len(matches) > 10:
                    reply += f"\n_...dan {len(matches) - 10} registlet lainnya._\n"
                reply += "\nTips: Ketik `,regis [nama_spesifik]` untuk melihat detail registlet secara spesifik."
                client.reply_message(reply, message)
                
    except Exception as e:
        client.reply_message(f"Gagal: Terjadi kesalahan saat mencari registlet. Detail: {e}", message)

def handle_lvling_command(client, message, query: str):
    """Mencari rekomendasi monster leveling (Boss & Mini Boss) sesuai level pengguna"""
    if not query:
        client.reply_message("Peringatan: Format salah. Gunakan `,lvling [level_karakter]` (contoh: `,lvling 150`)", message)
        return
        
    try:
        # Cari angka dalam query menggunakan regex
        lvl_match = re.search(r'\d+', query)
        if not lvl_match:
            client.reply_message("Gagal: Harap masukkan angka level yang valid. Contoh: `,lvling 150`", message)
            return
            
        user_lvl = int(lvl_match.group())
        if user_lvl < 1 or user_lvl > 1000:
            client.reply_message("Gagal: Level harus di antara 1 s/d 1000.", message)
            return

        # Load database lokal monster
        monsters_data = get_monsters_db()
        if not monsters_data:
            client.reply_message("Gagal: Database monster tidak ditemukan. Silakan hubungi admin.", message)
            return

        # Tentukan rentang level (mulai dari +/- 3)
        # Jika hasil sedikit, perluas ke +/- 5 lalu +/- 9
        ranges = [3, 5, 9]
        matches = []
        applied_range = 3
        
        for r in ranges:
            applied_range = r
            min_lvl = max(1, user_lvl - r)
            max_lvl = user_lvl + r
            
            matches = []
            for m in monsters_data:
                if m.get("level") is not None and min_lvl <= m["level"] <= max_lvl:
                    is_limited = m.get("limited", False)
                    name_lower = m.get("name", "").lower()
                    map_lower = m.get("map", "").lower()
                    if is_limited or "collab" in name_lower or "event" in name_lower or "collab" in map_lower or "event" in map_lower:
                        continue
                    matches.append(m)
            
            # Jika ditemukan minimal 5 monster, atau jika sudah mencapai jangkauan maksimal (+/- 9), stop
            if len(matches) >= 5 or r == 9:
                break

        if len(matches) == 0:
            client.reply_message(f"Gagal: Tidak ditemukan Boss atau Mini Boss untuk leveling di sekitar level {user_lvl}.", message)
            return

        # Pisahkan Boss dan Mini Boss
        bosses = []
        minibosses = []
        
        for m in matches:
            t = m.get("type", "")
            if t == "Boss":
                bosses.append(m)
            elif t == "Mini Boss":
                minibosses.append(m)

        # Urutkan berdasarkan level secara ascending
        bosses.sort(key=lambda x: x.get("level", 0))
        minibosses.sort(key=lambda x: x.get("level", 0))

        # Format pesan
        min_lvl = max(1, user_lvl - applied_range)
        max_lvl = user_lvl + applied_range
        
        reply = (
            f" *REKOMENDASI LEVELING: LVL {user_lvl}* \n"
            f"Rentang optimal EXP: Lv {min_lvl} s/d {max_lvl} (Jangkauan: ±{applied_range})\n"
            f"──────────────────────────\n\n"
        )

        if bosses:
            reply += "*BOSS* \n"
            for b in bosses:
                mode_str = f" ({b['mode']})" if b.get("mode") and b["mode"] != "Normal" else ""
                reply += f"• {b['name']}{mode_str} [Lv {b['level']}]\n"
            reply += "\n"

        if minibosses:
            reply += "*MINI BOSS* \n"
            for mb in minibosses:
                reply += f"• {mb['name']} [Lv {mb['level']}]\n"
            reply += "\n"

        reply += "Tips: *Tips:* Dapatkan EXP optimal dengan melawan monster dalam rentang level optimal."
        client.reply_message(reply.strip(), message)

    except Exception as e:
        client.reply_message(f"Gagal: Terjadi kesalahan saat memproses rekomendasi leveling. Detail: {e}", message)

@client.event(GroupInfoEv)
def on_group_info(client: NewClient, event: GroupInfoEv):
    group_jid = event.JID
    group_jid_str = f"{group_jid.User}@{group_jid.Server}"

    # Abaikan jika grup termasuk dalam daftar banned groups
    banned_groups = get_banned_groups()
    if group_jid_str in banned_groups or group_jid.User in banned_groups:
        return
    
    # Cek masa aktif sewa grup: jika grup belum aktif atau kedaluwarsa, abaikan event join/leave
    is_active, _, _ = check_group_subscription(group_jid_str)
    if not is_active:
        return
    
    # Cek jika ada anggota baru join
    if event.Join:
        # Bersihkan cache grup agar info anggota yang baru join terupdate di cache
        if group_jid_str in GROUP_CACHE:
            del GROUP_CACHE[group_jid_str]
            
        for index, user_jid in enumerate(event.Join):
            user_id = user_jid.User
            # Tag format di WhatsApp: @nomor
            caption_text = (
                f" * Yoo Halo @{user_id}!*\n\n"
                f"Welcome! Kami menghargai perbedaan bukan penyimpangan!!! \n\n"
                f"Intro dulu ga si :v\n"
                f"IGN :\n"
                f"Job :\n"
                f"Gender :\n"
                f"Ukuran sandal :"
            )
            
            try:
                bg_file = os.path.join(ASSETS_DIR, "kirito.jpg")
                if not os.path.exists(bg_file):
                    logging.warning(f"File {bg_file} tidak ditemukan, mengirim sambutan tanpa gambar.")
                    # Kirim pesan teks biasa jika gambar tidak ada
                    extended_text_msg = pb.Message(
                        extendedTextMessage=pb.ExtendedTextMessage(
                            text=caption_text,
                            contextInfo=pb.ContextInfo(
                                mentionedJID=[f"{user_jid.User}@{user_jid.Server}"]
                            )
                        )
                    )
                    client.send_message(group_jid, extended_text_msg)
                else:
                    # Bangun pesan gambar dengan caption
                    msg_to_send = client.build_image_message(
                        file=bg_file,
                        caption=caption_text
                    )
                    
                    # Masukkan JID ke mentionedJID agar ter-tag
                    jid_str = f"{user_jid.User}@{user_jid.Server}"
                    if jid_str not in msg_to_send.imageMessage.contextInfo.mentionedJID:
                        msg_to_send.imageMessage.contextInfo.mentionedJID.extend([jid_str])
                    
                    # Kirim ke grup
                    client.send_message(group_jid, msg_to_send)
                print(f"Sambutan sukses dikirim untuk @{user_id} di grup {group_jid_str}")
                
            except Exception as e:
                logging.error(f"Gagal mengirim sambutan untuk @{user_id}: {e}")
                
            # Jeda otomatis jika ada anggota lain dalam daftar join
            if index < len(event.Join) - 1:
                time.sleep(2.0)

    # Cek jika ada anggota yang keluar/dikeluarkan dari grup
    if event.Leave:
        # Bersihkan cache grup agar info anggota terupdate di cache
        if group_jid_str in GROUP_CACHE:
            del GROUP_CACHE[group_jid_str]
            
        for index, user_jid in enumerate(event.Leave):
            user_id = user_jid.User
            # Tag format di WhatsApp: @nomor
            caption_text = (
                f" *Selamat jalan @{user_id}!*\n\n"
                f"Semoga sampai di alam selanjutnya. "
            )
            
            try:
                bg_file = os.path.join(ASSETS_DIR, "kirito1.jpg")
                if not os.path.exists(bg_file):
                    logging.warning(f"File {bg_file} tidak ditemukan, mengirim ucapan selamat tinggal tanpa gambar.")
                    # Kirim pesan teks biasa jika gambar tidak ada
                    extended_text_msg = pb.Message(
                        extendedTextMessage=pb.ExtendedTextMessage(
                            text=caption_text,
                            contextInfo=pb.ContextInfo(
                                mentionedJID=[f"{user_jid.User}@{user_jid.Server}"]
                            )
                        )
                    )
                    client.send_message(group_jid, extended_text_msg)
                else:
                    # Bangun pesan gambar dengan caption
                    msg_to_send = client.build_image_message(
                        file=bg_file,
                        caption=caption_text
                    )
                    
                    # Masukkan JID ke mentionedJID agar ter-tag
                    jid_str = f"{user_jid.User}@{user_jid.Server}"
                    if jid_str not in msg_to_send.imageMessage.contextInfo.mentionedJID:
                        msg_to_send.imageMessage.contextInfo.mentionedJID.extend([jid_str])
                    
                    client.send_message(group_jid, msg_to_send)
                    print(f"Ucapan selamat tinggal sukses dikirim untuk @{user_id} di grup {group_jid_str}")
                
            except Exception as e:
                logging.error(f"Gagal mengirim ucapan selamat tinggal untuk @{user_id}: {e}")
                
            # Jeda otomatis jika ada anggota lain dalam daftar leave
            if index < len(event.Leave) - 1:
                time.sleep(2.0)

@client.event(ConnectedEv)
def on_connected(_: NewClient, __: ConnectedEv):
    print("\n" + "="*50)
    print(" Bot WhatsApp Berhasil Terhubung!")
    print("="*50 + "\n")

def fetch_toram_maintenance_info(query: str = "") -> str:
    """Mengambil informasi pemeliharaan/update terbaru dari situs resmi Toram Online (id.toram.jp)"""
    url = 'https://id.toram.jp/information/?type_code=maintenance'
    try:
        html = fetch_web_page(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        items = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            txt = a.get_text(separator=' ', strip=True)
            if 'information/detail' in href and txt and not txt.isdigit():
                full_url = href if href.startswith('http') else 'https:' + href if href.startswith('//') else 'https://id.toram.jp' + href
                m_date = re.search(r'(\d{4}-\d{2}-\d{2})', txt)
                date_str = m_date.group(1) if m_date else ''
                clean_title = re.sub(r'\d{4}-\d{2}-\d{2}', '', txt).strip()
                if clean_title and not any(x['url'] == full_url for x in items):
                    items.append({'date': date_str, 'title': clean_title, 'url': full_url})

        if not items:
            return "Gagal mengambil informasi pemeliharaan dari id.toram.jp"

        query_l = query.lower().strip()
        if query_l in ['list', 'daftar', 'menu', 'all']:
            reply = ["*DAFTAR UPDATE & PEMELIHARAAN TORAM ONLINE*\n"]
            for idx, it in enumerate(items[:6]):
                d_str = f"[{it['date']}] " if it.get('date') else ""
                reply.append(f"{idx+1}. {d_str}*{it['title']}*")
            reply.append("\nTips: Ketik `,mt` untuk melihat detail pemeliharaan terbaru.")
            return "\n".join(reply)

        mt_items = [i for i in items if any(k in i['title'].lower() for k in ['pemeliharaan', 'maintenance', 'update'])]
        target_item = mt_items[0] if mt_items else items[0]

        d_html = fetch_web_page(target_item['url'])
        d_soup = BeautifulSoup(d_html, 'html.parser')
        main_div = d_soup.find('div', class_=lambda c: c and ('use_icon' in c.lower() or 'detail' in c.lower() or 'news' in c.lower() or 'content' in c.lower()))
        if not main_div:
            main_div = d_soup.find('article') or d_soup.body

        lines = [l.strip() for l in main_div.get_text(separator='\n', strip=True).split('\n') if l.strip()]

        reply = []
        reply.append("*UPDATE / PEMELIHARAAN TORAM ONLINE*")
        reply.append(f"*{target_item['title']}*")
        if target_item.get('date'):
            reply.append(f"*Tanggal:* {target_item['date']}")
        reply.append("───────────────")

        capture = False
        for line in lines:
            l_lower = line.lower()
            if any(hdr in l_lower for hdr in ['waktu pemeliharaan', 'periode event', 'isi pemeliharaan', 'fitur berikut', 'isu berikut']):
                capture = True
                clean_hdr = line.replace(':', '').strip()
                reply.append(f"\n*{clean_hdr}:*")
                continue
            if capture:
                if any(stop in l_lower for stop in ['kembali ke atas', 'perhatian', 'mohon maklum']):
                    capture = False
                    continue
                if line.startswith('・') or line.startswith('-') or line.startswith('•'):
                    clean_l = re.sub(r'^[・\-•]\s*', '', line)
                    reply.append(f"- {clean_l}")
                elif not line.startswith('Silakan baca') and not line.startswith('"') and len(line) > 3:
                    reply.append(f"  {line}")

        reply.append("\n──────────────────")
        reply.append(f"*Sumber Resmi:* {target_item['url']}")
        return "\n".join(reply)
    except Exception as e:
        return f"Gagal mengambil data maintenance dari id.toram.jp: {e}"

def fetch_toram_boost_info(query: str = "") -> str:
    """Mengambil informasi boss/mini-boss boost terbaru dari situs resmi Toram Online (id.toram.jp)"""
    url = 'https://id.toram.jp/information/?type_code=event'
    try:
        html = fetch_web_page(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        items = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            txt = a.get_text(separator=' ', strip=True)
            if 'information/detail' in href and txt and not txt.isdigit():
                full_url = href if href.startswith('http') else 'https:' + href if href.startswith('//') else 'https://id.toram.jp' + href
                m_date = re.search(r'(\d{4}-\d{2}-\d{2})', txt)
                date_str = m_date.group(1) if m_date else ''
                clean_title = re.sub(r'\d{4}-\d{2}-\d{2}', '', txt).strip()
                if clean_title and not any(x['url'] == full_url for x in items):
                    items.append({'date': date_str, 'title': clean_title, 'url': full_url})

        if not items:
            return "Gagal mengambil informasi boost dari id.toram.jp"

        query_l = query.lower().strip()
        boost_items = [i for i in items if 'boost' in i['title'].lower()]
        
        if query_l in ['list', 'daftar', 'menu', 'all']:
            reply = ["*DAFTAR BOOST TORAM ONLINE*\n"]
            target_list = boost_items if boost_items else items
            for idx, it in enumerate(target_list[:6]):
                d_str = f"[{it['date']}] " if it.get('date') else ""
                reply.append(f"{idx+1}. {d_str}*{it['title']}*")
            reply.append("\nTips: Ketik `,boost` untuk melihat detail boss boost terbaru.")
            return "\n".join(reply)

        target_item = boost_items[0] if boost_items else items[0]

        d_html = fetch_web_page(target_item['url'])
        d_soup = BeautifulSoup(d_html, 'html.parser')
        main_div = d_soup.find('div', class_=lambda c: c and ('use_icon' in c.lower() or 'detail' in c.lower() or 'news' in c.lower() or 'content' in c.lower()))
        if not main_div:
            main_div = d_soup.find('article') or d_soup.body

        lines = [l.strip() for l in main_div.get_text(separator='\n', strip=True).split('\n') if l.strip()]

        reply = []
        reply.append("*BOOST TORAM ONLINE*")
        reply.append(f"*{target_item['title']}*")
        if target_item.get('date'):
            reply.append(f"*Tanggal:* {target_item['date']}")
        reply.append("───────────────")

        mobs = []
        periode_lines = []
        capture_mobs = False
        capture_periode = False

        for line in lines:
            l_lower = line.lower()
            if 'periode event' in l_lower or 'periode boost' in l_lower:
                capture_periode = True
                capture_mobs = False
                continue
            elif 'berlaku untuk bos berikut' in l_lower or 'berlaku untuk monster' in l_lower or 'bos monster' in l_lower:
                capture_mobs = True
                capture_periode = False
                continue
            elif any(stop in l_lower for stop in ['kembali ke atas', 'perhatian', 'mohon maklum']):
                capture_mobs = False
                capture_periode = False
                continue

            if capture_periode:
                if line.startswith('Mulai:') or line.startswith('Selesai:'):
                    periode_lines.append(f"- {line}")

            if capture_mobs:
                if line.startswith('Lv') or line.startswith('・') or line.startswith('-') or line.startswith('•'):
                    clean_m = re.sub(r'^[・\-•]\s*', '', line)
                    mobs.append(f"- {clean_m}")

        if periode_lines:
            reply.append("\n*Periode Boost:*")
            reply.extend(periode_lines)

        if mobs:
            reply.append("\n*Daftar Boss / Monster Boost:*")
            reply.extend(mobs)
        else:
            mob_pattern = [l for l in lines if l.startswith('Lv')]
            if mob_pattern:
                reply.append("\n*Daftar Boss / Monster Boost:*")
                for mp in mob_pattern:
                    reply.append(f"- {mp}")

        reply.append("\n──────────────────")
        reply.append(f"*Sumber Resmi:* {target_item['url']}")
        return "\n".join(reply)
    except Exception as e:
        return f"Gagal mengambil data boost dari id.toram.jp: {e}"

def extract_avatars_from_detail(detail_url: str) -> list:
    """Helper untuk mengambil daftar avatar dari halaman detail pengumuman Toram"""
    try:
        d_html = fetch_web_page(detail_url)
        d_soup = BeautifulSoup(d_html, 'html.parser')
        main_div = d_soup.find('div', class_=lambda c: c and ('use_icon' in c.lower() or 'detail' in c.lower() or 'news' in c.lower() or 'content' in c.lower()))
        if not main_div:
            main_div = d_soup.find('article') or d_soup.body

        avatar_results = []
        seen_urls = set()

        for img in main_div.find_all('img'):
            src = img.get('src', '')
            src_l = src.lower()

            # Pastikan hanya gambar avatar Toram, bukan banner atau item promo lainnya
            if 'toram_avatar' not in src_l and 'avatar' not in src_l:
                continue

            # Abaikan item non-avatar seperti special gem, lucky pack, orb, item banner, needle, dsb.
            if any(k in src_l for k in ['gem', 'pack', 'orb', 'item', 'banner', 'needle', 'piercer', 'booster', 'ticket', 'refine']):
                continue

            full_img_url = src if src.startswith('http') else 'https:' + src if src.startswith('//') else 'https://id.toram.jp' + src
            if full_img_url in seen_urls:
                continue
            seen_urls.add(full_img_url)

            title_txt = ''
            prev = img.find_previous(['h1', 'h2', 'h3', 'h4', 'div', 'p', 'b'])
            while prev:
                txt = prev.get_text(separator=' ', strip=True)
                m = re.search(r'"([^"]+)"', txt)
                if m and m.group(1) not in ['Open x11', 'Orb x15', 'Orb x20']:
                    candidate = m.group(1).replace('and more.', '').strip()
                    if not any(k in candidate.lower() for k in ['gem', 'pack', 'orb', 'item', 'needle', 'piercer', 'booster']):
                        title_txt = candidate
                        break
                elif any(k in txt.lower() for k in ['avatar chest', 'limited time offer']):
                    parts = re.split(r'for|:', txt, flags=re.IGNORECASE)
                    if len(parts) > 1:
                        candidate = parts[-1].replace('and more.', '').replace('"', '').strip()
                        if not any(k in candidate.lower() for k in ['gem', 'pack', 'orb', 'item', 'needle', 'piercer', 'booster']):
                            title_txt = candidate
                            break
                prev = prev.find_previous(['h1', 'h2', 'h3', 'h4', 'div', 'p', 'b'])

            if not title_txt:
                fn = src.split('/')[-1]
                title_txt = re.sub(r'toram_avatar_|\d{6,8}|\.png|\.jpg', '', fn, flags=re.IGNORECASE).replace('_', ' ').strip().title()

            # Pastikan nama avatar murni dan tidak membawa special gem, lucky pack, dsb.
            if any(bad in title_txt.lower() for bad in ['gem', 'special gem', 'lucky pack', 'pack', 'orb', 'needle', 'piercer', 'item']):
                continue

            avatar_results.append({'name': title_txt, 'image_url': full_img_url})

        return avatar_results
    except Exception as e:
        logging.error(f"Gagal extract avatar dari {detail_url}: {e}")
        return []

def fetch_toram_avatar_info(query: str = "") -> list:
    """Mengambil daftar gambar avatar dari pengumuman terbaru di situs resmi Toram Online (id.toram.jp)"""
    url = 'https://id.toram.jp/information/?type_code=shop'
    try:
        html = fetch_web_page(url)
        soup = BeautifulSoup(html, 'html.parser')
        
        items = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            txt = a.get_text(separator=' ', strip=True)
            if 'information/detail' in href and txt and not txt.isdigit():
                full_url = href if href.startswith('http') else 'https:' + href if href.startswith('//') else 'https://id.toram.jp' + href
                m_date = re.search(r'(\d{4}-\d{2}-\d{2})', txt)
                date_str = m_date.group(1) if m_date else ''
                clean_title = re.sub(r'\d{4}-\d{2}-\d{2}', '', txt).strip()
                if clean_title and not any(x['url'] == full_url for x in items):
                    items.append({'date': date_str, 'title': clean_title, 'url': full_url})

        if not items:
            return []

        query_l = query.strip().lower()

        # Jika query diberikan (misal: ,ava ninja atau ,ava ifrit)
        if query_l:
            # 1. Coba cari di pengumuman yang judulnya menyebut query
            for it in items:
                if query_l in it['title'].lower():
                    res = extract_avatars_from_detail(it['url'])
                    if res:
                        matched = [a for a in res if query_l in a['name'].lower()]
                        return matched if matched else res

            # 2. Coba periksa detail pengumuman terbaru
            for it in items[:8]:
                res = extract_avatars_from_detail(it['url'])
                matched = [a for a in res if query_l in a['name'].lower()]
                if matched:
                    return matched

        # Jika tanpa query (command standard ,ava):
        # Ambil selalu dari pengumuman TANGGAL TERBARU yang memiliki avatar!
        # items sudah terurut dari tanggal paling baru ke terlama
        for it in items[:10]:
            res = extract_avatars_from_detail(it['url'])
            if res:
                return res

        return []
    except Exception as e:
        logging.error(f"Gagal mendownload informasi avatar: {e}")
        return []

def handle_avatar_command(client: NewClient, message: MessageEv, query: str = ""):
    chat_jid = message.Info.MessageSource.Chat
    with typing_indicator(client, chat_jid):
        avatar_list = fetch_toram_avatar_info(query)
        if avatar_list:
            sent_count = 0

            for item in avatar_list:
                name = item.get("name", "Avatar Toram")
                image_url = item.get("image_url")
                if not image_url:
                    continue

                caption = f"*Avatar:* {name}"
                try:
                    img_bytes = fetch_fast_bytes(image_url, timeout=3.5)
                    msg_to_send = client.build_image_message(
                        file=img_bytes,
                        caption=caption,
                        quoted=message
                    )
                    client.send_message(chat_jid, msg_to_send)
                    sent_count += 1
                    time.sleep(1.0)
                except Exception as e:
                    logging.error(f"Gagal mengirim gambar avatar {name} ({image_url}): {e}")

            if sent_count > 0:
                return

        client.reply_message("Gagal mengambil data Avatar dari id.toram.jp", message)

# State limit penggunaan waifu (1x per user per hari reset jam 00:00 WIB)
waifu_usage_tracker = set()
waifu_used_characters = set()
waifu_used_images = set()
waifu_last_reset_date = None
WAIFU_LIMIT_FILE = os.path.join(DATA_DIR, "waifu_limit.json")
waifu_recent_animes = []

def load_waifu_tracker():
    global waifu_usage_tracker, waifu_last_reset_date, waifu_used_characters, waifu_used_images
    try:
        if os.path.exists(WAIFU_LIMIT_FILE):
            with open(WAIFU_LIMIT_FILE, "r") as f:
                data = json.load(f)
                waifu_last_reset_date = data.get("date", "")
                waifu_usage_tracker = set(data.get("users", []))
                waifu_used_characters = set(data.get("used_characters", []))
                waifu_used_images = set(data.get("used_images", []))
    except Exception as e:
        logging.error(f"Gagal memuat limit waifu: {e}")

def save_waifu_tracker():
    try:
        with open(WAIFU_LIMIT_FILE, "w") as f:
            json.dump({
                "date": waifu_last_reset_date,
                "users": list(waifu_usage_tracker),
                "used_characters": list(waifu_used_characters),
                "used_images": list(waifu_used_images)
            }, f)
    except Exception as e:
        logging.error(f"Gagal menyimpan limit waifu: {e}")

def check_and_reset_waifu_limit():
    global waifu_last_reset_date
    current_date_wib = (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d")
    
    if waifu_last_reset_date != current_date_wib:
        waifu_usage_tracker.clear()
        waifu_used_characters.clear()
        waifu_used_images.clear()
        waifu_last_reset_date = current_date_wib
        save_waifu_tracker()
        print(f" Limit waifu direset untuk hari baru: {current_date_wib}")

# Jalankan load saat modul di-import
load_waifu_tracker()


def format_source_url(source: str, post_id: str, site="safebooru") -> str:
    """Format the source URL, converting Pixiv images/IDs into valid Pixiv artwork links."""
    if not source:
        if site == "safebooru":
            return f"https://safebooru.org/index.php?page=post&s=view&id={post_id}"
        return ""
    
    source = source.strip()
    
    # 1. Jika source hanya berupa angka (Pixiv ID)
    if source.isdigit():
        return f"https://www.pixiv.net/artworks/{source}"
        
    # 1b. Jika source adalah link X / Twitter (twitter.com / x.com), rapikan menjadi link tweet x.com resmi
    if any(k in source.lower() for k in ["twitter.com", "x.com", "twimg.com"]):
        tw_match = re.search(r'(?:twitter\.com|x\.com)/([^/\s]+)/status/(\d+)', source, re.IGNORECASE)
        if tw_match:
            return f"https://x.com/{tw_match.group(1)}/status/{tw_match.group(2)}"
        tw_id_match = re.search(r'/status/(\d+)', source, re.IGNORECASE)
        if tw_id_match:
            return f"https://x.com/i/web/status/{tw_id_match.group(1)}"
        if "twimg.com" in source.lower() and post_id:
            if site == "danbooru":
                return f"https://danbooru.donmai.us/posts/{post_id}"
            return f"https://safebooru.org/index.php?page=post&s=view&id={post_id}"

    # 1c. Jika source adalah link Pinterest
    if "pinterest." in source.lower() or "pin.it" in source.lower() or "pinimg.com" in source.lower():
        pin_match = re.search(r'pinterest\.[a-z.]+/pin/(\d+)', source, re.IGNORECASE)
        if pin_match:
            return f"https://www.pinterest.com/pin/{pin_match.group(1)}/"
        if source.startswith("http"):
            return source

    # 2. Jika mengandung kata kunci Pixiv/pximg, ekstrak ID-nya (6-11 digit)
    if any(k in source for k in ["pixiv", "pximg", "illust_id"]):
        match = re.search(r'(\d{6,11})', source)
        if match:
            return f"https://www.pixiv.net/artworks/{match.group(1)}"
            
    # 3. Jika bukan URL valid, kembalikan URL default Booru
    if not source.startswith("http"):
        if site == "safebooru":
            return f"https://safebooru.org/index.php?page=post&s=view&id={post_id}"
            
    return source


safebooru_waifu_tags = [
    "sword_art_online", "one_piece", "naruto", "boruto", "black_clover", "bleach", "fairy_tail",
    "boku_no_hero_academia", "kimetsu_no_yaiba", "jujutsu_kaisen", "fate/stay_night", "fate/grand_order",
    "genshin_impact", "honkai:_star_rail", "blue_archive", "kono_subarashii_sekai_ni_shukufuku_wo!",
    "re:zero_kara_hajimeru_isekai_seikatsu", "spy_x_family", "chainsaw_man", "sousou_no_frieren",
    "vocaloid", "touhou"
]

safebooru_husbu_tags = [
    "sword_art_online", "one_piece", "naruto", "boruto", "black_clover", "bleach", "fairy_tail",
    "boku_no_hero_academia", "kimetsu_no_yaiba", "jujutsu_kaisen", "fate/stay_night", "fate/grand_order",
    "genshin_impact", "honkai:_star_rail", "kono_subarashii_sekai_ni_shukufuku_wo!",
    "re:zero_kara_hajimeru_isekai_seikatsu", "chainsaw_man", "sousou_no_frieren"
]

famous_anime_whitelist = [
    "sword_art_online", "sao", "naruto", "boruto", "bleach", "one_piece", "black_clover",
    "shingeki_no_kyojin", "attack_on_titan", "shokugeki_no_soma", "food_wars", "fairy_tail",
    "boku_no_hero_academia", "my_hero_academia", "demon_slayer", "kimetsu_no_yaiba",
    "jujutsu_kaisen", "death_note", "konosuba", "re:zero", "re_zero", "fate_stay_night",
    "fate_grand_order", "fgo", "genshin_impact", "chainsaw_man", "spy_x_family", "kaguya_sama",
    "overlord", "darling_in_the_franxx", "shield_hero", "no_game_no_life", "high_school_dxd",
    "violet_evergarden", "tokyo_ghoul", "one_punch_man", "dragon_ball", "evangelion",
    "gurren_lagann", "kill_la_kill", "clannad", "future_diary", "mirai_nikki",
    "classroom_of_the_elite", "touhou", "vocaloid", "star_rail", "honkai", "blue_archive",
    "azur_lane", "nikke", "dress-up_darling", "oshi_no_ko", "frieren", "apothecary_diaries",
    "mushoku_tensei", "date_a_live", "go-toubun_no_hanayome", "quintessential_quintuplets",
    "k-on", "k_on", "haruhi_suzumiya", "lucky_star", "toradora", "anohana", "angel_beats",
    "code_geass", "fullmetal_alchemist", "fma", "steins;gate", "steins_gate", "hunter_x_hunter",
    "hxh", "nanatsu_no_taizai", "seven_deadly_sins", "bakemonogatari", "monogatari",
    "love_live", "idolmaster", "bang_dream", "danganronpa", "lycoris_recoil", "cyberpunk"
]

safebooru_waifu_tags = [
    "sword_art_online", "one_piece", "naruto", "boruto", "black_clover", "bleach", "fairy_tail",
    "boku_no_hero_academia", "kimetsu_no_yaiba", "jujutsu_kaisen", "fate/stay_night", "fate/grand_order",
    "genshin_impact", "honkai:_star_rail", "blue_archive", "kono_subarashii_sekai_ni_shukufuku_wo!",
    "re:zero_kara_hajimeru_isekai_seikatsu", "spy_x_family", "chainsaw_man", "sousou_no_frieren",
    "vocaloid", "touhou"
]

safebooru_husbu_tags = [
    "sword_art_online", "one_piece", "naruto", "boruto", "black_clover", "bleach", "fairy_tail",
    "boku_no_hero_academia", "kimetsu_no_yaiba", "jujutsu_kaisen", "fate/stay_night", "fate/grand_order",
    "genshin_impact", "honkai:_star_rail", "kono_subarashii_sekai_ni_shukufuku_wo!",
    "re:zero_kara_hajimeru_isekai_seikatsu", "chainsaw_man", "sousou_no_frieren"
]

PINTEREST_WAIFU_CHARACTERS = [
    ("Asuna Yuuki", "Sword Art Online"), ("Frieren", "Sousou no Frieren"), ("Fern", "Sousou no Frieren"),
    ("Marin Kitagawa", "My Dress-Up Darling"), ("Yor Forger", "Spy x Family"), ("Rem", "Re:Zero"),
    ("Emilia", "Re:Zero"), ("Violet Evergarden", "Violet Evergarden"), ("Ai Hoshino", "Oshi no Ko"),
    ("Ruby Hoshino", "Oshi no Ko"), ("Kana Arima", "Oshi no Ko"), ("Akane Kurokawa", "Oshi no Ko"),
    ("Kurumi Tokisaki", "Date A Live"), ("Raiden Shogun", "Genshin Impact"), ("Furina", "Genshin Impact"),
    ("Hu Tao", "Genshin Impact"), ("Kamisato Ayaka", "Genshin Impact"), ("Navia", "Genshin Impact"),
    ("Firefly", "Honkai: Star Rail"), ("Kafka", "Honkai: Star Rail"), ("Acheron", "Honkai: Star Rail"),
    ("March 7th", "Honkai: Star Rail"), ("Megumin", "KonoSuba"), ("Aqua", "KonoSuba"),
    ("Artoria Pendragon", "Fate/stay night"), ("Rin Tohsaka", "Fate/stay night"), ("Mikasa Ackerman", "Attack on Titan"),
    ("Nezuko Kamado", "Kimetsu no Yaiba"), ("Shinobu Kocho", "Kimetsu no Yaiba"), ("Mitsuri Kanroji", "Kimetsu no Yaiba"),
    ("Hinata Hyuga", "Naruto"), ("Boa Hancock", "One Piece"), ("Nami", "One Piece"), ("Nico Robin", "One Piece"),
    ("Maomao", "The Apothecary Diaries"), ("Chisato Nishikigi", "Lycoris Recoil"), ("Takina Inoue", "Lycoris Recoil"),
    ("Zero Two", "Darling in the Franxx"), ("Kaguya Shinomiya", "Kaguya-sama: Love is War"),
    ("Chika Fujiwara", "Kaguya-sama: Love is War"), ("Mai Sakurajima", "Rascal Does Not Dream"),
    ("Miku Nakano", "The Quintessential Quintuplets"), ("Nino Nakano", "The Quintessential Quintuplets")
]

PINTEREST_HUSBU_CHARACTERS = [
    ("Gojo Satoru", "Jujutsu Kaisen"), ("Levi Ackerman", "Attack on Titan"), ("Roronoa Zoro", "One Piece"),
    ("Sanji", "One Piece"), ("Trafalgar Law", "One Piece"), ("Portgas D. Ace", "One Piece"),
    ("Uchiha Sasuke", "Naruto"), ("Uchiha Itachi", "Naruto"), ("Hatake Kakashi", "Naruto"),
    ("Minato Namikaze", "Naruto"), ("Kamado Tanjiro", "Kimetsu no Yaiba"), ("Tomioka Giyuu", "Kimetsu no Yaiba"),
    ("Rengoku Kyoujurou", "Kimetsu no Yaiba"), ("Muichiro Tokito", "Kimetsu no Yaiba"),
    ("Megumi Fushiguro", "Jujutsu Kaisen"), ("Nanami Kento", "Jujutsu Kaisen"), ("Inumaki Toge", "Jujutsu Kaisen"),
    ("Yuta Okkotsu", "Jujutsu Kaisen"), ("Zhongli", "Genshin Impact"), ("Neuvillette", "Genshin Impact"),
    ("Alhaitham", "Genshin Impact"), ("Childe Tartaglia", "Genshin Impact"), ("Kamisato Ayato", "Genshin Impact"),
    ("Xiao", "Genshin Impact"), ("Dan Heng", "Honkai: Star Rail"), ("Aventurine", "Honkai: Star Rail"),
    ("Blade", "Honkai: Star Rail"), ("Jing Yuan", "Honkai: Star Rail"), ("Sunday", "Honkai: Star Rail"),
    ("Kirito", "Sword Art Online"), ("Eugeo", "Sword Art Online"), ("Loid Forger", "Spy x Family"),
    ("Stark", "Sousou no Frieren"), ("Himmel", "Sousou no Frieren"), ("Aki Hayakawa", "Chainsaw Man"),
    ("Killua Zoldyck", "Hunter x Hunter"), ("Kurapika", "Hunter x Hunter"), ("Ichigo Kurosaki", "Bleach"),
    ("Hitsugaya Toshiro", "Bleach"), ("Byakuya Kuchiki", "Bleach"), ("Jinshi", "The Apothecary Diaries"),
    ("Aqua Hoshino", "Oshi no Ko")
]


import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def fetch_fast_json(url: str, headers: dict | None = None, timeout: float = 2.5) -> any:
    """Mengambil JSON secara cepat tanpa loop mirror proxy."""
    req_headers = DEFAULT_BROWSER_HEADERS.copy()
    if headers:
        req_headers.update(headers)
    req_headers["Accept"] = "application/json, text/plain, */*"
    try:
        r = requests.get(url, headers=req_headers, timeout=timeout, verify=False)
        if r.status_code == 200 and r.text:
            return r.json()
    except Exception:
        pass
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return json.loads(resp.read().decode('utf-8', errors='ignore'))
    except Exception:
        pass
    return None


def fetch_fast_bytes(url: str, headers: dict | None = None, timeout: float = 3.5) -> bytes:
    """Mengunduh binary gambar secara langsung tanpa loop mirror proxy HTML."""
    req_headers = DEFAULT_BROWSER_HEADERS.copy()
    if headers:
        req_headers.update(headers)
    req_headers["Accept"] = "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"
    try:
        r = requests.get(url, headers=req_headers, timeout=timeout, verify=False)
        if r.status_code == 200 and r.content and len(r.content) > 1000:
            return r.content
    except Exception:
        pass
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            data = resp.read()
            if data and len(data) > 1000:
                return data
    except Exception:
        pass
    return None


def fetch_fast_anime_image(is_husbu: bool = False) -> tuple:
    """Fallback instan berkecepatan tinggi (<1 detik) menggunakan Nekos.best / Waifu.pics CDN"""
    used_chars = husbu_used_characters if is_husbu else waifu_used_characters
    used_imgs = husbu_used_images if is_husbu else waifu_used_images

    endpoint = "https://nekos.best/api/v2/husbando?amount=20" if is_husbu else "https://nekos.best/api/v2/waifu?amount=20"
    try:
        data = fetch_fast_json(endpoint, timeout=2.5)
        if data and isinstance(data, dict) and data.get("results"):
            item = random.choice(data["results"])
            img_url = item.get("url")
            artist_name = item.get("artist_name") or ("Husbando" if is_husbu else "Waifu")
            source_url = item.get("source_url") or img_url
            if img_url and img_url not in used_imgs:
                img_bytes = fetch_fast_bytes(img_url, timeout=3.5)
                if img_bytes and len(img_bytes) > 2000:
                    used_imgs.add(img_url)
                    if is_husbu:
                        save_husbu_tracker()
                    else:
                        save_waifu_tracker()
                    return img_bytes, artist_name, source_url
    except Exception:
        pass

    endpoint2 = "https://nekos.best/api/v2/husbando" if is_husbu else "https://api.waifu.pics/sfw/waifu"
    try:
        data2 = fetch_fast_json(endpoint2, timeout=2.5)
        if data2 and isinstance(data2, dict) and data2.get("url"):
            img_url = data2["url"]
            if img_url not in used_imgs:
                img_bytes = fetch_fast_bytes(img_url, timeout=3.5)
                if img_bytes and len(img_bytes) > 2000:
                    used_imgs.add(img_url)
                    if is_husbu:
                        save_husbu_tracker()
                    else:
                        save_waifu_tracker()
                    return img_bytes, "Waifu", img_url
    except Exception:
        pass

    return None


def fetch_pinterest_character_image(is_husbu: bool = False) -> tuple:
    """Mengambil gambar karakter waifu/husbu dari Pinterest beserta URL pin aslinya."""
    char_pool = list(PINTEREST_HUSBU_CHARACTERS if is_husbu else PINTEREST_WAIFU_CHARACTERS)
    used_chars = husbu_used_characters if is_husbu else waifu_used_characters
    used_imgs = husbu_used_images if is_husbu else waifu_used_images

    available = [c for c in char_pool if f"{c[0]} ({c[1]})".lower() not in used_chars]
    if not available:
        available = char_pool
    random.shuffle(available)

    for char_name, anime_name in available[:1]:
        full_name = f"{char_name} ({anime_name})"
        query = urllib.parse.quote(f"{char_name} {anime_name} anime art illustration")
        pin_apis = [
            f"https://api.siputzx.my.id/api/s/pinterest?query={query}",
            f"https://api.ryzendesu.vip/api/search/pinterest?q={query}",
            f"https://api.agatz.xyz/api/pinsearch?message={query}",
        ]
        for api_url in pin_apis:
            try:
                data = fetch_fast_json(api_url, timeout=2.0)
                pass
                items = data.get("data") if isinstance(data, dict) else data
                if not isinstance(items, list) or not items:
                    continue
                random.shuffle(items)
                for item in items[:8]:
                    if isinstance(item, str) and item.startswith("http"):
                        img_url = item
                        pin_url = f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(char_name + ' ' + anime_name)}"
                    elif isinstance(item, dict):
                        img_url = (
                            item.get("images_url")
                            or item.get("image")
                            or item.get("directLink")
                            or item.get("url")
                            or ""
                        )
                        raw_pin = (
                            item.get("pin")
                            or item.get("link")
                            or item.get("pin_url")
                            or item.get("source")
                            or ""
                        )
                        pin_id = item.get("id") or ""
                        if isinstance(raw_pin, str) and "pinterest." in raw_pin:
                            pin_url = format_source_url(raw_pin, str(pin_id), "pinterest")
                        elif pin_id and str(pin_id).isdigit():
                            pin_url = f"https://www.pinterest.com/pin/{pin_id}/"
                        else:
                            pin_url = f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(char_name + ' ' + anime_name)}"
                    else:
                        continue

                    if not img_url or not img_url.startswith("http") or img_url in used_imgs:
                        continue
                    try:
                        img_bytes = fetch_fast_bytes(img_url, timeout=3.5)
                        if img_bytes and len(img_bytes) > 5000:
                            used_chars.add(full_name.lower())
                            used_imgs.add(img_url)
                            if is_husbu:
                                save_husbu_tracker()
                            else:
                                save_waifu_tracker()
                            return img_bytes, full_name, pin_url
                    except Exception:
                        continue
            except Exception:
                continue
    return None


def fetch_x_danbooru_character_image(is_husbu: bool = False, famous_whitelist: list = None) -> tuple:
    """Mengambil gambar waifu/husbu dari Danbooru yang memiliki source X/Twitter (x.com) atau Pixiv."""
    used_chars = husbu_used_characters if is_husbu else waifu_used_characters
    used_imgs = husbu_used_images if is_husbu else waifu_used_images
    gender_tag = "1boy" if is_husbu else "1girl"
    tag_pool = safebooru_husbu_tags if is_husbu else safebooru_waifu_tags

    try:
        chosen_tag = random.choice(tag_pool)
        api_url = f"https://danbooru.donmai.us/posts.json?tags={gender_tag}+solo+rating:g+{chosen_tag}&page={random.randint(1, 10)}&limit=30"
        posts = fetch_fast_json(api_url, timeout=2.5)
        pass
        if not isinstance(posts, list) or not posts:
            return None

        random.shuffle(posts)
        # Prioritaskan post yang memiliki source dari X / Twitter (x.com / twitter.com) atau Pinterest
        posts.sort(
            key=lambda p: 0
            if any(k in str(p.get("source", "")).lower() for k in ["twitter.com", "x.com", "pinterest."])
            else (1 if "pixiv" in str(p.get("source", "")).lower() or "pximg" in str(p.get("source", "")).lower() else 2)
        )

        for post in posts:
            char_str = (post.get("tag_string_character") or "").strip()
            copy_str = (post.get("tag_string_copyright") or "").strip()
            general_str = (post.get("tag_string_general") or "").lower()
            if not char_str or not copy_str:
                continue
            if is_husbu and any(f in general_str.split() for f in ["1girl", "2girls", "female", "girl", "skirt", "dress", "breasts"]):
                continue
            if "ai_generated" in general_str:
                continue

            first_char = char_str.split()[0]
            first_char_clean = re.sub(r'_\([^)]+\)$', '', first_char).replace('_', ' ').title()
            first_copy = copy_str.split()[0].replace('_', ' ').title()
            full_name = f"{first_char_clean} ({first_copy})"

            if full_name.lower() in used_chars:
                continue

            img_url = post.get("large_file_url") or post.get("file_url") or ""
            if not img_url or not img_url.startswith("http") or img_url in used_imgs:
                continue
            if not any(img_url.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                continue

            raw_source = (post.get("source") or "").strip()
            source_url = format_source_url(raw_source, str(post.get("id", "")), "danbooru")
            if not source_url:
                source_url = f"https://danbooru.donmai.us/posts/{post.get('id')}"

            try:
                img_bytes = fetch_fast_bytes(img_url, timeout=3.5)
                if img_bytes and len(img_bytes) > 5000:
                    used_chars.add(full_name.lower())
                    used_imgs.add(img_url)
                    if is_husbu:
                        save_husbu_tracker()
                    else:
                        save_waifu_tracker()
                    return img_bytes, full_name, source_url
            except Exception:
                continue
    except Exception as e:
        logging.error(f"Gagal mengambil gambar dari Danbooru/X: {e}")
    return None


def fetch_waifu_image() -> tuple:
    """Mengambil gambar waifu acak dari Safebooru/Pixiv beserta nama dan URL sumber aslinya (hanya karakter bernama, dari anime terkenal, dan bergantian anime)"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    ai_indicators = {
        "ai_generated", "novelai", "stable_diffusion",
        "midjourney", "artbreeder", "dall-e",
        "artificial_image", "artificial_images"
    }

    # Rotasi sumber gambar Waifu: Pinterest, X/Twitter (Danbooru), dan Safebooru/Pixiv
    source_roll = random.random()
    if source_roll < 0.35:
        pin_res = fetch_pinterest_character_image(is_husbu=False)
        if pin_res:
            return pin_res
        x_res = fetch_x_danbooru_character_image(is_husbu=False)
        if x_res:
            return x_res
        pass
        pass
        pass
        if pin_res:
            return pin_res
    elif source_roll < 0.70:
        x_res = fetch_x_danbooru_character_image(is_husbu=False)
        if x_res:
            return x_res

    # Daftar whitelist anime terkenal untuk menyaring waifu yang dikirim
    famous_anime_whitelist = [
        "sword_art_online", "sao", "naruto", "boruto", "bleach", "one_piece", "black_clover",
        "shingeki_no_kyojin", "attack_on_titan", "shokugeki_no_soma", "food_wars", "fairy_tail",
        "boku_no_hero_academia", "my_hero_academia", "demon_slayer", "kimetsu_no_yaiba",
        "jujutsu_kaisen", "death_note", "konosuba", "re:zero", "re_zero", "fate_stay_night",
        "fate_grand_order", "fgo", "genshin_impact", "chainsaw_man", "spy_x_family", "kaguya_sama",
        "overlord", "darling_in_the_franxx", "shield_hero", "no_game_no_life", "high_school_dxd",
        "violet_evergarden", "tokyo_ghoul", "one_punch_man", "dragon_ball", "evangelion",
        "gurren_lagann", "kill_la_kill", "clannad", "future_diary", "mirai_nikki",
        "classroom_of_the_elite", "touhou", "vocaloid", "star_rail", "honkai", "blue_archive",
        "azur_lane", "nikke", "dress-up_darling", "oshi_no_ko", "frieren", "apothecary_diaries",
        "mushoku_tensei", "date_a_live", "go-toubun_no_hanayome", "quintessential_quintuplets",
        "k-on", "k_on", "haruhi_suzumiya", "lucky_star", "toradora", "anohana", "angel_beats",
        "code_geass", "fullmetal_alchemist", "fma", "steins;gate", "steins_gate", "hunter_x_hunter",
        "hxh", "nanatsu_no_taizai", "seven_deadly_sins", "bakemonogatari", "monogatari",
        "love_live", "idolmaster", "bang_dream", "danganronpa", "lycoris_recoil", "cyberpunk"
    ]

    # Sumber 1: Safebooru + Pixiv (Hanya karakter bernama, dari anime terkenal, dan berbeda dari yang sebelumnya)
    try:
        posts = []
        if random.random() < 0.7:
            chosen_tag = random.choice(safebooru_waifu_tags)
            api_url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags=1girl+solo+rating:safe+highres+absurdres+-ai_generated+-novelai+-stable_diffusion+-midjourney+-dall-e+-artbreeder+-artificial_images+{chosen_tag}&pid={random.randint(0, 40)}&limit=30"
            try:
                data = fetch_fast_json(api_url, timeout=2.0)
                posts = data if isinstance(data, list) else []
            except Exception as e:
                logging.error(f"Gagal pencarian tag {chosen_tag}: {e}")
        
        if not posts:
            api_url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags=1girl+solo+rating:safe+highres+absurdres+-ai_generated+-novelai+-stable_diffusion+-midjourney+-dall-e+-artbreeder+-artificial_images+-western+-cartoon+-disney+-my_little_pony+-utdr+-toby_fox+-undertale+-deltarune&pid={random.randint(0, 80)}&limit=30"
            try:
                data = fetch_fast_json(api_url, timeout=2.0)
                posts = data if isinstance(data, list) else []
            except Exception as e:
                logging.error(f"Gagal pencarian fallback waifu: {e}")

        if posts and isinstance(posts, list):
            random.shuffle(posts)
            posts.sort(
                key=lambda p: 0
                if any(k in str(p.get("source", "")).lower() for k in ["twitter.com", "x.com", "pinterest."])
                else (1 if any(k in str(p.get("source", "")).lower() for k in ["pixiv", "pximg"]) or str(p.get("source", "")).strip().isdigit() else 2)
            )
                
        if posts:
            for strict in [True, False]:
                posts.sort(key=lambda p: 0 if any(k in str(p.get("source", "")).lower() for k in ["twitter.com", "x.com", "pinterest."]) else (1 if any(k in str(p.get("source", "")).lower() for k in ["pixiv", "pximg"]) or str(p.get("source", "")).strip().isdigit() else 2))
                skipped_due_to_recent = []
                
                for post in posts:
                    tags = post.get("tags", "")
                    tags_list = tags.lower().split()
                    
                    ai_indicators = {
                        "ai_generated", "novelai", "stable_diffusion", 
                        "midjourney", "artbreeder", "dall-e", 
                        "artificial_image", "artificial_images"
                    }
                    if any(t in ai_indicators for t in tags_list):
                        continue
                    char_match = re.search(r'\b([a-zA-Z0-9_]+)_\(([a-zA-Z0-9_:]+)\)', tags)
                    if not char_match:
                        continue
                    
                    anime_tag = char_match.group(2).lower()
                    
                    is_famous = False
                    for famous_name in famous_anime_whitelist:
                        if famous_name in anime_tag or anime_tag in famous_name:
                            is_famous = True
                            break
                            
                    if not is_famous:
                        continue
                    
                    char_name = char_match.group(1).replace('_', ' ').title()
                    anime_name = char_match.group(2).replace('_', ' ').title()
                    waifu_name = f"{char_name} ({anime_name})"
                    
                    raw_source = post.get("source", "").strip()
                    source_url = format_source_url(raw_source, post.get("id"), "safebooru")
                    
                    if post.get("sample") and post.get("sample_url"):
                        image_url = post.get("sample_url").replace('\\/', '/')
                    else:
                        image_url = f"https://safebooru.org/images/{post['directory']}/{post['image']}"
                    
                    if image_url in waifu_used_images or (strict and waifu_name.lower() in waifu_used_characters):
                        continue
                        
                    if anime_tag in waifu_recent_animes:
                        skipped_due_to_recent.append((post, waifu_name, source_url, image_url, anime_tag))
                        continue
                        
                    try:
                        img_bytes = fetch_fast_bytes(image_url, timeout=3.5)
                        waifu_recent_animes.append(anime_tag)
                        if len(waifu_recent_animes) > 10:
                            waifu_recent_animes.pop(0)
                        waifu_used_characters.add(waifu_name.lower())
                        waifu_used_images.add(image_url)
                        save_waifu_tracker()
                        return img_bytes, waifu_name, source_url
                    except Exception as pe:
                        logging.error(f"Gagal mendownload gambar dari {image_url}: {pe}")
                        
                if skipped_due_to_recent:
                    for post, waifu_name, source_url, image_url, anime_tag in skipped_due_to_recent:
                        try:
                            img_bytes = fetch_fast_bytes(image_url, timeout=3.5)
                            waifu_recent_animes.append(anime_tag)
                            if len(waifu_recent_animes) > 10:
                                waifu_recent_animes.pop(0)
                            waifu_used_characters.add(waifu_name.lower())
                            waifu_used_images.add(image_url)
                            save_waifu_tracker()
                            return img_bytes, waifu_name, source_url
                        except Exception as pe:
                            logging.error(f"Gagal mendownload gambar fallback dari {image_url}: {pe}")

            for post in posts:
                tags = post.get("tags", "")
                tags_list = tags.lower().split()
                if any(t in ai_indicators for t in tags_list):
                    continue
                char_match = re.search(r'\b([a-zA-Z0-9_]+)_\(([a-zA-Z0-9_:]+)\)', tags)
                if not char_match:
                    continue
                char_name = char_match.group(1).replace('_', ' ').title()
                anime_name = char_match.group(2).replace('_', ' ').title()
                waifu_name = f"{char_name} ({anime_name})"
                raw_source = post.get("source", "").strip()
                source_url = format_source_url(raw_source, post.get("id"), "safebooru")
                if post.get("sample") and post.get("sample_url"):
                    image_url = post.get("sample_url").replace('\\/', '/')
                else:
                    image_url = f"https://safebooru.org/images/{post['directory']}/{post['image']}"
                try:
                    img_bytes = fetch_fast_bytes(image_url, timeout=3.5)
                    waifu_used_characters.add(waifu_name.lower())
                    waifu_used_images.add(image_url)
                    save_waifu_tracker()
                    return img_bytes, waifu_name, source_url
                except Exception:
                    continue
    except Exception as e:
        logging.error(f"Gagal mengambil gambar dari Safebooru/Pixiv: {e}")

    try:
        fallback_url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags=1girl+solo+rating:safe+highres+-ai_generated&pid={random.randint(0, 100)}&limit=30"
        posts = fetch_fast_json(fallback_url, timeout=2.5)
        # fast fallback
        pass
        if posts:
            random.shuffle(posts)
            for post in posts:
                tags = post.get("tags", "")
                char_match = re.search(r'\b([a-zA-Z0-9_]+)_\(([a-zA-Z0-9_:]+)\)', tags)
                if not char_match:
                    continue
                char_name = char_match.group(1).replace('_', ' ').title()
                anime_name = char_match.group(2).replace('_', ' ').title()
                waifu_name = f"{char_name} ({anime_name})"
                raw_source = post.get("source", "").strip()
                source_url = format_source_url(raw_source, post.get("id"), "safebooru")
                if post.get("sample") and post.get("sample_url"):
                    image_url = post.get("sample_url").replace('\\/', '/')
                else:
                    image_url = f"https://safebooru.org/images/{post['directory']}/{post['image']}"
                try:
                    img_bytes = fetch_fast_bytes(image_url, timeout=3.5)
                    waifu_used_characters.add(waifu_name.lower())
                    waifu_used_images.add(image_url)
                    save_waifu_tracker()
                    return img_bytes, waifu_name, source_url
                except Exception:
                    continue
    except Exception as fe:
        logging.error(f"Gagal mengambil fallback waifu Safebooru: {fe}")

    fast_res = fetch_fast_anime_image(is_husbu=False)
    if fast_res:
        return fast_res
    raise Exception("Semua server penyedia gambar waifu sedang tidak dapat dihubungi.")


# State limit penggunaan husbu (1x per user per hari reset jam 00:00 WIB)
husbu_usage_tracker = set()
husbu_used_characters = set()
husbu_used_images = set()
husbu_last_reset_date = None
HUSBU_LIMIT_FILE = os.path.join(DATA_DIR, "husbu_limit.json")
husbu_recent_animes = []

def load_husbu_tracker():
    global husbu_usage_tracker, husbu_last_reset_date, husbu_used_characters, husbu_used_images
    try:
        if os.path.exists(HUSBU_LIMIT_FILE):
            with open(HUSBU_LIMIT_FILE, "r") as f:
                data = json.load(f)
                husbu_last_reset_date = data.get("date", "")
                husbu_usage_tracker = set(data.get("users", []))
                husbu_used_characters = set(data.get("used_characters", []))
                husbu_used_images = set(data.get("used_images", []))
    except Exception as e:
        logging.error(f"Gagal memuat limit husbu: {e}")

def save_husbu_tracker():
    try:
        with open(HUSBU_LIMIT_FILE, "w") as f:
            json.dump({
                "date": husbu_last_reset_date,
                "users": list(husbu_usage_tracker),
                "used_characters": list(husbu_used_characters),
                "used_images": list(husbu_used_images)
            }, f)
    except Exception as e:
        logging.error(f"Gagal menyimpan limit husbu: {e}")

def check_and_reset_husbu_limit():
    global husbu_last_reset_date
    current_date_wib = (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d")
    
    if husbu_last_reset_date != current_date_wib:
        husbu_usage_tracker.clear()
        husbu_used_characters.clear()
        husbu_used_images.clear()
        husbu_last_reset_date = current_date_wib
        save_husbu_tracker()
        print(f" Limit husbu direset untuk hari baru: {current_date_wib}")

# Jalankan load saat modul di-import
load_husbu_tracker()


def fetch_husbu_image() -> tuple:
    """Mengambil gambar husbu acak dari Safebooru/Pixiv beserta nama dan URL sumber aslinya (hanya karakter bernama, dari anime terkenal, dan bergantian anime)"""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    female_or_ai_indicators = {
        "ai_generated", "novelai", "stable_diffusion",
        "midjourney", "artbreeder", "dall-e",
        "artificial_image", "artificial_images",
        "1girl", "2girls", "3girls", "multiple_girls", "female"
    }

    # Rotasi sumber gambar Husbu: Pinterest, X/Twitter (Danbooru), dan Safebooru/Pixiv
    source_roll = random.random()
    if source_roll < 0.35:
        pin_res = fetch_pinterest_character_image(is_husbu=True)
        if pin_res:
            return pin_res
        x_res = fetch_x_danbooru_character_image(is_husbu=True)
        if x_res:
            return x_res
        pass
        pass
        pass
        if pin_res:
            return pin_res
    elif source_roll < 0.70:
        x_res = fetch_x_danbooru_character_image(is_husbu=True)
        if x_res:
            return x_res

    # Daftar whitelist anime terkenal untuk menyaring husbu yang dikirim
    famous_anime_whitelist = [
        "sword_art_online", "sao", "naruto", "boruto", "bleach", "one_piece", "black_clover",
        "shingeki_no_kyojin", "attack_on_titan", "shokugeki_no_soma", "food_wars", "fairy_tail",
        "boku_no_hero_academia", "my_hero_academia", "demon_slayer", "kimetsu_no_yaiba",
        "jujutsu_kaisen", "death_note", "konosuba", "re:zero", "re_zero", "fate_stay_night",
        "fate_grand_order", "fgo", "genshin_impact", "chainsaw_man", "spy_x_family", "kaguya_sama",
        "overlord", "darling_in_the_franxx", "shield_hero", "no_game_no_life", "high_school_dxd",
        "violet_evergarden", "tokyo_ghoul", "one_punch_man", "dragon_ball", "evangelion",
        "gurren_lagann", "kill_la_kill", "clannad", "future_diary", "mirai_nikki",
        "classroom_of_the_elite", "touhou", "vocaloid", "star_rail", "honkai", "blue_archive",
        "azur_lane", "nikke", "dress-up_darling", "oshi_no_ko", "frieren", "apothecary_diaries",
        "mushoku_tensei", "date_a_live", "go-toubun_no_hanayome", "quintessential_quintuplets",
        "k-on", "k_on", "haruhi_suzumiya", "lucky_star", "toradora", "anohana", "angel_beats",
        "code_geass", "fullmetal_alchemist", "fma", "steins;gate", "steins_gate", "hunter_x_hunter",
        "hxh", "nanatsu_no_taizai", "seven_deadly_sins", "bakemonogatari", "monogatari",
        "love_live", "idolmaster", "bang_dream", "danganronpa", "lycoris_recoil", "cyberpunk"
    ]

    # Sumber 1: Safebooru + Pixiv (Hanya karakter bernama, dari anime terkenal, dan berbeda dari yang sebelumnya)
    try:
        posts = []
        if random.random() < 0.7:
            chosen_tag = random.choice(safebooru_husbu_tags)
            api_url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags=1boy+solo+rating:safe+highres+absurdres+-1girl+-female+-breasts+-skirt+-dress+-bikini+-panties+-thighhighs+-cleavage+-ai_generated+-novelai+-stable_diffusion+-midjourney+-dall-e+-artbreeder+-artificial_images+{chosen_tag}&pid={random.randint(0, 40)}&limit=30"
            try:
                data = fetch_fast_json(api_url, timeout=2.0)
                posts = data if isinstance(data, list) else []
            except Exception as e:
                logging.error(f"Gagal pencarian tag husbu {chosen_tag}: {e}")
        
        if not posts:
            api_url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags=1boy+solo+rating:safe+highres+absurdres+-1girl+-female+-breasts+-skirt+-dress+-bikini+-panties+-thighhighs+-cleavage+-ai_generated+-novelai+-stable_diffusion+-midjourney+-dall-e+-artbreeder+-artificial_images+-western+-cartoon+-disney+-my_little_pony+-utdr+-toby_fox+-automated+-undertale+-deltarune&pid={random.randint(0, 80)}&limit=30"
            try:
                data = fetch_fast_json(api_url, timeout=2.0)
                posts = data if isinstance(data, list) else []
            except Exception as e:
                logging.error(f"Gagal pencarian fallback husbu: {e}")

        if posts and isinstance(posts, list):
            random.shuffle(posts)
            posts.sort(
                key=lambda p: 0
                if any(k in str(p.get("source", "")).lower() for k in ["twitter.com", "x.com", "pinterest."])
                else (1 if any(k in str(p.get("source", "")).lower() for k in ["pixiv", "pximg"]) or str(p.get("source", "")).strip().isdigit() else 2)
            )
                
        if posts:
            for strict in [True, False]:
                posts.sort(key=lambda p: 0 if any(k in str(p.get("source", "")).lower() for k in ["twitter.com", "x.com", "pinterest."]) else (1 if any(k in str(p.get("source", "")).lower() for k in ["pixiv", "pximg"]) or str(p.get("source", "")).strip().isdigit() else 2))
                skipped_due_to_recent = []
                
                for post in posts:
                    tags = post.get("tags", "")
                    tags_list = tags.lower().split()
                    
                    female_or_ai_indicators = {
                        "1girl", "female", "girl", "breasts", "skirt", 
                        "bra", "bikini", "panties", "cleavage", "dress",
                        "tomboy", "maid", "miko", "magical_girl", "genderbend",
                        "gender_swapped", "crossdressing",
                        "ai_generated", "novelai", "stable_diffusion", 
                        "midjourney", "artbreeder", "dall-e", 
                        "artificial_image", "artificial_images"
                    }
                    if any(t in female_or_ai_indicators for t in tags_list):
                        continue
                        
                    char_match = re.search(r'\b([a-zA-Z0-9_]+)_\(([a-zA-Z0-9_:]+)\)', tags)
                    if not char_match:
                        continue
                    
                    anime_tag = char_match.group(2).lower()
                    
                    is_famous = False
                    for famous_name in famous_anime_whitelist:
                        if famous_name in anime_tag or anime_tag in famous_name:
                            is_famous = True
                            break
                            
                    if not is_famous:
                        continue
                    
                    char_name = char_match.group(1).replace('_', ' ').title()
                    anime_name = char_match.group(2).replace('_', ' ').title()
                    husbu_name = f"{char_name} ({anime_name})"
                    
                    raw_source = post.get("source", "").strip()
                    source_url = format_source_url(raw_source, post.get("id"), "safebooru")
                    
                    if post.get("sample") and post.get("sample_url"):
                        image_url = post.get("sample_url").replace('\\/', '/')
                    else:
                        image_url = f"https://safebooru.org/images/{post['directory']}/{post['image']}"
                    
                    if image_url in husbu_used_images or (strict and husbu_name.lower() in husbu_used_characters):
                        continue
                        
                    if anime_tag in husbu_recent_animes:
                        skipped_due_to_recent.append((post, husbu_name, source_url, image_url, anime_tag))
                        continue
                        
                    try:
                        img_bytes = fetch_fast_bytes(image_url, timeout=3.5)
                        husbu_recent_animes.append(anime_tag)
                        if len(husbu_recent_animes) > 10:
                            husbu_recent_animes.pop(0)
                        husbu_used_characters.add(husbu_name.lower())
                        husbu_used_images.add(image_url)
                        save_husbu_tracker()
                        return img_bytes, husbu_name, source_url
                    except Exception as pe:
                        logging.error(f"Gagal mendownload gambar dari {image_url}: {pe}")
                        
                if skipped_due_to_recent:
                    for post, husbu_name, source_url, image_url, anime_tag in skipped_due_to_recent:
                        try:
                            img_bytes = fetch_fast_bytes(image_url, timeout=3.5)
                            husbu_recent_animes.append(anime_tag)
                            if len(husbu_recent_animes) > 10:
                                husbu_recent_animes.pop(0)
                            husbu_used_characters.add(husbu_name.lower())
                            husbu_used_images.add(image_url)
                            save_husbu_tracker()
                            return img_bytes, husbu_name, source_url
                        except Exception as pe:
                            logging.error(f"Gagal mendownload gambar fallback dari {image_url}: {pe}")

            for post in posts:
                tags = post.get("tags", "")
                tags_list = tags.lower().split()
                if any(t in female_or_ai_indicators for t in tags_list):
                    continue
                char_match = re.search(r'\b([a-zA-Z0-9_]+)_\(([a-zA-Z0-9_:]+)\)', tags)
                if not char_match:
                    continue
                char_name = char_match.group(1).replace('_', ' ').title()
                anime_name = char_match.group(2).replace('_', ' ').title()
                husbu_name = f"{char_name} ({anime_name})"
                raw_source = post.get("source", "").strip()
                source_url = format_source_url(raw_source, post.get("id"), "safebooru")
                if post.get("sample") and post.get("sample_url"):
                    image_url = post.get("sample_url").replace('\\/', '/')
                else:
                    image_url = f"https://safebooru.org/images/{post['directory']}/{post['image']}"
                try:
                    img_bytes = fetch_fast_bytes(image_url, timeout=3.5)
                    husbu_used_characters.add(husbu_name.lower())
                    husbu_used_images.add(image_url)
                    save_husbu_tracker()
                    return img_bytes, husbu_name, source_url
                except Exception:
                    continue
    except Exception as e:
        logging.error(f"Gagal mengambil gambar dari Safebooru/Pixiv: {e}")

    try:
        fallback_url = f"https://safebooru.org/index.php?page=dapi&s=post&q=index&json=1&tags=1boy+solo+rating:safe+highres+-ai_generated&pid={random.randint(0, 100)}&limit=30"
        posts = fetch_fast_json(fallback_url, timeout=2.5)
        # fast fallback
        pass
        if posts:
            random.shuffle(posts)
            for post in posts:
                tags = post.get("tags", "")
                char_match = re.search(r'\b([a-zA-Z0-9_]+)_\(([a-zA-Z0-9_:]+)\)', tags)
                if not char_match:
                    continue
                char_name = char_match.group(1).replace('_', ' ').title()
                anime_name = char_match.group(2).replace('_', ' ').title()
                husbu_name = f"{char_name} ({anime_name})"
                raw_source = post.get("source", "").strip()
                source_url = format_source_url(raw_source, post.get("id"), "safebooru")
                if post.get("sample") and post.get("sample_url"):
                    image_url = post.get("sample_url").replace('\\/', '/')
                else:
                    image_url = f"https://safebooru.org/images/{post['directory']}/{post['image']}"
                try:
                    img_bytes = fetch_fast_bytes(image_url, timeout=3.5)
                    husbu_used_characters.add(husbu_name.lower())
                    husbu_used_images.add(image_url)
                    save_husbu_tracker()
                    return img_bytes, husbu_name, source_url
                except Exception:
                    continue
    except Exception as fe:
        logging.error(f"Gagal mengambil fallback husbu Safebooru: {fe}")

    fast_res = fetch_fast_anime_image(is_husbu=True)
    if fast_res:
        return fast_res
    raise Exception("Semua server penyedia gambar husbu sedang tidak dapat dihubungi.")



@client.event(ConnectedEv)
def on_connected(client: NewClient, event: ConnectedEv):
    print(" Bot berhasil terhubung ke WhatsApp!")
    try:
        client.send_presence(Presence.AVAILABLE)
    except Exception as e:
        logging.debug(f"Gagal mengirim status presence saat connected: {e}")

@client.event(MessageEv)
def on_message(client: NewClient, message: MessageEv):
    # Ekstrak waktu pesan dan abaikan pesan lampau yang dikirim saat bot sedang mati / offline
    msg_ts = 0.0
    if hasattr(message.Info, 'Timestamp') and message.Info.Timestamp:
        raw_ts = message.Info.Timestamp
        if hasattr(raw_ts, 'seconds'):
            msg_ts = float(raw_ts.seconds)
        elif isinstance(raw_ts, (int, float)):
            msg_ts = float(raw_ts)
            if msg_ts > 1e11:
                msg_ts = msg_ts / 1000.0

    # Jika pesan dikirim sebelum bot aktif (saat bot mati) atau usia pesan terlalu lama (> 120 detik saat bot baru hidup)
    if msg_ts > 0 and (msg_ts < (BOT_START_TIME - 5) or (time.time() - msg_ts > 120 and time.time() - BOT_START_TIME < 60)):
        return

    # Simpan pesan grup ke cache riwayat pesan untuk mendukung fitur multi-media / 2 gambar pada command ,a
    cache_group_message(message)

    # Ekstrak teks pesan
    is_interactive_choice = False
    resolved_cmd, resolved_orig_msg, is_poll_tap = resolve_interactive_or_poll_command(client, message)
    if is_poll_tap and resolved_cmd:
        msg_text = resolved_cmd.strip()
        is_interactive_choice = True
        if resolved_orig_msg is not None:
            message = resolved_orig_msg
    else:
        msg_text = extract_text(message).strip()
    
    # Lewati jika pesan kosong (misal: hanya kirim stiker/gambar tanpa caption)
    if not msg_text:
        return

    # Ambil pengirim dan nama chat
    chat_jid = message.Info.MessageSource.Chat
    chat_jid_str = f"{chat_jid.User}@{chat_jid.Server}"
    sender_name = message.Info.Pushname or "Teman"
    is_group = message.Info.MessageSource.IsGroup or chat_jid.Server == "g.us" or chat_jid_str.endswith("@g.us")
    is_from_me = message.Info.MessageSource.IsFromMe

    # Ambil identitas pengirim (nomor telepon / LID)
    sender_user = ""
    if message.Info.MessageSource.Sender and message.Info.MessageSource.Sender.User:
        sender_user = message.Info.MessageSource.Sender.User
    elif message.Info.MessageSource.Chat and message.Info.MessageSource.Chat.User:
        sender_user = message.Info.MessageSource.Chat.User

    clean_sender = sender_user.split('.')[0].split(':')[0].split('@')[0]
    owner_set = get_owner_numbers()
    is_owner = is_from_me or (clean_sender in owner_set) or (sender_user in owner_set)

    # Parsing perintah
    lower_text = msg_text.lower()

    # Cek apakah pengirim mengirim pesan dari dirinya sendiri (akun bot)
    # Hindari loop, kecuali jika bot/owner sendiri mengetik command khusus
    if is_from_me and not is_interactive_choice:
        if not (lower_text.startswith(",set") or lower_text in [",id", ",jid", ",cekbot", ",ceksewa", ",sewa", ",statussewa", ",clearcache", ",resethistory", ",hapushistory"]):
            return

    # Nonaktifkan fitur umum jika melalui personal chat (hanya aktif di grup, kecuali Owner untuk administrasi)
    if not is_group:
        if not is_owner:
            return
        # Jika owner di personal chat, hanya boleh command administrasi (,set, ,id, ,ceksewa, ,clearcache)
        if not (lower_text.startswith(",set") or lower_text in [",id", ",jid", ",cekbot", ",ceksewa", ",sewa", ",statussewa", ",clearcache", ",resethistory", ",hapushistory"]):
            return

    # Perintah untuk melihat ID grup / chat ini
    if lower_text in [",id", ",jid"]:
        send_reply_or_message(client, f"*ID Chat ini:*\n`{chat_jid_str}`", message)
        return

    # Command manual untuk membersihkan riwayat cache chat (KHUSUS OWNER)
    if lower_text in [",clearcache", ",resethistory", ",hapushistory"]:
        if not is_owner:
            send_reply_or_message(client, "Perintah `,clearcache` hanya dapat digunakan oleh Akun Bot / Owner.", message)
            return
        if clear_chat_history_cache():
            send_reply_or_message(client, "Berhasil menghapus seluruh riwayat cache pesan grup.", message)
        else:
            send_reply_or_message(client, "Gagal menghapus riwayat cache pesan grup.", message)
        return

    # Cek pembatasan grup (banned groups): abaikan semua perintah jika grup ini dibatasi
    banned_groups = get_banned_groups()
    if chat_jid_str in banned_groups or chat_jid.User in banned_groups:
        return

    # Command pengaturan masa aktif grup (KHUSUS BOT SENDIRI / OWNER)
    if lower_text == ",set" or lower_text.startswith(",set "):
        if not is_owner:
            send_reply_or_message(
                client, 
                f"Perintah `,set` hanya dapat digunakan oleh Akun Bot / Owner.\n(ID Pengirim Anda: `{clean_sender}`)", 
                message
            )
            return
        args = msg_text[len(",set"):].strip()
        handle_set_subscription(client, message, args, chat_jid_str)
        return

    # Command cek masa aktif sewa grup
    if any(lower_text == p or lower_text.startswith(p + " ") for p in [",cekbot", ",ceksewa", ",sewa", ",statussewa"]):
        prefix = next((p for p in [",cekbot", ",ceksewa", ",statussewa", ",sewa"] if lower_text.startswith(p)), ",cekbot")
        args = msg_text[len(prefix):].strip()
        handle_ceksewa_command(client, message, chat_jid_str, args)
        return

    # Cek masa aktif sewa grup (Kunci utama: Fitur bot hanya aktif per-grup):
    is_active, exp_str, remaining = check_group_subscription(chat_jid_str)
    if not is_active:
        # Jika grup belum aktif / masa aktif habis, fitur bot TIDAK BISA digunakan oleh siapa pun di grup ini
        if msg_text.startswith(","):
            now_ts = time.time()
            last_warn = SUBSCRIPTION_COOLDOWN.get(chat_jid_str, 0)
            if now_ts - last_warn > 15:
                SUBSCRIPTION_COOLDOWN[chat_jid_str] = now_ts
                if is_owner:
                    client.reply_message(
                        f"*Pemberitahuan Owner*: Bot di grup ini belum aktif atau masa aktif telah habis ({remaining}).\n"
                        f"Perintah fitur umum dinonaktifkan di grup ini. Gunakan `,set [jumlah] hari` jika ingin mengaktifkan bot di grup ini.",
                        message
                    )
                else:
                    client.reply_message(
                        "Masa aktif bot di grup ini belum diaktifkan atau telah habis.\n"
                        "Jika ingin mengaktifkan bot, silakan hubungi Owner untuk menyelesaikan sewa dan kirimkan ID grup ini.\n\n"
                        f"• ID Grup: `{chat_jid_str}`\n\nThanks :*",
                        message
                    )
        return

    # Cek apakah pesan merupakan jawaban tebakan permainan interaktif di grup ini
    if is_group and games.check_game_answer(client, message, chat_jid_str, clean_sender, sender_name, msg_text):
        return

    # Respon jika memanggil ditdut
    if "ditdut" in lower_text:
        client.reply_message("Ada yang bisa aku bantu? Silakan gunakan command *,menu* untuk melihat semua command yang tersedia.", message)
        return

    # Hanya log ke terminal jika pesan berupa perintah (diawali dengan ",")
    if msg_text.startswith(","):
        loc_info = f"grup [{chat_jid_str}]" if is_group else f"private [{chat_jid_str}]"
        print(f" Perintah dari '{sender_name}' di {loc_info}: {msg_text}")

    if lower_text == ",ping":
        client.reply_message(PING_TEXT, message)
        
    elif lower_text in [",help", ",menu"]:
        send_image_reply(client, message, DSGIRL_IMAGE_PATH, get_menu_text(sender_name))
        
    elif lower_text == ",about":
        send_image_reply(client, message, DSGIRL_IMAGE_PATH, ABOUT_TEXT)
        
    elif lower_text in [",family100", ",f100"]:
        games.start_family100(client, message, chat_jid_str)

    elif lower_text in [",susunkata", ",tebakkata"]:
        games.start_susun_kata(client, message, chat_jid_str)

    elif lower_text in [",kuistoram", ",tebaktoram"]:
        games.start_kuis_toram(client, message, chat_jid_str)

    elif lower_text in [",nyerah", ",stopgame", ",surrender"]:
        games.handle_surrender(client, message, chat_jid_str)

    elif lower_text in [",skor", ",topskor", ",leaderboard"]:
        client.reply_message(games.get_group_leaderboard(chat_jid_str), message)

    elif (
        lower_text == ",resetskor" or lower_text.startswith(",resetskor ") 
        or lower_text == ",resetleaderboard" or lower_text.startswith(",resetleaderboard ")
        or lower_text == ",resetpoin" or lower_text.startswith(",resetpoin ")
        or lower_text == ",resetscore" or lower_text.startswith(",resetscore ")
    ):
        if is_group:
            group_data = get_group_members_info(client, chat_jid)
            admins_list = group_data.get('admins', [])
        else:
            admins_list = []
        is_admin = sender_user in admins_list or clean_sender in admins_list or is_owner
        if not is_admin:
            client.reply_message("Peringatan: Perintah `,resetskor` hanya dapat digunakan oleh Admin Grup atau Owner Bot.", message)
        else:
            args = msg_text.split()
            reset_all = is_owner and len(args) > 1 and args[1].lower() == "all"
            games.reset_group_leaderboard(chat_jid_str, reset_all=reset_all)
            if reset_all:
                client.reply_message("Berhasil mereset seluruh leaderboard game di semua grup (Oleh Owner).", message)
            else:
                client.reply_message("Berhasil mereset skor game di grup ini. Papan klasemen telah kembali ke 0.", message)

    elif lower_text in [",game", ",games", ",permainan"]:
        game_help = (
            "🎮 *GAME INTERAKTIF BOT TORAM*\n\n"
            "Ayo bermain bareng anggota grup! Pilih salah satu permainan berikut:\n\n"
            "• *,f100* (atau *,family100*)\n"
            "  └ Game survei Family 100 seru dengan banyak jawaban.\n\n"
            "• *,kuistoram*\n"
            "  └ Kuis seru seputar boss, crysta, dan dunia Toram Online.\n\n"
            "• *,susunkata*\n"
            "  └ Asah otak menyusun huruf-huruf acak menjadi kata.\n\n"
            "• *,nyerah*\n"
            "  └ Menyerah dan membuka seluruh kunci jawaban sesi aktif.\n\n"
            "• *,skor*\n"
            "  └ Melihat klasemen peringkat poin pemain di grup ini.\n\n"
            "• *,resetskor*\n"
            "  └ Mereset klasemen poin game di grup ini (Khusus Admin/Owner).\n\n"
            "💡 *Catatan:* Sesi permainan di grup ini bersifat mandiri dan tidak mengganggu grup lain!"
        )
        client.reply_message(game_help, message)

    elif lower_text == ",quote":
        client.reply_message(QUOTE_TEXT, message)
        
    elif lower_text == ",waifu":
        # Jalankan pengecekan reset limit harian
        check_and_reset_waifu_limit()
        
        # Ambil JID pengirim secara unik
        if message.Info.MessageSource.Sender and message.Info.MessageSource.Sender.User:
            sender_user = message.Info.MessageSource.Sender.User
            sender_server = message.Info.MessageSource.Sender.Server
        else:
            sender_user = message.Info.MessageSource.Chat.User
            sender_server = message.Info.MessageSource.Chat.Server
            
        sender_jid_str = f"{sender_user}@{sender_server}"
        clean_sender = sender_user.split('.')[0].split(':')[0].split('@')[0]
        is_unlimited_user = clean_sender in ["6287828697399", "087828697399", "205479875735664"]
        
        print(f"DEBUG ,waifu: sender_user={sender_user}, clean_sender={clean_sender}, is_unlimited={is_unlimited_user}")
        
        # Jika sudah menggunakan hari ini, abaikan
        if sender_jid_str in waifu_usage_tracker and not is_unlimited_user:
            return
            
        try:
            img_bytes, waifu_name, source_url = fetch_waifu_image()
            caption_text = "Berikut waifumu hari ini semangat yaa 😘"



            
            msg_to_send = client.build_image_message(
                file=img_bytes,
                caption=caption_text,
                quoted=message
            )
            client.send_message(chat_jid, msg_to_send)
            
            # Catat penggunaan dan simpan ke file JSON
            if not is_unlimited_user:
                waifu_usage_tracker.add(sender_jid_str)
                save_waifu_tracker()
        except Exception as e:
            client.reply_message(f"Gagal: Gagal mengambil gambar waifu dari internet. Detail: {e}", message)
            
    elif lower_text == ",husbu":
        # Jalankan pengecekan reset limit harian
        check_and_reset_husbu_limit()
        
        # Ambil JID pengirim secara unik
        if message.Info.MessageSource.Sender and message.Info.MessageSource.Sender.User:
            sender_user = message.Info.MessageSource.Sender.User
            sender_server = message.Info.MessageSource.Sender.Server
        else:
            sender_user = message.Info.MessageSource.Chat.User
            sender_server = message.Info.MessageSource.Chat.Server
            
        sender_jid_str = f"{sender_user}@{sender_server}"
        clean_sender = sender_user.split('.')[0].split(':')[0].split('@')[0]
        is_unlimited_user = clean_sender in ["6287828697399", "087828697399", "205479875735664"]
        
        print(f"DEBUG ,husbu: sender_user={sender_user}, clean_sender={clean_sender}, is_unlimited={is_unlimited_user}")
        
        # Jika sudah menggunakan hari ini, abaikan
        if sender_jid_str in husbu_usage_tracker and not is_unlimited_user:
            return
            
        try:
            img_bytes, husbu_name, source_url = fetch_husbu_image()
            caption_text = "Berikut husbumu hari ini semangat yaa 😘"



            
            msg_to_send = client.build_image_message(
                file=img_bytes,
                caption=caption_text,
                quoted=message
            )
            client.send_message(chat_jid, msg_to_send)
            
            # Catat penggunaan dan simpan ke file JSON
            if not is_unlimited_user:
                husbu_usage_tracker.add(sender_jid_str)
                save_husbu_tracker()
        except Exception as e:
            client.reply_message(f"Gagal: Gagal mengambil gambar husbu dari internet. Detail: {e}", message)
        
    elif lower_text.startswith(",calc "):
        # Ambil ekspresi setelah kata ,calc
        expression = msg_text[len(",calc "):]
        calc_result = safe_calc(expression)
        client.reply_message(calc_result, message)
        
    elif lower_text == ",a" or lower_text.startswith(",a "):
        if not message.Info.MessageSource.IsGroup:
            client.reply_message("Peringatan: Perintah `,a` hanya dapat digunakan di dalam grup obrolan.", message)
        else:
            try:
                # Ambil data anggota dari cache/API
                group_data = get_group_members_info(client, chat_jid)
                jids_list = list(dict.fromkeys(group_data.get('jids', [])))
                admins_list = group_data.get('admins', [])

                # Cek apakah pengirim adalah admin/superadmin
                sender_user = message.Info.MessageSource.Sender.User if message.Info.MessageSource.Sender else ""
                clean_sender = sender_user.split('.')[0].split(':')[0].split('@')[0]
                is_admin = sender_user in admins_list or clean_sender in admins_list or is_owner

                if not is_admin:
                    client.reply_message("Lu bukan atmin kocak, memang pedut problematik kick aja!!!", message)
                    return

                custom_msg = msg_text[len(",a"):].strip()

                target_msg_to_download = None
                caption_text = None
                is_image = False
                target_item = None
                context_info = None

                unwrapped_curr = deep_unwrap_message(message.Message)

                # 1. Cek jika admin mengirim gambar langsung dari galeri dengan caption ,a
                direct_media, is_direct, direct_cap = extract_media_submessage(unwrapped_curr)
                if is_direct and direct_media:
                    is_image = True
                    target_msg_to_download = direct_media
                    caption_text = custom_msg if custom_msg else (direct_cap if direct_cap else None)

                # 2. Cek jika admin mereply / mengutip pesan (gambar tunggal, multi-gambar/album, atau pesan teks)
                else:
                    context_info = None
                    for cand_m in [unwrapped_curr, message.Message]:
                        if not cand_m:
                            continue
                        for field_name in ['extendedTextMessage', 'imageMessage', 'documentMessage', 'videoMessage', 'buttonsMessage', 'interactiveMessage', 'templateMessage']:
                            if cand_m.HasField(field_name):
                                sub_f = getattr(cand_m, field_name)
                                if hasattr(sub_f, 'contextInfo') and sub_f.HasField('contextInfo'):
                                    context_info = sub_f.contextInfo
                                    break
                        if context_info:
                            break

                    if context_info and context_info.HasField('quotedMessage'):
                        quoted_raw = context_info.quotedMessage
                        quoted_unwrapped = deep_unwrap_message(quoted_raw)
                        quoted_id = context_info.stanzaID or ""
                        cached_items = GROUP_MESSAGE_CACHE.get(chat_jid_str, [])

                        # A. Ekstrak media langsung dari quotedMessage
                        q_media, is_q_img, q_cap = extract_media_submessage(quoted_unwrapped)
                        if not is_q_img:
                            q_media, is_q_img, q_cap = extract_media_submessage(quoted_raw)

                        # B. Cek apakah quotedMessage bertipe albumMessage
                        is_q_album = False
                        for q_cand in [quoted_unwrapped, quoted_raw]:
                            if q_cand and hasattr(q_cand, 'HasField') and q_cand.HasField('albumMessage'):
                                is_q_album = True
                                break

                        # C. Cek parent_id asosiasi jika pesan memiliki messageAssociation
                        assoc_parent_id = ""
                        for q_cand in [quoted_raw, quoted_unwrapped]:
                            if q_cand and hasattr(q_cand, 'HasField') and q_cand.HasField('messageContextInfo'):
                                mci = q_cand.messageContextInfo
                                if mci.HasField('messageAssociation'):
                                    assoc = mci.messageAssociation
                                    if assoc.HasField('parentMessageKey') and assoc.parentMessageKey.ID:
                                        assoc_parent_id = assoc.parentMessageKey.ID
                                        break

                        # D. Cari pesan di dalam cache grup
                        matched_idx = -1
                        target_item = None
                        if quoted_id:
                            for idx, it in enumerate(cached_items):
                                if it["id"] == quoted_id:
                                    matched_idx = idx
                                    target_item = it
                                    break

                        target_is_img = target_item.get("is_image", False) if target_item else False
                        target_is_album = target_item.get("is_album", False) if target_item else False
                        target_parent_id = target_item.get("parent_id", "") if target_item else ""

                        # E. Validasi apakah pesan yang direply BENAR-BENAR merupakan media/gambar/album
                        has_assoc_parent_imgs = bool(assoc_parent_id and any(it.get("parent_id") == assoc_parent_id and it.get("is_image") for it in cached_items))
                        is_quoted_parent_of_imgs = bool(quoted_id and any(it.get("parent_id") == quoted_id and it.get("is_image") for it in cached_items))
                        target_has_parent_imgs = bool(target_parent_id and any(it.get("parent_id") == target_parent_id and it.get("is_image") for it in cached_items))

                        is_media_target = (
                            is_q_img or 
                            is_q_album or 
                            target_is_img or 
                            target_is_album or 
                            has_assoc_parent_imgs or 
                            is_quoted_parent_of_imgs or 
                            target_has_parent_imgs
                        )

                        candidate_cluster = []

                        # HANYA cari/ambil gambar jika pesan yang direply memang pesan media / gambar!
                        if is_media_target:
                            # TIER 1: Match by parent_id (album ID)
                            target_parents = [p for p in [assoc_parent_id, target_parent_id, quoted_id] if p]
                            for tp in target_parents:
                                by_parent = [it for it in cached_items if it.get("parent_id") == tp and it.get("is_image")]
                                if by_parent:
                                    by_parent.sort(key=lambda x: (x.get("message_index", 0), x.get("timestamp", 0)))
                                    candidate_cluster = by_parent
                                    break

                            # TIER 2: Match berdasarkan target_item di cache
                            if not candidate_cluster and target_item:
                                # 2A: target_item punya parent_id
                                if target_item.get("parent_id"):
                                    by_p = [it for it in cached_items if it.get("parent_id") == target_item["parent_id"] and it.get("is_image")]
                                    if by_p:
                                        by_p.sort(key=lambda x: (x.get("message_index", 0), x.get("timestamp", 0)))
                                        candidate_cluster = by_p

                                # 2B: target_item adalah gambar, cari cluster gambar berdekatan dari pengirim yang sama (multi-gambar / 2 gambar berurutan)
                                if not candidate_cluster and target_item.get("is_image"):
                                    cluster = [target_item]
                                    t_senders = set(target_item.get("all_senders", [])) or {target_item.get("sender", "").lower()}
                                    # Cek sebelum (mundur)
                                    p = matched_idx - 1
                                    while p >= 0 and (matched_idx - p <= 10):
                                        prev_it = cached_items[p]
                                        if prev_it.get("is_image"):
                                            p_senders = set(prev_it.get("all_senders", [])) or {prev_it.get("sender", "").lower()}
                                            if (not t_senders or not p_senders or bool(t_senders & p_senders)) and abs(prev_it.get("timestamp", 0) - cluster[0].get("timestamp", 0)) <= 45:
                                                cluster.insert(0, prev_it)
                                                p -= 1
                                                continue
                                        p -= 1

                                    # Cek sesudah (maju)
                                    n = matched_idx + 1
                                    while n < len(cached_items) and (n - matched_idx <= 10):
                                        next_it = cached_items[n]
                                        if next_it.get("is_image"):
                                            n_senders = set(next_it.get("all_senders", [])) or {next_it.get("sender", "").lower()}
                                            if (not t_senders or not n_senders or bool(t_senders & n_senders)) and abs(next_it.get("timestamp", 0) - cluster[-1].get("timestamp", 0)) <= 45:
                                                cluster.append(next_it)
                                                n += 1
                                                continue
                                        n += 1

                                    cluster.sort(key=lambda x: (x.get("message_index", 0), x.get("timestamp", 0)))
                                    candidate_cluster = cluster

                                # 2C: target_item adalah albumMessage (is_album), cari gambar di sekitarnya
                                if not candidate_cluster and target_item.get("is_album"):
                                    t_ts = target_item.get("timestamp", 0)
                                    t_senders = set(target_item.get("all_senders", [])) or {target_item.get("sender", "").lower()}
                                    nearby_imgs = []
                                    start_i = max(0, matched_idx - 10)
                                    end_i = min(len(cached_items), matched_idx + 11)
                                    for idx_near in range(start_i, end_i):
                                        if idx_near == matched_idx:
                                            continue
                                        nit = cached_items[idx_near]
                                        if nit.get("is_image"):
                                            n_senders = set(nit.get("all_senders", [])) or {nit.get("sender", "").lower()}
                                            sender_match = (not t_senders or not n_senders or bool(t_senders & n_senders))
                                            time_match = abs(nit.get("timestamp", 0) - t_ts) <= 45
                                            if sender_match and time_match:
                                                nearby_imgs.append(nit)
                                    if nearby_imgs:
                                        nearby_imgs.sort(key=lambda x: (x.get("message_index", 0), x.get("timestamp", 0)))
                                        candidate_cluster = nearby_imgs

                            # TIER 3: Fallback langsung jika quotedMessage sendiri adalah gambar
                            if not candidate_cluster and is_q_img and q_media:
                                candidate_cluster = [{
                                    "raw_message": q_media,
                                    "media_msg": q_media,
                                    "caption": q_cap
                                }]

                        # Jika ditemukan cluster gambar dari target media
                        if candidate_cluster:
                            # Jika pesan yang direply (target_item) sendiri adalah gambar, prioritaskan target_item
                            selected_item = target_item if (target_item and target_item.get("is_image")) else candidate_cluster[0]
                            target_raw = selected_item.get("media_msg") or selected_item.get("raw_message")
                            if not target_raw and selected_item.get("raw_json"):
                                try:
                                    target_raw = pb.Message()
                                    Parse(selected_item["raw_json"], target_raw)
                                except Exception:
                                    pass

                            if not target_raw:
                                first_item = candidate_cluster[0]
                                target_raw = first_item.get("media_msg") or first_item.get("raw_message")
                                if not target_raw and first_item.get("raw_json"):
                                    try:
                                        target_raw = pb.Message()
                                        Parse(first_item["raw_json"], target_raw)
                                    except Exception:
                                        pass

                            if target_raw:
                                target_msg_to_download = target_raw
                                is_image = True

                                # Ambil kata-kata / caption secara presisi:
                                # 1. Prioritaskan q_cap langsung dari quotedMessage yang direply di WhatsApp (sumber paling akurat saat user tekan reply)
                                orig_caption = ""
                                if q_cap and q_cap.strip():
                                    orig_caption = q_cap.strip()
                                # 2. Jika q_cap kosong, cek caption dari target_item di cache
                                elif target_item and target_item.get("caption", "").strip():
                                    orig_caption = target_item["caption"].strip()
                                # 3. Cek caption dari selected_item
                                elif selected_item and selected_item.get("caption", "").strip():
                                    orig_caption = selected_item["caption"].strip()
                                # 4. Cari dari item lain di candidate_cluster
                                else:
                                    for it in candidate_cluster:
                                        if it.get("caption", "").strip():
                                            orig_caption = it["caption"].strip()
                                            break
                                        if it.get("text", "").strip():
                                            orig_caption = it["text"].strip()
                                            break

                                if custom_msg and orig_caption:
                                    caption_text = f"{custom_msg}\n\n{orig_caption}"
                                elif custom_msg:
                                    caption_text = custom_msg
                                elif orig_caption:
                                    caption_text = orig_caption
                                else:
                                    caption_text = None

                if is_image and target_msg_to_download:
                    try:
                        # Unduh bytes gambar
                        image_bytes = None
                        download_candidates = [
                            target_msg_to_download,
                            target_item.get("raw_message") if target_item else None,
                            target_item.get("media_msg") if target_item else None,
                            candidate_cluster[0].get("raw_message") if candidate_cluster else None,
                            candidate_cluster[0].get("media_msg") if candidate_cluster else None
                        ]
                        for cand in download_candidates:
                            if not cand or image_bytes:
                                continue
                            try:
                                image_bytes = client.download_any(cand)
                            except Exception as de1:
                                logging.debug(f"download_any direct failed: {de1}")
                            if not image_bytes:
                                try:
                                    unwrapped_cand = deep_unwrap_message(cand)
                                    image_bytes = client.download_any(unwrapped_cand)
                                except Exception as de2:
                                    logging.debug(f"download_any unwrapped failed: {de2}")
                            if not image_bytes:
                                sub_m, is_sub, _ = extract_media_submessage(cand)
                                if sub_m and sub_m != cand:
                                    try:
                                        image_bytes = client.download_any(sub_m)
                                    except Exception as de3:
                                        logging.debug(f"download_any sub_m failed: {de3}")

                        if not image_bytes:
                            client.reply_message("Gagal: Gagal mengunduh gambar yang dimaksud.", message)
                            return

                        # Bangun image message
                        msg_to_send = client.build_image_message(
                            file=image_bytes,
                            caption=caption_text,
                            quoted=message
                        )

                        # Masukkan list JID langsung ke mentionedJID untuk hide tag all
                        msg_to_send.imageMessage.contextInfo.mentionedJID.extend(jids_list)

                        # Kirim message ke grup
                        client.send_message(chat_jid, msg_to_send)
                    except Exception as media_err:
                        client.reply_message(f"Gagal: Gagal mengirim kembali gambar dengan hidetag. Detail: {media_err}", message)
                else:
                    # Teks pesan yang dikirim (jika kosong dan mereply pesan teks, gunakan teks quoted jika ada)
                    quoted_text = ""
                    if context_info and context_info.HasField('quotedMessage'):
                        quoted_text = extract_text_from_message_pb(context_info.quotedMessage)
                    if not quoted_text and target_item:
                        if target_item.get("raw_message"):
                            quoted_text = extract_text_from_message_pb(target_item["raw_message"])
                        if not quoted_text and target_item.get("text"):
                            quoted_text = target_item["text"]
                        if not quoted_text and target_item.get("caption"):
                            quoted_text = target_item["caption"]

                    if custom_msg and quoted_text:
                        text_to_send = f"{custom_msg}\n\n{quoted_text}"
                    elif custom_msg:
                        text_to_send = custom_msg
                    elif quoted_text:
                        text_to_send = quoted_text
                    else:
                        text_to_send = "."

                    # Bangun ExtendedTextMessage secara langsung dengan mentionedJID
                    extended_text_msg = pb.ExtendedTextMessage(
                        text=text_to_send,
                        contextInfo=pb.ContextInfo(
                            mentionedJID=jids_list
                        )
                    )

                    # Kirim pesan bersih tanpa menampilkan daftar nomor telepon di teks pesan
                    client.reply_message(extended_text_msg, message)
            except Exception as e:
                client.reply_message(f"Gagal: Gagal mengambil informasi anggota grup. Detail: {e}", message)
        
    elif lower_text == ",kick" or lower_text.startswith(",kick "):
        if not message.Info.MessageSource.IsGroup:
            client.reply_message("Peringatan: Perintah `,kick` hanya dapat digunakan di dalam grup obrolan.", message)
        else:
            try:
                # Ambil data anggota dari cache/API
                group_data = get_group_members_info(client, chat_jid)
                jids_list = group_data['jids']
                admins_list = group_data['admins']
                jids_raw = group_data['jids_raw']
                
                # Cek apakah pengirim adalah admin/superadmin
                sender_user = message.Info.MessageSource.Sender.User if message.Info.MessageSource.Sender else ""
                is_admin = sender_user in admins_list
                
                if not is_admin:
                    client.reply_message("Lu bukan atmin kocak, tidak punya wewenang kick!!!", message)
                    return
                
                # Cari target yang akan di-kick
                target_jid_str = ""
                extended_msg = message.Message.extendedTextMessage
                if extended_msg and extended_msg.contextInfo:
                    if extended_msg.contextInfo.mentionedJID:
                        target_jid_str = extended_msg.contextInfo.mentionedJID[0]
                    elif extended_msg.contextInfo.participant:
                        target_jid_str = extended_msg.contextInfo.participant
                
                if not target_jid_str:
                    client.reply_message("Peringatan: Silakan tag (@) orang yang ingin di-kick atau reply pesannya dengan `,kick`.", message)
                    return
                
                # Cari objek JID target yang lengkap dari data anggota
                target_jid = None
                for jid_obj in jids_raw:
                    jid_obj_str = f"{jid_obj.User}@{jid_obj.Server}"
                    if jid_obj_str == target_jid_str:
                        target_jid = jid_obj
                        break
                
                if not target_jid:
                    client.reply_message("Peringatan: Target tidak ditemukan di dalam grup.", message)
                    return
                
                # Lakukan kick
                client.update_group_participants(chat_jid, [target_jid], ParticipantChange.REMOVE)
                user_id = target_jid.User
                
                # Kirim konfirmasi dengan ghost mention
                client.reply_message("Makan tuh kocak di kick, join antek antek pedut aja problematik!!!haha ↔", message, ghost_mentions=f"@{user_id}")
                
                # Hapus cache agar data grup terbaru di-refresh lain kali
                if chat_jid_str in GROUP_CACHE:
                    del GROUP_CACHE[chat_jid_str]
                    
            except Exception as e:
                client.reply_message(f"Gagal: Gagal kick. Jadiin atmin dulu oii!!! Detail: {e}", message)

    elif lower_text == ",view" or lower_text.startswith(",view "):
        # Cek apakah ini di grup
        is_group = message.Info.MessageSource.IsGroup
        if is_group:
            # Ambil admins dari cache/API
            group_data = get_group_members_info(client, chat_jid)
            admins_list = group_data['admins']
            
            sender_user = message.Info.MessageSource.Sender.User if message.Info.MessageSource.Sender else ""
            if sender_user not in admins_list:
                client.reply_message("Lu bukan atmin kocak, tidak punya wewenang view!!!", message)
                return

        extended_msg = message.Message.extendedTextMessage
        if not (extended_msg and extended_msg.contextInfo and extended_msg.contextInfo.HasField('quotedMessage')):
            client.reply_message("Peringatan: Silakan reply gambar/video/audio 1x lihat dengan menggunakan perintah `,view`.", message)
            return

        quoted_msg = extended_msg.contextInfo.quotedMessage

        def unwrap(msg):
            for _ in range(5):
                try:
                    if msg.HasField('viewOnceMessage') and msg.viewOnceMessage.message:
                        msg = msg.viewOnceMessage.message
                    elif msg.HasField('viewOnceMessageV2') and msg.viewOnceMessageV2.message:
                        msg = msg.viewOnceMessageV2.message
                    elif msg.HasField('viewOnceMessageV2Extension') and msg.viewOnceMessageV2Extension.message:
                        msg = msg.viewOnceMessageV2Extension.message
                    elif msg.HasField('ephemeralMessage') and msg.ephemeralMessage.message:
                        msg = msg.ephemeralMessage.message
                    else:
                        break
                except Exception:
                    break
            return msg

        unwrapped = unwrap(quoted_msg)
        def download_media(msg_wrapped, msg_unwrapped):
            # 1. Coba download dari wrapped message (misal viewOnceMessage)
            try:
                res = client.download_any(msg_wrapped)
                if res:
                    return res
            except Exception:
                pass
                
            # 2. Coba download dari unwrapped message (misal videoMessage/imageMessage di dalam Message)
            try:
                res = client.download_any(msg_unwrapped)
                if res:
                    return res
            except Exception:
                pass
                
            # 3. Coba manual dengan download_media_with_path menggunakan metadata langsung
            from neonize.utils.enum import MediaType, MediaTypeToMMS
            try:
                if msg_unwrapped.HasField('imageMessage'):
                    img = msg_unwrapped.imageMessage
                    return client.download_media_with_path(
                        direct_path=img.directPath,
                        enc_file_hash=img.fileEncSHA256,
                        file_hash=img.fileSHA256,
                        media_key=img.mediaKey,
                        file_length=img.fileLength,
                        media_type=MediaType.MediaImage,
                        mms_type=MediaTypeToMMS.MediaImage
                    )
                elif msg_unwrapped.HasField('videoMessage'):
                    vid = msg_unwrapped.videoMessage
                    return client.download_media_with_path(
                        direct_path=vid.directPath,
                        enc_file_hash=vid.fileEncSHA256,
                        file_hash=vid.fileSHA256,
                        media_key=vid.mediaKey,
                        file_length=vid.fileLength,
                        media_type=MediaType.MediaVideo,
                        mms_type=MediaTypeToMMS.MediaVideo
                    )
                elif msg_unwrapped.HasField('audioMessage'):
                    aud = msg_unwrapped.audioMessage
                    return client.download_media_with_path(
                        direct_path=aud.directPath,
                        enc_file_hash=aud.fileEncSHA256,
                        file_hash=aud.fileSHA256,
                        media_key=aud.mediaKey,
                        file_length=aud.fileLength,
                        media_type=MediaType.MediaAudio,
                        mms_type=MediaTypeToMMS.MediaAudio
                    )
                elif msg_unwrapped.HasField('documentMessage'):
                    doc = msg_unwrapped.documentMessage
                    return client.download_media_with_path(
                        direct_path=doc.directPath,
                        enc_file_hash=doc.fileEncSHA256,
                        file_hash=doc.fileSHA256,
                        media_key=doc.mediaKey,
                        file_length=doc.fileLength,
                        media_type=MediaType.MediaDocument,
                        mms_type=MediaTypeToMMS.MediaDocument
                    )
            except Exception:
                pass
                
            # Jika semuanya gagal, panggil download_any sekali lagi agar exception aslinya terlempar keluar
            return client.download_any(msg_unwrapped)

        media_bytes = None
        msg_to_send = None

        try:
            if unwrapped.HasField('imageMessage'):
                media_bytes = download_media(quoted_msg, unwrapped)
                caption = unwrapped.imageMessage.caption or None
                msg_to_send = client.build_image_message(file=media_bytes, caption=caption, quoted=message)
            elif unwrapped.HasField('videoMessage'):
                media_bytes = download_media(quoted_msg, unwrapped)
                caption = unwrapped.videoMessage.caption or None
                try:
                    msg_to_send = client.build_video_message(file=media_bytes, caption=caption, quoted=message)
                except Exception:
                    # Fallback jika ffmpeg/ffprobe tidak terinstall di sistem host
                    upload = client.upload(media_bytes)
                    orig_video = unwrapped.videoMessage
                    
                    ctx_info = pb.ContextInfo()
                    if message:
                        ctx_info.MergeFrom(client._make_quoted_message(message))
                        
                    video_msg = pb.VideoMessage(
                        URL=upload.url,
                        caption=caption,
                        seconds=orig_video.seconds or 0,
                        directPath=upload.DirectPath,
                        fileEncSHA256=upload.FileEncSHA256,
                        fileLength=upload.FileLength,
                        fileSHA256=upload.FileSHA256,
                        mediaKey=upload.MediaKey,
                        mimetype=orig_video.mimetype or "video/mp4",
                        JPEGThumbnail=orig_video.JPEGThumbnail,
                        thumbnailDirectPath=upload.DirectPath,
                        thumbnailEncSHA256=upload.FileEncSHA256,
                        thumbnailSHA256=upload.FileSHA256,
                        contextInfo=ctx_info
                    )
                    msg_to_send = pb.Message(videoMessage=video_msg)
            elif unwrapped.HasField('audioMessage'):
                media_bytes = download_media(quoted_msg, unwrapped)
                ptt = unwrapped.audioMessage.PTT
                try:
                    msg_to_send = client.build_audio_message(file=media_bytes, ptt=ptt, quoted=message)
                except Exception:
                    # Fallback jika ffmpeg/ffprobe tidak terinstall di sistem host
                    upload = client.upload(media_bytes)
                    orig_audio = unwrapped.audioMessage
                    
                    ctx_info = pb.ContextInfo()
                    if message:
                        ctx_info.MergeFrom(client._make_quoted_message(message))
                        
                    audio_msg = pb.AudioMessage(
                        URL=upload.url,
                        seconds=orig_audio.seconds or 0,
                        directPath=upload.DirectPath,
                        fileEncSHA256=upload.FileEncSHA256,
                        fileLength=upload.FileLength,
                        fileSHA256=upload.FileSHA256,
                        mediaKey=upload.MediaKey,
                        mimetype=orig_audio.mimetype or "audio/ogg; codecs=opus",
                        PTT=ptt,
                        contextInfo=ctx_info
                    )
                    msg_to_send = pb.Message(audioMessage=audio_msg)
            elif unwrapped.HasField('documentMessage'):
                media_bytes = download_media(quoted_msg, unwrapped)
                caption = unwrapped.documentMessage.caption or None
                title = unwrapped.documentMessage.title or None
                filename = unwrapped.documentMessage.fileName or None
                mimetype = unwrapped.documentMessage.mimetype or None
                msg_to_send = client.build_document_message(file=media_bytes, caption=caption, title=title, filename=filename, mimetype=mimetype, quoted=message)
            else:
                client.reply_message("Peringatan: Pesan yang di-reply bukan merupakan media (gambar/video/audio/dokumen) atau bukan pesan 1x lihat.", message)
                return

            if msg_to_send:
                client.send_message(chat_jid, msg_to_send)
            else:
                client.reply_message("Gagal: Gagal memproses media.", message)
        except Exception as e:
            client.reply_message(f"Gagal: Terjadi kesalahan saat mengunduh/mengirim media. Detail: {e}", message)

        
    elif lower_text == ",warn" or lower_text.startswith(",warn "):
        if not message.Info.MessageSource.IsGroup:
            client.reply_message("Peringatan: Perintah `,warn` hanya dapat digunakan di dalam grup obrolan.", message)
            return

        chat_jid_str = f"{chat_jid.User}@{chat_jid.Server}"
        now = time.time()
        group_data = get_group_members_info(client, chat_jid)
        admins_list = group_data.get('admins', [])
        jids_raw = group_data.get('jids_raw', [])

        # Cek apakah pengirim adalah admin/superadmin
        sender_user = message.Info.MessageSource.Sender.User if message.Info.MessageSource.Sender else ""
        clean_sender = sender_user.split('.')[0].split(':')[0].split('@')[0]
        is_admin = sender_user in admins_list or clean_sender in admins_list or is_owner
        if not is_admin:
            client.reply_message("Lu bukan atmin kocak, tidak punya wewenang warn!!!", message)
            return

        # Cari target yang akan di-warn
        target_jid_str = ""
        extended_msg = message.Message.extendedTextMessage
        if extended_msg and extended_msg.contextInfo:
            if extended_msg.contextInfo.mentionedJID:
                target_jid_str = extended_msg.contextInfo.mentionedJID[0]
            elif extended_msg.contextInfo.participant:
                target_jid_str = extended_msg.contextInfo.participant

        if not target_jid_str:
            client.reply_message("Peringatan: Silakan tag (@) orang yang ingin di-warn atau reply pesannya dengan `,warn`.", message)
            return

        # Cari objek JID target yang lengkap dari data anggota
        target_jid = None
        for jid_obj in jids_raw:
            jid_obj_str = f"{jid_obj.User}@{jid_obj.Server}"
            if jid_obj_str == target_jid_str:
                target_jid = jid_obj
                break

        if not target_jid:
            client.reply_message("Peringatan: Anggota tidak ditemukan di dalam grup.", message)
            return

        # Proses Warning
        warnings_data = load_warnings()
        group_warns = get_group_warnings_data(warnings_data, chat_jid)
        user_warns = group_warns.get(target_jid_str, [])

        # Filter warnings yang berumur lebih dari 7 hari (7 * 24 * 3600 detik)
        active_warns = [ts for ts in user_warns if now - ts <= 7 * 86400]
        
        # Tambah warning baru
        active_warns.append(now)
        warn_count = len(active_warns)
        user_id = target_jid.User

        if warn_count >= 3:
            # Kick user
            try:
                client.update_group_participants(chat_jid, [target_jid], ParticipantChange.REMOVE)
                # Bersihkan warnings
                if target_jid_str in group_warns:
                    del group_warns[target_jid_str]
                save_warnings(warnings_data)
                
                # Hapus cache grup agar data terbaru di-refresh
                if chat_jid_str in GROUP_CACHE:
                    del GROUP_CACHE[chat_jid_str]
                
                client.reply_message("Peringatan: *Peringatan 3/3*: Anggota telah melebihi batas 3 kali peringatan dan telah dikeluarkan dari grup!", message)
            except Exception as e:
                client.reply_message(f"Gagal: Gagal mengeluarkan anggota setelah 3 kali peringatan. Pastikan bot adalah admin. Detail: {e}", message)
        else:
            # Simpan warning
            group_warns[target_jid_str] = active_warns
            try:
                save_warnings(warnings_data)
                client.reply_message(f"Peringatan: *Peringatan ({warn_count}/3)*: Anggota telah diberi peringatan oleh Admin! Peringatan akan kedaluwarsa otomatis dalam 7 hari.", message)
            except Exception as e:
                client.reply_message(f"Gagal: Gagal menyimpan data peringatan. Detail: {e}", message)

    elif lower_text == ",reset" or lower_text.startswith(",reset "):
        if not message.Info.MessageSource.IsGroup:
            client.reply_message("Peringatan: Perintah `,reset` hanya dapat digunakan di dalam grup obrolan.", message)
            return

        chat_jid_str = f"{chat_jid.User}@{chat_jid.Server}"
        now = time.time()
        group_data = get_group_members_info(client, chat_jid)
        admins_list = group_data.get('admins', [])
        jids_raw = group_data.get('jids_raw', [])

        # Cek apakah pengirim adalah admin/superadmin
        sender_user = message.Info.MessageSource.Sender.User if message.Info.MessageSource.Sender else ""
        clean_sender = sender_user.split('.')[0].split(':')[0].split('@')[0]
        is_admin = sender_user in admins_list or clean_sender in admins_list or is_owner
        if not is_admin:
            client.reply_message("Lu bukan atmin kocak, tidak punya wewenang reset!!!", message)
            return

        # Cari target yang akan di-reset
        target_jid_str = ""
        extended_msg = message.Message.extendedTextMessage
        if extended_msg and extended_msg.contextInfo:
            if extended_msg.contextInfo.mentionedJID:
                target_jid_str = extended_msg.contextInfo.mentionedJID[0]
            elif extended_msg.contextInfo.participant:
                target_jid_str = extended_msg.contextInfo.participant

        if not target_jid_str:
            client.reply_message("Peringatan: Silakan tag (@) orang yang ingin di-reset warning-nya atau reply pesannya dengan `,reset`.", message)
            return

        # Cari objek JID target yang lengkap dari data anggota
        target_jid = None
        for jid_obj in jids_raw:
            jid_obj_str = f"{jid_obj.User}@{jid_obj.Server}"
            if jid_obj_str == target_jid_str:
                target_jid = jid_obj
                break

        if not target_jid:
            client.reply_message("Peringatan: Anggota tidak ditemukan di dalam grup.", message)
            return

        # Proses Reset Warning
        warnings_data = load_warnings()
        group_warns = get_group_warnings_data(warnings_data, chat_jid)

        if target_jid_str in group_warns:
            del group_warns[target_jid_str]
            try:
                save_warnings(warnings_data)
                client.reply_message("Berhasil: Berhasil mereset semua peringatan untuk anggota tersebut.", message)
            except Exception as e:
                client.reply_message(f"Gagal: Gagal memperbarui data peringatan. Detail: {e}", message)
        else:
            client.reply_message("Info: Anggota tersebut tidak memiliki catatan peringatan aktif.", message)

    elif lower_text in [",listwarn", ",warnlist"] or lower_text.startswith(",listwarn ") or lower_text.startswith(",warnlist "):
        if not message.Info.MessageSource.IsGroup:
            client.reply_message("Peringatan: Perintah `,listwarn` hanya dapat digunakan di dalam grup obrolan.", message)
            return

        chat_jid_str = f"{chat_jid.User}@{chat_jid.Server}"
        now = time.time()
        warnings_data = load_warnings()
        group_warns = get_group_warnings_data(warnings_data, chat_jid)

        # Filter dan kumpulkan anggota yang memiliki peringatan aktif (<= 7 hari)
        active_list = []
        expired_keys = []
        for target_jid, ts_list in list(group_warns.items()):
            active_ts = [ts for ts in ts_list if now - ts <= 7 * 86400]
            if active_ts:
                group_warns[target_jid] = active_ts
                active_list.append((target_jid, len(active_ts), min(active_ts)))
            else:
                expired_keys.append(target_jid)

        # Bersihkan warning yang telah kedaluwarsa dari database
        if expired_keys:
            for k in expired_keys:
                del group_warns[k]
            save_warnings(warnings_data)

        if not active_list:
            client.reply_message("*DAFTAR PERINGATAN (WARN) GRUP*\n\nTidak ada anggota yang memiliki catatan peringatan aktif di grup ini.", message)
        else:
            # Urutkan berdasarkan jumlah warning terbanyak, lalu waktu warning terlama
            active_list.sort(key=lambda x: (-x[1], x[2]))

            lines = [
                "*DAFTAR PERINGATAN (WARN) GRUP*",
                f"Total Pelanggar: {len(active_list)} orang",
                ""
            ]

            mentioned_jids = []
            for idx, (target_jid, count, oldest_ts) in enumerate(active_list, start=1):
                clean_target = target_jid.split('@')[0]
                sisa_detik = max(0, 7 * 86400 - (now - oldest_ts))
                sisa_hari = int(sisa_detik // 86400)
                sisa_jam = int((sisa_detik % 86400) // 3600)
                
                waktu_str = f"{sisa_hari} hari" if sisa_hari > 0 else f"{sisa_jam} jam"
                lines.append(f"{idx}. @{clean_target} - {count}/3 warning (sisa waktu: {waktu_str})")
                mentioned_jids.append(target_jid)

            lines.append("")
            lines.append("Keterangan:")
            lines.append("- Batas maksimal: 3 kali peringatan (otomatis dikeluarkan jika mencapai 3).")
            lines.append("- Peringatan akan kedaluwarsa otomatis dalam 7 hari sejak diberikan.")

            reply_text = "\n".join(lines)

            extended_text_msg = pb.ExtendedTextMessage(
                text=reply_text,
                contextInfo=pb.ContextInfo(
                    mentionedJID=mentioned_jids
                )
            )
            client.reply_message(extended_text_msg, message)


    elif lower_text == ",pet" or lower_text.startswith(",pet "):
        query = msg_text[len(",pet"):].strip().lower()
        
        if not query or query in ["list", "menu"]:
            natures_list = "\n".join([f"• *{val['name']}*" for val in pet_natures.values()])
            client.reply_message(get_pet_menu_text(natures_list), message)
        else:
            matched_nature = None
            for key, val in pet_natures.items():
                name_low = val.get("name", "").lower()
                if query == key or query in name_low:
                    matched_nature = val
                    break
            
            if matched_nature:
                client.reply_message(format_pet_detail(matched_nature), message)
            else:
                client.reply_message(f"Peringatan: Sifat Pet '{query}' tidak ditemukan. Ketik *,pet* untuk melihat daftar sifat pet yang tersedia.", message)

    elif lower_text == ",trait" or lower_text.startswith(",trait "):
        query = msg_text[len(",trait"):].strip().lower()
        
        if not query or query in ["list", "menu"]:
            reply = "*DAFTAR TRAIT PET TORAM ONLINE*\n\n"
            reply += "Berikut adalah daftar trait yang tersedia:\n\n"
            for idx, t_key in enumerate(sorted(traits_db.keys()), start=1):
                en_title = t_key.title() if t_key not in ["str", "int", "vit", "agi", "dex", "atk", "matk", "def", "mdef", "aspd", "cspd", "maxhp", "maxmp"] else t_key.upper()
                reply += f"{idx}. *{en_title}*\n"
            reply += "\nTips: Ketik `,trait [nama]` (contoh: `,trait battlecast`) untuk melihat detail efek."
            client.reply_message(reply, message)
        else:
            matches = []
            for t_key in sorted(traits_db.keys()):
                en_name = t_key.lower()
                if query in en_name:
                    matches.append(format_trait_detail(t_key))
            
            if matches:
                show_matches = matches[:5]
                detail_msg = "*HASIL PENCARIAN TRAIT TORAM ONLINE*\n\n" + "\n\n──────────────────\n\n".join(show_matches)
                if len(matches) > 5:
                    detail_msg += f"\n\n_...dan {len(matches) - 5} hasil lainnya. Silakan ketik nama trait yang lebih spesifik!_"
                client.reply_message(detail_msg, message)
            else:
                client.reply_message(f"Peringatan: Trait '{query}' tidak ditemukan. Ketik *,trait* untuk melihat daftar lengkap.", message)

    elif lower_text == ",fillwp" or lower_text.startswith(",fillwp "):
        query = msg_text[len(",fillwp"):].strip()
        handle_fillwp_command(client, message, query)

    elif lower_text == ",fillarm" or lower_text.startswith(",fillarm "):
        query = msg_text[len(",fillarm"):].strip()
        handle_fillarm_command(client, message, query)

    elif lower_text == ",item" or lower_text.startswith(",item "):
        query = msg_text[len(",item"):].strip()
        handle_item_search_command(client, message, query, "item", "Item")

    elif lower_text == ",arrow" or lower_text.startswith(",arrow ") or lower_text == ",panah" or lower_text.startswith(",panah "):
        prefix = ",panah" if lower_text.startswith(",panah") else ",arrow"
        query = msg_text[len(prefix):].strip()
        handle_arrow_command(client, message, query)

    elif lower_text == ",wp" or lower_text.startswith(",wp "):
        query = msg_text[len(",wp"):].strip()
        handle_item_search_command(client, message, query, "wp", "Weapon")

    elif lower_text == ",armor" or lower_text.startswith(",armor "):
        query = msg_text[len(",armor"):].strip()
        handle_item_search_command(client, message, query, "armor", "Armor")

    elif lower_text == ",add" or lower_text.startswith(",add "):
        query = msg_text[len(",add"):].strip()
        handle_item_search_command(client, message, query, "add", "Additional Gear")

    elif lower_text == ",ring" or lower_text.startswith(",ring "):
        query = msg_text[len(",ring"):].strip()
        handle_item_search_command(client, message, query, "ring", "Special Gear")

    elif lower_text == ",xtall" or lower_text.startswith(",xtall "):
        query = msg_text[len(",xtall"):].strip()
        handle_item_search_command(client, message, query, "xtall", "Crysta")

    elif lower_text == ",mats" or lower_text.startswith(",mats "):
        query = msg_text[len(",mats"):].strip()
        handle_item_search_command(client, message, query, "mats", "Material")

    elif lower_text == ",use" or lower_text.startswith(",use "):
        query = msg_text[len(",use"):].strip()
        handle_item_search_command(client, message, query, "use", "Item Konsumsi")

    elif lower_text == ",mob" or lower_text.startswith(",mob "):
        query = msg_text[len(",mob"):].strip()
        handle_monster_search_command(client, message, query, "mob", "Monster", None)

    elif lower_text == ",monster" or lower_text.startswith(",monster "):
        query = msg_text[len(",monster"):].strip()
        handle_monster_search_command(client, message, query, "mob", "Monster", None)

    elif lower_text == ",boss" or lower_text.startswith(",boss "):
        query = msg_text[len(",boss"):].strip()
        handle_monster_search_command(client, message, query, "boss", "Boss", "boss")

    elif lower_text == ",mboss" or lower_text.startswith(",mboss ") or lower_text == ",miniboss" or lower_text.startswith(",miniboss "):
        prefix = ",miniboss" if lower_text.startswith(",miniboss") else ",mboss"
        query = msg_text[len(prefix):].strip()
        handle_monster_search_command(client, message, query, "mboss", "Mini Boss", "mboss")


    elif lower_text == ",rute" or lower_text.startswith(",rute "):
        query = msg_text[len(",rute"):].strip()
        handle_crysta_route_command(client, message, query)

    elif lower_text == ",skill" or lower_text.startswith(",skill "):
        query = msg_text[len(",skill"):].strip()
        handle_skill_search_command(client, message, query)

    elif lower_text == ",regis" or lower_text.startswith(",regis "):
        query = msg_text[len(",regis"):].strip()
        handle_registlet_search_command(client, message, query)

    elif lower_text == ",buff" or lower_text.startswith(",buff "):
        query = msg_text[len(",buff"):].strip()
        client.reply_message(get_buff_response(query), message)

    elif lower_text == ",bahanmq" or lower_text.startswith(",bahanmq ") or lower_text == ",bahan_mq" or lower_text.startswith(",bahan_mq "):
        client.reply_message(MQ_TEXT, message)


    elif lower_text.startswith(",mqspam"):
        m_spam = re.match(r"^,mqspam(\d*)", lower_text)
        spam_num = 2
        if m_spam and m_spam.group(1):
            spam_num = max(2, min(20, int(m_spam.group(1))))
            raw_q = msg_text[len(m_spam.group(0)):].strip()
        else:
            raw_q = msg_text[len(",mqspam"):].strip()
            toks = raw_q.split()
            if toks and toks[0].isdigit() and int(toks[0]) in range(1, 21) and len(toks) > 1:
                spam_num = int(toks.pop(0))
                raw_q = " ".join(toks)
        client.reply_message(calculate_mq_exp(raw_q, spam_runs=spam_num), message)

    elif lower_text == ",mq" or lower_text.startswith(",mq ") or any(lower_text == p or lower_text.startswith(p + " ") for p in [",mqexp", ",calcmq", ",mqcalc"]):
        prefix = next((p for p in [",mqexp", ",calcmq", ",mqcalc", ",mq"] if lower_text.startswith(p)), ",mq")
        query = msg_text[len(prefix):].strip()
        client.reply_message(calculate_mq_exp(query), message)
    elif False:
        """



        query = msg_text[len(prefix):].strip()
        # removed duplicate




                break
        query = msg_text[len(prefix):].strip()
        # removed duplicate





            return


        """
    elif lower_text == ",statlist":
        client.reply_message(STATLIST_TEXT, message)


    elif lower_text == ",lvling" or lower_text.startswith(",lvling "):
        query = msg_text[len(",lvling"):].strip()
        handle_lvling_command(client, message, query)

    elif lower_text == ",bag":
        client.reply_message(TAS_TEXT, message)

    elif lower_text == ",sunk":
        client.reply_message(SUNK_TEXT, message)

    elif lower_text == ",mt" or lower_text.startswith(",mt ") or lower_text == ",maintenance" or lower_text.startswith(",maintenance "):
        query = ""
        if lower_text.startswith(",mt "):
            query = msg_text[len(",mt"):].strip()
        elif lower_text.startswith(",maintenance "):
            query = msg_text[len(",maintenance"):].strip()
        client.reply_message(fetch_toram_maintenance_info(query), message)

    elif lower_text == ",ava" or lower_text.startswith(",ava ") or lower_text == ",avatar" or lower_text.startswith(",avatar "):
        query = ""
        if lower_text.startswith(",ava "):
            query = msg_text[len(",ava"):].strip()
        elif lower_text.startswith(",avatar "):
            query = msg_text[len(",avatar"):].strip()
        handle_avatar_command(client, message, query)

    elif lower_text == ",boost" or lower_text.startswith(",boost "):
        query = msg_text[len(",boost"):].strip()
        client.reply_message(fetch_toram_boost_info(query), message)

    elif lower_text == ",ai" or lower_text.startswith(",ai "):
        query = msg_text[len(",ai"):].strip()
        handle_gemini_ai_command(client, message, query)

    elif lower_text == ",gemini" or lower_text.startswith(",gemini "):
        query = msg_text[len(",gemini"):].strip()
        handle_gemini_ai_command(client, message, query)

    elif lower_text == ",s" or lower_text == ",sticker":
        handle_sticker_command(client, message)

    elif lower_text == ",setmeme" or lower_text.startswith(",setmeme "):
        query = msg_text[len(",setmeme"):].strip()
        handle_setmeme_command(client, message, query)

    elif lower_text == ",smeme" or lower_text.startswith(",smeme "):
        query = msg_text[len(",smeme"):].strip()
        handle_setmeme_command(client, message, query)

    elif lower_text == ",sm" or lower_text.startswith(",sm "):
        query = msg_text[len(",sm"):].strip()
        handle_setmeme_command(client, message, query)

    elif any(
        lower_text == p or lower_text.startswith(p + " ")
        for p in [
            ",tiktok", ",tt",
            ",facebook", ",fb",
            ",instagram", ",ig",
            ",dl"
        ]
    ):
        cmd_platform_map = [
            (",tiktok", "tiktok"), (",tt", "tiktok"),
            (",facebook", "facebook"), (",fb", "facebook"),
            (",instagram", "instagram"), (",ig", "instagram"),
            (",dl", None),
        ]
        matched_prefix = ",dl"
        matched_platform = None
        for p, plat_k in cmd_platform_map:
            if lower_text == p or lower_text.startswith(p + " "):
                matched_prefix = p
                matched_platform = plat_k
                break
        query = msg_text[len(matched_prefix):].strip()
        handle_media_download_command(client, message, query, platform_key=matched_platform, cmd_used=matched_prefix)
    elif False:
        """



                break
        query = msg_text[len(prefix):].strip()
        handle_media_download_command(client, message, query)

        """
    elif lower_text == ",music" or lower_text.startswith(",music ") or lower_text.startswith((",play ", ",lagu ")):
        prefix = next((p for p in [",play", ",lagu"] if lower_text.startswith(p)), ",music")

        query = msg_text[len(prefix):].strip()
        handle_music_command(client, message, query)
    elif False:
        """




                break
        query = msg_text[len(prefix):].strip()
        handle_music_command(client, message, query)

        """
    elif lower_text == ",dlmp3" or lower_text.startswith(",dlmp3 "):
        # Alias ,dlmp3 ke pencarian musik
        query = msg_text[len(",dlmp3"):].strip()
        handle_music_command(client, message, query)

if __name__ == "__main__":
    # Jalankan klien bot
    print(" Menghubungkan ke WhatsApp... Silakan scan QR code jika muncul di terminal.")
    client.connect()
