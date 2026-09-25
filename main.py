#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Kids OS Launcher
================
Antarmuka kiosk ("gembok sistem") untuk anak di antiX Linux (IceWM / Fluxbox).

- Menutupi seluruh desktop: fullscreen, tanpa bingkai, selalu di atas.
- Keyboard di-grab di level X11 sehingga Alt+Tab, Alt+F4, tombol Super, dsb.
  tidak sampai ke window manager.
- Tombol "Mode Admin" (kiri atas) + password -> Panel Admin (desktop admin,
  terminal, mulai ulang, matikan).
- Tombol "Matikan" (kanan atas) agar anak bisa mematikan komputer sendiri.
- Setiap kartu menu menjalankan aplikasi Linux lewat launch_app(command).
  Selama aplikasi anak berjalan, launcher turun ke belakang (tetap hidup),
  lalu otomatis mengunci layar lagi begitu aplikasi itu ditutup.

Jalankan:
    python3 main.py            -> mode kiosk di atas desktop yang sudah ada
    python3 main.py --session  -> launcher = seluruh sistem (dipakai oleh
                                  linux/kidsos-session, lihat linux/install.sh)
    python3 main.py --dev      -> mode uji: berjendela, tanpa kunci, Esc = keluar
"""

import hashlib
import hmac
import json
import os
import re
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

from PyQt5.QtCore import (
    Qt, QEvent, QObject, QTimer, QPropertyAnimation, QPoint, QEasingCurve,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QFont, QMovie
from PyQt5.QtWidgets import (
    QApplication, QWidget, QFrame, QPushButton, QLabel, QLineEdit, QCheckBox,
    QStackedWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy,
    QAbstractButton,
)

import sounds
from activities import create_activity, stop_speech

# ---------------------------------------------------------------------------
# KONFIGURASI
# ---------------------------------------------------------------------------

# Password Mode Admin (hardcoded sesuai kebutuhan). Untuk produksi sebaiknya
# simpan hash-nya (mis. hashlib.sha256) daripada teks polos.
ADMIN_PASSWORD = "admin123"

# Jika file ini ada (dibuat oleh linux/install.sh), password admin dicek
# terhadap hash SHA-256 di dalamnya dan ADMIN_PASSWORD di atas diabaikan.
ADMIN_HASH_FILE = "/etc/kidsos/admin.sha256"

# Mode pengembangan: jendela biasa, tanpa grab keyboard, Esc untuk keluar.
DEV_MODE = "--dev" in sys.argv

# Mode sesi: launcher adalah SATU-SATUNYA antarmuka sistem (tanpa desktop di
# belakangnya). Kode keluar dibaca oleh skrip linux/kidsos-session.
SESSION_MODE = "--session" in sys.argv
EXIT_ADMIN_DESKTOP = 10   # -> skrip sesi membuka desktop IceWM untuk admin
EXIT_RESTART = 11         # -> skrip sesi langsung menjalankan launcher lagi

# Terminal untuk admin (alternatif Debian/antiX: roxterm, urxvt, xterm, ...).
TERMINAL_COMMAND = "x-terminal-emulator"

# Layar sambutan saat launcher mulai (mode --session, atau --splash untuk uji).
SPLASH_GIF = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "assets", "boot", "splash.gif")
SHOW_SPLASH = SESSION_MODE or "--splash" in sys.argv
SPLASH_MS = 3500

# Repository menu: admin mengisi URL menu.json (atau repo GitHub yang berisi
# menu.json di root-nya) di Panel Admin. Pengaturan & salinan menu terakhir
# disimpan di home user anak.
DEFAULT_REPO_URL = "https://github.com/Mrx112/OSAnak"
CONFIG_DIR = os.path.expanduser("~/.config/kidsos")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
MENU_CACHE_FILE = os.path.join(CONFIG_DIR, "menu.json")
MENU_MAX_BYTES = 1_000_000
# Isi aktivitas yang ikut diunduh dari folder content/ di sebelah menu.json.
CONTENT_DIR = os.path.join(CONFIG_DIR, "content")
CONTENT_FILES = ("cerita.json",)

# Helper root (lewat sudo, lihat packaging/kidsos-pkg): memasang paket apt
# yang dibutuhkan menu, dan meng-upgrade main.py dari repository resmi.
PKG_HELPER = "/usr/lib/kidsos/kidsos-pkg"
PKG_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.+-]*$")

# Warna kartu bergiliran untuk item menu.json yang tidak menentukan warna.
CARD_PALETTE = [
    ("#FFB76B", "#E38B34"), ("#8FD6FF", "#4AA8DE"), ("#9EE6A0", "#56B85B"),
    ("#FFAFD4", "#E26DA4"), ("#FFE57A", "#D9B52C"), ("#CDB0FF", "#9168DA"),
    ("#7EDFD0", "#35AE9B"),
]

# Grab keyboard di level X11 (XGrabKeyboard). Inilah yang membuat Alt+Tab,
# tombol Super, Ctrl+Esc, dll. tidak bisa diproses oleh IceWM/Fluxbox.
USE_KEYBOARD_GRAB = not DEV_MODE

# True = jendela "override-redirect" (IceWM sama sekali tidak mengelolanya,
# jadi taskbar pasti tidak bisa di atasnya). Lebih keras, tetapi beberapa WM
# jadi tidak memberi fokus otomatis. Coba False dulu; aktifkan jika taskbar
# IceWM masih bisa muncul di atas launcher.
BYPASS_WINDOW_MANAGER = False

# Interval pemeriksaan (milidetik).
CHILD_WATCH_MS = 1000     # cek apakah aplikasi anak sudah ditutup
FOCUS_GUARD_MS = 700      # paksa launcher tetap aktif & fullscreen

# Tema warna teks utama.
TEXT_DARK = "#3B2F5C"

# Menu bawaan (dipakai sampai admin menekan "Update Menu"; isinya sama dengan
# menu.json di repository). "command" boleh memakai ~ dan $VAR.
#   "kidsos:<nama>" -> aktivitas bawaan (activities.py & games.py), tampil di
#                      dalam launcher; semua menu bawaan memakai ini, jadi
#                      langsung bisa dimainkan tanpa aplikasi tambahan.
# PENTING untuk aplikasi luar: pakai perintah yang TIDAK langsung "fork lalu
# keluar" (hindari xdg-open / skrip pembungkus yang langsung selesai).
# Launcher memantau proses ini; begitu selesai, layar dikunci lagi.
MENU_ITEMS = [
    {"emoji": "📖", "title": "Buku Cerita", "subtitle": "Dongeng bergambar & dibacakan",
     "color": "#CDB0FF", "shade": "#9168DA", "command": "kidsos:cerita"},
    {"emoji": "🔤", "title": "Belajar Membaca", "subtitle": "Kenal huruf & tebak kata",
     "color": "#FFB76B", "shade": "#E38B34", "command": "kidsos:membaca"},
    {"emoji": "🔢", "title": "Ayo Berhitung", "subtitle": "Hitung benda & tambah-tambahan",
     "color": "#FFAFD4", "shade": "#E26DA4", "command": "kidsos:berhitung"},
    {"emoji": "🐮", "title": "Suara Hewan", "subtitle": "Dengar suara sapi, kucing & kawan-kawan",
     "color": "#FFE57A", "shade": "#D9B52C", "command": "kidsos:hewan"},
    {"emoji": "🔷", "title": "Bentuk & Warna", "subtitle": "Kenali bulat, kotak & warna-warni",
     "color": "#8FD6FF", "shade": "#4AA8DE", "command": "kidsos:bentuk"},
    {"emoji": "🖍️", "title": "Mewarnai", "subtitle": "Warnai gambar atau menggambar bebas",
     "color": "#9EE6A0", "shade": "#56B85B", "command": "kidsos:mewarnai"},
    {"emoji": "🧩", "title": "Puzzle Seru", "subtitle": "Susun kepingan jadi gambar",
     "color": "#FFAFD4", "shade": "#E26DA4", "command": "kidsos:puzzle"},
    {"emoji": "🎹", "title": "Bermain Musik", "subtitle": "Piano, drum & lagu",
     "color": "#FFE57A", "shade": "#D9B52C", "command": "kidsos:musik"},
    {"emoji": "⌨️", "title": "Belajar Mengetik", "subtitle": "Cari huruf di keyboard",
     "color": "#CDB0FF", "shade": "#9168DA", "command": "kidsos:mengetik"},
    {"emoji": "🦖", "title": "Petualangan Dinosaurus", "subtitle": "Lompat, lari & kumpulkan bintang!",
     "color": "#7EDFD0", "shade": "#35AE9B", "command": "kidsos:dino",
     "wide": True},                                        # rentang semua kolom
]


# ---------------------------------------------------------------------------
# FUNGSI GLOBAL: MENJALANKAN APLIKASI EKSTERNAL
# ---------------------------------------------------------------------------

def launch_app(command):
    """Jalankan aplikasi Linux eksternal tanpa memblokir launcher.

    `command` boleh berupa string ("tuxpaint --fullscreen") atau list argumen.
    Mengembalikan objek subprocess.Popen, atau None jika gagal dijalankan
    (mis. aplikasi belum terpasang).

    - Popen (bukan run/call) -> launcher tidak menunggu, tetap hidup di latar.
    - start_new_session=True -> aplikasi anak punya sesi/proses-grup sendiri,
      jadi sinyal ke launcher tidak ikut mematikannya (dan sebaliknya).
    - stdout/stderr dibuang agar tidak ada pipe penuh yang membuat app macet.
    """
    if isinstance(command, str):
        args = shlex.split(command)
    else:
        args = list(command)
    # Ekspansi ~ dan $VAR per argumen (shlex tidak melakukannya).
    args = [os.path.expanduser(os.path.expandvars(a)) for a in args]
    if not args:
        return None

    try:
        return subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except OSError as exc:  # FileNotFoundError, PermissionError, dll.
        print(f"[KidsOS] Gagal menjalankan {args!r}: {exc}", file=sys.stderr)
        return None


def check_admin_password(text):
    """Cocokkan password dengan hash di ADMIN_HASH_FILE, atau ADMIN_PASSWORD."""
    try:
        with open(ADMIN_HASH_FILE, encoding="ascii") as f:
            stored = f.read().strip().lower()
    except OSError:
        stored = ""
    if stored:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, stored)
    return hmac.compare_digest(text.encode("utf-8"), ADMIN_PASSWORD.encode("utf-8"))


def power_action(action):
    """Jalankan 'poweroff' atau 'reboot' lewat sudo tanpa password.

    Izinnya diberikan oleh /etc/sudoers.d/kidsos (dibuat linux/install.sh),
    hanya untuk dua perintah itu. Mengembalikan True jika berhasil.
    """
    if DEV_MODE:
        print(f"[KidsOS] (dev) '{action}' tidak dijalankan", file=sys.stderr)
        return True
    try:
        return subprocess.call(
            ["sudo", "-n", action],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        ) == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# REPOSITORY MENU & UPGRADE
# ---------------------------------------------------------------------------

def _write_json(path, data):
    """Tulis JSON secara atomik (file lama tidak rusak jika listrik mati)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def load_settings():
    settings = {"repo_url": DEFAULT_REPO_URL, "auto_update": False, "music": True}
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            settings.update(data)
    except (OSError, ValueError):
        pass
    return settings


def save_settings(settings):
    _write_json(SETTINGS_FILE, settings)


def resolve_repo_url(url):
    """Link repo GitHub -> URL mentah menu.json; URL lain dipakai apa adanya."""
    url = url.strip()
    m = re.match(r"^https?://github\.com/([^/]+)/([^/#?]+?)(?:\.git)?/?$", url)
    if m:
        return f"https://raw.githubusercontent.com/{m[1]}/{m[2]}/HEAD/menu.json"
    return url


def normalize_menu(data):
    """Validasi isi menu.json dan kembalikan daftar item siap pakai.

    Format: {"items": [{"title", "command", "emoji"?, "subtitle"?, "color"?,
    "shade"?, "wide"?, "packages"?}, ...]} atau langsung list item.
    Melempar ValueError jika tidak valid.
    """
    items = data.get("items") if isinstance(data, dict) else data
    if not isinstance(items, list) or not items:
        raise ValueError("tidak ada daftar 'items'")
    result = []
    for i, raw in enumerate(items, 1):
        if not isinstance(raw, dict) or not raw.get("title") or not raw.get("command"):
            raise ValueError(f"item ke-{i} wajib punya 'title' dan 'command'")
        command = raw["command"]
        if not (isinstance(command, str)
                or (isinstance(command, list) and all(isinstance(a, str) for a in command))):
            raise ValueError(f"'command' item ke-{i} harus teks atau list teks")
        packages = raw.get("packages", [])
        if not isinstance(packages, list) or not all(
                isinstance(pk, str) and PKG_NAME_RE.match(pk) for pk in packages):
            raise ValueError(f"'packages' item ke-{i} tidak valid")
        color, shade = CARD_PALETTE[(i - 1) % len(CARD_PALETTE)]
        if QColor(str(raw.get("color", ""))).isValid():
            color = str(raw["color"])
            shade = QColor(color).darker(125).name()
        if QColor(str(raw.get("shade", ""))).isValid():
            shade = str(raw["shade"])
        result.append({
            "emoji": str(raw.get("emoji", "⭐")),
            "title": str(raw["title"]),
            "subtitle": str(raw.get("subtitle", "")),
            "color": color,
            "shade": shade,
            "command": command,
            "wide": bool(raw.get("wide", False)),
            "packages": packages,
        })
    return result


def load_menu():
    """Menu dari repository (salinan terakhir) atau MENU_ITEMS bawaan."""
    try:
        with open(MENU_CACHE_FILE, encoding="utf-8") as f:
            return normalize_menu(json.load(f))
    except (OSError, ValueError):
        return MENU_ITEMS


def package_installed(name):
    try:
        out = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", name],
            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return True   # bukan sistem Debian (mis. uji di Windows): lewati
    return out.returncode == 0 and "install ok installed" in out.stdout


def run_helper(auth, *args, timeout=3600):
    """Jalankan PKG_HELPER sebagai root (izin: /etc/sudoers.d/kidsos).

    auth = (username, password) akun admin Linux. Dikirim lewat stdin (tidak
    terlihat di `ps`); helper memeriksanya sendiri sebagai root dan menolak
    bekerja jika salah, jadi izin sudo tanpa password itu tidak bisa
    disalahgunakan tanpa password admin.
    """
    if DEV_MODE:
        print(f"[KidsOS] (dev) helper tidak dijalankan: {args}", file=sys.stderr)
        return auth[1] == ADMIN_PASSWORD   # uji: pakai password admin bawaan
    user, password = auth
    try:
        return subprocess.run(
            ["sudo", "-n", PKG_HELPER, *args],
            input=f"{user}\n{password}\n".encode("utf-8"),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
        ).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def check_linux_login(auth):
    """True jika auth adalah akun admin Linux (root / grup sudo) yang benar."""
    return run_helper(auth, "check-auth", timeout=60)


def read_conf(key, default):
    """Nilai dari /etc/kidsos/kidsos.conf (dibuat kidsos-setup)."""
    try:
        with open("/etc/kidsos/kidsos.conf", encoding="utf-8") as f:
            for line in f:
                if line.startswith(key + "="):
                    return line.split("=", 1)[1].strip() or default
    except OSError:
        pass
    return default


def default_admin_user():
    return read_conf("ADMIN_USER", "root")


# Resolusi layar: default 640x480 (ringan); admin bisa mengubah di Panel Admin.
# Nilainya disimpan root di /etc/kidsos/kidsos.conf (RESOLUTION=...) dan
# dipakai kidsos-session (xrandr) serta menu boot GRUB.
RES_RE = re.compile(r"^\d{3,4}x\d{3,4}$")
FALLBACK_RESOLUTIONS = ["640x480", "800x600", "1024x768", "1280x720", "1366x768", "1920x1080"]


def current_resolution():
    return read_conf("RESOLUTION", "640x480")


def _xrandr(*args):
    try:
        return subprocess.run(["xrandr", *args], capture_output=True, text=True,
                              timeout=10, stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None


def available_resolutions():
    """Resolusi yang didukung monitor (dari xrandr), kecil ke besar."""
    out = _xrandr()
    modes = []
    if out is not None and out.returncode == 0:
        for line in out.stdout.splitlines():
            m = re.match(r"^\s+(\d{3,4}x\d{3,4})\s", line)
            if m and m[1] not in modes:
                modes.append(m[1])
    if not modes:
        modes = list(FALLBACK_RESOLUTIONS)
    modes.sort(key=lambda r: tuple(int(v) for v in r.split("x")))
    return modes[:11]


def apply_resolution(res):
    """Ubah resolusi X sekarang juga (sebagai user anak, tanpa root)."""
    if DEV_MODE:
        print(f"[KidsOS] (dev) resolusi tidak diubah: {res}", file=sys.stderr)
        return True
    if res == "auto":
        out = _xrandr()
        if out is None or out.returncode != 0:
            return False
        ok = True
        for line in out.stdout.splitlines():
            if " connected" in line:
                r = _xrandr("--output", line.split()[0], "--auto")
                ok = ok and r is not None and r.returncode == 0
        return ok
    r = _xrandr("-s", res)
    return r is not None and r.returncode == 0


def update_menu(url, progress, auth=None):
    """Unduh menu.json, pasang aplikasi yang dibutuhkan, simpan salinannya.

    Tanpa auth (update otomatis saat menyala) hanya menu & isi yang
    diperbarui; aplikasi baru dipasang saat admin login & Update Menu.
    """
    url = resolve_repo_url(url)
    progress("⬇️ Mengunduh menu...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "KidsOS"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read(MENU_MAX_BYTES + 1)
    except urllib.error.URLError as exc:
        return False, f"😅 Gagal mengunduh: {getattr(exc, 'reason', exc)}"
    try:
        if len(raw) > MENU_MAX_BYTES:
            raise ValueError("file terlalu besar")
        items = normalize_menu(json.loads(raw.decode("utf-8")))
    except (ValueError, UnicodeDecodeError) as exc:
        return False, f"😅 menu.json tidak valid: {exc}"

    note = ""
    wanted = sorted({pk for it in items for pk in it["packages"]})
    missing = [pk for pk in wanted if not package_installed(pk)]
    if missing and auth is None:
        note = " (aplikasi baru dipasang saat admin Update Menu)"
    elif missing:
        progress(f"📦 Memasang aplikasi: {', '.join(missing)}...")
        if not run_helper(auth, "install", *missing):
            note = " (ada aplikasi yang gagal dipasang)"

    fetch_content(url.rsplit("/", 1)[0], progress)

    _write_json(MENU_CACHE_FILE, {
        "source": url,
        "updated": time.strftime("%Y-%m-%d %H:%M"),
        "items": items,
    })
    return True, f"✅ Menu diperbarui: {len(items)} permainan{note}"


def fetch_content(base_url, progress):
    """Unduh content/<file>.json (opsional); file yang gagal dilewati saja."""
    for name in CONTENT_FILES:
        progress(f"📚 Mengunduh {name}...")
        try:
            req = urllib.request.Request(f"{base_url}/content/{name}",
                                         headers={"User-Agent": "KidsOS"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read(MENU_MAX_BYTES + 1)
            if len(raw) > MENU_MAX_BYTES:
                continue
            data = json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, ValueError, UnicodeDecodeError, OSError):
            continue
        if isinstance(data, dict):
            _write_json(os.path.join(CONTENT_DIR, name), data)


def upgrade_self(progress, auth):
    """Ganti /opt/kidsos/main.py dengan versi terbaru dari repository resmi.

    Dikerjakan helper root; sumbernya REPO_URL di /etc/kidsos/kidsos.conf
    (milik root), bukan dari input di layar.
    """
    progress("⬆️ Mengunduh KidsOS terbaru...")
    if run_helper(auth, "upgrade-self", timeout=600):
        return True, "✅ KidsOS diperbarui. Memulai ulang menu..."
    return False, "😅 Upgrade gagal (cek internet / isi repository)."


class Worker(QObject):
    """Jalankan fungsi lambat (unduh, apt) di thread terpisah.

    fn(progress) harus mengembalikan (berhasil, pesan). Sinyal dipancarkan
    dari thread pekerja; Qt otomatis mengantrekannya ke thread UI, jadi slot
    yang terhubung aman menyentuh widget.
    """

    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self._fn = fn

    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            ok, msg = self._fn(self.progress.emit)
        except Exception as exc:  # jangan sampai thread mati diam-diam
            ok, msg = False, f"😅 Gagal: {exc}"
        self.finished.emit(ok, msg)


# ---------------------------------------------------------------------------
# KOMPONEN UI
# ---------------------------------------------------------------------------

class CardButton(QPushButton):
    """Kartu menu besar: emoji di kiri, judul + keterangan di kanan.

    Efek "ditekan" dibuat dengan gaya tombol 3D: sisi bawah (border-bottom)
    tebal berwarna lebih gelap. Saat :pressed, border-bottom menipis dan
    margin-top bertambah sehingga muka kartu terlihat "turun" masuk ke bawah.
    Isi kartu (label) ikut digeser agar ilusi tetap rapi.
    """

    def __init__(self, item, scale, parent=None):
        super().__init__(parent)
        px = lambda v: max(1, int(v * scale))

        self.setObjectName("card")
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)          # tidak bisa dipilih lewat Tab
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(px(110))

        self._depth = px(10)                      # tebal "sisi bawah" kartu
        self._shift = 0
        pad = px(18)
        self._margins = (pad * 2, pad, pad, pad + self._depth)

        # --- Isi kartu -----------------------------------------------------
        lay = QHBoxLayout(self)
        lay.setContentsMargins(*self._margins)
        lay.setSpacing(px(20))

        emoji = QLabel(item["emoji"])
        emoji.setObjectName("cardEmoji")
        emoji.setAlignment(Qt.AlignCenter)

        text_box = QVBoxLayout()
        text_box.setSpacing(px(2))
        title = QLabel(item["title"])
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        subtitle = QLabel(item.get("subtitle", ""))
        subtitle.setObjectName("cardSubtitle")
        subtitle.setWordWrap(True)
        text_box.addStretch(1)
        text_box.addWidget(title)
        text_box.addWidget(subtitle)
        text_box.addStretch(1)

        lay.addWidget(emoji)
        lay.addLayout(text_box, 1)

        # Label tidak boleh "menelan" klik; klik harus sampai ke tombol.
        for lbl in (emoji, title, subtitle):
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        # --- QSS khusus kartu ini -------------------------------------------
        base = QColor(item["color"])
        hover = base.lighter(106).name()
        pressed = base.darker(106).name()
        shade = item["shade"]
        self.setStyleSheet(f"""
            QPushButton#card {{
                background-color: {item['color']};
                border: none;
                border-bottom: {self._depth}px solid {shade};
                border-radius: {px(34)}px;
                margin-top: 0px;
            }}
            QPushButton#card:hover {{
                background-color: {hover};
            }}
            QPushButton#card:pressed {{
                background-color: {pressed};
                border-bottom: 2px solid {shade};
                margin-top: {self._depth - 2}px;
            }}
            QLabel {{ background: transparent; color: {TEXT_DARK}; }}
            QLabel#cardEmoji    {{ font-size: {px(64)}px; }}
            QLabel#cardTitle    {{ font-size: {px(30)}px; font-weight: 900; }}
            QLabel#cardSubtitle {{ font-size: {px(18)}px; font-weight: 600;
                                   color: rgba(59, 47, 92, 170); }}
        """)

    # Geser isi kartu mengikuti status ditekan (isDown) --------------------
    def _sync_press_offset(self):
        shift = (self._depth - 2) if self.isDown() else 0
        if shift != self._shift:
            self._shift = shift
            l, t, r, b = self._margins
            self.layout().setContentsMargins(l, t + shift, r, b - shift)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        self._sync_press_offset()

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self._sync_press_offset()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._sync_press_offset()


class Overlay(QWidget):
    """Dasar semua dialog: kartu putih di tengah, latar gelap transparan.

    Dibuat sebagai overlay di DALAM jendela launcher (bukan jendela X11
    terpisah). Alasannya khusus untuk antiX:
      * antiX biasanya tanpa compositor -> jendela terpisah tidak bisa punya
        sudut membulat/transparan (sudutnya jadi kotak hitam).
      * Grab keyboard tetap milik launcher, jadi anak tetap tidak bisa
        Alt+Tab saat dialog terbuka; ketikan tetap masuk ke kotak isian.
      * Tidak ada urusan "dialog tertutup di belakang jendela always-on-top".
    """

    closed = pyqtSignal()

    def __init__(self, parent, scale, accent="#CDB0FF", timeout_ms=30_000,
                 width=560):
        super().__init__(parent)
        self.px = px = lambda v: max(1, int(v * scale))

        self.setObjectName("overlay")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.hide()

        self.card = QFrame(self)
        self.card.setObjectName("overlayCard")
        self.card.setFixedWidth(px(width))
        self.body = QVBoxLayout(self.card)
        self.body.setContentsMargins(px(36), px(30), px(36), px(30))
        self.body.setSpacing(px(14))

        outer = QVBoxLayout(self)
        outer.addStretch(1)
        outer.addWidget(self.card, 0, Qt.AlignHCenter)
        outer.addStretch(1)

        self.setStyleSheet(f"""
            QWidget#overlay {{ background-color: rgba(40, 30, 70, 170); }}
            QFrame#overlayCard {{
                background-color: #FFFFFF;
                border: {px(6)}px solid {accent};
                border-radius: {px(32)}px;
            }}
            QLabel {{ background: transparent; color: {TEXT_DARK}; }}
            QLabel#dlgTitle {{ font-size: {px(36)}px; font-weight: 900; }}
            QLabel#dlgInfo  {{ font-size: {px(18)}px; }}
            QLabel#dlgError {{ font-size: {px(18)}px; font-weight: 700; color: #E0405E; }}
            QLineEdit#adminEdit {{
                font-size: {px(28)}px;
                padding: {px(12)}px;
                border: {px(4)}px solid #8FD6FF;
                border-radius: {px(20)}px;
                background: #F4FAFF;
                color: {TEXT_DARK};
            }}
            QLineEdit#adminEdit:focus {{ border-color: #4AA8DE; }}
            QLineEdit#urlEdit {{
                font-size: {px(19)}px;
                padding: {px(10)}px;
                border: {px(4)}px solid #FFE57A;
                border-radius: {px(18)}px;
                background: #FFFCEB;
                color: {TEXT_DARK};
            }}
            QLineEdit#urlEdit:focus {{ border-color: #D9B52C; }}
            QCheckBox {{ font-size: {px(18)}px; color: {TEXT_DARK}; spacing: {px(10)}px; }}
            QCheckBox::indicator {{
                width: {px(26)}px; height: {px(26)}px;
                border: {px(3)}px solid #D9B52C; border-radius: {px(8)}px;
                background: #FFFFFF;
            }}
            QCheckBox::indicator:checked {{ background: #56B85B; }}
            QPushButton:disabled {{ color: rgba(59, 47, 92, 90); }}
            QPushButton {{
                font-size: {px(24)}px; font-weight: 800;
                min-height: {px(58)}px;
                padding: 0 {px(14)}px;
                border: none;
                border-radius: {px(22)}px;
                color: {TEXT_DARK};
            }}
            QPushButton#btnCancel {{ background: #EDE7F6; border-bottom: {px(6)}px solid #C7BCDD; }}
            QPushButton#btnOk     {{ background: #9EE6A0; border-bottom: {px(6)}px solid #56B85B; }}
            QPushButton#btnInfo   {{ background: #8FD6FF; border-bottom: {px(6)}px solid #4AA8DE; }}
            QPushButton#btnWarn   {{ background: #FFE57A; border-bottom: {px(6)}px solid #D9B52C; }}
            QPushButton#btnDanger {{ background: #FFB0BE; border-bottom: {px(6)}px solid #E0405E; }}
            QPushButton:pressed {{ border-bottom-width: 2px; margin-top: {px(4)}px; }}
        """)

        # Tutup otomatis jika dibiarkan terbuka (mis. anak iseng menekan).
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(timeout_ms)
        self._idle.timeout.connect(self.close_dialog)

    # -- Pembantu untuk subclass ------------------------------------------
    def add_label(self, text, name, wrap=True):
        lbl = QLabel(text)
        lbl.setObjectName(name)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setWordWrap(wrap)
        self.body.addWidget(lbl)
        return lbl

    def make_button(self, text, name, slot):
        btn = QPushButton(text)
        btn.setObjectName(name)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    def button_row(self, *buttons):
        row = QHBoxLayout()
        row.setSpacing(self.px(16))
        for b in buttons:
            row.addWidget(b)
        self.body.addLayout(row)

    def poke(self):
        """Reset hitungan mundur tutup-otomatis."""
        self._idle.start()

    def _shake(self):
        """Animasi 'geleng' kecil saat password salah."""
        start = self.card.pos()
        anim = QPropertyAnimation(self.card, b"pos", self)
        anim.setDuration(360)
        anim.setEasingCurve(QEasingCurve.InOutSine)
        for i, dx in enumerate((0, -18, 16, -12, 8, -4, 0)):
            anim.setKeyValueAt(i / 6, start + QPoint(dx, 0))
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    # -- API ---------------------------------------------------------------
    def open_dialog(self):
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self._idle.start()
        self.on_open()

    def on_open(self):
        pass

    def finish(self):
        """Tutup tanpa sinyal 'closed' (dipakai saat aksi berhasil)."""
        self._idle.stop()
        self.hide()

    def close_dialog(self):
        self.finish()
        self.closed.emit()

    def mousePressEvent(self, event):
        self.poke()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close_dialog()
        event.accept()  # jangan teruskan tombol apa pun ke atas


class AdminDialog(Overlay):
    """Dialog password Mode Admin."""

    accepted = pyqtSignal()

    def __init__(self, parent, scale):
        super().__init__(parent, scale)

        self.add_label("🔒 Mode Admin", "dlgTitle", wrap=False)
        self.add_label("Masukkan kata sandi untuk membuka pengaturan.", "dlgInfo")

        self.edit = QLineEdit()
        self.edit.setObjectName("adminEdit")
        self.edit.setEchoMode(QLineEdit.Password)
        self.edit.setPlaceholderText("Kata sandi")
        self.edit.setAlignment(Qt.AlignCenter)
        self.edit.returnPressed.connect(self._try_login)
        self.edit.textEdited.connect(lambda _t: self.poke())
        self.body.addWidget(self.edit)

        self.error = self.add_label(" ", "dlgError")

        self.button_row(
            self.make_button("Batal", "btnCancel", self.close_dialog),
            self.make_button("Masuk", "btnOk", self._try_login),
        )

    def on_open(self):
        self.edit.clear()
        self.error.setText(" ")
        self.edit.setFocus()

    def _try_login(self):
        if check_admin_password(self.edit.text()):
            self.edit.clear()
            self.finish()
            self.accepted.emit()
        else:
            self.error.setText("Kata sandi salah 🙅")
            self.edit.clear()
            self.poke()
            self._shake()



class AdminPanel(Overlay):
    """Menu setelah password benar: jalan keluar resmi dari mode anak."""

    desktop = pyqtSignal()
    terminal = pyqtSignal()
    repository = pyqtSignal()
    update = pyqtSignal()
    upgrade = pyqtSignal()
    resolution = pyqtSignal()
    reboot = pyqtSignal()
    poweroff = pyqtSignal()

    def __init__(self, parent, scale):
        super().__init__(parent, scale, accent="#8FD6FF",
                         timeout_ms=60_000, width=760)

        self.add_label("🛠️ Panel Admin", "dlgTitle", wrap=False)
        self.add_label("Panel ini tertutup sendiri setelah 1 menit tanpa aktivitas.",
                       "dlgInfo")

        def act(signal):
            return lambda: (self.finish(), signal.emit())

        self.button_row(
            self.make_button("🖥️ Desktop Admin", "btnInfo", act(self.desktop)),
            self.make_button("💻 Terminal", "btnInfo", act(self.terminal)),
            self.make_button("🖥️ Resolusi", "btnInfo", act(self.resolution)),
        )
        self.button_row(
            self.make_button("📦 Repository", "btnOk", act(self.repository)),
            self.make_button("⬇️ Update Menu", "btnOk", act(self.update)),
            self.make_button("⬆️ Upgrade", "btnOk", act(self.upgrade)),
        )
        self.button_row(
            self.make_button("🔄 Mulai Ulang", "btnWarn", act(self.reboot)),
            self.make_button("⏻ Matikan", "btnDanger", act(self.poweroff)),
        )
        self.button_row(
            self.make_button("↩ Kembali ke Mode Anak", "btnOk", self.close_dialog),
        )


class ConfirmDialog(Overlay):
    """Konfirmasi ya/tidak yang ramah anak."""

    confirmed = pyqtSignal()

    def __init__(self, parent, scale, title, info, yes_text, no_text):
        super().__init__(parent, scale, accent="#FFAFD4", timeout_ms=20_000,
                         width=720)
        self.add_label(title, "dlgTitle", wrap=False)
        self.add_label(info, "dlgInfo")
        self.button_row(
            self.make_button(no_text, "btnOk", self.close_dialog),
            self.make_button(yes_text, "btnDanger", self._yes),
        )

    def _yes(self):
        self.finish()
        self.confirmed.emit()


class LoginDialog(Overlay):
    """Login akun Linux (root / anggota grup sudo) sebelum update & upgrade.

    Password diperiksa oleh helper root (unix_chkpwd), bukan oleh launcher.
    Jika benar, callback dipanggil dengan (username, password); password
    hanya disimpan di memori selama proses itu berjalan.
    """

    def __init__(self, parent, scale):
        super().__init__(parent, scale, accent="#FFB76B", width=640)
        self._callback = None
        self._worker = None

        self.add_label("🔑 Login Akun Linux", "dlgTitle", wrap=False)
        self.add_label("Update & upgrade butuh akun admin Linux "
                       "(root atau anggota grup sudo).", "dlgInfo")

        self.user = QLineEdit()
        self.user.setObjectName("urlEdit")
        self.user.setPlaceholderText("Nama user (mis. root)")
        self.user.setAlignment(Qt.AlignCenter)
        self.user.textEdited.connect(lambda _t: self.poke())
        self.user.returnPressed.connect(lambda: self.password.setFocus())
        self.body.addWidget(self.user)

        self.password = QLineEdit()
        self.password.setObjectName("adminEdit")
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Password Linux")
        self.password.setAlignment(Qt.AlignCenter)
        self.password.textEdited.connect(lambda _t: self.poke())
        self.password.returnPressed.connect(self._submit)
        self.body.addWidget(self.password)

        self.error = self.add_label(" ", "dlgError")

        self.btn_ok = self.make_button("Masuk", "btnOk", self._submit)
        self.button_row(self.make_button("Batal", "btnCancel", self.close_dialog),
                        self.btn_ok)

    def ask(self, callback):
        """Buka dialog; callback((user, password)) dipanggil jika login benar."""
        self._callback = callback
        self.open_dialog()

    def on_open(self):
        if not self.user.text():
            self.user.setText(default_admin_user())
        self.password.clear()
        self.error.setText(" ")
        self._set_busy(False)
        self.password.setFocus()

    def _set_busy(self, busy):
        for w in (self.user, self.password, self.btn_ok):
            w.setEnabled(not busy)

    def _submit(self):
        if self._worker is not None:
            return
        auth = (self.user.text().strip(), self.password.text())
        if not auth[0] or not auth[1]:
            self.error.setText("Isi nama user & password.")
            return
        self._set_busy(True)
        self._idle.stop()
        self.error.setText("⏳ Memeriksa...")
        self._worker = Worker(lambda _emit: (check_linux_login(auth), ""), self)
        self._worker.finished.connect(lambda ok, _m: self._checked(ok, auth))
        self._worker.start()

    def _checked(self, ok, auth):
        self._worker = None
        if not self.isVisible():        # dialog sudah ditutup saat memeriksa
            return
        if ok:
            callback, self._callback = self._callback, None
            self.password.clear()
            self.finish()
            if callback:
                callback(auth)
            return
        self._set_busy(False)
        self.password.clear()
        self.password.setFocus()
        self.error.setText("User/password salah, atau bukan admin 🙅")
        self.poke()
        self._shake()


class ResolutionDialog(Overlay):
    """Admin memilih resolusi layar (berlaku untuk menu anak & menu boot)."""

    chosen = pyqtSignal(str)

    def __init__(self, parent, scale):
        super().__init__(parent, scale, accent="#8FD6FF", timeout_ms=60_000, width=700)
        self.add_label("🖥️ Resolusi Layar", "dlgTitle", wrap=False)
        self.add_label("Resolusi kecil = lebih ringan. Berlaku untuk menu anak "
                       "& menu boot.", "dlgInfo")
        self.current = self.add_label("", "dlgInfo")
        self.grid = QGridLayout()
        self.grid.setSpacing(self.px(10))
        self.body.addLayout(self.grid)
        self.button_row(self.make_button("Batal", "btnCancel", self.close_dialog))

    def on_open(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        now = current_resolution()
        self.current.setText(f"Sekarang: {'Otomatis' if now == 'auto' else now}")
        modes = available_resolutions()
        for i, res in enumerate(modes + ["auto"]):
            text = "✨ Otomatis (terbaik)" if res == "auto" else res.replace("x", " × ")
            btn = self.make_button(text, "btnOk" if res == now else "btnInfo",
                                   lambda _c=False, r=res: self._pick(r))
            if res == "auto":                     # satu baris penuh di bawah
                self.grid.addWidget(btn, (len(modes) + 2) // 3, 0, 1, 3)
            else:
                self.grid.addWidget(btn, i // 3, i % 3)

    def _pick(self, res):
        self.finish()
        self.chosen.emit(res)


class RepoDialog(Overlay):
    """Admin mengisi link repository menu & memicu update."""

    saved = pyqtSignal(str, bool)        # url, update otomatis saat menyala
    update_requested = pyqtSignal(str)   # url

    def __init__(self, parent, scale):
        super().__init__(parent, scale, accent="#FFE57A",
                         timeout_ms=120_000, width=780)

        self.add_label("📦 Repository Menu", "dlgTitle", wrap=False)
        self.add_label("Link repo GitHub (berisi menu.json di root) "
                       "atau link langsung ke file menu.json.", "dlgInfo")

        self.edit = QLineEdit()
        self.edit.setObjectName("urlEdit")
        self.edit.setPlaceholderText(DEFAULT_REPO_URL)
        self.edit.textEdited.connect(lambda _t: self.poke())
        self.body.addWidget(self.edit)

        self.auto = QCheckBox("Update otomatis setiap komputer menyala")
        self.auto.setCursor(Qt.PointingHandCursor)
        self.body.addWidget(self.auto, 0, Qt.AlignHCenter)

        self.status = self.add_label(" ", "dlgInfo")

        self.btn_close = self.make_button("Tutup", "btnCancel", self.close_dialog)
        self.btn_save = self.make_button("Simpan", "btnOk", self._save)
        self.btn_update = self.make_button("⬇️ Update Sekarang", "btnInfo", self._update)
        self.button_row(self.btn_close, self.btn_save, self.btn_update)
        self._busy = False

    def on_open(self):
        settings = load_settings()
        self.edit.setText(settings.get("repo_url", ""))
        self.auto.setChecked(bool(settings.get("auto_update")))
        if not self._busy:
            self.status.setText(self._last_update_text())
        self.edit.setFocus()

    @staticmethod
    def _last_update_text():
        try:
            with open(MENU_CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            return f"Update terakhir: {data.get('updated', '?')}"
        except (OSError, ValueError):
            return "Belum pernah update: memakai menu bawaan."

    def _url(self):
        url = self.edit.text().strip()
        if not re.match(r"^https?://", url):
            self.status.setText("😅 Link harus diawali http:// atau https://")
            return None
        return url

    def _save(self):
        url = self._url()
        if url:
            self.saved.emit(url, self.auto.isChecked())
            self.status.setText("💾 Tersimpan.")

    def _update(self):
        url = self._url()
        if url:
            self.saved.emit(url, self.auto.isChecked())
            self.update_requested.emit(url)

    def set_busy(self, busy, text=None):
        self._busy = busy
        for w in (self.edit, self.auto, self.btn_save, self.btn_update):
            w.setEnabled(not busy)
        if text:
            self.status.setText(text)
        if busy:
            self._idle.stop()      # jangan tutup sendiri saat sedang update
        elif self.isVisible():
            self.poke()


class ClickSounds(QObject):
    """Bunyi "pop" untuk SEMUA tombol yang ditekan.

    Tombol yang punya bunyi sendiri (tuts piano, jawaban kuis, dll.) diberi
    properti "silent" agar tidak berbunyi dua kali.
    """

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.MouseButtonPress and isinstance(obj, QAbstractButton)
                and obj.isEnabled() and not obj.property("silent")):
            sounds.play("pop")
        return False


class Splash(QWidget):
    """Layar sambutan (splash.gif) saat menu anak pertama kali tampil."""

    finished = pyqtSignal()

    def __init__(self, parent, scale):
        super().__init__(parent)
        px = lambda v: max(1, int(v * scale))
        self.setObjectName("splash")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget#splash {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #FFF6E5, stop:0.5 #FFEFF6, stop:1 #E9F6FF);
            }}
            QLabel {{ background: transparent; color: {TEXT_DARK}; }}
            QLabel#splashTitle {{ font-size: {px(46)}px; font-weight: 900; }}
            QLabel#splashSub {{ font-size: {px(24)}px; font-weight: 700;
                                color: rgba(59, 47, 92, 170); }}
        """)
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        self.anim = QLabel()
        self.anim.setAlignment(Qt.AlignCenter)
        self.movie = QMovie(SPLASH_GIF)
        if self.movie.isValid():
            self.movie.setScaledSize(_fit(self.movie, px(360)))
            self.anim.setMovie(self.movie)
        lay.addWidget(self.anim)
        title = QLabel("Halo! Selamat datang 🌈")
        title.setObjectName("splashTitle")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel("Ayo bermain & belajar!")
        sub.setObjectName("splashSub")
        sub.setAlignment(Qt.AlignCenter)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addStretch(1)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.close_splash)

    def start(self):
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        if self.movie.isValid():
            self.movie.start()
        sounds.play("tada")
        self._timer.start(SPLASH_MS)

    def close_splash(self):
        if not self.isVisible():
            return
        self._timer.stop()
        self.movie.stop()
        self.hide()
        self.finished.emit()

    def mousePressEvent(self, _event):
        self.close_splash()                 # sentuh = langsung ke menu

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())


def _fit(movie, box):
    """Ukuran GIF diperkecil/diperbesar agar muat di kotak box x box."""
    movie.jumpToFrame(0)
    size = movie.currentImage().size()
    size.scale(box, box, Qt.KeepAspectRatio)
    return size


# ---------------------------------------------------------------------------
# JENDELA UTAMA LAUNCHER
# ---------------------------------------------------------------------------

class KidsLauncher(QWidget):

    def __init__(self):
        super().__init__()
        self._allow_exit = False      # hanya True setelah password admin benar
        self._child = None            # Popen aplikasi anak yang sedang jalan
        self._child_name = ""
        self._child_started = 0.0
        self._grabbed = False         # status grab keyboard X11
        self._worker = None           # Worker update/upgrade yang sedang jalan
        self.menu_items = load_menu()
        sounds.enabled["music"] = bool(load_settings().get("music", True))

        # --- Flags jendela kiosk -------------------------------------------
        if not DEV_MODE:
            flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
            if BYPASS_WINDOW_MANAGER:
                flags |= Qt.X11BypassWindowManagerHint
            self.setWindowFlags(flags)
        self.setWindowTitle("Kids OS Launcher")
        self.setObjectName("root")
        self.setAttribute(Qt.WA_StyledBackground, True)

        # Skala UI mengikuti ukuran layar (acuan 1024x768). Lebar ikut dihitung
        # agar tetap muat di layar kecil seperti 640x480.
        screen = QApplication.primaryScreen().geometry()
        self.scale = max(0.45, min(screen.height() / 768.0, screen.width() / 1024.0, 2.2))
        self.compact = screen.width() < 900

        self._build_ui()

        # Timer pemantau aplikasi anak.
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(CHILD_WATCH_MS)
        self._watch_timer.timeout.connect(self._check_child)

        # Timer "penjaga fokus": kalau entah bagaimana launcher kehilangan
        # fokus / keluar dari fullscreen saat tidak ada app anak, kembalikan.
        self._guard_timer = QTimer(self)
        self._guard_timer.setInterval(FOCUS_GUARD_MS)
        self._guard_timer.timeout.connect(self._guard_focus)
        if not DEV_MODE:
            self._guard_timer.start()

        # Musik latar: ulangi lagu yang selesai; mulai setelah layar sambutan.
        self._music_timer = QTimer(self)
        self._music_timer.setInterval(1000)
        self._music_timer.timeout.connect(sounds.music.tick)
        self._music_timer.start()
        if SHOW_SPLASH:
            self.splash = Splash(self, self.scale)
            self.splash.finished.connect(lambda: sounds.music.play("menu"))
            QTimer.singleShot(0, self.splash.start)
        else:
            QTimer.singleShot(300, lambda: sounds.music.play("menu"))

        # Update menu otomatis saat menyala (jika diaktifkan admin). Diam saja
        # kalau gagal, mis. internet belum tersambung.
        settings = load_settings()
        if settings.get("auto_update") and settings.get("repo_url"):
            QTimer.singleShot(5000, lambda: self._update_menu(
                settings["repo_url"], silent=True))

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        s = self.scale
        px = lambda v: max(1, int(v * s))

        self.setStyleSheet(f"""
            QWidget#root {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 #FFF6E5, stop:0.5 #FFEFF6, stop:1 #E9F6FF);
            }}
            QLabel {{ background: transparent; color: {TEXT_DARK}; }}
            QLabel#header    {{ font-size: {px(34 if self.compact else 48)}px; font-weight: 900; }}
            QLabel#subheader {{ font-size: {px(22)}px; font-weight: 600;
                                color: rgba(59, 47, 92, 160); }}
            QPushButton#adminBtn {{
                font-size: {px(15)}px; font-weight: 700;
                color: rgba(59, 47, 92, 150);
                background: rgba(255, 255, 255, 150);
                border: {px(2)}px solid rgba(59, 47, 92, 40);
                border-radius: {px(18)}px;
                padding: {px(8)}px {px(16)}px;
            }}
            QPushButton#adminBtn:pressed {{ background: rgba(205, 176, 255, 200); }}
            QPushButton#powerBtn {{
                font-size: {px(17)}px; font-weight: 800;
                color: {TEXT_DARK};
                background: #FFD1DC;
                border: none;
                border-bottom: {px(4)}px solid #E26DA4;
                border-radius: {px(18)}px;
                padding: {px(8)}px {px(16)}px;
            }}
            QPushButton#powerBtn:pressed {{ border-bottom-width: 1px; margin-top: {px(3)}px; }}
            QLabel#toast {{
                font-size: {px(22)}px; font-weight: 800;
                background: #FFFFFF;
                border: {px(4)}px solid #FFAFD4;
                border-radius: {px(24)}px;
                padding: {px(10)}px {px(28)}px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(px(40), px(20), px(40), px(24))
        root.setSpacing(px(14))

        # Halaman: [0] menu utama, [1] aktivitas bawaan yang sedang dibuka.
        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)
        self.home = QWidget()
        self.stack.addWidget(self.home)
        home = QVBoxLayout(self.home)
        home.setContentsMargins(0, 0, 0, 0)
        home.setSpacing(px(14))
        self._activity = None

        # --- Header: [Mode Admin] [judul di tengah] [Matikan] ----------------
        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)

        admin_btn = QPushButton("🔒 Mode Admin", self)
        admin_btn.setObjectName("adminBtn")
        admin_btn.setCursor(Qt.PointingHandCursor)
        admin_btn.setFocusPolicy(Qt.NoFocus)
        admin_btn.clicked.connect(self._open_admin)

        power_btn = QPushButton("🌙 Matikan", self)
        power_btn.setObjectName("powerBtn")
        power_btn.setCursor(Qt.PointingHandCursor)
        power_btn.setFocusPolicy(Qt.NoFocus)
        power_btn.clicked.connect(lambda: self.power_dialog.open_dialog())

        self.music_btn = QPushButton(self)
        self.music_btn.setObjectName("powerBtn")
        self.music_btn.setCursor(Qt.PointingHandCursor)
        self.music_btn.setFocusPolicy(Qt.NoFocus)
        self.music_btn.clicked.connect(self._toggle_music)
        self._update_music_btn()

        # Kolom kiri & kanan sama lebar agar judul tetap tepat di tengah.
        # ensurePolished(): terapkan QSS dulu supaya sizeHint memakai font/padding QSS.
        for b in (admin_btn, power_btn, self.music_btn):
            b.ensurePolished()
        gap = px(10)
        side = max(admin_btn.sizeHint().width(),
                   power_btn.sizeHint().width() + self.music_btn.sizeHint().width() + gap)
        admin_btn.setFixedWidth(side)
        right = QWidget()
        right.setFixedWidth(side)
        right_lay = QHBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(gap)
        right_lay.addStretch(1)
        right_lay.addWidget(self.music_btn)
        right_lay.addWidget(power_btn)

        header_box = QVBoxLayout()
        header_box.setSpacing(0)
        # Layar sempit (mis. 640x480): judul ringkas & boleh terlipat.
        header = QLabel("Dunia Bermain & Belajar" if self.compact
                        else "🌈 Dunia Bermain & Belajar 🎈")
        header.setObjectName("header")
        header.setAlignment(Qt.AlignCenter)
        header.setWordWrap(True)
        sub = QLabel("Pilih permainan kesukaanmu! 👇")
        sub.setObjectName("subheader")
        sub.setAlignment(Qt.AlignCenter)
        sub.setWordWrap(True)
        header_box.addWidget(header)
        header_box.addWidget(sub)

        top.addWidget(admin_btn, 0, Qt.AlignLeft | Qt.AlignTop)
        top.addLayout(header_box, 1)
        top.addWidget(right, 0, Qt.AlignRight | Qt.AlignTop)

        home.addLayout(top)

        # --- Grid kartu menu (diisi oleh _populate_menu) --------------------
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(px(26))
        self.grid.setVerticalSpacing(px(22))
        home.addLayout(self.grid, 1)
        self._populate_menu()

        # --- Toast pesan (mis. aplikasi belum terpasang) ---------------------
        self.toast = QLabel("")
        self.toast.setObjectName("toast")
        self.toast.setAlignment(Qt.AlignCenter)
        self.toast.hide()
        root.addWidget(self.toast, 0, Qt.AlignHCenter)
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(self.toast.hide)

        # --- Dialog (overlay) -----------------------------------------------
        self.admin_dialog = AdminDialog(self, s)
        self.admin_panel = AdminPanel(self, s)
        self.admin_dialog.accepted.connect(self.admin_panel.open_dialog)
        self.admin_panel.desktop.connect(self._admin_exit)
        self.admin_panel.terminal.connect(
            lambda: self._start_child(TERMINAL_COMMAND, "Terminal"))
        self.admin_panel.reboot.connect(lambda: self._power("reboot"))
        self.admin_panel.poweroff.connect(lambda: self._power("poweroff"))

        self.power_dialog = ConfirmDialog(
            self, s,
            title="🌙 Sudah selesai bermain?",
            info="Komputer akan dimatikan. Sampai jumpa lagi! 👋",
            yes_text="Ya, matikan", no_text="Belum",
        )
        self.power_dialog.confirmed.connect(lambda: self._power("poweroff"))

        self.repo_dialog = RepoDialog(self, s)
        self.repo_dialog.saved.connect(self._save_repo)
        self.login_dialog = LoginDialog(self, s)
        # Update & upgrade selalu lewat login akun Linux dulu.
        self.repo_dialog.update_requested.connect(
            lambda url: self.login_dialog.ask(
                lambda auth: self._update_menu(url, auth=auth)))
        self.admin_panel.repository.connect(self.repo_dialog.open_dialog)
        self.admin_panel.update.connect(
            lambda: self.login_dialog.ask(
                lambda auth: self._update_menu(load_settings()["repo_url"], auth=auth)))
        self.admin_panel.upgrade.connect(
            lambda: self.login_dialog.ask(self._upgrade_self))

        self.res_dialog = ResolutionDialog(self, s)
        self.admin_panel.resolution.connect(self.res_dialog.open_dialog)
        self.res_dialog.chosen.connect(
            lambda res: self.login_dialog.ask(
                lambda auth: self._set_resolution(res, auth)))

        self.overlays = (self.admin_dialog, self.admin_panel, self.power_dialog,
                         self.repo_dialog, self.login_dialog, self.res_dialog)

    def _populate_menu(self):
        """(Ulang) isi grid; kartu "wide" merentang semua kolom.

        2 kolom untuk menu pendek, 3 kolom jika lebih dari 7 kartu.
        """
        while self.grid.count():
            widget = self.grid.takeAt(0).widget()
            if widget is not None:
                widget.deleteLater()
        cols = 3 if len(self.menu_items) > 7 else 2
        for c in range(3):
            self.grid.setColumnStretch(c, 1 if c < cols else 0)
        row = col = 0
        for item in self.menu_items:
            card = CardButton(item, self.scale * (0.85 if cols == 3 else 1.0))
            # Default argument mengikat item saat ini (hindari bug closure).
            card.clicked.connect(lambda _c=False, it=item: self._on_card(it))
            if item.get("wide"):
                if col != 0:
                    row, col = row + 1, 0
                self.grid.addWidget(card, row, 0, 1, cols)
                row += 1
            else:
                self.grid.addWidget(card, row, col)
                col += 1
                if col == cols:
                    row, col = row + 1, 0
        # Kartu baru tergambar di atas saudara lama; naikkan dialog yang terbuka.
        for overlay in getattr(self, "overlays", ()):
            if overlay.isVisible():
                overlay.raise_()

    def _show_toast(self, text, ms=4000):
        self.toast.setText(text)
        self.toast.show()
        self._toast_timer.start(ms)

    # ------------------------------------------------ Kunci / Lepas layar
    def _grab_keyboard(self):
        """XGrabKeyboard lewat Qt: semua tombol masuk ke launcher, WM buta."""
        if not USE_KEYBOARD_GRAB or self._grabbed:
            return
        handle = self.windowHandle()
        if handle is not None and self.isVisible():
            self._grabbed = handle.setKeyboardGrabEnabled(True)

    def _release_keyboard(self):
        handle = self.windowHandle()
        if handle is not None and self._grabbed:
            handle.setKeyboardGrabEnabled(False)
        self._grabbed = False

    def lock_screen(self):
        """Launcher di atas semua jendela, fullscreen, fokus, keyboard di-grab."""
        if DEV_MODE:
            self.show()
            self.raise_()
            self.activateWindow()
            return
        if BYPASS_WINDOW_MANAGER:
            self.showFullScreen()
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            self.showFullScreen()
        self.raise_()
        self.activateWindow()
        # Grab setelah jendela benar-benar ter-map oleh X server.
        QTimer.singleShot(300, self._grab_keyboard)

    def _yield_to_child(self):
        """Beri jalan untuk aplikasi anak: lepas grab & turun ke belakang.

        Launcher TIDAK ditutup; ia tetap menjadi latar penuh di belakang
        aplikasi anak sehingga desktop IceWM tetap tertutup.
        """
        self._release_keyboard()
        if DEV_MODE:
            return
        if BYPASS_WINDOW_MANAGER:
            # Jendela override-redirect tidak bisa "diturunkan" oleh WM,
            # jadi disembunyikan sementara.
            self.hide()
        else:
            self.setWindowFlag(Qt.WindowStaysOnTopHint, False)  # re-map jendela
            self.showFullScreen()
            self.lower()

    # ------------------------------------------------------ Aplikasi anak
    def _on_card(self, item):
        command = item["command"]
        if isinstance(command, str) and command.startswith("kidsos:"):
            self._open_activity(command[len("kidsos:"):], item["title"])
        else:
            self._start_child(command, item["title"])

    # ------------------------------------------------- Aktivitas bawaan
    def _open_activity(self, name, title):
        if self._activity is not None or self._child is not None:
            return
        activity = create_activity(name, self.scale)
        if activity is None:
            self._show_toast(f"😅 Ups! \"{title}\" belum tersedia. Coba Update Menu.")
            return
        activity.exit_requested.connect(self._close_activity)
        self._activity = activity
        self.stack.addWidget(activity)
        self.stack.setCurrentWidget(activity)
        sounds.play("open")
        sounds.music.play(activity.MUSIC)

    def _close_activity(self):
        activity = self._activity
        if activity is None:
            return
        activity.closing()
        self.stack.setCurrentWidget(self.home)
        self.stack.removeWidget(activity)
        activity.deleteLater()
        self._activity = None
        sounds.music.play("menu")

    def _start_child(self, command, title):
        if self._child is not None:       # cegah dobel-klik membuka 2 app
            return
        proc = launch_app(command)
        if proc is None:
            self._show_toast(f"😅 Ups! \"{title}\" belum terpasang.")
            return
        self._child = proc
        self._child_name = title
        self._child_started = time.monotonic()
        sounds.music.stop()                   # aplikasi luar punya suaranya sendiri
        self._yield_to_child()
        self._watch_timer.start()

    def _check_child(self):
        """Dipanggil berkala: kunci layar lagi setelah aplikasi anak selesai."""
        if self._child is None:
            self._watch_timer.stop()
            return
        code = self._child.poll()         # poll() juga membereskan zombie
        if code is None:
            return                        # masih berjalan
        elapsed = time.monotonic() - self._child_started
        name = self._child_name
        self._child = None
        self._watch_timer.stop()
        self.lock_screen()
        sounds.music.play("menu")
        if code != 0 and elapsed < 3:
            self._show_toast(f"😅 Ups! \"{name}\" belum bisa dibuka.")

    # ------------------------------------------------------- Mode Admin
    def _open_admin(self):
        self.admin_dialog.open_dialog()

    def _leave(self, code):
        """Hentikan launcher dengan kode keluar untuk skrip sesi."""
        stop_speech()
        sounds.shutdown()
        self._allow_exit = True
        self._guard_timer.stop()
        self._release_keyboard()
        QApplication.exit(code)

    def _admin_exit(self):
        """Tutup launcher dan buka desktop IceWM untuk admin.

        Mode --session: skrip kidsos-session membaca kode EXIT_ADMIN_DESKTOP,
        menjalankan IceWM, lalu membuka launcher lagi setelah admin logout.
        Tanpa --session: launcher cukup ditutup (IceWM sudah ada di belakang).
        """
        self._close_activity()
        self._leave(EXIT_ADMIN_DESKTOP if SESSION_MODE else 0)

    # ------------------------------------------- Repository menu & upgrade
    def _save_repo(self, url, auto_update):
        settings = load_settings()
        settings.update(repo_url=url, auto_update=auto_update)
        try:
            save_settings(settings)
        except OSError as exc:
            self._show_toast(f"😅 Gagal menyimpan pengaturan: {exc}")

    def _run_worker(self, fn, on_progress, on_done):
        if self._worker is not None:
            self._show_toast("⏳ Tunggu, proses sebelumnya belum selesai.")
            return
        self._worker = Worker(fn, self)
        self._worker.progress.connect(on_progress)
        self._worker.finished.connect(on_done)
        self._worker.start()

    def _update_menu(self, url, silent=False, auth=None):
        def progress(text):
            self.repo_dialog.set_busy(True, text)
            if not silent:
                self._show_toast(text, 60_000)

        def done(ok, msg):
            self._worker = None
            self.repo_dialog.set_busy(False, msg)
            if ok:
                self.menu_items = load_menu()
                self._populate_menu()
            if ok or not silent:
                self._show_toast(msg, 6000)

        self._run_worker(lambda emit: update_menu(url, emit, auth), progress, done)

    def _upgrade_self(self, auth):
        def done(ok, msg):
            self._worker = None
            self._show_toast(msg, 6000)
            if ok and SESSION_MODE:
                QTimer.singleShot(2500, self._restart)

        self._run_worker(lambda emit: upgrade_self(emit, auth),
                         lambda t: self._show_toast(t, 60_000), done)

    def _set_resolution(self, res, auth):
        """Simpan resolusi (root, lewat helper) lalu terapkan & mulai ulang menu."""
        label = "Otomatis" if res == "auto" else res

        def work(emit):
            emit(f"🖥️ Mengubah resolusi ke {label}...")
            if not run_helper(auth, "set-resolution", res, timeout=600):
                return False, "😅 Gagal menyimpan resolusi."
            if not apply_resolution(res):
                return True, f"✅ Tersimpan ({label}); berlaku setelah komputer dinyalakan ulang."
            return True, f"✅ Resolusi diubah ke {label}."

        def done(ok, msg):
            self._worker = None
            self._show_toast(msg, 5000)
            if ok and SESSION_MODE:
                QTimer.singleShot(1500, self._restart)   # susun ulang tampilan

        self._run_worker(work, lambda t: self._show_toast(t, 60_000), done)

    def _restart(self):
        self._leave(EXIT_RESTART)

    # ------------------------------------------------------ Musik on/off
    def _update_music_btn(self):
        self.music_btn.setText("🎵 Musik" if sounds.enabled["music"] else "🔇 Musik")

    def _toggle_music(self):
        sounds.enabled["music"] = not sounds.enabled["music"]
        settings = load_settings()
        settings["music"] = sounds.enabled["music"]
        try:
            save_settings(settings)
        except OSError:
            pass
        self._update_music_btn()
        if sounds.enabled["music"]:
            sounds.music.theme = None
            sounds.music.play(self._activity.MUSIC if self._activity else "menu")
        else:
            sounds.music.stop()

    def _power(self, action):
        self._show_toast("👋 Sampai jumpa!" if action == "poweroff"
                         else "🔄 Memulai ulang...", 15_000)
        # Beri waktu toast tergambar sebelum sudo dijalankan.
        QTimer.singleShot(200, lambda: self._power_now(action))

    def _power_now(self, action):
        sounds.shutdown()
        if not power_action(action):
            self._show_toast("😅 Gagal: izin sudo untuk mematikan belum diatur.")

    # ---------------------------------------------------- Penjaga fokus
    def _guard_focus(self):
        if self._child is not None:
            return                          # jangan ganggu aplikasi anak
        if not self.isVisible() or not self.isFullScreen():
            self.lock_screen()
            return
        if not self.isActiveWindow():
            self.raise_()
            self.activateWindow()
        self._grab_keyboard()               # coba lagi bila grab sempat gagal

    # ---------------------------------------------------- Event override
    def showEvent(self, event):
        super().showEvent(event)
        if self._child is None and not DEV_MODE:
            QTimer.singleShot(300, self._grab_keyboard)

    def changeEvent(self, event):
        # Jika WM mencoba meminimalkan launcher, langsung kembalikan.
        if (event.type() == event.WindowStateChange and not DEV_MODE
                and self._child is None and self.isMinimized()):
            QTimer.singleShot(0, self.lock_screen)
        super().changeEvent(event)

    def closeEvent(self, event):
        # Alt+F4 dari WM (atau xkill "sopan") berakhir di sini -> tolak.
        if self._allow_exit or DEV_MODE:
            event.accept()
        else:
            event.ignore()

    def event(self, event):
        # ShortcutOverride dikirim Qt sebelum shortcut diproses; dengan
        # meng-accept-nya, tidak ada shortcut Qt yang terpicu.
        if event.type() == event.ShortcutOverride and not DEV_MODE:
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        """Telan SEMUA tombol yang sampai ke launcher.

        Kombinasi yang secara khusus kita blokir (dicatat agar jelas):
          Alt+F4, Alt+Tab, Alt+Esc, Ctrl+Esc, tombol Super/Meta/Menu, Esc.
        Karena keyboard di-grab (XGrabKeyboard), kombinasi ini tidak sampai
        ke IceWM/Fluxbox; di sini kita pastikan Qt juga tidak memprosesnya.
        """
        if DEV_MODE and event.key() == Qt.Key_Escape:
            self._allow_exit = True
            self.close()
            return

        key = event.key()
        mods = event.modifiers()
        blocked = (
            key in (Qt.Key_Super_L, Qt.Key_Super_R, Qt.Key_Meta,
                    Qt.Key_Menu, Qt.Key_Escape)
            or (mods & Qt.AltModifier and key in (Qt.Key_F4, Qt.Key_Tab,
                                                  Qt.Key_Backtab, Qt.Key_Escape))
            or (mods & Qt.ControlModifier and key == Qt.Key_Escape)
        )
        if blocked:
            pass  # sengaja tidak melakukan apa pun
        event.accept()

    def keyReleaseEvent(self, event):
        event.accept()


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    # Ctrl+C dari terminal tetap bisa mematikan launcher (untuk developer via
    # SSH/TTY). Anak tidak punya akses terminal, jadi aman.
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setApplicationName("KidsOSLauncher")
    # Jangan keluar hanya karena jendela sempat disembunyikan (mode bypass).
    app.setQuitOnLastWindowClosed(DEV_MODE)
    # Font default antiX; emoji otomatis diambil dari fonts-noto-color-emoji.
    app.setFont(QFont("DejaVu Sans", 12))
    clicks = ClickSounds(app)
    app.installEventFilter(clicks)
    app.aboutToQuit.connect(sounds.shutdown)

    win = KidsLauncher()
    if DEV_MODE:
        win.resize(1280, 800)
        win.show()
    else:
        win.lock_screen()

    code = app.exec_()
    # Keluar langsung dengan os._exit: pembongkaran objek Qt saat interpreter
    # berhenti kadang segfault, dan itu akan mengubah kode keluar (10/11) yang
    # dibaca kidsos-session menjadi 139.
    sounds.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)


if __name__ == "__main__":
    main()
