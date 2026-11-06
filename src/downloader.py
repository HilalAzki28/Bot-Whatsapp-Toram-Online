import re
import os
import time
import shutil
import tempfile
import subprocess
import urllib.parse
import requests
from bs4 import BeautifulSoup

try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

# Pastikan binary ffmpeg dari imageio_ffmpeg selalu terdeteksi di PATH (baik di Windows maupun Linux VPS)
try:
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    if ffmpeg_exe and os.path.exists(ffmpeg_exe):
        ffmpeg_dir = os.path.dirname(ffmpeg_exe)
        bin_name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
        target_ffmpeg = os.path.join(ffmpeg_dir, bin_name)
        if not os.path.exists(target_ffmpeg):
            try:
                shutil.copyfile(ffmpeg_exe, target_ffmpeg)
                if os.name != 'nt':
                    os.chmod(target_ffmpeg, 0o755)
            except Exception:
                pass
        if ffmpeg_dir not in os.environ.get('PATH', ''):
            os.environ['PATH'] = ffmpeg_dir + os.pathsep + os.environ.get('PATH', '')
except Exception:
    pass


def _get_ffmpeg_path() -> str | None:
    """Mendapatkan path binary ffmpeg yang valid di sistem atau dari imageio_ffmpeg."""
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    return None


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8',
    'Accept-Language': 'id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7',
}


def _http_get(url: str, headers: dict | None = None, timeout: int = 15):
    """Melakukan HTTP GET dengan memprioritaskan curl_cffi (Chrome TLS Impersonation) agar tembus Cloudflare di VPS."""
    req_headers = dict(HEADERS)
    if headers:
        req_headers.update(headers)
    try:
        from curl_cffi import requests as cffi_requests
        r = cffi_requests.get(url, headers=req_headers, impersonate="chrome120", timeout=timeout, verify=False, allow_redirects=True)
        if r.status_code == 200:
            return r
    except Exception:
        pass
    try:
        return requests.get(url, headers=req_headers, timeout=timeout, verify=False, allow_redirects=True)
    except Exception:
        return None


def _http_post(url: str, data: dict | None = None, json_data: dict | None = None, headers: dict | None = None, timeout: int = 15):
    """Melakukan HTTP POST dengan memprioritaskan curl_cffi (Chrome TLS Impersonation) agar tembus Cloudflare di VPS."""
    req_headers = dict(HEADERS)
    if headers:
        req_headers.update(headers)
    try:
        from curl_cffi import requests as cffi_requests
        r = cffi_requests.post(url, data=data, json=json_data, headers=req_headers, impersonate="chrome120", timeout=timeout, verify=False, allow_redirects=True)
        if r.status_code == 200:
            return r
    except Exception:
        pass
    try:
        return requests.post(url, data=data, json=json_data, headers=req_headers, timeout=timeout, verify=False, allow_redirects=True)
    except Exception:
        return None


def resolve_redirect_url(url: str) -> str:
    """Mendeteksi dan mengikuti redirect pada shortlink (vt.tiktok.com, fb.watch, facebook.com/share, youtu.be, instagram.com/share, pin.it dll.)"""
    try:
        url_lower = url.lower()
        shortlink_domains = [
            'vt.tiktok.com', 'vm.tiktok.com', 'tiktok.com/t/',
            'fb.watch', 'fb.com', 'facebook.com/share', 'm.facebook.com', 'l.facebook.com',
            'youtu.be', 'instagram.com/share', 't.co', 'bit.ly', 'tinyurl.com',
            'pin.it', 's.snackvideo.com', 'capcut.com/t/'
        ]
        if any(s in url_lower for s in shortlink_domains):
            try:
                from curl_cffi import requests as cffi_requests
                r = cffi_requests.get(url, headers=HEADERS, impersonate="chrome120", allow_redirects=True, timeout=10, verify=False)
                if r.url and r.url.startswith('http') and 'login' not in r.url.lower():
                    return r.url
            except Exception:
                pass
            resp = requests.get(url, headers=HEADERS, allow_redirects=True, stream=True, timeout=10, verify=False)
            final_url = resp.url
            resp.close()
            if final_url and final_url.startswith('http') and 'login' not in final_url.lower():
                return final_url
    except Exception:
        pass
    return url


def _is_valid_media_bytes(data: bytes | None) -> bool:
    """Memastikan bytes yang diunduh adalah file media asli (bukan halaman HTML/JSON error Cloudflare)."""
    if not data or len(data) < 5120:
        return False
    head = data[:64].lstrip().lower()
    if head.startswith((b'<!doctype', b'<html', b'<head', b'<script', b'<body', b'{"error', b'{"status":false', b'{"code":', b'error')):
        return False
    return True


def _fetch_stream_bytes(url: str, custom_headers: dict | None = None, max_size: int = 45 * 1024 * 1024) -> bytes | None:
    """Mengunduh stream URL menjadi bytes dengan dukungan bypass Cloudflare (curl_cffi -> requests -> curl CLI)."""
    if not url or not isinstance(url, str) or not url.startswith('http'):
        return None
    req_headers = dict(HEADERS)
    if custom_headers:
        req_headers.update(custom_headers)

    # 1. Coba melalui curl_cffi (Chrome TLS Impersonation)
    try:
        from curl_cffi import requests as cffi_requests
        resp = cffi_requests.get(url, headers=req_headers, impersonate="chrome120", timeout=45, verify=False, allow_redirects=True)
        if resp.status_code == 200 and resp.content:
            ctype = (resp.headers.get('Content-Type') or resp.headers.get('content-type') or '').lower()
            if 'text/html' not in ctype and 'application/json' not in ctype:
                if len(resp.content) <= max_size and _is_valid_media_bytes(resp.content):
                    return resp.content
    except Exception:
        pass

    # 2. Coba melalui requests.get stream
    try:
        resp = requests.get(url, headers=req_headers, stream=True, timeout=45, allow_redirects=True, verify=False)
        if resp.status_code == 200:
            ctype = resp.headers.get('Content-Type', '').lower()
            if 'text/html' not in ctype and 'application/json' not in ctype:
                clen = resp.headers.get('Content-Length')
                if not (clen and clen.isdigit() and int(clen) > max_size):
                    chunks = []
                    total = 0
                    for chunk in resp.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            chunks.append(chunk)
                            total += len(chunk)
                            if total > max_size:
                                chunks = []
                                break
                    resp.close()
                    if chunks:
                        data = b"".join(chunks)
                        if _is_valid_media_bytes(data):
                            return data
        resp.close()
    except Exception:
        pass

    # 3. Coba melalui curl CLI bawaan Linux VPS
    if shutil.which('curl'):
        try:
            cmd = ['curl', '-4', '-s', '-L', '-k', '--max-time', '45', '-A', req_headers['User-Agent']]
            if custom_headers and custom_headers.get('Referer'):
                cmd.extend(['-e', custom_headers['Referer']])
            cmd.append(url)
            res = subprocess.run(cmd, capture_output=True, timeout=50)
            if res.returncode == 0 and res.stdout and len(res.stdout) <= max_size and _is_valid_media_bytes(res.stdout):
                return res.stdout
        except Exception:
            pass

    return None


def detect_platform(url: str) -> str:
    url_lower = url.lower()
    if 'tiktok.com' in url_lower:
        return 'tiktok'
    elif 'facebook.com' in url_lower or 'fb.watch' in url_lower or 'fb.com' in url_lower:
        return 'facebook'
    elif 'instagram.com' in url_lower:
        return 'instagram'
    elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower or 't.co/' in url_lower:
        return 'twitter'
    elif 'pinterest.com' in url_lower or 'pin.it' in url_lower:
        return 'pinterest'
    elif 'threads.net' in url_lower or 'threads.com' in url_lower:
        return 'threads'
    elif 'capcut.com' in url_lower:
        return 'capcut'
    elif 'snackvideo.com' in url_lower or 'kwai.com' in url_lower:
        return 'snackvideo'
    elif 'spotify.com' in url_lower:
        return 'spotify'
    elif 'soundcloud.com' in url_lower:
        return 'soundcloud'
    elif 'bilibili.tv' in url_lower or 'bilibili.com' in url_lower or 'b23.tv' in url_lower:
        return 'bilibili'
    elif 'reddit.com' in url_lower or 'redd.it' in url_lower:
        return 'reddit'
    return 'generic'

def decode_snapsave(html_code: str):
    """Unpack JavaScript obfuscation used by SnapSave."""
    try:
        pattern = r'\(\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)'
        match = re.search(pattern, html_code)
        if not match:
            return None
        
        h, u, n, t, e, r = match.groups()
        u, t, e, r = int(u), int(t), int(e), int(r)
        
        def decode_base(d, base_e, base_f):
            charset = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/"
            h_set = charset[:base_e]
            i_set = charset[:base_f]
            j = 0
            for c, b in enumerate(reversed(d)):
                idx = h_set.find(b)
                if idx != -1:
                    j += idx * (base_e ** c)
            k = ""
            while j > 0:
                k = i_set[j % base_f] + k
                j = (j - (j % base_f)) // base_f
            return k or "0"
            
        res = ""
        i = 0
        while i < len(h):
            s = ""
            while i < len(h) and h[i] != n[e]:
                s += h[i]
                i += 1
            for j in range(len(n)):
                s = s.replace(n[j], str(j))
            try:
                res += chr(int(decode_base(s, e, 10)) - t)
            except Exception:
                pass
            i += 1
        return res
    except Exception:
        return None

def find_cookie_file() -> str | None:
    """Mencari file cookie secara cerdas (case-insensitive, mendukung www.youtube.com_cookies.txt, cookies.txt.txt dll.)"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    cwd = os.getcwd()
    home = os.path.expanduser("~")

    search_dirs = [cwd, project_root, script_dir, home, "/root", "/root/ditdut-wa-bot", os.path.join(home, "ditdut-wa-bot")]
    seen_dirs = set()

    for s_dir in search_dirs:
        if not s_dir or not os.path.isdir(s_dir):
            continue
        try:
            real_s_dir = os.path.realpath(s_dir)
            if real_s_dir in seen_dirs:
                continue
            seen_dirs.add(real_s_dir)

            for fname in os.listdir(real_s_dir):
                fl = fname.lower()
                if "cookie" in fl and (fl.endswith(".txt") or fl.endswith(".netscape") or fl.endswith(".dat")):
                    full_p = os.path.join(real_s_dir, fname)
                    if os.path.isfile(full_p) and os.path.getsize(full_p) > 20:
                        return full_p
        except Exception:
            pass
    return None

def is_valid_cookie_file(cookie_path: str) -> bool:
    """Cek apakah file cookie memuat sesi login Google/YouTube yang valid (bukan sekadar komentar header kosong/sesi tamu)"""
    try:
        if not os.path.isfile(cookie_path) or os.path.getsize(cookie_path) < 100:
            return False
        with open(cookie_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            # Wajib memuat token otentikasi login akun Google yang sebenarnya (termasuk cookie #HttpOnly_)
            auth_tokens = ['LOGIN_INFO', 'SAPISID', 'SSID', 'HSID', '__Secure-1PSID', '__Secure-3PSID', 'SID']
            return any(k in content for k in auth_tokens)
    except Exception:
        return False

class _SilentYtdlLogger:
    """Logger hening agar yt-dlp tidak mencetak spam ERROR ke terminal saat mencoba jalur fallback."""
    def debug(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        pass


def download_via_ytdlp(url: str, is_audio: bool = False, default_title: str = "Media") -> dict:
    """Mengunduh media menggunakan yt-dlp secara lokal dengan dukungan multi-client & proteksi cookies."""
    try:
        import yt_dlp

        temp_dir = tempfile.gettempdir()
        ffmpeg_bin = _get_ffmpeg_path()
        has_ffmpeg = ffmpeg_bin is not None

        # Format selector:
        # Untuk video: utamakan codec H.264 (avc) + AAC (mp4a) agar 100% langsung playable di WhatsApp
        if is_audio:
            if has_ffmpeg:
                ydl_format = 'bestaudio/best'
            else:
                ydl_format = 'bestaudio[ext=m4a]/bestaudio/best'
        else:
            if has_ffmpeg:
                ydl_format = (
                    'bestvideo[height<=720][vcodec^=avc]+bestaudio[acodec^=mp4a]/'
                    'bestvideo[height<=720][vcodec^=avc]+bestaudio/'
                    '18/best[height<=720][ext=mp4]/'
                    'bestvideo[height<=720]+bestaudio/best[height<=720]/best'
                )
            else:
                ydl_format = '18/best[height<=720][ext=mp4]/best[ext=mp4]/best'

        js_runtimes = {}
        if shutil.which("node"):
            js_runtimes["node"] = {}
        elif shutil.which("deno"):
            js_runtimes["deno"] = {}

        is_yt = ("youtube.com" in url.lower() or "youtu.be" in url.lower() or url.lower().startswith("ytsearch"))
        cookie_file = find_cookie_file() if is_yt else None
        has_valid_cookie = bool(cookie_file and is_valid_cookie_file(cookie_file))

        # Susun daftar percobaan (attempts) secara terpisah per client:
        # Jika digabung dalam 1 list dan client pertama gagal karena bot-check, yt-dlp langsung berhenti tanpa mencoba client berikutnya.
        attempts = []
        if is_yt:
            attempts.append({"use_cookie": False, "clients": ['tv_embedded']})
            attempts.append({"use_cookie": False, "clients": ['android_vr']})
            attempts.append({"use_cookie": False, "clients": ['ios']})
            attempts.append({"use_cookie": False, "clients": ['mweb']})
            if has_valid_cookie:
                attempts.append({"use_cookie": True, "clients": ['tv', 'mweb', 'web']})
        else:
            attempts.append({"use_cookie": False, "clients": None})

        last_error = "Media tidak ditemukan"
        for idx, attempt in enumerate(attempts):
            temp_cookie_path = None
            try:
                out_template = os.path.join(temp_dir, f"ytdl_%(id)s_{int(time.time())}_{idx}.%(ext)s")
                ydl_opts = {
                    'format': ydl_format,
                    'outtmpl': out_template,
                    'noplaylist': True,
                    'quiet': True,
                    'no_warnings': True,
                    'nocheckcertificate': True,
                    'geo_bypass': True,
                    'logger': _SilentYtdlLogger(),
                    'source_address': '0.0.0.0',
                    'http_headers': HEADERS,
                }

                if ffmpeg_bin:
                    ydl_opts['ffmpeg_location'] = ffmpeg_bin

                if attempt["clients"]:
                    ydl_opts['extractor_args'] = {'youtube': {'player_client': attempt["clients"]}}

                if js_runtimes:
                    ydl_opts['js_runtimes'] = js_runtimes

                if not is_audio and has_ffmpeg:
                    ydl_opts['merge_output_format'] = 'mp4'
                    ydl_opts['postprocessor_args'] = {'merger': ['-movflags', '+faststart']}

                if is_audio and has_ffmpeg:
                    ydl_opts['postprocessors'] = [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]

                if attempt["use_cookie"] and cookie_file:
                    temp_cookie_path = os.path.join(temp_dir, f"ytdl_cookie_copy_{int(time.time())}_{idx}.txt")
                    shutil.copy2(cookie_file, temp_cookie_path)
                    ydl_opts['cookiefile'] = temp_cookie_path

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        continue

                    actual_info = info['entries'][0] if ('entries' in info and info['entries']) else info
                    if not actual_info:
                        continue

                    filename = ydl.prepare_filename(actual_info)
                    if not os.path.exists(filename):
                        base, _ = os.path.splitext(filename)
                        for possible_ext in ['.mp3', '.m4a', '.mp4', '.webm', '.mkv', '.ogg', '.opus']:
                            if os.path.exists(base + possible_ext):
                                filename = base + possible_ext
                                break

                    if not os.path.exists(filename):
                        continue

                    title = actual_info.get('title') or default_title
                    ext = filename.split('.')[-1].lower()
                    if ext == 'mp3':
                        mimetype = 'audio/mpeg'
                    elif ext in ['m4a', 'aac']:
                        mimetype = 'audio/mp4'
                    elif ext in ['ogg', 'opus']:
                        mimetype = 'audio/ogg'
                    elif is_audio:
                        mimetype = 'audio/mp4'
                    else:
                        mimetype = 'video/mp4'

                    with open(filename, 'rb') as f:
                        media_bytes = f.read()

                    try:
                        os.remove(filename)
                    except Exception:
                        pass

                    if media_bytes and len(media_bytes) > 1000:
                        return {
                            "status": True,
                            "title": title,
                            "media_bytes": media_bytes,
                            "type": "audio" if is_audio else "video",
                            "filename": f"download.{ext}",
                            "mimetype": mimetype,
                            "duration": int(actual_info.get('duration') or 0)
                        }
            except Exception as e_att:
                last_error = str(e_att)
            finally:
                if temp_cookie_path and os.path.exists(temp_cookie_path):
                    try:
                        os.remove(temp_cookie_path)
                    except Exception:
                        pass

        err_str = last_error.lower()
        if not has_ffmpeg and ("requested format is not available" in err_str or "ffmpeg is not installed" in err_str):
            return {
                "status": False,
                "error": (
                    "Video memerlukan ffmpeg di VPS untuk menggabungkan audio dan video.\n\n"
                    "💡 *Solusi (Jalankan di terminal VPS):*\n"
                    "`sudo apt update && sudo apt install -y ffmpeg`"
                )
            }
        return {"status": False, "error": last_error}
    except Exception as e:
        return {"status": False, "error": str(e)}


def _is_webpage_or_image_url(u: str) -> bool:
    """Memfilter URL yang hanya berupa halaman web atau gambar thumbnail, bukan stream video/audio."""
    ul = u.lower()
    bad_patterns = [
        "youtube.com/watch", "youtube.com/shorts", "youtube.com/@", "youtube.com/channel",
        "youtu.be/", "tiktok.com/@", "vt.tiktok.com", "vm.tiktok.com",
        "instagram.com/p/", "instagram.com/reel/", "instagram.com/tv/",
        "facebook.com/share", "facebook.com/watch", "fb.watch/",
        "twitter.com/", "x.com/", "threads.net/@", "pinterest.com/pin/", "pin.it/",
        "open.spotify.com/track", "soundcloud.com/",
        ".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg", "ytimg.com", "ggpht.com", "avatars"
    ]
    return any(bp in ul for bp in bad_patterns)


def _extract_all_dl_urls_from_json(obj) -> list[str]:
    """Mengekstrak seluruh kandidat URL unduhan media (CDN) dari struktur JSON API secara rekursif."""
    found = []

    def _walk(node):
        if isinstance(node, dict):
            # 1. Periksa sub-objek utama terlebih dahulu (download, data, result, media)
            for priority_sub in ["download", "downloads", "media", "video", "audio", "data", "result", "urls"]:
                if priority_sub in node and isinstance(node[priority_sub], (dict, list)):
                    _walk(node[priority_sub])

            # 2. Periksa kunci string URL unduhan
            for k in ["dl", "download_url", "dlink", "downloadUrl", "hdplay", "play", "hd", "sd", "video_url", "audio_url", "mp4", "mp3", "music", "video", "audio", "link", "url"]:
                val = node.get(k)
                if isinstance(val, str) and val.startswith("http") and not _is_webpage_or_image_url(val):
                    if val not in found:
                        found.append(val)

            # 3. Telusuri sisa kunci kecuali metadata non-media
            for k, val in node.items():
                if k in ["thumbnail", "thumb", "image", "cover", "avatar", "author", "channel", "owner", "user", "metadata"]:
                    continue
                if isinstance(val, (dict, list)):
                    _walk(val)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(obj)
    # Prioritaskan URL CDN non-googlevideo.com terlebih dahulu (karena tidak terkena IP-lock)
    cdn_urls = [u for u in found if "googlevideo.com" not in u.lower()]
    gvideo_urls = [u for u in found if "googlevideo.com" in u.lower()]
    return cdn_urls + gvideo_urls


def _extract_title_from_json(obj) -> str:
    """Mencari judul media dari struktur JSON API."""
    if isinstance(obj, dict):
        for k in ["title", "caption", "desc", "description", "name"]:
            val = obj.get(k)
            if isinstance(val, str) and val.strip():
                return val.strip()[:100]
        for k in ["data", "result", "metadata", "meta", "info", "detail"]:
            sub = obj.get(k)
            if isinstance(sub, dict):
                t = _extract_title_from_json(sub)
                if t:
                    return t
    return ""


def download_tiktok(url: str, is_audio: bool = False) -> dict:
    """Mengunduh video/audio TikTok tanpa watermark (TikWM -> TiklyDown -> Multi-API -> yt-dlp -> SaveFrom)"""
    real_url = resolve_redirect_url(url)

    # 1. Jalur Utama: TikWM API (via _http_post dengan bypass Cloudflare)
    try:
        api_url = "https://www.tikwm.com/api/"
        data = None
        for _ in range(2):
            r = _http_post(api_url, data={"url": real_url, "hd": 1}, headers={"Referer": "https://www.tikwm.com/"}, timeout=12)
            if r is not None and r.status_code == 200:
                data = r.json()
                if data.get("code") != 0 and "1 request/second" in str(data.get("msg")):
                    time.sleep(1.2)
                    continue
                break

        if data and data.get("code") == 0:
            d = data.get("data", {})
            title = d.get("title") or "TikTok Video"
            duration = int(d.get("duration") or 0)

            if is_audio:
                audio_url = d.get("music") or d.get("play")
                if audio_url:
                    if audio_url.startswith("/"):
                        audio_url = "https://www.tikwm.com" + audio_url
                    m_bytes = _fetch_stream_bytes(audio_url, custom_headers={"Referer": "https://www.tikwm.com/"})
                    if m_bytes:
                        return {
                            "status": True,
                            "title": title,
                            "media_bytes": m_bytes,
                            "url": audio_url,
                            "type": "audio",
                            "filename": f"tiktok_{d.get('id', 'audio')}.mp3",
                            "mimetype": "audio/mpeg",
                            "duration": duration
                        }
            else:
                for v_key in ["play", "hdplay", "wmplay"]:
                    video_url = d.get(v_key)
                    if not video_url:
                        continue
                    if video_url.startswith("/"):
                        video_url = "https://www.tikwm.com" + video_url
                    m_bytes = _fetch_stream_bytes(video_url, custom_headers={"Referer": "https://www.tikwm.com/"})
                    if m_bytes:
                        return {
                            "status": True,
                            "title": title,
                            "media_bytes": m_bytes,
                            "url": video_url,
                            "type": "video",
                            "filename": f"tiktok_{d.get('id', 'video')}.mp4",
                            "mimetype": "video/mp4",
                            "duration": duration
                        }
    except Exception:
        pass

    # 2. Jalur Cadangan 1: Multi-Provider TikTok APIs (TiklyDown, Siputzx, Ryzendesu, Vreden, Agatz)
    clean_u = urllib.parse.quote(real_url, safe='')
    tt_apis = [
        f"https://api.tiklydown.eu.org/api/download?url={clean_u}",
        f"https://api.siputzx.my.id/api/d/tiktok?url={clean_u}",
        f"https://api.ryzendesu.vip/api/downloader/ttdl?url={clean_u}",
        f"https://api.vreden.my.id/api/tiktok?url={clean_u}",
        f"https://api.agatz.xyz/api/tiktok?url={clean_u}",
    ]
    for api_u in tt_apis:
        try:
            r = _http_get(api_u, timeout=14)
            if r is not None and r.status_code == 200:
                jdata = r.json()
                cand_urls = _extract_all_dl_urls_from_json(jdata)
                for cu in cand_urls[:3]:
                    m_bytes = _fetch_stream_bytes(cu)
                    if m_bytes:
                        title = _extract_title_from_json(jdata) or "TikTok Video"
                        return {
                            "status": True,
                            "title": title,
                            "media_bytes": m_bytes,
                            "url": cu,
                            "type": "audio" if is_audio else "video",
                            "filename": "tiktok.mp3" if is_audio else "tiktok.mp4",
                            "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                        }
        except Exception:
            continue

    # 3. Jalur Cadangan 2: yt-dlp lokal
    res_yt = download_via_ytdlp(real_url, is_audio=is_audio, default_title="TikTok Video")
    if res_yt.get("status"):
        return res_yt

    # 4. Jalur Cadangan 3: SaveFrom API
    res_sf = download_savefrom(real_url, is_audio=is_audio, default_title="TikTok Video")
    if res_sf.get("status"):
        return res_sf

    return {"status": False, "error": res_yt.get("error") or res_sf.get("error") or "Gagal memproses video TikTok dari link tersebut"}


def download_facebook(url: str, is_audio: bool = False) -> dict:
    """Mengunduh video/audio Facebook (SnapSave -> Multi-API -> Direct FB Scraper -> yt-dlp -> SaveFrom)"""
    real_url = resolve_redirect_url(url)

    # 1. Jalur Utama: SnapSave (dengan _http_post curl_cffi agar tembus Cloudflare di VPS)
    for target_fb_url in ([real_url, url] if real_url != url else [real_url]):
        try:
            req_headers = {
                'Origin': 'https://snapsave.app',
                'Referer': 'https://snapsave.app/'
            }
            r = _http_post('https://snapsave.app/action.php?lang=id', data={'url': target_fb_url}, headers=req_headers, timeout=14)
            if r is not None and r.status_code == 200:
                unpacked = decode_snapsave(r.text)
                if unpacked:
                    soup = BeautifulSoup(unpacked, 'html.parser')
                    links = []
                    for a in soup.find_all('a', href=True):
                        href = a['href'].replace('\\"', '').replace('"', '').strip()
                        if href.startswith('http') and not _is_webpage_or_image_url(href):
                            links.append(href)
                    for dl_link in links[:4]:
                        m_bytes = _fetch_stream_bytes(dl_link, custom_headers={'Referer': 'https://snapsave.app/'})
                        if m_bytes:
                            return {
                                "status": True,
                                "title": "Facebook Video",
                                "media_bytes": m_bytes,
                                "url": dl_link,
                                "type": "audio" if is_audio else "video",
                                "filename": "facebook_audio.mp3" if is_audio else "facebook_video.mp4",
                                "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                            }
        except Exception:
            pass

    # 2. Jalur Cadangan 1: Multi-Provider Facebook Downloader APIs
    for target_fb_url in ([real_url, url] if real_url != url else [real_url]):
        clean_u = urllib.parse.quote(target_fb_url, safe='')
        fb_apis = [
            f"https://api.siputzx.my.id/api/d/facebook?url={clean_u}",
            f"https://api.ryzendesu.vip/api/downloader/fbdl?url={clean_u}",
            f"https://api.vreden.my.id/api/fbdl?url={clean_u}",
            f"https://api.agatz.xyz/api/facebook?url={clean_u}",
        ]
        for api_u in fb_apis:
            try:
                r = _http_get(api_u, timeout=15)
                if r is not None and r.status_code == 200:
                    jdata = r.json()
                    cand_urls = _extract_all_dl_urls_from_json(jdata)
                    for cu in cand_urls[:3]:
                        m_bytes = _fetch_stream_bytes(cu)
                        if m_bytes:
                            title = _extract_title_from_json(jdata) or "Facebook Video"
                            return {
                                "status": True,
                                "title": title,
                                "media_bytes": m_bytes,
                                "url": cu,
                                "type": "audio" if is_audio else "video",
                                "filename": "facebook_audio.mp3" if is_audio else "facebook_video.mp4",
                                "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                            }
            except Exception:
                continue

    # 3. Jalur Cadangan 2: Direct Facebook HTML Stream Extractor (playable_url / hd_src / sd_src)
    try:
        r_page = _http_get(real_url, headers={'Accept': 'text/html,application/xhtml+xml'}, timeout=12)
        if r_page is not None and r_page.status_code == 200 and r_page.text:
            html_txt = r_page.text
            fb_patterns = [
                r'"playable_url_quality_hd"\s*:\s*"([^"]+)"',
                r'"browser_native_hd_url"\s*:\s*"([^"]+)"',
                r'"hd_src_no_ratelimit"\s*:\s*"([^"]+)"',
                r'"hd_src"\s*:\s*"([^"]+)"',
                r'"playable_url"\s*:\s*"([^"]+)"',
                r'"browser_native_sd_url"\s*:\s*"([^"]+)"',
                r'"sd_src_no_ratelimit"\s*:\s*"([^"]+)"',
                r'"sd_src"\s*:\s*"([^"]+)"',
            ]
            for pat in fb_patterns:
                m = re.search(pat, html_txt)
                if m:
                    raw_vurl = m.group(1).replace('\\/', '/').encode('utf-8').decode('unicode_escape')
                    if raw_vurl.startswith('http'):
                        m_bytes = _fetch_stream_bytes(raw_vurl)
                        if m_bytes:
                            return {
                                "status": True,
                                "title": "Facebook Video",
                                "media_bytes": m_bytes,
                                "url": raw_vurl,
                                "type": "audio" if is_audio else "video",
                                "filename": "facebook_audio.mp3" if is_audio else "facebook_video.mp4",
                                "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                            }
    except Exception:
        pass

    # 4. Jalur Cadangan 3: yt-dlp lokal
    res_yt = download_via_ytdlp(real_url, is_audio=is_audio, default_title="Facebook Video")
    if res_yt.get("status"):
        return res_yt

    # 5. Jalur Cadangan 4: SaveFrom API
    res_sf = download_savefrom(real_url, is_audio=is_audio, default_title="Facebook Video")
    if res_sf.get("status"):
        return res_sf

    return {"status": False, "error": res_yt.get("error") or res_sf.get("error") or "Gagal memproses video Facebook dari link tersebut"}


def clean_youtube_url(url: str) -> str:
    """Bersihkan parameter playlist/radio (&list=RDMM...) serta normalisasi YouTube Shorts/youtu.be."""
    try:
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        if 'v' in qs and qs['v']:
            return f"https://www.youtube.com/watch?v={qs['v'][0]}"
        if 'youtu.be' in parsed.netloc:
            vid_id = parsed.path.strip('/').split('/')[0].split('?')[0]
            if vid_id:
                return f"https://www.youtube.com/watch?v={vid_id}"
        if '/shorts/' in parsed.path:
            vid_id = parsed.path.split('/shorts/')[1].split('/')[0].split('?')[0]
            if vid_id:
                return f"https://www.youtube.com/watch?v={vid_id}"
    except Exception:
        pass
    return url


def extract_youtube_id(url: str) -> str:
    """Mengekstrak 11 karakter Video ID dari URL YouTube."""
    try:
        clean_u = clean_youtube_url(url)
        m = re.search(r'(?:v=|/shorts/|youtu\.be/)([a-zA-Z0-9_-]{11})', clean_u)
        if m:
            return m.group(1)
    except Exception:
        pass
    return ""


def get_youtube_video_title(url: str) -> str:
    """Mengambil judul asli video YouTube melalui oEmbed (tanpa terkena blokir bot)."""
    try:
        clean_u = urllib.parse.quote(url, safe='')
        r = _http_get(f"https://www.youtube.com/oembed?url={clean_u}&format=json", timeout=6)
        if r is not None and r.status_code == 200:
            return r.json().get("title") or ""
    except Exception:
        pass
    return ""


def download_youtube_cdn_apis(url: str, is_audio: bool = False, default_title: str = "YouTube Media") -> dict:
    """Mengunduh video/audio YouTube melalui API Konverter berbasis CDN & Proxy Invidious/Piped (bebas dari IP-lock googlevideo.com)."""
    clean_url = urllib.parse.quote(url, safe='')
    vid_id = extract_youtube_id(url)

    # 1. Jalur OceanSaver / Loader.to CDN API (Sangat stabil untuk VPS)
    # Untuk video, gunakan format 360 atau 480 terlebih dahulu agar konversi cepat (3-5 detik) & ukuran di bawah 45 MB
    formats_to_try = ["mp3"] if is_audio else ["360", "480", "720"]
    ocean_headers = {"Referer": "https://ddownr.com/", "Origin": "https://ddownr.com"}
    for fmt in formats_to_try:
        init_endpoints = [
            ("https://p.oceansaver.in/ajax/download.php", "https://p.oceansaver.in/ajax/progress.php"),
            ("https://p.savenow.to/ajax/download.php", "https://p.savenow.to/ajax/progress"),
        ]
        for init_base, prog_base in init_endpoints:
            try:
                init_url = f"{init_base}?button=1&start=1&end=1&format={fmt}&iframe_source=https://allinonedownloader.com/&url={clean_url}"
                r = _http_get(init_url, headers=ocean_headers, timeout=10)
                if r is not None and r.status_code == 200:
                    data = r.json()
                    job_id = data.get("id")
                    title = data.get("title") or data.get("info", {}).get("title") or default_title
                    if job_id:
                        for _ in range(15):
                            time.sleep(1.4)
                            pr = _http_get(f"{prog_base}?id={job_id}", headers=ocean_headers, timeout=8)
                            if pr is not None and pr.status_code == 200:
                                pdata = pr.json()
                                dl_url = pdata.get("download_url")
                                if dl_url and (pdata.get("success") == 1 or int(pdata.get("progress") or 0) >= 1000):
                                    m_bytes = _fetch_stream_bytes(dl_url, custom_headers=ocean_headers)
                                    if m_bytes:
                                        return {
                                            "status": True,
                                            "title": title,
                                            "media_bytes": m_bytes,
                                            "url": dl_url,
                                            "type": "audio" if is_audio else "video",
                                            "filename": "download.mp3" if is_audio else "download.mp4",
                                            "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                                        }
                                    break
                                if str(pdata.get("text", "")).lower() in ["error", "failed", "no file"]:
                                    break
                        break
            except Exception:
                continue

    # 2. Jalur Multi-Provider YouTube CDN REST APIs (Siputzx, Ryzendesu, Vreden, Agatz)
    if is_audio:
        api_endpoints = [
            f"https://api.siputzx.my.id/api/d/ytmp3?url={clean_url}",
            f"https://api.ryzendesu.vip/api/downloader/ytmp3?url={clean_url}",
            f"https://api.vreden.my.id/api/ytmp3?url={clean_url}",
            f"https://api.agatz.xyz/api/ytmp3?url={clean_url}",
            f"https://api.siputzx.my.id/api/d/youtube?url={clean_url}",
        ]
    else:
        api_endpoints = [
            f"https://api.siputzx.my.id/api/d/ytmp4?url={clean_url}",
            f"https://api.ryzendesu.vip/api/downloader/ytmp4?url={clean_url}",
            f"https://api.vreden.my.id/api/ytmp4?url={clean_url}",
            f"https://api.agatz.xyz/api/ytmp4?url={clean_url}",
            f"https://api.siputzx.my.id/api/d/youtube?url={clean_url}",
        ]

    for api_url in api_endpoints:
        try:
            r = _http_get(api_url, timeout=15)
            if r is not None and r.status_code == 200:
                data = r.json()
                cand_urls = _extract_all_dl_urls_from_json(data)
                for dl_url in cand_urls[:3]:
                    m_bytes = _fetch_stream_bytes(dl_url)
                    if m_bytes:
                        title = _extract_title_from_json(data) or get_youtube_video_title(url) or default_title
                        return {
                            "status": True,
                            "title": title,
                            "media_bytes": m_bytes,
                            "url": dl_url,
                            "type": "audio" if is_audio else "video",
                            "filename": "download.mp3" if is_audio else "download.mp4",
                            "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                        }
        except Exception:
            continue

    # 3. Jalur Invidious Local Proxy Stream (Mem-proxy stream langsung dari server Invidious tanpa IP-lock)
    if vid_id:
        inv_instances = [
            "https://inv.nadeko.net",
            "https://invidious.nerdvpn.de",
            "https://inv.tux.pizza",
            "https://yewtu.be",
        ]
        for inst in inv_instances:
            try:
                if not is_audio:
                    # itag=18 adalah stream MP4 360p (Video H.264 + Audio AAC menyatu)
                    direct_proxy_url = f"{inst}/latest_version?id={vid_id}&itag=18&local=true"
                    m_bytes = _fetch_stream_bytes(direct_proxy_url)
                    if m_bytes:
                        title = get_youtube_video_title(url) or default_title
                        return {
                            "status": True,
                            "title": title,
                            "media_bytes": m_bytes,
                            "url": direct_proxy_url,
                            "type": "video",
                            "filename": "download.mp4",
                            "mimetype": "video/mp4"
                        }
                else:
                    direct_audio_url = f"{inst}/latest_version?id={vid_id}&itag=140&local=true"
                    m_bytes = _fetch_stream_bytes(direct_audio_url)
                    if m_bytes:
                        title = get_youtube_video_title(url) or default_title
                        return {
                            "status": True,
                            "title": title,
                            "media_bytes": m_bytes,
                            "url": direct_audio_url,
                            "type": "audio",
                            "filename": "download.m4a",
                            "mimetype": "audio/mp4"
                        }
            except Exception:
                continue

    return {"status": False, "error": "Gagal mengunduh dari CDN YouTube"}


def resolve_fast_song_query(query: str) -> str:
    """Mencari nama penyanyi dan judul lagu resmi secara instan (<0.4 detik) via iTunes / Deezer Search API."""
    try:
        clean_q = urllib.parse.quote_plus(query.strip())
        r = _http_get(f"https://itunes.apple.com/search?term={clean_q}&media=music&entity=song&limit=1", timeout=2.5)
        if r is not None and r.status_code == 200:
            results = r.json().get("results") or []
            if results:
                artist = (results[0].get("artistName") or "").strip()
                track = (results[0].get("trackName") or "").strip()
                if artist and track:
                    return f"{artist} - {track}"
    except Exception:
        pass
    try:
        clean_q = urllib.parse.quote_plus(query.strip())
        r = _http_get(f"https://api.deezer.com/search?q={clean_q}&limit=1", timeout=2.5)
        if r is not None and r.status_code == 200:
            data = r.json().get("data") or []
            if data:
                artist = (data[0].get("artist", {}).get("name") or "").strip()
                track = (data[0].get("title") or "").strip()
                if artist and track:
                    return f"{artist} - {track}"
    except Exception:
        pass
    return ""


def download_soundcloud_music(query: str) -> dict:
    """Mencari dan mengunduh lagu penuh dari SoundCloud via yt-dlp secara kilat (2-4 detik tanpa re-encode ulang)."""
    try:
        import yt_dlp

        clean_query = re.sub(
            r'\(.*?\)|\[.*?\]|official\s*music\s*video|official\s*video|official\s*audio|lyric\s*video|lirik',
            '',
            query,
            flags=re.IGNORECASE
        ).strip()
        if not clean_query:
            clean_query = query.strip()

        temp_dir = tempfile.gettempdir()
        ffmpeg_bin = _get_ffmpeg_path()
        out_template = os.path.join(temp_dir, f"scdl_%(id)s_{int(time.time())}.%(ext)s")

        # 1. Pencarian cepat metadata (extract_flat='in_playlist' hanya 1 request API ~0.3 detik, bukan 5x ekstraksi penuh)
        flat_opts = {
            'extract_flat': 'in_playlist',
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'logger': _SilentYtdlLogger(),
            'source_address': '0.0.0.0',
            'socket_timeout': 6,
        }

        target_sc_url = None
        flat_title = None
        flat_dur = 0
        with yt_dlp.YoutubeDL(flat_opts) as ydl_flat:
            search_info = ydl_flat.extract_info(f"scsearch5:{clean_query}", download=False)
            entries = (search_info or {}).get("entries") or []
            if not entries:
                return {"status": False, "error": "Lagu tidak ditemukan di SoundCloud"}

            chosen_entry = None
            for entry in entries:
                if not entry:
                    continue
                dur = int(entry.get("duration") or 0)
                # Prioritaskan lagu utuh dengan durasi 55 detik s/d 15 menit (hindari preview 30 detik Go+)
                if 55 <= dur <= 900:
                    chosen_entry = entry
                    break
            if not chosen_entry:
                # Jika durasi tidak tercantum di flat search, pilih entry pertama
                chosen_entry = entries[0]

            target_sc_url = chosen_entry.get("url") or chosen_entry.get("webpage_url")
            flat_title = chosen_entry.get("title")
            flat_dur = int(chosen_entry.get("duration") or 0)

        if not target_sc_url:
            return {"status": False, "error": "URL lagu SoundCloud tidak valid"}

        # 2. Unduh stream MP3 asli SoundCloud secara langsung (tanpa FFmpegExtractAudio re-encode yang memakan waktu lama)
        dl_opts = {
            'format': 'http_mp3_1_0/hls_mp3_1_0/bestaudio[ext=mp3]/bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': out_template,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'concurrent_fragment_downloads': 4,
            'logger': _SilentYtdlLogger(),
            'source_address': '0.0.0.0',
            'socket_timeout': 8,
        }
        if ffmpeg_bin:
            dl_opts['ffmpeg_location'] = ffmpeg_bin

        with yt_dlp.YoutubeDL(dl_opts) as ydl_dl:
            dl_info = ydl_dl.extract_info(target_sc_url, download=True)
            if not dl_info:
                return {"status": False, "error": "Gagal mengunduh audio dari SoundCloud"}

            filename = ydl_dl.prepare_filename(dl_info)
            if not os.path.exists(filename):
                base, _ = os.path.splitext(filename)
                for possible_ext in ['.mp3', '.m4a', '.ogg', '.opus', '.wav']:
                    if os.path.exists(base + possible_ext):
                        filename = base + possible_ext
                        break

            if not os.path.exists(filename):
                return {"status": False, "error": "File audio hasil unduhan tidak ditemukan"}

            ext = filename.split('.')[-1].lower()
            mimetype = 'audio/mpeg' if ext == 'mp3' else ('audio/mp4' if ext in ['m4a', 'aac'] else 'audio/ogg')

            with open(filename, 'rb') as f:
                media_bytes = f.read()

            try:
                os.remove(filename)
            except Exception:
                pass

            if media_bytes and len(media_bytes) > 1000:
                return {
                    "status": True,
                    "title": dl_info.get("title") or flat_title or clean_query,
                    "media_bytes": media_bytes,
                    "type": "audio",
                    "filename": f"download.{ext}",
                    "mimetype": mimetype,
                    "duration": int(dl_info.get("duration") or flat_dur or 0)
                }
    except Exception as e:
        return {"status": False, "error": str(e)}
    return {"status": False, "error": "Gagal mengunduh dari SoundCloud"}


def download_youtube(url: str, is_audio: bool = False, skip_ytdlp: bool = False) -> dict:
    """Mengunduh video/audio YouTube (yt-dlp -> CDN APIs & Invidious Proxy -> SaveFrom -> Ummy -> SoundCloud Fallback untuk Audio)"""
    target_url = clean_youtube_url(url)

    # 1. Jalur Utama: yt-dlp lokal (multi-client & proteksi cookies)
    res_yt = {"status": False, "error": ""}
    if not skip_ytdlp:
        res_yt = download_via_ytdlp(target_url, is_audio=is_audio, default_title="YouTube Media")
        if res_yt.get("status"):
            return res_yt

    # 2. Jalur Cadangan 1: API Konverter berbasis CDN & Proxy (OceanSaver, Siputzx, Ryzendesu, Vreden, Agatz, Invidious)
    res_cdn = download_youtube_cdn_apis(target_url, is_audio=is_audio, default_title="YouTube Media")
    if res_cdn.get("status"):
        return res_cdn

    # 3. Jalur Cadangan 2: SaveFrom API
    res_sf = download_savefrom(target_url, is_audio=is_audio, default_title="YouTube Media")
    if res_sf.get("status"):
        return res_sf

    # 4. Jalur Cadangan 3: Ummy API
    try:
        clean_url = urllib.parse.quote(target_url, safe='')
        api_url = f"https://api.siputzx.my.id/api/d/ummy?url={clean_url}"
        r = _http_get(api_url, timeout=12)
        if r is not None and r.status_code == 200:
            data = r.json()
            if data.get("status"):
                meta = data.get("data", {}).get("meta", {})
                title = meta.get("title") or "YouTube Media"
                urls = data.get("data", {}).get("url", [])
                valid_urls = [u for u in urls if "sf-converter.com" not in u.get("url", "")]

                candidates = []
                if is_audio:
                    for u in valid_urls:
                        ext_u = str(u.get("ext", "")).lower()
                        name_u = str(u.get("name", "")).lower()
                        if u.get("audio") is True or "audio" in name_u or ext_u in ["m4a", "mp3", "opus", "aac"]:
                            if ext_u in ["m4a", "aac"]:
                                candidates.append((u.get("url"), "audio/mp4", "m4a"))
                            elif ext_u == "opus":
                                candidates.append((u.get("url"), "audio/ogg; codecs=opus", "opus"))
                            else:
                                candidates.append((u.get("url"), "audio/mpeg", "mp3"))
                else:
                    for u in valid_urls:
                        ext_u = str(u.get("ext", "")).lower()
                        durl = u.get("url", "")
                        quality = str(u.get("quality", ""))
                        if ext_u == "mp4" and ("360" in quality or "480" in quality or "720" in quality or "itag=18" in durl):
                            candidates.append((durl, "video/mp4", "mp4"))
                    for u in valid_urls:
                        ext_u = str(u.get("ext", "")).lower()
                        if ext_u == "mp4":
                            candidates.append((u.get("url"), "video/mp4", "mp4"))

                for cand_url, cand_mime, cand_ext in candidates:
                    if not cand_url:
                        continue
                    m_bytes = _fetch_stream_bytes(cand_url)
                    if m_bytes:
                        return {
                            "status": True,
                            "title": title,
                            "media_bytes": m_bytes,
                            "url": cand_url,
                            "type": "audio" if is_audio else "video",
                            "filename": f"download.{cand_ext}",
                            "mimetype": cand_mime
                        }
    except Exception:
        pass

    # 5. Jalur Cadangan 4 (Khusus Audio): Ambil judul video YouTube via oEmbed lalu unduh lagunya via SoundCloud
    if is_audio:
        yt_title = get_youtube_video_title(target_url)
        if yt_title:
            res_sc = download_soundcloud_music(yt_title)
            if res_sc.get("status"):
                res_sc["title"] = yt_title
                return res_sc

    err_yt = res_yt.get("error", "")
    if "confirm you're not a bot" in err_yt.lower() or "sign in" in err_yt.lower():
        return {
            "status": False,
            "error": (
                "YouTube mendeteksi IP server (*Sign in to confirm you're not a bot*) dan seluruh server CDN cadangan sedang sibuk.\n\n"
                "💡 *Solusi:* Perbarui file `cookies.txt` akun Google Anda di folder bot menggunakan Jendela Samaran (Incognito)."
            )
        }

    return {"status": False, "error": res_sf.get("error") or res_yt.get("error") or "Gagal mengunduh media dari YouTube"}


def download_instagram(url: str, is_audio: bool = False) -> dict:
    """Mengunduh video/audio Instagram Reels/Post (SnapSave -> Multi-API -> Embed Extractor -> yt-dlp -> SaveFrom)"""
    real_url = resolve_redirect_url(url)

    # 1. Jalur Utama: SnapSave (via _http_post curl_cffi)
    try:
        req_headers = {
            'Origin': 'https://snapsave.app',
            'Referer': 'https://snapsave.app/'
        }
        r = _http_post('https://snapsave.app/action.php?lang=id', data={'url': real_url}, headers=req_headers, timeout=14)
        if r is not None and r.status_code == 200:
            unpacked = decode_snapsave(r.text)
            if unpacked:
                soup = BeautifulSoup(unpacked, 'html.parser')
                links = []
                for a in soup.find_all('a', href=True):
                    href = a['href'].replace('\\"', '').replace('"', '').strip()
                    if href.startswith('http') and not _is_webpage_or_image_url(href):
                        links.append(href)
                for dl_link in links[:3]:
                    m_bytes = _fetch_stream_bytes(dl_link, custom_headers={'Referer': 'https://snapsave.app/'})
                    if m_bytes:
                        return {
                            "status": True,
                            "title": "Instagram Video",
                            "media_bytes": m_bytes,
                            "url": dl_link,
                            "type": "audio" if is_audio else "video",
                            "filename": "instagram_audio.mp3" if is_audio else "instagram_video.mp4",
                            "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                        }
    except Exception:
        pass

    # 2. Jalur Cadangan 1: Multi-Provider Instagram Downloader APIs
    clean_u = urllib.parse.quote(real_url, safe='')
    ig_apis = [
        f"https://api.siputzx.my.id/api/d/igdl?url={clean_u}",
        f"https://api.ryzendesu.vip/api/downloader/igdl?url={clean_u}",
        f"https://api.vreden.my.id/api/igdownload?url={clean_u}",
        f"https://api.agatz.xyz/api/instagram?url={clean_u}",
    ]
    for api_u in ig_apis:
        try:
            r = _http_get(api_u, timeout=15)
            if r is not None and r.status_code == 200:
                jdata = r.json()
                cand_urls = _extract_all_dl_urls_from_json(jdata)
                for cu in cand_urls[:3]:
                    m_bytes = _fetch_stream_bytes(cu)
                    if m_bytes:
                        title = _extract_title_from_json(jdata) or "Instagram Video"
                        return {
                            "status": True,
                            "title": title,
                            "media_bytes": m_bytes,
                            "url": cu,
                            "type": "audio" if is_audio else "video",
                            "filename": "instagram_audio.mp3" if is_audio else "instagram_video.mp4",
                            "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                        }
        except Exception:
            continue

    # 3. Jalur Cadangan 2: Direct Instagram Embed Page Extractor (Bebas Login)
    try:
        m_sc = re.search(r'instagram\.com/(?:reel|reels|p|tv)/([A-Za-z0-9_-]+)', real_url)
        if m_sc:
            shortcode = m_sc.group(1)
            embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
            r_emb = _http_get(embed_url, timeout=12)
            if r_emb is not None and r_emb.status_code == 200 and r_emb.text:
                m_vid = re.search(r'"video_url"\s*:\s*"([^"]+)"', r_emb.text)
                if m_vid:
                    v_url = m_vid.group(1).replace('\\/', '/').encode('utf-8').decode('unicode_escape')
                    m_bytes = _fetch_stream_bytes(v_url)
                    if m_bytes:
                        return {
                            "status": True,
                            "title": "Instagram Video",
                            "media_bytes": m_bytes,
                            "url": v_url,
                            "type": "audio" if is_audio else "video",
                            "filename": "instagram_audio.mp3" if is_audio else "instagram_video.mp4",
                            "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                        }
    except Exception:
        pass

    # 4. Jalur Cadangan 3: yt-dlp lokal
    res_yt = download_via_ytdlp(real_url, is_audio=is_audio, default_title="Instagram Video")
    if res_yt.get("status"):
        return res_yt

    # 5. Jalur Cadangan 4: SaveFrom API
    res_sf = download_savefrom(real_url, is_audio=is_audio, default_title="Instagram Video")
    if res_sf.get("status"):
        return res_sf

    return {"status": False, "error": res_yt.get("error") or res_sf.get("error") or "Gagal memproses video Instagram dari link tersebut"}


def download_twitter(url: str, is_audio: bool = False) -> dict:
    """Mengunduh video/audio dari Twitter / X (vxTwitter API -> fxTwitter API -> Multi-API -> yt-dlp -> SaveFrom)"""
    real_url = resolve_redirect_url(url)

    # 1. Jalur Utama: vxTwitter & fxTwitter JSON API (100% stabil & tanpa rate-limit untuk VPS)
    try:
        m_tw = re.search(r'(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)', real_url)
        if not m_tw:
            m_tw = re.search(r'status/(\d+)', real_url)
            tw_user, tw_id = ("i", m_tw.group(1)) if m_tw else (None, None)
        else:
            tw_user, tw_id = m_tw.group(1), m_tw.group(2)

        if tw_id:
            for api_tw in [f"https://api.vxtwitter.com/{tw_user}/status/{tw_id}", f"https://api.fxtwitter.com/{tw_user}/status/{tw_id}"]:
                try:
                    r = _http_get(api_tw, timeout=10)
                    if r is not None and r.status_code == 200:
                        data = r.json()
                        title = data.get("text") or data.get("tweet", {}).get("text") or "Twitter/X Video"
                        title = title.strip()[:80] or "Twitter/X Video"
                        media_list = data.get("media_extended") or data.get("tweet", {}).get("media", {}).get("videos") or data.get("tweet", {}).get("media", {}).get("all") or []
                        for m_item in media_list:
                            v_url = m_item.get("url")
                            if v_url and v_url.startswith("http") and (".mp4" in v_url or "video.twimg.com" in v_url):
                                m_bytes = _fetch_stream_bytes(v_url)
                                if m_bytes:
                                    return {
                                        "status": True,
                                        "title": title,
                                        "media_bytes": m_bytes,
                                        "url": v_url,
                                        "type": "audio" if is_audio else "video",
                                        "filename": "twitter_audio.mp3" if is_audio else "twitter_video.mp4",
                                        "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                                    }
                except Exception:
                    continue
    except Exception:
        pass

    # 2. Jalur Cadangan 1: Multi-Provider Twitter Downloader APIs
    clean_u = urllib.parse.quote(real_url, safe='')
    for api_u in [
        f"https://api.siputzx.my.id/api/d/twitter?url={clean_u}",
        f"https://api.ryzendesu.vip/api/downloader/twitter?url={clean_u}",
        f"https://api.agatz.xyz/api/twitter?url={clean_u}",
    ]:
        try:
            r = _http_get(api_u, timeout=14)
            if r is not None and r.status_code == 200:
                jdata = r.json()
                for cu in _extract_all_dl_urls_from_json(jdata)[:3]:
                    m_bytes = _fetch_stream_bytes(cu)
                    if m_bytes:
                        return {
                            "status": True,
                            "title": _extract_title_from_json(jdata) or "Twitter/X Video",
                            "media_bytes": m_bytes,
                            "url": cu,
                            "type": "audio" if is_audio else "video",
                            "filename": "twitter_audio.mp3" if is_audio else "twitter_video.mp4",
                            "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                        }
        except Exception:
            continue

    # 3. Jalur Cadangan 2: yt-dlp & SaveFrom
    res_yt = download_via_ytdlp(real_url, is_audio=is_audio, default_title="Twitter/X Video")
    if res_yt.get("status"):
        return res_yt
    return download_savefrom(real_url, is_audio=is_audio, default_title="Twitter/X Video")


def download_pinterest(url: str, is_audio: bool = False) -> dict:
    """Mengunduh video dari Pinterest (Direct Page Scraper -> Multi-API -> yt-dlp -> SaveFrom)"""
    real_url = resolve_redirect_url(url)

    # 1. Jalur Utama: Ekstraksi langsung stream v.pinimg.com/*.mp4 dari halaman Pinterest
    try:
        r = _http_get(real_url, timeout=12)
        if r is not None and r.status_code == 200 and r.text:
            mp4_matches = re.findall(r'https://v\d*\.pinimg\.com/videos/[^\s"\'\\]+\.mp4', r.text)
            for v_url in mp4_matches[:3]:
                m_bytes = _fetch_stream_bytes(v_url)
                if m_bytes:
                    return {
                        "status": True,
                        "title": "Pinterest Video",
                        "media_bytes": m_bytes,
                        "url": v_url,
                        "type": "audio" if is_audio else "video",
                        "filename": "pinterest.mp3" if is_audio else "pinterest.mp4",
                        "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                    }
    except Exception:
        pass

    # 2. Jalur Cadangan 1: Multi-Provider Pinterest APIs
    clean_u = urllib.parse.quote(real_url, safe='')
    for api_u in [
        f"https://api.siputzx.my.id/api/d/pinterest?url={clean_u}",
        f"https://api.agatz.xyz/api/pinterest?url={clean_u}",
        f"https://api.vreden.my.id/api/pin?url={clean_u}",
    ]:
        try:
            r = _http_get(api_u, timeout=14)
            if r is not None and r.status_code == 200:
                jdata = r.json()
                for cu in _extract_all_dl_urls_from_json(jdata)[:3]:
                    m_bytes = _fetch_stream_bytes(cu)
                    if m_bytes:
                        return {
                            "status": True,
                            "title": _extract_title_from_json(jdata) or "Pinterest Video",
                            "media_bytes": m_bytes,
                            "url": cu,
                            "type": "audio" if is_audio else "video",
                            "filename": "pinterest.mp3" if is_audio else "pinterest.mp4",
                            "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                        }
        except Exception:
            continue

    res_yt = download_via_ytdlp(real_url, is_audio=is_audio, default_title="Pinterest Video")
    if res_yt.get("status"):
        return res_yt
    return download_savefrom(real_url, is_audio=is_audio, default_title="Pinterest Video")


def download_threads(url: str, is_audio: bool = False) -> dict:
    """Mengunduh video dari Threads (Multi-API -> yt-dlp -> SaveFrom)"""
    real_url = resolve_redirect_url(url)
    clean_u = urllib.parse.quote(real_url, safe='')
    for api_u in [
        f"https://api.siputzx.my.id/api/d/threads?url={clean_u}",
        f"https://api.ryzendesu.vip/api/downloader/threads?url={clean_u}",
        f"https://api.agatz.xyz/api/threads?url={clean_u}",
    ]:
        try:
            r = _http_get(api_u, timeout=14)
            if r is not None and r.status_code == 200:
                jdata = r.json()
                for cu in _extract_all_dl_urls_from_json(jdata)[:3]:
                    m_bytes = _fetch_stream_bytes(cu)
                    if m_bytes:
                        return {
                            "status": True,
                            "title": _extract_title_from_json(jdata) or "Threads Video",
                            "media_bytes": m_bytes,
                            "url": cu,
                            "type": "audio" if is_audio else "video",
                            "filename": "threads.mp3" if is_audio else "threads.mp4",
                            "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                        }
        except Exception:
            continue

    res_yt = download_via_ytdlp(real_url, is_audio=is_audio, default_title="Threads Video")
    if res_yt.get("status"):
        return res_yt
    return download_savefrom(real_url, is_audio=is_audio, default_title="Threads Video")


def download_capcut(url: str, is_audio: bool = False) -> dict:
    """Mengunduh video template dari CapCut (Multi-API -> yt-dlp -> SaveFrom)"""
    real_url = resolve_redirect_url(url)
    clean_u = urllib.parse.quote(real_url, safe='')
    for api_u in [
        f"https://api.siputzx.my.id/api/d/capcut?url={clean_u}",
        f"https://api.ryzendesu.vip/api/downloader/capcut?url={clean_u}",
        f"https://api.vreden.my.id/api/capcut?url={clean_u}",
        f"https://api.agatz.xyz/api/capcut?url={clean_u}",
    ]:
        try:
            r = _http_get(api_u, timeout=14)
            if r is not None and r.status_code == 200:
                jdata = r.json()
                for cu in _extract_all_dl_urls_from_json(jdata)[:3]:
                    m_bytes = _fetch_stream_bytes(cu)
                    if m_bytes:
                        return {
                            "status": True,
                            "title": _extract_title_from_json(jdata) or "CapCut Video",
                            "media_bytes": m_bytes,
                            "url": cu,
                            "type": "audio" if is_audio else "video",
                            "filename": "capcut.mp3" if is_audio else "capcut.mp4",
                            "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                        }
        except Exception:
            continue

    res_yt = download_via_ytdlp(real_url, is_audio=is_audio, default_title="CapCut Video")
    if res_yt.get("status"):
        return res_yt
    return download_savefrom(real_url, is_audio=is_audio, default_title="CapCut Video")


def download_snackvideo(url: str, is_audio: bool = False) -> dict:
    """Mengunduh video dari SnackVideo / Kwai (Multi-API -> yt-dlp -> SaveFrom)"""
    real_url = resolve_redirect_url(url)
    clean_u = urllib.parse.quote(real_url, safe='')
    for api_u in [
        f"https://api.siputzx.my.id/api/d/snackvideo?url={clean_u}",
        f"https://api.agatz.xyz/api/snackvideo?url={clean_u}",
    ]:
        try:
            r = _http_get(api_u, timeout=14)
            if r is not None and r.status_code == 200:
                jdata = r.json()
                for cu in _extract_all_dl_urls_from_json(jdata)[:3]:
                    m_bytes = _fetch_stream_bytes(cu)
                    if m_bytes:
                        return {
                            "status": True,
                            "title": _extract_title_from_json(jdata) or "SnackVideo",
                            "media_bytes": m_bytes,
                            "url": cu,
                            "type": "audio" if is_audio else "video",
                            "filename": "snackvideo.mp3" if is_audio else "snackvideo.mp4",
                            "mimetype": "audio/mpeg" if is_audio else "video/mp4"
                        }
        except Exception:
            continue

    res_yt = download_via_ytdlp(real_url, is_audio=is_audio, default_title="SnackVideo")
    if res_yt.get("status"):
        return res_yt
    return download_savefrom(real_url, is_audio=is_audio, default_title="SnackVideo")


def download_spotify(url: str) -> dict:
    """Mengunduh lagu dari link Spotify (Multi-API -> Spotify oEmbed + Pencarian Lagu)"""
    real_url = resolve_redirect_url(url)
    clean_u = urllib.parse.quote(real_url, safe='')
    for api_u in [
        f"https://api.siputzx.my.id/api/d/spotify?url={clean_u}",
        f"https://api.ryzendesu.vip/api/downloader/spotify?url={clean_u}",
        f"https://api.vreden.my.id/api/spotify?url={clean_u}",
    ]:
        try:
            r = _http_get(api_u, timeout=15)
            if r is not None and r.status_code == 200:
                jdata = r.json()
                for cu in _extract_all_dl_urls_from_json(jdata)[:3]:
                    m_bytes = _fetch_stream_bytes(cu)
                    if m_bytes:
                        return {
                            "status": True,
                            "title": _extract_title_from_json(jdata) or "Spotify Music",
                            "media_bytes": m_bytes,
                            "url": cu,
                            "type": "audio",
                            "filename": "spotify.mp3",
                            "mimetype": "audio/mpeg"
                        }
        except Exception:
            continue

    # Fallback: Ambil judul lagu via Spotify oEmbed lalu unduh via search_and_download_music
    try:
        r_oe = _http_get(f"https://open.spotify.com/oembed?url={clean_u}", timeout=8)
        if r_oe is not None and r_oe.status_code == 200:
            sp_title = r_oe.json().get("title")
            if sp_title:
                return search_and_download_music(sp_title)
    except Exception:
        pass

    return {"status": False, "error": "Gagal mengunduh lagu dari link Spotify tersebut"}


def download_soundcloud(url: str) -> dict:
    """Mengunduh lagu dari link SoundCloud via yt-dlp."""
    real_url = resolve_redirect_url(url)
    res_yt = download_via_ytdlp(real_url, is_audio=True, default_title="SoundCloud Audio")
    if res_yt.get("status"):
        return res_yt
    return download_savefrom(real_url, is_audio=True, default_title="SoundCloud Audio")


def download_savefrom(url: str, is_audio: bool = False, default_title: str = "Media") -> dict:
    """Mengunduh media melalui engine SaveFrom API dan langsung memvalidasi stream bytes-nya."""
    try:
        clean_url = urllib.parse.quote(url, safe='')
        api_url = f"https://api.siputzx.my.id/api/d/savefrom?url={clean_url}"

        data = None
        last_err = ""
        for _ in range(2):
            try:
                r = _http_get(api_url, timeout=20)
                if r is not None and r.status_code == 200:
                    data = r.json()
                    break
                elif r is not None:
                    last_err = f"status {r.status_code}"
                else:
                    last_err = "koneksi gagal"
            except Exception as e_req:
                last_err = str(e_req)
                time.sleep(1)

        if not data:
            return {"status": False, "error": f"Gagal menghubungi server downloader ({last_err})"}

        if not data.get("status"):
            return {"status": False, "error": data.get("error", "Link tidak dapat diproses")}

        data_list = data.get("data", [])
        if not data_list or not isinstance(data_list, list):
            return {"status": False, "error": "Media tidak ditemukan dari link tersebut"}

        first_item = data_list[0]
        if not isinstance(first_item, dict) or first_item.get("type") == "error":
            err_msg = "Media tidak ditemukan atau link kadaluarsa"
            if isinstance(first_item, dict) and isinstance(first_item.get("data"), dict):
                err_msg = first_item.get("data", {}).get("html") or err_msg
            return {"status": False, "error": err_msg}

        sub_list = first_item.get("data", [])
        if not sub_list or not isinstance(sub_list, list):
            return {"status": False, "error": "Data media kosong"}

        media_obj = sub_list[0]
        if not isinstance(media_obj, dict):
            return {"status": False, "error": "Format data media tidak sesuai"}

        title = media_obj.get("meta", {}).get("title") or default_title
        urls = media_obj.get("url", [])

        if not urls:
            return {"status": False, "error": "Link download tidak ditemukan"}

        valid_urls = [u for u in urls if "sf-converter.com" not in u.get("url", "")]
        if not valid_urls:
            valid_urls = urls

        candidates = []
        if is_audio:
            for u in valid_urls:
                ext_u = str(u.get("ext", "")).lower()
                name_u = str(u.get("name", "")).lower()
                if u.get("audio") is True or "audio" in name_u or ext_u in ["m4a", "mp3", "opus", "aac"]:
                    if ext_u in ["m4a", "aac"]:
                        candidates.append((u.get("url"), "audio/mp4", "m4a"))
                    elif ext_u == "opus":
                        candidates.append((u.get("url"), "audio/ogg; codecs=opus", "opus"))
                    else:
                        candidates.append((u.get("url"), "audio/mpeg", "mp3"))
        else:
            for u in valid_urls:
                ext_u = str(u.get("ext", "")).lower()
                durl = u.get("url", "")
                quality = str(u.get("quality", ""))
                if ext_u == "mp4" and ("360" in quality or "480" in quality or "720" in quality or "itag=18" in durl):
                    candidates.append((durl, "video/mp4", "mp4"))

            for u in valid_urls:
                ext_u = str(u.get("ext", "")).lower()
                if ext_u == "mp4":
                    candidates.append((u.get("url"), "video/mp4", "mp4"))

        if not candidates and valid_urls:
            ext_default = "mp3" if is_audio else "mp4"
            mime_default = "audio/mpeg" if is_audio else "video/mp4"
            candidates.append((valid_urls[0].get("url"), mime_default, ext_default))

        sf_headers = {
            'Origin': 'https://en1.savefrom.net',
            'Referer': 'https://en1.savefrom.net/'
        }
        for cand_url, cand_mime, cand_ext in candidates:
            if not cand_url:
                continue
            m_bytes = _fetch_stream_bytes(cand_url, custom_headers=sf_headers) or _fetch_stream_bytes(cand_url)
            if m_bytes:
                return {
                    "status": True,
                    "title": title,
                    "media_bytes": m_bytes,
                    "url": cand_url,
                    "type": "audio" if is_audio else "video",
                    "filename": f"download.{cand_ext}",
                    "mimetype": cand_mime
                }

        return {"status": False, "error": "Stream media tidak dapat diunduh dari server"}
    except Exception as e:
        return {"status": False, "error": f"Error downloader: {str(e)}"}


def get_media(url: str, is_audio: bool = False, forced_platform: str | None = None) -> dict:
    """Unified entry point to get downloadable media info across all supported platforms."""
    real_url = resolve_redirect_url(url)
    platform = forced_platform or detect_platform(real_url)

    if platform == 'tiktok':
        return download_tiktok(real_url, is_audio=is_audio)
    elif platform == 'facebook':
        return download_facebook(real_url, is_audio=is_audio)
    elif platform == 'youtube':
        return download_youtube(real_url, is_audio=is_audio)
    elif platform == 'instagram':
        return download_instagram(real_url, is_audio=is_audio)
    elif platform == 'twitter':
        return download_twitter(real_url, is_audio=is_audio)
    elif platform == 'pinterest':
        return download_pinterest(real_url, is_audio=is_audio)
    elif platform == 'threads':
        return download_threads(real_url, is_audio=is_audio)
    elif platform == 'capcut':
        return download_capcut(real_url, is_audio=is_audio)
    elif platform == 'snackvideo':
        return download_snackvideo(real_url, is_audio=is_audio)
    elif platform == 'spotify':
        return download_spotify(real_url)
    elif platform == 'soundcloud':
        return download_soundcloud(real_url)
    else:
        res_yt = download_via_ytdlp(real_url, is_audio=is_audio, default_title="Media")
        if res_yt.get("status"):
            return res_yt
        return download_savefrom(real_url, is_audio=is_audio, default_title="Media")


def search_youtube_music_info(query: str) -> dict:
    """Mencari video musik di YouTube dan mengembalikan URL serta judul terbaik."""
    # 1. Coba melalui Siputzx YouTube Search API
    try:
        clean_q = urllib.parse.quote_plus(query)
        api_url = f"https://api.siputzx.my.id/api/s/youtube?query={clean_q}"
        r = _http_get(api_url, timeout=8)
        if r is not None and r.status_code == 200:
            data = r.json()
            if data.get("status") and data.get("data"):
                items = data.get("data", [])
                for item in items:
                    v_url = item.get("url")
                    v_title = item.get("title")
                    if v_url and "watch?v=" in v_url:
                        return {"url": v_url, "title": v_title}
                    elif item.get("videoId"):
                        return {"url": f"https://www.youtube.com/watch?v={item['videoId']}", "title": v_title}
    except Exception:
        pass

    # 2. Coba scraping hasil pencarian YouTube web
    try:
        clean_q = urllib.parse.quote_plus(query)
        search_url = f"https://www.youtube.com/results?search_query={clean_q}"
        r = _http_get(search_url, timeout=8)
        if r is not None and r.status_code == 200:
            vids = re.findall(r'/watch\?v=([a-zA-Z0-9_-]{11})', r.text)
            if vids:
                unique_vids = list(dict.fromkeys(vids))
                return {"url": f"https://www.youtube.com/watch?v={unique_vids[0]}", "title": query}
    except Exception:
        pass

    return {}


def search_and_download_music(query: str) -> dict:
    """Mencari musik berdasarkan judul lagu secara kilat (2-5 detik) tanpa menunggu timeout YouTube."""
    query = query.strip()
    if not query:
        return {"status": False, "error": "Judul musik tidak boleh kosong"}

    # Jika pengguna memasukkan link URL secara langsung
    if re.search(r'https?://[^\s]+', query):
        url_match = re.search(r'https?://[^\s]+', query)
        target_url = url_match.group(0).rstrip('>')
        return get_media(target_url, is_audio=True)

    # 1. JALUR KILAT UTAMA (2-4 Detik): Unduh langsung dari SoundCloud via yt-dlp
    # (Tidak membuang waktu 3 menit di antrean timeout YouTube yang memblokir IP VPS)
    res_sc = download_soundcloud_music(query)
    if res_sc.get("status"):
        return res_sc

    # 2. JALUR PENCARIAN CERDAS (iTunes / Deezer API <0.4 detik -> SoundCloud):
    # Jika pengguna mengetik potongan lirik atau judul kurang lengkap, cari judul & penyanyi resminya
    canonical_query = resolve_fast_song_query(query)
    if canonical_query and canonical_query.lower() != query.lower():
        res_sc_canon = download_soundcloud_music(canonical_query)
        if res_sc_canon.get("status"):
            return res_sc_canon

    # 3. JALUR CADANGAN CEPAT YOUTUBE CDN (Jika lagu tidak ada di SoundCloud):
    search_info = search_youtube_music_info(canonical_query or query)
    target_url = search_info.get("url")
    if target_url:
        clean_url = urllib.parse.quote(target_url, safe='')
        fast_yt_apis = [
            f"https://api.siputzx.my.id/api/d/ytmp3?url={clean_url}",
            f"https://api.ryzendesu.vip/api/downloader/ytmp3?url={clean_url}",
            f"https://api.vreden.my.id/api/ytmp3?url={clean_url}",
        ]
        for api_u in fast_yt_apis:
            try:
                r = _http_get(api_u, timeout=8)
                if r is not None and r.status_code == 200:
                    data = r.json()
                    for dl_url in _extract_all_dl_urls_from_json(data)[:2]:
                        m_bytes = _fetch_stream_bytes(dl_url)
                        if m_bytes:
                            return {
                                "status": True,
                                "title": search_info.get("title") or _extract_title_from_json(data) or query,
                                "media_bytes": m_bytes,
                                "url": dl_url,
                                "type": "audio",
                                "filename": "download.mp3",
                                "mimetype": "audio/mpeg"
                            }
            except Exception:
                continue

    return {"status": False, "error": res_sc.get("error") or f"Musik dengan judul '{query}' tidak ditemukan."}
