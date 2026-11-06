import os
import json
import random
import time
import re
import threading
import logging

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
GAMES_DATA_DIR = os.path.join(DATA_DIR, "games")
LEADERBOARD_FILE = os.path.join(DATA_DIR, "games_leaderboard.json")

# In-memory active game sessions per group (Key: chat_jid)
ACTIVE_GAMES = {}
GAMES_LOCK = threading.Lock()

# ----------------- LEADERBOARD PERSISTENCE -----------------

def load_leaderboard() -> dict:
    try:
        if os.path.exists(LEADERBOARD_FILE):
            with open(LEADERBOARD_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
    except Exception as e:
        logging.error(f"Gagal membaca games_leaderboard.json: {e}")
    return {}

def save_leaderboard(data: dict):
    try:
        with open(LEADERBOARD_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Gagal menyimpan games_leaderboard.json: {e}")

def add_player_score(chat_jid: str, player_jid: str, player_name: str, points: int):
    with GAMES_LOCK:
        board = load_leaderboard()
        if chat_jid not in board:
            board[chat_jid] = {}
        clean_pid = player_jid.split('@')[0].split(':')[0]
        user_info = board[chat_jid].get(clean_pid, {"name": player_name, "score": 0})
        user_info["name"] = player_name
        user_info["score"] = user_info.get("score", 0) + points
        board[chat_jid][clean_pid] = user_info
        save_leaderboard(board)

def get_group_leaderboard(chat_jid: str) -> str:
    board = load_leaderboard()
    group_data = board.get(chat_jid, {})
    if not group_data:
        return "Belum ada riwayat skor game di grup ini. Ayo mulai bermain dengan *,f100*, *,kuistoram*, atau *,susunkata*!"

    sorted_players = sorted(group_data.items(), key=lambda x: x[1].get("score", 0), reverse=True)
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    reply = "*KLASEMEN TOP SKOR GAME GRUP*\n\n"
    for idx, (pid, pdata) in enumerate(sorted_players[:10]):
        m = medals[idx] if idx < len(medals) else f"{idx+1}."
        name = pdata.get("name", f"Pemain {pid[:6]}")
        score = pdata.get("score", 0)
        reply += f"{m} *{name}* — `{score} Poin`\n"

    reply += f"\nTotal Pemain Tercatat: {len(sorted_players)}"
    return reply.strip()

def reset_group_leaderboard(chat_jid: str, reset_all: bool = False) -> bool:
    with GAMES_LOCK:
        board = load_leaderboard()
        if reset_all:
            board = {}
        else:
            if chat_jid in board:
                del board[chat_jid]
        save_leaderboard(board)
        return True

# ----------------- DATASET LOADERS -----------------

def load_game_dataset(filename: str) -> list:
    filepath = os.path.join(GAMES_DATA_DIR, filename)
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Gagal memuat dataset {filename}: {e}")
    return []

# ----------------- GAME CONTROLLERS -----------------

def clean_answer_text(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9\s]', '', text.strip().lower())

def generate_scrambled_letters(word: str) -> str:
    """Mengacak huruf-huruf kata dan memastikan hasilnya benar-benar teracak (tidak sama dengan aslinya)"""
    letters = list(re.sub(r'[^a-zA-Z0-9]', '', word.upper()))
    if len(letters) <= 1:
        return " - ".join(letters)
    orig = "".join(letters)
    for _ in range(30):
        random.shuffle(letters)
        if "".join(letters) != orig:
            break
    return " - ".join(letters)

def cancel_game_timer(session: dict):
    timer = session.get("timer")
    if timer and timer.is_alive():
        try:
            timer.cancel()
        except Exception:
            pass

def game_timeout_callback(client, chat_jid: str, game_type: str):
    with GAMES_LOCK:
        session = ACTIVE_GAMES.get(chat_jid)
        if not session or session.get("game_type") != game_type:
            return
        del ACTIVE_GAMES[chat_jid]

    # Format pesan timeout
    orig_msg = session.get("message")
    if game_type == "family100":
        reply = "⏰ *WAKTU HABIS! (FAMILY 100)*\n\n"
        reply += f"*Pertanyaan:* {session['question']}\n\n"
        reply += "*Kunci Jawaban Lengkap:*\n"
        for idx, ans in enumerate(session["answers"], start=1):
            status = "✅" if ans["found"] else "❌"
            finder = f" (Ditebak: {ans['found_by']})" if ans["found"] else ""
            reply += f"{idx}. {ans['display']} [{ans['points']} Poin] {status}{finder}\n"

        if session.get("session_scores"):
            reply += "\n*Skor Sesi Ini:*\n"
            for pid, pdata in session["session_scores"].items():
                reply += f"• *{pdata['name']}:* +{pdata['points']} Poin\n"
        reply += "\nKetik *,family100* untuk bermain babak baru!"
    else:
        answer_disp = session.get("correct_display", session.get("answers", [""])[0])
        reply = f"⏰ *WAKTU HABIS!*\n\nJawaban yang benar adalah: *{answer_disp}*\n\nJangan berkecil hati, ayo coba lagi babak berikutnya!"

    try:
        client.reply_message(reply, orig_msg)
    except Exception as e:
        logging.error(f"Gagal mengirim pesan timeout game ke {chat_jid}: {e}")

# 1. FAMILY 100
def start_family100(client, message, chat_jid: str):
    with GAMES_LOCK:
        if chat_jid in ACTIVE_GAMES:
            active = ACTIVE_GAMES[chat_jid]
            gtype = active.get("game_type", "permainan")
            client.reply_message(f"Masih ada sesi *{gtype.upper()}* yang sedang berlangsung di grup ini!\nSelesaikan terlebih dahulu atau ketik *,nyerah* untuk berhenti.", message)
            return

        dataset = load_game_dataset("family100.json")
        if not dataset:
            client.reply_message("Gagal: Database soal Family 100 kosong atau tidak ditemukan.", message)
            return

        question_data = random.choice(dataset)
        answers_state = []
        for a in question_data["answers"]:
            answers_state.append({
                "text": clean_answer_text(a["text"]),
                "display": a.get("display", a["text"]),
                "points": a.get("points", 10),
                "found": False,
                "found_by": ""
            })

        session = {
            "game_type": "family100",
            "question": question_data["question"],
            "answers": answers_state,
            "total_answers": len(answers_state),
            "found_count": 0,
            "session_scores": {},
            "message": message,
            "client": client,
            "started_at": time.time(),
            "timeout_seconds": 90
        }

        # Pasang timer 90 detik
        t = threading.Timer(90.0, game_timeout_callback, args=[client, chat_jid, "family100"])
        t.daemon = True
        session["timer"] = t
        ACTIVE_GAMES[chat_jid] = session
        t.start()

    # Tampilkan papan awal Family 100
    reply = "👨‍👩‍👧‍👦 *FAMILY 100 INDONESIA*\n\n"
    reply += f"*Pertanyaan:*\n{question_data['question']}\n\n"
    reply += "*Papan Jawaban Survei:*\n"
    for idx, ans in enumerate(answers_state, start=1):
        reply += f"{idx}. ❓ _----------_ [{ans['points']}]\n"
    reply += f"\n⏳ Waktu: *90 Detik* (Terdapat {len(answers_state)} jawaban)\n"
    reply += "💡 *Cara Jawab:* Ketik langsung jawabanmu di grup tanpa tanda koma!\n"
    reply += "🏳️ Ketik *,nyerah* untuk mengakhiri permainan."

    client.reply_message(reply, message)

# 2. SUSUN KATA
def start_susun_kata(client, message, chat_jid: str):
    with GAMES_LOCK:
        if chat_jid in ACTIVE_GAMES:
            active = ACTIVE_GAMES[chat_jid]
            gtype = active.get("game_type", "permainan")
            client.reply_message(f"Masih ada sesi *{gtype.upper()}* yang sedang berlangsung di grup ini!\nSelesaikan terlebih dahulu atau ketik *,nyerah* untuk berhenti.", message)
            return

        dataset = load_game_dataset("susun_kata.json")
        if not dataset:
            client.reply_message("Gagal: Database soal Susun Kata kosong atau tidak ditemukan.", message)
            return

        q = random.choice(dataset)
        raw_ans = q.get("display") or q["answer"]
        scrambled_display = generate_scrambled_letters(raw_ans)
        session = {
            "game_type": "susunkata",
            "scrambled": scrambled_display,
            "answers": [clean_answer_text(q["answer"])],
            "correct_display": q.get("display", q["answer"]),
            "clue": q.get("clue", ""),
            "points": q.get("points", 50),
            "message": message,
            "client": client,
            "started_at": time.time(),
            "timeout_seconds": 75
        }

        t = threading.Timer(75.0, game_timeout_callback, args=[client, chat_jid, "susunkata"])
        t.daemon = True
        session["timer"] = t
        ACTIVE_GAMES[chat_jid] = session
        t.start()

    reply = "🔤 *GAME SUSUN KATA*\n\n"
    reply += f"Susun huruf-huruf berikut menjadi kata yang tepat:\n\n"
    reply += f"👉 *[ {scrambled_display} ]*\n\n"
    if q.get("clue"):
        reply += f"🔎 *Petunjuk:* {q['clue']}\n"
    reply += f"🎁 *Poin Hadiah:* +{q.get('points', 50)} Poin\n"
    reply += "⏳ Waktu: *75 Detik*\n\n"
    reply += "💡 *Cara Jawab:* Ketik langsung kata tebakanmu di chat grup!\n"
    reply += "🏳️ Ketik *,nyerah* untuk menyerah."

    client.reply_message(reply, message)

# 3. KUIS TORAM
def start_kuis_toram(client, message, chat_jid: str):
    with GAMES_LOCK:
        if chat_jid in ACTIVE_GAMES:
            active = ACTIVE_GAMES[chat_jid]
            gtype = active.get("game_type", "permainan")
            client.reply_message(f"Masih ada sesi *{gtype.upper()}* yang sedang berlangsung di grup ini!\nSelesaikan terlebih dahulu atau ketik *,nyerah* untuk berhenti.", message)
            return

        dataset = load_game_dataset("kuis_toram.json")
        if not dataset:
            client.reply_message("Gagal: Database soal Kuis Toram kosong atau tidak ditemukan.", message)
            return

        q = random.choice(dataset)
        clean_ans = [clean_answer_text(a) for a in q.get("answers", [])]
        session = {
            "game_type": "kuistoram",
            "question": q["question"],
            "answers": clean_ans,
            "correct_display": q.get("display", q.get("answers", [""])[0]),
            "clue": q.get("clue", ""),
            "points": q.get("points", 50),
            "message": message,
            "client": client,
            "started_at": time.time(),
            "timeout_seconds": 90
        }

        t = threading.Timer(90.0, game_timeout_callback, args=[client, chat_jid, "kuistoram"])
        t.daemon = True
        session["timer"] = t
        ACTIVE_GAMES[chat_jid] = session
        t.start()

    reply = "⚔️ *KUIS TORAM ONLINE*\n\n"
    reply += f"*Pertanyaan:*\n{q['question']}\n\n"
    if q.get("clue"):
        reply += f"🔎 *Petunjuk:* {q['clue']}\n"
    reply += f"🎁 *Hadiah:* +{q.get('points', 50)} Poin\n"
    reply += "⏳ Waktu: *90 Detik*\n\n"
    reply += "💡 *Cara Jawab:* Ketik langsung jawabanmu di grup!\n"
    reply += "🏳️ Ketik *,nyerah* untuk menyerah."

    client.reply_message(reply, message)

# 4. SURRENDER / STOP
def handle_surrender(client, message, chat_jid: str):
    with GAMES_LOCK:
        session = ACTIVE_GAMES.get(chat_jid)
        if not session:
            client.reply_message("Tidak ada sesi permainan yang sedang aktif di grup ini.\nKetik *,f100*, *,kuistoram*, atau *,susunkata* untuk memulai permainan baru!", message)
            return
        cancel_game_timer(session)
        del ACTIVE_GAMES[chat_jid]

    gtype = session.get("game_type")
    if gtype == "family100":
        reply = "🏳️ *SESI FAMILY 100 DIAKHIRI*\n\n"
        reply += f"*Pertanyaan:* {session['question']}\n\n"
        reply += "*Kunci Jawaban Lengkap:*\n"
        for idx, ans in enumerate(session["answers"], start=1):
            status = "✅" if ans["found"] else "❌"
            finder = f" ({ans['found_by']})" if ans["found"] else ""
            reply += f"{idx}. {ans['display']} [{ans['points']} Poin] {status}{finder}\n"
        if session.get("session_scores"):
            reply += "\n*Poin yang Berhasil Didapatkan:*\n"
            for pid, pdata in session["session_scores"].items():
                reply += f"• *{pdata['name']}:* +{pdata['points']} Poin\n"
    else:
        ans_disp = session.get("correct_display", session.get("answers", [""])[0])
        reply = f"🏳️ *PERMAINAN DIAKHIRI*\n\nJawaban yang benar adalah: *{ans_disp}*\n\nKetik *,f100* atau *,kuistoram* untuk bermain lagi!"

    client.reply_message(reply, message)

# ----------------- ANSWER CHECKER (NON-BLOCKING) -----------------

def check_game_answer(client, message, chat_jid: str, sender_jid: str, sender_name: str, text: str) -> bool:
    """Mengecek apakah pesan dari grup merupakan jawaban game aktif. Mengembalikan True jika jawaban benar."""
    if not text or text.startswith(","):
        return False

    with GAMES_LOCK:
        session = ACTIVE_GAMES.get(chat_jid)
        if not session:
            return False

    cleaned_input = clean_answer_text(text)
    if not cleaned_input:
        return False

    gtype = session.get("game_type")

    # 1. LOGIKA CEK FAMILY 100
    if gtype == "family100":
        matched_idx = -1
        with GAMES_LOCK:
            # Cari apakah input cocok dengan salah satu jawaban yang belum terjawab
            for idx, ans in enumerate(session["answers"]):
                if not ans["found"]:
                    # Exact match atau substring jika jawaban panjang
                    if cleaned_input == ans["text"] or (len(cleaned_input) >= 4 and cleaned_input in ans["text"]):
                        ans["found"] = True
                        ans["found_by"] = sender_name
                        session["found_count"] += 1
                        matched_idx = idx
                        break

            if matched_idx == -1:
                return False

            matched_ans = session["answers"][matched_idx]
            points = matched_ans["points"]

            # Catat skor sesi
            clean_pid = sender_jid.split('@')[0].split(':')[0]
            if clean_pid not in session["session_scores"]:
                session["session_scores"][clean_pid] = {"name": sender_name, "points": 0}
            session["session_scores"][clean_pid]["points"] += points

            is_completed = (session["found_count"] >= session["total_answers"])
            if is_completed:
                cancel_game_timer(session)
                del ACTIVE_GAMES[chat_jid]

        # Tambahkan skor permanen ke leaderboard
        add_player_score(chat_jid, sender_jid, sender_name, points)

        # Bangun pesan papan update
        if is_completed:
            reply = f"🎉 *SEMPURNA! SEMUA JAWABAN TERTEBAK!*\n\n"
            reply += f"Tebakan terakhir oleh *{sender_name}*: *{matched_ans['display']}* (+{points} Poin) 🎯\n\n"
            reply += "*Papan Jawaban Lengkap:*\n"
            for idx, ans in enumerate(session["answers"], start=1):
                reply += f"{idx}. {ans['display']} [{ans['points']}] ✅ ({ans['found_by']})\n"
            reply += "\n🏆 *Total Poin Sesi Ini:*\n"
            for pid, pdata in session["session_scores"].items():
                reply += f"• *{pdata['name']}:* {pdata['points']} Poin\n"
            reply += "\nKetik *,family100* untuk bermain babak berikutnya!"
        else:
            remaining = session["total_answers"] - session["found_count"]
            reply = f"🎯 *TEBAKAN TEPAT! (+{points} Poin)*\n"
            reply += f"*{sender_name}* berhasil menebak: *{matched_ans['display']}*!\n\n"
            reply += f"*Pertanyaan:*\n{session['question']}\n\n"
            reply += "*Papan Survei:*\n"
            for idx, ans in enumerate(session["answers"], start=1):
                if ans["found"]:
                    reply += f"{idx}. {ans['display']} [{ans['points']}] ✅ ({ans['found_by']})\n"
                else:
                    reply += f"{idx}. ❓ _----------_ [{ans['points']}]\n"
            reply += f"\nSisa {remaining} jawaban belum terbuka. Ayo tebak lagi!"

        client.reply_message(reply, message)
        return True

    # 2. LOGIKA CEK SUSUN KATA & KUIS TORAM
    elif gtype in ["susunkata", "kuistoram"]:
        is_match = False
        with GAMES_LOCK:
            target_answers = session.get("answers", [])
            for target in target_answers:
                if cleaned_input == target or (len(cleaned_input) >= 4 and cleaned_input in target):
                    is_match = True
                    break

            if not is_match:
                return False

            cancel_game_timer(session)
            del ACTIVE_GAMES[chat_jid]
            points = session.get("points", 50)
            correct_disp = session.get("correct_display", text.title())

        add_player_score(chat_jid, sender_jid, sender_name, points)

        title_badge = "⚔️ *KUIS TORAM*" if gtype == "kuistoram" else "🔤 *SUSUN KATA*"
        reply = f"🎉 *JAWABAN BENAR!* {title_badge}\n\n"
        reply += f"Selamat kepada *{sender_name}*!\n"
        reply += f"• Jawaban: *{correct_disp}*\n"
        reply += f"• Poin Diperoleh: *+{points} Poin* 🎁\n\n"
        reply += "Ketik *,f100*, *,kuistoram*, atau *,susunkata* untuk bermain babak selanjutnya!"

        client.reply_message(reply, message)
        return True

    return False

