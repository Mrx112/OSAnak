#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aktivitas bawaan KidsOS
=======================
Dibuka dari kartu menu dengan command "kidsos:<nama>":

    kidsos:cerita     -> Buku Cerita (isi dari content/cerita.json)
    kidsos:membaca    -> Belajar Membaca (Kenal Huruf & Tebak Kata)
    kidsos:berhitung  -> Ayo Berhitung (Menghitung & Penjumlahan)
    kidsos:bentuk     -> Bentuk & Warna (Tebak Bentuk & Tebak Warna)
    kidsos:hewan      -> Suara Hewan (Kenal Hewan & Tebak Hewan)
    kidsos:mengetik   -> Belajar Mengetik (Cari Huruf & Ketik Kata)
    kidsos:mewarnai, kidsos:puzzle, kidsos:musik, kidsos:dino -> games.py

Semuanya berjalan di DALAM jendela launcher (bukan jendela baru), jadi
kunci keyboard & layar penuh tetap berlaku. Tombol 🔊 memakai espeak-ng
(suara bahasa Indonesia) bila terpasang.
"""

import json
import os
import random
import shutil
import subprocess

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy,
)

import sounds

TEXT_DARK = "#3B2F5C"

# Isi (cerita, dll.) dicari di sini, berurutan: hasil Update Menu dulu,
# lalu bawaan paket (folder content/ di sebelah file ini).
HERE = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIRS = (
    os.path.expanduser("~/.config/kidsos/content"),
    os.path.join(HERE, "content"),
)

# Pasangan (warna muka, warna sisi bawah) ala kartu launcher.
PINK = ("#FFAFD4", "#E26DA4")
BLUE = ("#8FD6FF", "#4AA8DE")
GREEN = ("#9EE6A0", "#56B85B")
YELLOW = ("#FFE57A", "#D9B52C")
PURPLE = ("#CDB0FF", "#9168DA")
ORANGE = ("#FFB76B", "#E38B34")
TEAL = ("#7EDFD0", "#35AE9B")
RED = ("#FFB0BE", "#E0405E")
GREY = ("#EDE7F6", "#C7BCDD")
PALETTE = (ORANGE, BLUE, GREEN, PINK, YELLOW, PURPLE, TEAL)


def load_content(name):
    for folder in CONTENT_DIRS:
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            continue
    return None


# ---------------------------------------------------------------------------
# SUARA (espeak-ng)
# ---------------------------------------------------------------------------

_speech = None


def speak(text):
    """Bacakan teks (tidak memblokir). Diam saja jika espeak tidak ada."""
    global _speech
    stop_speech()
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe or not text:
        return
    try:
        _speech = subprocess.Popen(
            [exe, "-v", "id", "-s", "135", "-p", "60", text],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        _speech = None


def stop_speech():
    global _speech
    if _speech is not None and _speech.poll() is None:
        _speech.terminate()
        try:
            _speech.wait(timeout=1)
        except subprocess.TimeoutExpired:
            _speech.kill()
    _speech = None


# ---------------------------------------------------------------------------
# PEMBANTU UI
# ---------------------------------------------------------------------------

def make_label(text, size, weight=800, color=TEXT_DARK, wrap=True):
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setWordWrap(wrap)
    lbl.setStyleSheet(f"font-size: {size}px; font-weight: {weight}; "
                      f"color: {color}; background: transparent;")
    return lbl


def style_button(btn, colors, px, font=26, radius=26):
    color, shade = colors
    depth = px(7)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {color}; color: {TEXT_DARK};
            font-size: {px(font)}px; font-weight: 900;
            border: none; border-bottom: {depth}px solid {shade};
            border-radius: {px(radius)}px; padding: 0 {px(18)}px;
        }}
        QPushButton:pressed {{ border-bottom-width: 2px; margin-top: {depth - 2}px; }}
        QPushButton:disabled {{
            background: #F1EDF7; border-bottom-color: #DDD6EA;
            color: rgba(59, 47, 92, 80);
        }}
    """)


def kid_button(text, colors, px, font=26, height=70, radius=26):
    """Tombol besar 3D yang ramah jari kecil."""
    btn = QPushButton(text)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFocusPolicy(Qt.NoFocus)
    btn.setMinimumHeight(px(height))
    style_button(btn, colors, px, font, radius)
    return btn


class TileButton(QPushButton):
    """Ubin besar: emoji di atas, judul & keterangan di bawah."""

    def __init__(self, emoji, title, subtitle, colors, px):
        super().__init__()
        color, shade = colors
        depth = px(10)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(px(150))

        lay = QVBoxLayout(self)
        lay.setContentsMargins(px(16), px(12), px(16), px(12) + depth)
        lay.setSpacing(px(2))
        labels = [make_label(emoji, px(64)), make_label(title, px(28), 900)]
        if subtitle:
            labels.append(make_label(subtitle, px(17), 600,
                                     color="rgba(59, 47, 92, 170)"))
        lay.addStretch(1)
        for lbl in labels:
            lbl.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            lay.addWidget(lbl)
        lay.addStretch(1)

        self.setStyleSheet(f"""
            QPushButton {{
                background: {color}; border: none;
                border-bottom: {depth}px solid {shade};
                border-radius: {px(34)}px;
            }}
            QPushButton:pressed {{ border-bottom-width: 2px; margin-top: {depth - 2}px; }}
        """)


def white_card(px, border):
    card = QFrame()
    card.setObjectName("whiteCard")
    card.setStyleSheet(f"""
        QFrame#whiteCard {{
            background: rgba(255, 255, 255, 235);
            border: {px(6)}px solid {border};
            border-radius: {px(36)}px;
        }}
    """)
    return card


# ---------------------------------------------------------------------------
# KERANGKA AKTIVITAS
# ---------------------------------------------------------------------------

class Activity(QWidget):
    """Layar aktivitas: bar atas [🏠 Menu][◀ Kembali] judul [⭐ bintang]."""

    exit_requested = pyqtSignal()
    MUSIC = None           # tema musik latar (sounds.MUSIC_THEMES) selama dibuka

    def __init__(self, title, scale, parent=None):
        super().__init__(parent)
        self.px = px = lambda v: max(1, int(v * scale))
        self.base_title = title
        self.score = 0

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(px(16))

        top = QHBoxLayout()
        top.setSpacing(px(12))
        self.home_btn = kid_button("🏠 Menu", PINK, px, font=22, height=58)
        self.home_btn.clicked.connect(self.exit_requested.emit)
        self.up_btn = kid_button("◀ Kembali", GREY, px, font=22, height=58)
        self.up_btn.clicked.connect(self.go_up)
        self.up_btn.hide()
        # Judul boleh terlipat & tidak memaksa lebar (penting di layar 640x480).
        self.title = make_label(title, px(36), 900)
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.stars = make_label("", px(30), 900, wrap=False)
        # Lebar kolom kanan = kolom kiri, agar judul tetap di tengah.
        side = self.home_btn.sizeHint().width() + self.up_btn.sizeHint().width() + px(12)
        self.stars.setFixedWidth(side)
        self.stars.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        left = QWidget()
        left.setFixedWidth(side)
        left_lay = QHBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(px(12))
        left_lay.addWidget(self.home_btn)
        left_lay.addWidget(self.up_btn)
        left_lay.addStretch(1)
        top.addWidget(left)
        top.addWidget(self.title, 1)
        top.addWidget(self.stars)
        lay.addLayout(top)

        self.pages = QStackedWidget()
        lay.addWidget(self.pages, 1)

    def show_page(self, widget, title=None):
        stop_speech()
        self.pages.setCurrentWidget(widget)
        self.title.setText(title or self.base_title)
        self.up_btn.setVisible(self.pages.currentIndex() > 0)

    def go_up(self):
        self.show_page(self.pages.widget(0))

    def add_star(self):
        self.score += 1
        self.stars.setText(f"⭐ {self.score}")
        if self.score % 5 == 0:
            QTimer.singleShot(600, lambda: sounds.play("tada"))

    def closing(self):
        """Dipanggil launcher sebelum aktivitas ditutup."""
        stop_speech()


def chooser_page(px, tiles):
    """Halaman pilihan mode: deretan TileButton (emoji, judul, ket, warna, slot)."""
    page = QWidget()
    lay = QHBoxLayout(page)
    lay.setContentsMargins(px(40), px(40), px(40), px(60))
    lay.setSpacing(px(30))
    for emoji, title, subtitle, colors, slot in tiles:
        tile = TileButton(emoji, title, subtitle, colors, px)
        tile.clicked.connect(slot)
        lay.addWidget(tile)
    return page


# ---------------------------------------------------------------------------
# KUIS (dipakai Tebak Kata, Menghitung, Penjumlahan)
# ---------------------------------------------------------------------------

PRAISE = [
    ("Hebat! 🎉", "Hebat!"),
    ("Pintar sekali! 🌟", "Pintar sekali!"),
    ("Betul! 👏", "Betul!"),
    ("Keren! 🚀", "Keren!"),
    ("Mantap! 💯", "Mantap!"),
]
OPTION_COLORS = (BLUE, YELLOW, PURPLE)


class QuizView(QWidget):
    """Satu soal = gambar besar + pertanyaan + 3 pilihan jawaban.

    generator() mengembalikan dict: visual, visual_size, question, say,
    options (list teks), answer (teks).
    """

    correct = pyqtSignal()

    def __init__(self, px, parent=None):
        super().__init__(parent)
        self.px = px
        self.generator = None
        self.q = None
        self.locked = False
        self.wrong = set()      # tombol yang sudah dijawab salah (tetap merah)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(px(60), 0, px(60), px(10))
        lay.setSpacing(px(16))

        card = white_card(px, "#8FD6FF")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(px(20), px(14), px(20), px(14))
        self.visual = make_label("", px(120))
        self.question = make_label("", px(36), 900)
        card_lay.addWidget(self.visual, 1)
        card_lay.addWidget(self.question)
        lay.addWidget(card, 1)

        row = QHBoxLayout()
        row.setSpacing(px(24))
        self.buttons = []
        for colors in OPTION_COLORS:
            btn = kid_button("", colors, px, font=40, height=100, radius=32)
            btn.setProperty("silent", True)     # bunyi benar/salah menggantikan "pop"
            btn.clicked.connect(lambda _c=False, b=btn: self._answer(b))
            row.addWidget(btn)
            self.buttons.append(btn)
        lay.addLayout(row)

        self.feedback = make_label(" ", px(32), 900)
        lay.addWidget(self.feedback)

        self._next = QTimer(self)
        self._next.setSingleShot(True)
        self._next.setInterval(1500)
        self._next.timeout.connect(self.new_question)

    def start(self, generator):
        self._next.stop()
        self.generator = generator
        self.new_question()

    def new_question(self):
        self.q = self.generator()
        self.locked = False
        self.wrong.clear()
        self.visual.setText(self.q["visual"])
        self.visual.setStyleSheet(
            f"font-size: {self.px(self.q.get('visual_size', 120))}px; background: transparent;")
        self.question.setText(self.q["question"])
        self.feedback.setText(" ")
        for btn, text, colors in zip(self.buttons, self.q["options"], OPTION_COLORS):
            btn.setText(text)
            style_button(btn, colors, self.px, font=40, radius=32)
        speak(self.q.get("say", ""))
        if self.q.get("sound"):                 # mis. suara hewan, setelah pertanyaan
            QTimer.singleShot(1300, self.replay)

    def replay(self):
        if self.q and self.q.get("sound"):
            sounds.play(self.q["sound"])

    def mousePressEvent(self, event):
        self.replay()                           # sentuh kartu = dengar lagi
        super().mousePressEvent(event)

    def _answer(self, btn):
        if self.locked or btn in self.wrong:
            return
        if btn.text() == self.q["answer"]:
            self.locked = True
            style_button(btn, GREEN, self.px, font=40, radius=32)
            self.correct.emit()
            sounds.play("correct")
            shown, said = random.choice(PRAISE)
            self.feedback.setText(shown)
            QTimer.singleShot(500, lambda: speak(said))
            self._next.start()
        else:
            style_button(btn, RED, self.px, font=40, radius=32)
            self.wrong.add(btn)
            sounds.play("wrong")
            self.feedback.setText("Hampir! Coba lagi, ya 💪")
            QTimer.singleShot(450, lambda: speak("Coba lagi"))

    def stop(self):
        self._next.stop()


# ---------------------------------------------------------------------------
# 📖 BUKU CERITA
# ---------------------------------------------------------------------------

class StoryActivity(Activity):

    MUSIC = "cerita"

    def __init__(self, scale, parent=None):
        super().__init__("📖 Buku Cerita", scale, parent)
        px = self.px
        data = load_content("cerita.json") or {}
        self.stories = [s for s in data.get("stories", [])
                        if isinstance(s, dict) and s.get("title") and s.get("pages")]
        self.story = None
        self.page = 0

        # --- Rak buku ----------------------------------------------------
        shelf = QWidget()
        grid = QGridLayout(shelf)
        grid.setContentsMargins(px(20), px(10), px(20), px(20))
        grid.setSpacing(px(24))
        if not self.stories:
            grid.addWidget(make_label("Belum ada cerita. Minta ayah/ibu menekan "
                                      "Update Menu, ya! 📚", px(30)), 0, 0)
        cols = 3 if len(self.stories) > 4 else 2
        for i, story in enumerate(self.stories):
            colors = PALETTE[i % len(PALETTE)]
            tile = TileButton(story.get("cover", "📖"), story["title"],
                              f"{len(story['pages'])} halaman", colors, px)
            tile.clicked.connect(lambda _c=False, n=i: self.open_story(n))
            grid.addWidget(tile, i // cols, i % cols)
        self.pages.addWidget(shelf)

        # --- Pembaca -----------------------------------------------------
        reader = QWidget()
        rl = QVBoxLayout(reader)
        rl.setContentsMargins(px(40), 0, px(40), px(10))
        rl.setSpacing(px(18))
        self.card = white_card(px, "#CDB0FF")
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(px(40), px(20), px(40), px(24))
        self.scene = make_label("", px(130))
        self.text = make_label("", px(34), 700)
        cl.addWidget(self.scene, 3)
        cl.addWidget(self.text, 2)
        rl.addWidget(self.card, 1)

        nav = QHBoxLayout()
        nav.setSpacing(px(18))
        self.prev_btn = kid_button("◀ Sebelumnya", YELLOW, px, font=26, height=80)
        self.prev_btn.setProperty("silent", True)       # bunyi "wush" halaman
        self.prev_btn.clicked.connect(self.prev_page)
        self.dots = make_label("", px(26), 900, color="#9168DA", wrap=False)
        self.read_btn = kid_button("🔊 Bacakan", BLUE, px, font=26, height=80)
        self.read_btn.clicked.connect(self.read_aloud)
        self.next_btn = kid_button("Berikutnya ▶", GREEN, px, font=26, height=80)
        self.next_btn.setProperty("silent", True)
        self.next_btn.clicked.connect(self.next_page)
        nav.addWidget(self.prev_btn, 2)
        nav.addWidget(self.dots, 2)
        nav.addWidget(self.read_btn, 2)
        nav.addWidget(self.next_btn, 2)
        rl.addLayout(nav)
        self.reader = reader
        self.pages.addWidget(reader)

    def open_story(self, index):
        self.story = self.stories[index]
        self.page = 0
        color = PALETTE[index % len(PALETTE)][0]
        self.card.setStyleSheet(f"""
            QFrame#whiteCard {{
                background: rgba(255, 255, 255, 235);
                border: {self.px(6)}px solid {color};
                border-radius: {self.px(36)}px;
            }}
        """)
        self.show_page(self.reader, f"{self.story.get('cover', '📖')} {self.story['title']}")
        self._render()

    def _render(self):
        stop_speech()
        pages = self.story["pages"]
        total = len(pages)
        if self.page >= total:            # halaman "Tamat"
            sounds.play("tada")
            self.scene.setText("🎉📚🌟")
            self.text.setText("Tamat! Seru sekali ceritanya, ya?")
            self.next_btn.setText("📚 Cerita Lain")
        else:
            page = pages[self.page]
            self.scene.setText(str(page.get("scene", "📖")))
            self.text.setText(str(page.get("text", "")))
            self.next_btn.setText("Berikutnya ▶")
        self.prev_btn.setEnabled(self.page > 0)
        self.dots.setText(" ".join("●" if i == self.page else "○"
                                   for i in range(total + 1)))

    def read_aloud(self):
        speak(self.text.text())

    def prev_page(self):
        if self.page > 0:
            self.page -= 1
            sounds.play("page")
            self._render()

    def next_page(self):
        if self.page < len(self.story["pages"]):
            self.page += 1
            if self.page < len(self.story["pages"]):
                sounds.play("page")
            self._render()
        else:
            self.go_up()


# ---------------------------------------------------------------------------
# 🔤 BELAJAR MEMBACA
# ---------------------------------------------------------------------------

ALPHABET = [
    ("A", "Apel", "🍎"), ("B", "Bola", "⚽"), ("C", "Cicak", "🦎"),
    ("D", "Domba", "🐑"), ("E", "Elang", "🦅"), ("F", "Foto", "📷"),
    ("G", "Gajah", "🐘"), ("H", "Harimau", "🐯"), ("I", "Ikan", "🐟"),
    ("J", "Jeruk", "🍊"), ("K", "Kucing", "🐱"), ("L", "Lebah", "🐝"),
    ("M", "Mobil", "🚗"), ("N", "Nanas", "🍍"), ("O", "Ombak", "🌊"),
    ("P", "Pisang", "🍌"), ("Q", "Quokka", "🦘"), ("R", "Roti", "🍞"),
    ("S", "Sapi", "🐄"), ("T", "Topi", "🎩"), ("U", "Ular", "🐍"),
    ("V", "Vas", "🏺"), ("W", "Wortel", "🥕"), ("X", "Xilofon", "🎼"),
    ("Y", "Yoyo", "🪀"), ("Z", "Zebra", "🦓"),
]

WORDS = [(w, e) for _l, w, e in ALPHABET if w not in ("Quokka", "Xilofon")] + [
    ("Buku", "📚"), ("Rumah", "🏠"), ("Bulan", "🌙"), ("Matahari", "☀️"),
    ("Bunga", "🌸"), ("Pohon", "🌳"), ("Kereta", "🚂"), ("Pesawat", "✈️"),
    ("Kapal", "🚢"), ("Kue", "🎂"), ("Susu", "🥛"), ("Telur", "🥚"),
    ("Anjing", "🐶"), ("Ayam", "🐔"), ("Bebek", "🦆"), ("Kupu-kupu", "🦋"),
    ("Jam", "⏰"), ("Sepatu", "👟"), ("Payung", "☂️"), ("Pensil", "✏️"),
]


class ReadingActivity(Activity):

    MUSIC = "membaca"

    def __init__(self, scale, parent=None):
        super().__init__("🔤 Belajar Membaca", scale, parent)
        px = self.px
        self.index = 0
        self._last_word = None

        self.pages.addWidget(chooser_page(px, [
            ("🔤", "Kenal Huruf", "A sampai Z dengan gambar", ORANGE, self.open_letters),
            ("🧩", "Tebak Kata", "Cocokkan gambar dengan katanya", TEAL, self.open_quiz),
        ]))

        # --- Kenal Huruf -------------------------------------------------
        letters = QWidget()
        ll = QVBoxLayout(letters)
        ll.setContentsMargins(px(30), 0, px(30), px(6))
        ll.setSpacing(px(14))

        card = white_card(px, "#FFB76B")
        cl = QHBoxLayout(card)
        cl.setContentsMargins(px(30), px(10), px(30), px(10))
        self.big_letter = make_label("", px(170), 900, color="#E26DA4", wrap=False)
        right = QVBoxLayout()
        self.big_emoji = make_label("", px(130))
        self.word = make_label("", px(60), 900, wrap=False)
        self.word.setTextFormat(Qt.RichText)
        right.addWidget(self.big_emoji, 2)
        right.addWidget(self.word, 1)
        cl.addWidget(self.big_letter, 1)
        cl.addLayout(right, 1)
        ll.addWidget(card, 1)

        nav = QHBoxLayout()
        nav.setSpacing(px(18))
        prev_btn = kid_button("◀", YELLOW, px, font=34, height=76)
        prev_btn.clicked.connect(lambda: self.show_letter(self.index - 1))
        say_btn = kid_button("🔊 Dengarkan", BLUE, px, font=28, height=76)
        say_btn.clicked.connect(self.say_letter)
        next_btn = kid_button("▶", GREEN, px, font=34, height=76)
        next_btn.clicked.connect(lambda: self.show_letter(self.index + 1))
        nav.addWidget(prev_btn, 1)
        nav.addWidget(say_btn, 2)
        nav.addWidget(next_btn, 1)
        ll.addLayout(nav)

        # Deretan A-Z: sentuh huruf mana saja untuk lompat ke sana.
        strip = QGridLayout()
        strip.setSpacing(px(6))
        for i, (letter, _w, _e) in enumerate(ALPHABET):
            btn = kid_button(letter, PALETTE[i % len(PALETTE)], px,
                             font=22, height=46, radius=14)
            btn.clicked.connect(lambda _c=False, n=i: self.show_letter(n))
            strip.addWidget(btn, i // 13, i % 13)
        ll.addLayout(strip)
        self.letters = letters
        self.pages.addWidget(letters)

        # --- Tebak Kata --------------------------------------------------
        self.quiz = QuizView(px)
        self.quiz.correct.connect(self.add_star)
        self.pages.addWidget(self.quiz)

    def open_letters(self):
        self.show_page(self.letters, "🔤 Kenal Huruf")
        self.show_letter(self.index)

    def show_letter(self, index):
        self.index = index % len(ALPHABET)
        letter, word, emoji = ALPHABET[self.index]
        self.big_letter.setText(f"{letter}{letter.lower()}")
        self.big_emoji.setText(emoji)
        self.word.setText(f"<span style='color:#E26DA4'>{word[0].upper()}</span>"
                          f"{word[1:].upper()}")
        self.say_letter()

    def say_letter(self):
        letter, word, _e = ALPHABET[self.index]
        speak(f"{letter}. {letter} untuk {word}.")

    def open_quiz(self):
        self.show_page(self.quiz, "🧩 Tebak Kata")
        self.quiz.start(self._word_question)

    def _word_question(self):
        choices = [w for w in WORDS if w[0] != self._last_word]
        word, emoji = random.choice(choices)
        self._last_word = word
        others = random.sample([w for w, _e in WORDS if w != word], 2)
        options = [w.upper() for w in [word] + others]
        random.shuffle(options)
        return {
            "visual": emoji, "visual_size": 150,
            "question": "Gambar apa ini?", "say": "Gambar apa ini?",
            "options": options, "answer": word.upper(),
        }

    def go_up(self):
        self.quiz.stop()
        super().go_up()

    def closing(self):
        self.quiz.stop()
        super().closing()


# ---------------------------------------------------------------------------
# 🔢 AYO BERHITUNG
# ---------------------------------------------------------------------------

OBJECTS = [
    ("🍎", "apel"), ("⭐", "bintang"), ("🐟", "ikan"), ("🎈", "balon"),
    ("🐥", "anak ayam"), ("🚗", "mobil"), ("🌸", "bunga"), ("🍌", "pisang"),
]


def number_options(answer, low, high):
    options = {answer}
    while len(options) < 3:
        options.add(random.randint(max(low, answer - 3), min(high, answer + 3)))
    options = [str(n) for n in options]
    random.shuffle(options)
    return options


def emoji_rows(emoji, count, per_row=5):
    rows = [emoji * min(per_row, count - i) for i in range(0, count, per_row)]
    return "\n".join(rows)


class CountingActivity(Activity):

    MUSIC = "berhitung"

    def __init__(self, scale, parent=None):
        super().__init__("🔢 Ayo Berhitung", scale, parent)
        px = self.px
        self.pages.addWidget(chooser_page(px, [
            ("🍎", "Menghitung", "Ada berapa bendanya?", PINK, self.open_count),
            ("➕", "Penjumlahan", "Tambah-tambahan sampai 10", PURPLE, self.open_plus),
        ]))
        self.quiz = QuizView(px)
        self.quiz.correct.connect(self.add_star)
        self.pages.addWidget(self.quiz)

    def open_count(self):
        self.show_page(self.quiz, "🍎 Menghitung")
        self.quiz.start(self._count_question)

    def open_plus(self):
        self.show_page(self.quiz, "➕ Penjumlahan")
        self.quiz.start(self._plus_question)

    @staticmethod
    def _count_question():
        n = random.randint(1, 10)
        emoji, name = random.choice(OBJECTS)
        return {
            "visual": emoji_rows(emoji, n), "visual_size": 70,
            "question": f"Ada berapa {name}?", "say": f"Ada berapa {name}?",
            "options": number_options(n, 1, 10), "answer": str(n),
        }

    @staticmethod
    def _plus_question():
        a, b = random.randint(1, 5), random.randint(1, 5)
        emoji, _name = random.choice(OBJECTS)
        return {
            "visual": f"{emoji * a}  ➕  {emoji * b}", "visual_size": 64,
            "question": f"{a} + {b} = ?",
            "say": f"{a} tambah {b} sama dengan berapa?",
            "options": number_options(a + b, 2, 10), "answer": str(a + b),
        }

    def go_up(self):
        self.quiz.stop()
        super().go_up()

    def closing(self):
        self.quiz.stop()
        super().closing()


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 🔷 BENTUK & WARNA
# ---------------------------------------------------------------------------

SHAPES = [
    ("LINGKARAN", "🔴🟠🟡🟢🔵🟣"),
    ("PERSEGI", "🟥🟧🟨🟩🟦🟪"),
    ("SEGITIGA", "🔺"),
    ("BINTANG", "⭐"),
    ("HATI", "❤️🧡💛💚💙💜"),
    ("BELAH KETUPAT", "🔶🔷"),
    ("BULAN SABIT", "🌙"),
]

COLORS = [
    ("MERAH", ["🔴", "🍎", "🍓", "🌹"]),
    ("ORANYE", ["🟠", "🍊", "🥕"]),
    ("KUNING", ["🟡", "🍌", "🌻", "🐤"]),
    ("HIJAU", ["🟢", "🥦", "🐸", "🍀"]),
    ("BIRU", ["🔵", "🐳", "💎"]),
    ("UNGU", ["🟣", "🍇", "🍆"]),
    ("COKELAT", ["🟤", "🐻", "🍫"]),
    ("HITAM", ["⚫", "🎱"]),
    ("PUTIH", ["⚪", "🐑", "⛄"]),
]


def split_emoji(text):
    """Pisahkan deretan emoji (termasuk yang memakai variation selector)."""
    out = []
    for ch in text:
        if ch == "️" and out:
            out[-1] += ch
        else:
            out.append(ch)
    return out


def quiz_options(answer, pool):
    options = [answer] + random.sample([p for p in pool if p != answer], 2)
    random.shuffle(options)
    return options


class ShapesActivity(Activity):

    MUSIC = "bentuk"

    def __init__(self, scale, parent=None):
        super().__init__("🔷 Bentuk & Warna", scale, parent)
        px = self.px
        self._last = None
        self.pages.addWidget(chooser_page(px, [
            ("🔺", "Tebak Bentuk", "Lingkaran, segitiga, bintang...", BLUE, self.open_shapes),
            ("🎨", "Tebak Warna", "Merah, kuning, hijau...", YELLOW, self.open_colors),
        ]))
        self.quiz = QuizView(px)
        self.quiz.correct.connect(self.add_star)
        self.pages.addWidget(self.quiz)

    def open_shapes(self):
        self.show_page(self.quiz, "🔺 Tebak Bentuk")
        self.quiz.start(self._shape_question)

    def open_colors(self):
        self.show_page(self.quiz, "🎨 Tebak Warna")
        self.quiz.start(self._color_question)

    def _pick(self, items):
        item = random.choice([i for i in items if i[0] != self._last])
        self._last = item[0]
        return item

    def _shape_question(self):
        name, emojis = self._pick(SHAPES)
        return {
            "visual": random.choice(split_emoji(emojis)), "visual_size": 170,
            "question": "Bentuk apa ini?", "say": "Bentuk apa ini?",
            "options": quiz_options(name, [n for n, _e in SHAPES]), "answer": name,
        }

    def _color_question(self):
        name, emojis = self._pick(COLORS)
        return {
            "visual": random.choice(emojis), "visual_size": 170,
            "question": "Warna apa ini?", "say": "Warna apa ini?",
            "options": quiz_options(name, [n for n, _e in COLORS]), "answer": name,
        }

    def go_up(self):
        self.quiz.stop()
        super().go_up()

    def closing(self):
        self.quiz.stop()
        super().closing()


# ---------------------------------------------------------------------------
# 🐮 SUARA HEWAN
# ---------------------------------------------------------------------------

ANIMALS = [
    ("🐄", "Sapi", "Mooo... mooo!"),
    ("🐱", "Kucing", "Meong... meong!"),
    ("🐶", "Anjing", "Guk guk! Guk guk!"),
    ("🐔", "Ayam", "Kukuruyuuuk!"),
    ("🦆", "Bebek", "Kwek kwek kwek!"),
    ("🐐", "Kambing", "Mbeeek... mbeeek!"),
    ("🐑", "Domba", "Beee... beee!"),
    ("🐴", "Kuda", "Hiiii hi hi hi!"),
    ("🦁", "Singa", "Aummm!"),
    ("🐘", "Gajah", "Prooot!"),
    ("🐸", "Katak", "Kwok kwok kwok!"),
    ("🐦", "Burung", "Cuit cuit cuit!"),
    ("🐝", "Lebah", "Nguuung... nguuung!"),
    ("🐯", "Harimau", "Grrr... aummm!"),
    ("🐒", "Monyet", "Uu uu aa aa!"),
    ("🐭", "Tikus", "Cit cit cit!"),
]


class AnimalsActivity(Activity):

    MUSIC = "hewan"

    def __init__(self, scale, parent=None):
        super().__init__("🐮 Suara Hewan", scale, parent)
        px = self.px
        self._last = None
        self.pages.addWidget(chooser_page(px, [
            ("🐄", "Kenal Hewan", "Sentuh hewan, dengar suaranya", GREEN, self.open_learn),
            ("🔊", "Tebak Hewan", "Suara siapa ini?", ORANGE, self.open_quiz),
        ]))

        # --- Kenal Hewan: kartu besar di atas, deretan hewan di bawah ----
        learn = QWidget()
        ll = QVBoxLayout(learn)
        ll.setContentsMargins(px(30), 0, px(30), px(6))
        ll.setSpacing(px(14))
        card = white_card(px, "#9EE6A0")
        cl = QHBoxLayout(card)
        cl.setContentsMargins(px(30), px(8), px(30), px(8))
        self.animal_big = make_label("", px(150))
        info = QVBoxLayout()
        self.animal_name = make_label("", px(56), 900, wrap=False)
        self.animal_sound = make_label("", px(36), 800, color="#E38B34")
        info.addStretch(1)
        info.addWidget(self.animal_name)
        info.addWidget(self.animal_sound)
        info.addStretch(1)
        cl.addWidget(self.animal_big, 1)
        cl.addLayout(info, 1)
        ll.addWidget(card, 1)

        grid = QGridLayout()
        grid.setSpacing(px(10))
        for i, animal in enumerate(ANIMALS):
            btn = kid_button(animal[0], PALETTE[i % len(PALETTE)], px,
                             font=46, height=86, radius=24)
            btn.setProperty("silent", True)             # suara hewannya sendiri
            btn.clicked.connect(lambda _c=False, a=animal: self.show_animal(a))
            grid.addWidget(btn, i // 8, i % 8)
        ll.addLayout(grid)
        self.learn = learn
        self.pages.addWidget(learn)

        self.quiz = QuizView(px)
        self.quiz.correct.connect(self.add_star)
        self.pages.addWidget(self.quiz)

    def open_learn(self):
        self.show_page(self.learn, "🐄 Kenal Hewan")
        self.show_animal(ANIMALS[0])

    def show_animal(self, animal):
        emoji, name, sound = animal
        self.animal_big.setText(emoji)
        self.animal_name.setText(name.upper())
        self.animal_sound.setText(f"🔊 {sound}")
        stop_speech()
        sounds.play(f"animal-{name.lower()}")
        QTimer.singleShot(1600, lambda: speak(f"Ini {name}."))

    def open_quiz(self):
        self.show_page(self.quiz, "🔊 Tebak Hewan")
        self.quiz.start(self._animal_question)

    def _animal_question(self):
        emoji, name, sound = random.choice([a for a in ANIMALS if a[1] != self._last])
        self._last = name
        labels = {a[1]: f"{a[0]} {a[1].upper()}" for a in ANIMALS}
        options = quiz_options(name, list(labels))
        return {
            "visual": f"🔊\n{sound}", "visual_size": 60,
            "question": "Hewan apa yang bersuara begini?",
            "say": "Dengar! Hewan apa ini?", "sound": f"animal-{name.lower()}",
            "options": [labels[o] for o in options], "answer": labels[name],
        }

    def go_up(self):
        self.quiz.stop()
        super().go_up()

    def closing(self):
        self.quiz.stop()
        super().closing()


# ---------------------------------------------------------------------------
# ⌨️ BELAJAR MENGETIK
# ---------------------------------------------------------------------------

KEY_ROWS = ("QWERTYUIOP", "ASDFGHJKL", "ZXCVBNM")
TYPING_WORDS = [(w.upper(), e) for w, e in WORDS if w.isalpha() and len(w) <= 6]


class TypingActivity(Activity):
    """Tekan huruf yang ditunjuk pada keyboard sungguhan.

    Keyboard di-grab oleh launcher, dan widget yang punya fokus menerima
    tombolnya lebih dulu, jadi aktivitas ini cukup mengambil fokus.
    """

    MUSIC = "mengetik"

    def __init__(self, scale, parent=None):
        super().__init__("⌨️ Belajar Mengetik", scale, parent)
        px = self.px
        self.setFocusPolicy(Qt.StrongFocus)
        self.mode = None
        self.target = ""        # huruf atau kata yang harus diketik
        self.typed = 0          # jumlah huruf kata yang sudah benar
        self.emoji = ""

        self.pages.addWidget(chooser_page(px, [
            ("🔤", "Cari Huruf", "Tekan huruf yang muncul", PURPLE, lambda: self.open_mode("huruf")),
            ("📝", "Ketik Kata", "Ketik nama gambarnya", TEAL, lambda: self.open_mode("kata")),
        ]))

        play = QWidget()
        pl = QVBoxLayout(play)
        pl.setContentsMargins(px(40), 0, px(40), px(6))
        pl.setSpacing(px(12))
        card = white_card(px, "#CDB0FF")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(px(20), px(8), px(20), px(8))
        self.picture = make_label("", px(90))
        self.word = make_label("", px(110), 900, wrap=False)
        self.word.setTextFormat(Qt.RichText)
        self.hint = make_label("", px(28), 800)
        cl.addWidget(self.picture)
        cl.addWidget(self.word, 1)
        cl.addWidget(self.hint)
        pl.addWidget(card, 1)

        # Keyboard di layar sebagai petunjuk letak tombol.
        self.keys = {}
        for r, row in enumerate(KEY_ROWS):
            line = QHBoxLayout()
            line.setSpacing(px(6))
            line.addStretch(1 + r)
            for ch in row:
                key = make_label(ch, px(26), 900, wrap=False)
                key.setFixedSize(px(64), px(54))
                self.keys[ch] = key
                line.addWidget(key)
            line.addStretch(1 + r)
            pl.addLayout(line)
        self.play = play
        self.pages.addWidget(play)

    def _key_style(self, key, active):
        bg, border = ("#FFE57A", "#D9B52C") if active else ("#FFFFFF", "#DDD6EA")
        key.setStyleSheet(
            f"font-size: {self.px(26)}px; font-weight: 900; color: {TEXT_DARK};"
            f"background: {bg}; border: {self.px(3)}px solid {border};"
            f"border-bottom-width: {self.px(6)}px; border-radius: {self.px(12)}px;")

    def open_mode(self, mode):
        self.mode = mode
        self.show_page(self.play, "🔤 Cari Huruf" if mode == "huruf" else "📝 Ketik Kata")
        self.next_target()
        self.setFocus()

    def next_target(self):
        if self.mode == "huruf":
            letter, word, emoji = random.choice(ALPHABET)
            self.target, self.emoji = letter, emoji
            self.hint.setText(f"Tekan huruf {letter} di keyboard! ({letter} untuk {word})")
            speak(f"Tekan huruf {letter}")
        else:
            self.target, self.emoji = random.choice(TYPING_WORDS)
            self.hint.setText("Ketik nama gambar ini, huruf demi huruf!")
            speak(f"Ketik {self.target.lower()}")
        self.typed = 0
        self._render()

    def _render(self):
        done = self.target[:self.typed]
        rest = self.target[self.typed:]
        self.picture.setText(self.emoji)
        self.word.setText(f"<span style='color:#56B85B'>{done}</span>"
                          f"<span style='color:#9168DA'>{rest}</span>")
        current = rest[:1]
        for ch, key in self.keys.items():
            self._key_style(key, ch == current)

    def keyPressEvent(self, event):
        text = event.text().upper()
        if (self.pages.currentWidget() is not self.play or len(text) != 1
                or not text.isalpha() or self.typed >= len(self.target)):
            event.accept()
            return
        expected = self.target[self.typed]
        if text == expected:
            self.typed += 1
            if self.typed == len(self.target):
                self.add_star()
                sounds.play("correct")
                shown, said = random.choice(PRAISE)
                self.hint.setText(shown)
                QTimer.singleShot(500, lambda: speak(said))
                self._render()
                QTimer.singleShot(1200, self._next_if_open)
            else:
                sounds.play("key")
                self._render()
        else:
            sounds.play("wrong")
            self.hint.setText(f"Itu huruf {text}. Cari huruf {expected}, ya! 💪")
        event.accept()

    def _next_if_open(self):
        if self.pages.currentWidget() is self.play and self.typed == len(self.target):
            self.next_target()

    def mousePressEvent(self, event):
        self.setFocus()     # sentuhan layar tidak boleh mencuri fokus keyboard
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------

ACTIVITIES = {
    "cerita": StoryActivity,
    "membaca": ReadingActivity,
    "berhitung": CountingActivity,
    "bentuk": ShapesActivity,
    "hewan": AnimalsActivity,
    "mengetik": TypingActivity,
}


def create_activity(name, scale):
    """Buat aktivitas dari nama di command "kidsos:<nama>"; None jika tak dikenal."""
    import games   # permainan kanvas (mewarnai, puzzle, musik, dino); impor di sini
    cls = ACTIVITIES.get(name) or games.GAMES.get(name)  # agar tidak saling impor
    return cls(scale) if cls else None
