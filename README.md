# Ditdut Toram - WhatsApp Bot Toram Online

**Ditdut Toram** adalah Bot WhatsApp serbaguna yang dibangun menggunakan Python dan library **Neonize** (gocrypt/whatsmeow binding). Bot ini dirancang untuk menyediakan informasi real-time dari situs resmi, pencarian database terlengkap, game waifu/husbu, serta simulasi dan panduan terlengkap untuk game **Toram Online**.

---

## 🌟 Fitur Utama

### 1. 📢 Real-Time News & Updates (Situs Resmi Toram Online)
* `,mt` / `,maintenance` — Informasi jadwal, isi pemeliharaan, dan perbaikan bug real-time dari situs resmi (`id.toram.jp`).
* `,ava` / `,avatar` — Daftar dan gambar banner Avatar Chest promo real-time.
* `,boost` — Daftar boss dan mini-boss yang sedang mendapatkan boost EXP (+100%) dan Drop Rate (+50%).

### 2. 🛡️ Toram Online Search & Tools
* **Pencarian Equipment & Item:** `,item`, `,wp` (weapon), `,armor` (drop boss & craft blacksmith), `,add` (additional gear), `,ring` (special gear), `,xtall` (crysta), `,mats` (material), `,use` (konsumsi).
* **Informasi Database:** `,mob` / `,boss` / `,mboss` (detail monster & drop), `,rute` (rute upgrade crysta), `,skill` (detail skill), `,regis` (detail registlet), `,trait` (detail trait pet), `,pet` (daftar & perilaku sifat pet).
* **Panduan Game:** `,lvling` (rekomendasi leveling), `,buff [kategori]` (daftar food buff land & kalkulator exp cooking), `,mq` (bahan main quest), `,bag` (bahan tas/storage), `,statlist` (daftar status).
* **Toram Tools:** `,fillwp` & `,fillarm` (simulasi pengisian status/statting pada senjata dan zirah).

### 3. 🤖 Menu Umum & Hiburan
* `,menu` / `,help` — Menampilkan seluruh daftar perintah.
* `,ping` — Memeriksa respon dan kecepatan bot.
* `,about` — Informasi seputar Ditdut Toram Bot.
* `,quote` — Kutipan acak.
* `,calc <ekspresi>` — Kalkulator langsung di WhatsApp.
* `,waifu` / `,husbu` — Mengklaim gambar waifu/husbu acak (Safe-rating, karakter bernama, dan variasi anime).
* `,dl <link>` — Mengunduh media/video dari link (TikTok, FB, IG, YouTube, dll.) dalam bentuk file dokumen.
* `,music <judul lagu>` — Mencari dan mengunduh musik/lagu langsung berdasarkan judul lagu.
* `,s` / `,sticker` — Membuat stiker dari gambar.
* `,setmeme <teks>` — Membuat stiker meme dengan teks.
* `,ai <tanyaan>` — Gemini AI Assistant.
* **Fitur Moderasi Grup:** `,a` (hidetag), `,kick` (mengeluarkan member), `,warn` (peringatan member), `,reset` (mereset peringatan), `,view` (view once media viewer).

---

## 💻 Persyaratan Sistem

* **Python 3.10 ke atas** (Direkomendasikan Python 3.10 / 3.11 / 3.12).
* **Sistem Operasi:** Windows, Linux (Ubuntu/Debian/VPS), Daytona Cloud, atau macOS.
* **Akun WhatsApp aktif** untuk pemindaian (scan) QR Code.

---

## 🚀 Langkah-Langkah Instalasi & Penggunaan

### 1. Unduh / Clone Project
```bash
git clone https://github.com/HilalAzki28/Bot-Whatsapp-Toram-Online.git
cd Bot-Whatsapp-Toram-Online
```

### 2. Buat & Aktifkan Virtual Environment
* **Windows (PowerShell):**
  ```powershell
  python -m venv venv
  .\venv\Scripts\Activate.ps1
  ```
* **Linux / macOS:**
  ```bash
  python3 -m venv venv
  source venv/bin/activate
  ```

### 3. Instal Dependensi
```bash
pip install -r requirements.txt
```

### 4. Jalankan Bot
```bash
python src/bot.py
```

### 5. Hubungkan ke WhatsApp (Scan QR Code)
* Saat pertama kali dijalankan, bot akan menghasilkan QR Code terminal & file `whatsapp_qr.png`.
* Buka WhatsApp di HP Anda -> **Perangkat Tertaut (Linked Devices)** -> **Tautkan Perangkat**, lalu scan QR Code tersebut.
* Setelah tersambung, file sesi `whatsapp_session.sqlite3` akan dibuat secara otomatis.
