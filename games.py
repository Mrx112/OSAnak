#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Permainan bawaan KidsOS (berbasis kanvas)
=========================================
    kidsos:mewarnai  -> Mewarnai (6 gambar + gambar bebas, bisa disimpan)
    kidsos:puzzle    -> Puzzle Seru (tukar kepingan, 2x2 / 3x3 / 4x4)
    kidsos:musik     -> Bermain Musik (piano Do-Re-Mi, drum, lagu contoh)
    kidsos:dino      -> Petualangan Dinosaurus (lari, lompat, kumpulkan bintang)

Tidak butuh file gambar atau suara: gambar digambar dengan QPainter/emoji,
semua suara disintesis oleh sounds.py.
"""

import math
import os
import random
import time

from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, pyqtSignal
from PyQt5.QtGui import (
    QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
    QPixmap, QPolygonF, QTransform,
)
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QSizePolicy,
)

import sounds
from activities import (
    Activity, TileButton, kid_button, style_button, make_label, speak,
    TEXT_DARK, PALETTE, BLUE, GREEN, YELLOW, PURPLE, PINK, ORANGE,
    TEAL, RED, GREY,
)


# ---------------------------------------------------------------------------
# PEMBANTU
# ---------------------------------------------------------------------------

_emoji_cache = {}


def emoji_pixmap(emoji, size):
    """Emoji sebagai QPixmap (di-cache; menggambar teks tiap frame itu lambat)."""
    size = max(8, int(size))
    key = (emoji, size)
    if key not in _emoji_cache:
        box = int(size * 1.3)
        pm = QPixmap(box, box)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        font = QFont()
        font.setPixelSize(size)
        p.setFont(font)
        p.drawText(pm.rect(), Qt.AlignCenter, emoji)
        p.end()
        _emoji_cache[key] = pm
    return _emoji_cache[key]


NOTES = [("Do", "C"), ("Re", "D"), ("Mi", "E"), ("Fa", "F"),     # tangga nada C mayor
         ("Sol", "G"), ("La", "A"), ("Si", "B"), ("Do'", "C")]


# ---------------------------------------------------------------------------
# 🖍️ MEWARNAI
# ---------------------------------------------------------------------------

CW, CH = 100.0, 70.0      # ukuran logis kanvas; diskalakan ke layar


def _rect(x, y, w, h, r=0):
    p = QPainterPath()
    if r:
        p.addRoundedRect(QRectF(x, y, w, h), r, r)
    else:
        p.addRect(QRectF(x, y, w, h))
    return p


def _ellipse(x, y, w, h):
    p = QPainterPath()
    p.addEllipse(QRectF(x, y, w, h))
    return p


def _circle(cx, cy, r):
    return _ellipse(cx - r, cy - r, 2 * r, 2 * r)


def _poly(*pts):
    p = QPainterPath()
    p.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
    p.closeSubpath()
    return p


def _curve(*segments):
    """Garis hias (tidak diwarnai): segments = [(x0,y0,cx,cy,x1,y1), ...]."""
    p = QPainterPath()
    for x0, y0, cx, cy, x1, y1 in segments:
        p.moveTo(x0, y0)
        p.quadTo(cx, cy, x1, y1)
    return p


def page_rumah():
    return [
        _rect(0, 0, CW, CH), _rect(0, 55, CW, 15), _circle(86, 12, 7),
        _rect(56, 13, 7, 14),                                   # cerobong
        _poly((19, 31), (45, 11), (71, 31)),                    # atap
        _rect(25, 31, 40, 26), _rect(40, 40, 10, 17),
        _rect(29, 36, 8, 8), _rect(53, 36, 8, 8),
        _ellipse(4, 8, 18, 8), _ellipse(12, 4, 14, 9),          # awan
    ], []


def page_matahari():
    cx, cy = 50, 35
    rays = []
    for k in range(8):
        a = k * math.pi / 4
        rays.append(_poly(
            (cx + 17 * math.cos(a - 0.26), cy + 17 * math.sin(a - 0.26)),
            (cx + 29 * math.cos(a), cy + 29 * math.sin(a)),
            (cx + 17 * math.cos(a + 0.26), cy + 17 * math.sin(a + 0.26))))
    return ([_rect(0, 0, CW, CH)] + rays + [
        _circle(cx, cy, 15), _circle(44, 31, 2.2), _circle(56, 31, 2.2),
        _circle(41, 38, 2.4), _circle(59, 38, 2.4),
    ], [_curve((43, 39, 50, 46, 57, 39))])


def page_ikan():
    return [
        _rect(0, 0, CW, CH),
        _poly((8, 70), (6, 50), (11, 58), (12, 42), (16, 70)),  # rumput laut
        _poly((38, 22), (48, 10), (57, 22)),                    # sirip atas
        _poly((64, 35), (86, 20), (86, 50)),                    # ekor
        _ellipse(20, 20, 48, 30),
        _ellipse(44, 21, 6, 28),                                # belang
        _circle(32, 32, 3.8), _circle(32, 32, 1.6),
        _circle(88, 12, 2.6), _circle(93, 5, 1.9), _circle(81, 7, 1.5),
    ], [_curve((22, 38, 26, 40, 27, 36))]


def page_bunga():
    petals = [_circle(50 + 10 * math.cos(k * math.pi / 3),
                      24 + 10 * math.sin(k * math.pi / 3), 7.5) for k in range(6)]
    return ([_rect(0, 0, CW, CH), _rect(0, 60, CW, 10), _rect(48.5, 30, 3, 31),
             _ellipse(33, 44, 16, 7), _ellipse(51, 40, 16, 7)]
            + petals + [_circle(50, 24, 6.5), _circle(84, 12, 6)], [])


def page_mobil():
    return [
        _rect(0, 0, CW, CH), _rect(0, 56, CW, 14),
        _poly((28, 32), (37, 17), (63, 17), (74, 32)),          # kabin
        _rect(12, 31, 76, 19, 4),                               # badan
        _poly((34, 31), (40, 20), (49, 20), (49, 31)),
        _poly((52, 31), (52, 20), (61, 20), (69, 31)),
        _circle(30, 51, 7.5), _circle(70, 51, 7.5),
        _circle(30, 51, 3), _circle(70, 51, 3),
        _circle(85, 37, 2.4), _rect(14, 37, 4, 5),
    ], [_curve((50, 34, 50, 34, 50, 47))]


def page_kupu():
    return [
        _rect(0, 0, CW, CH),
        _ellipse(18, 10, 31, 26), _ellipse(51, 10, 31, 26),
        _ellipse(24, 34, 24, 21), _ellipse(52, 34, 24, 21),
        _circle(32, 21, 4.5), _circle(68, 21, 4.5),
        _circle(36, 44, 3.2), _circle(64, 44, 3.2),
        _ellipse(46.5, 12, 7, 42), _circle(50, 11, 4.5),
    ], [_curve((49, 7, 45, 0, 40, 2), (51, 7, 55, 0, 60, 2))]


def page_bebas():
    return [_rect(0, 0, CW, CH)], []


COLORING_PAGES = [
    ("🏠", "Rumah", page_rumah), ("☀️", "Matahari", page_matahari),
    ("🐟", "Ikan", page_ikan), ("🌸", "Bunga", page_bunga),
    ("🚗", "Mobil", page_mobil), ("🦋", "Kupu-kupu", page_kupu),
    ("✏️", "Gambar Bebas", page_bebas),
]
PAINT_COLORS = [
    "#FF5A5F", "#FF9F43", "#FFE14D", "#7ED957", "#2EB872", "#4FC3F7", "#3D7BFF",
    "#9B6BFF", "#FF7EB6", "#FFD1A6", "#A0673B", "#B0B0B0", "#333333", "#FFFFFF",
]


class ColoringCanvas(QWidget):
    """Gambar garis yang tiap bagiannya bisa diisi warna, plus kuas bebas."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.regions, self.fills, self.decor = [], [], []
        self.strokes, self.history = [], []
        self.color = QColor(PAINT_COLORS[0])
        self.tool = "fill"
        self.brush = 2.2

    def load(self, page):
        self.regions, self.decor = page()
        self.fills = [QColor("#FFFFFF") for _ in self.regions]
        self.strokes, self.history = [], []
        self.update()

    def _transform(self):
        s = min(self.width() / CW, self.height() / CH)
        return QTransform(s, 0, 0, s, (self.width() - CW * s) / 2,
                          (self.height() - CH * s) / 2)

    def _draw(self, p):
        p.setRenderHint(QPainter.Antialiasing)
        for path, fill in zip(self.regions, self.fills):
            p.fillPath(path, fill)
        for color, width, points in self.strokes:
            p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            if len(points) == 1:
                p.drawPoint(points[0])
            else:
                p.drawPolyline(QPolygonF(points))
        p.setPen(QPen(QColor(TEXT_DARK), 0.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        for path in self.regions + self.decor:
            p.drawPath(path)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setTransform(self._transform())
        self._draw(p)
        p.end()

    def _logical(self, pos):
        pt, ok = self._transform().inverted()
        q = pt.map(QPointF(pos))
        return q if 0 <= q.x() <= CW and 0 <= q.y() <= CH else None

    def mousePressEvent(self, event):
        pt = self._logical(event.pos())
        if pt is None:
            return
        if self.tool == "fill":
            for i in range(len(self.regions) - 1, -1, -1):
                if self.regions[i].contains(pt):
                    if self.fills[i] != self.color:
                        self.history.append(("fill", i, self.fills[i]))
                        self.fills[i] = QColor(self.color)
                        sounds.play("fill")
                    break
        else:
            self.strokes.append((QColor(self.color), self.brush, [pt]))
            self.history.append(("stroke",))
        self.update()

    def mouseMoveEvent(self, event):
        if self.tool == "brush" and self.strokes and event.buttons() & Qt.LeftButton:
            pt = self._logical(event.pos())
            if pt is not None:
                self.strokes[-1][2].append(pt)
                self.update()

    def undo(self):
        if not self.history:
            return
        action = self.history.pop()
        if action[0] == "fill":
            self.fills[action[1]] = action[2]
        elif self.strokes:
            self.strokes.pop()
        self.update()

    def clear(self):
        self.fills = [QColor("#FFFFFF") for _ in self.regions]
        self.strokes, self.history = [], []
        self.update()

    def save(self, folder):
        image = QImage(1000, 700, QImage.Format_ARGB32)
        image.fill(Qt.white)
        p = QPainter(image)
        p.setTransform(QTransform.fromScale(10, 10))
        self._draw(p)
        p.end()
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, time.strftime("gambar-%Y%m%d-%H%M%S.png"))
        return path if image.save(path) else None


class ColoringActivity(Activity):

    MUSIC = "mewarnai"
    SAVE_DIR = os.path.expanduser("~/Gambar")

    def __init__(self, scale, parent=None):
        super().__init__("🖍️ Mewarnai", scale, parent)
        px = self.px

        chooser = QWidget()
        grid = QGridLayout(chooser)
        grid.setContentsMargins(px(20), px(10), px(20), px(20))
        grid.setSpacing(px(22))
        for i, (emoji, title, page) in enumerate(COLORING_PAGES):
            tile = TileButton(emoji, title, "", PALETTE[i % len(PALETTE)], px)
            tile.clicked.connect(lambda _c=False, n=i: self.open_page(n))
            grid.addWidget(tile, i // 4, i % 4)
        self.pages.addWidget(chooser)

        play = QWidget()
        outer = QVBoxLayout(play)
        outer.setContentsMargins(px(10), 0, px(10), px(6))
        outer.setSpacing(px(12))
        row = QHBoxLayout()
        row.setSpacing(px(16))
        self.canvas = ColoringCanvas()
        row.addWidget(self.canvas, 1)

        tools = QVBoxLayout()
        tools.setSpacing(px(10))
        self.fill_btn = kid_button("🪣 Isi", YELLOW, px, font=22, height=64)
        self.fill_btn.clicked.connect(lambda: self.set_tool("fill"))
        self.brush_btn = kid_button("🖌️ Kuas", GREY, px, font=22, height=64)
        self.brush_btn.clicked.connect(lambda: self.set_tool("brush"))
        undo_btn = kid_button("↩️ Batal", BLUE, px, font=22, height=64)
        undo_btn.clicked.connect(self.canvas.undo)
        clear_btn = kid_button("🗑️ Hapus", RED, px, font=22, height=64)
        clear_btn.clicked.connect(self.canvas.clear)
        save_btn = kid_button("💾 Simpan", GREEN, px, font=22, height=64)
        save_btn.clicked.connect(self.save)
        for b in (self.fill_btn, self.brush_btn, undo_btn, clear_btn, save_btn):
            b.setFixedWidth(px(170))
            tools.addWidget(b)
        self.status = make_label("", px(18), 800)
        self.status.setFixedWidth(px(170))
        tools.addWidget(self.status)
        tools.addStretch(1)
        row.addLayout(tools)
        outer.addLayout(row, 1)

        palette = QHBoxLayout()
        palette.setSpacing(px(8))
        palette.addStretch(1)
        self.swatches = []
        for color in PAINT_COLORS:
            sw = QPushButton()
            sw.setCursor(Qt.PointingHandCursor)
            sw.setFocusPolicy(Qt.NoFocus)
            sw.setFixedSize(px(58), px(58))
            sw.clicked.connect(lambda _c=False, c=color: self.set_color(c))
            palette.addWidget(sw)
            self.swatches.append((color, sw))
        palette.addStretch(1)
        outer.addLayout(palette)
        self.play = play
        self.pages.addWidget(play)
        self.set_color(PAINT_COLORS[0])

    def open_page(self, index):
        emoji, title, page = COLORING_PAGES[index]
        self.canvas.load(page)
        self.set_tool("brush" if page is page_bebas else "fill")
        self.status.setText("")
        self.show_page(self.play, f"{emoji} {title}")
        speak("Sentuh gambar untuk mewarnai" if page is not page_bebas
              else "Ayo menggambar sesukamu")

    def set_tool(self, tool):
        self.canvas.tool = tool
        style_button(self.fill_btn, YELLOW if tool == "fill" else GREY, self.px, font=22)
        style_button(self.brush_btn, YELLOW if tool == "brush" else GREY, self.px, font=22)

    def set_color(self, color):
        self.canvas.color = QColor(color)
        for c, sw in self.swatches:
            chosen = c == color
            sw.setStyleSheet(
                f"background: {c}; border-radius: {self.px(29)}px;"
                f"border: {self.px(6) if chosen else self.px(3)}px solid "
                f"{TEXT_DARK if chosen else '#DDD6EA'};")

    def save(self):
        path = self.canvas.save(self.SAVE_DIR)
        self.status.setText("💾 Tersimpan!" if path else "😅 Gagal menyimpan")
        if path:
            sounds.play("tada")
            speak("Gambarmu sudah disimpan")


# ---------------------------------------------------------------------------
# 🧩 PUZZLE SERU
# ---------------------------------------------------------------------------

PUZZLE_PICTURES = [
    ("🦁", "Singa", "#FFE57A", "#FFB76B"), ("🚀", "Roket", "#8FD6FF", "#CDB0FF"),
    ("🐢", "Kura-kura", "#9EE6A0", "#7EDFD0"), ("🐬", "Lumba-lumba", "#8FD6FF", "#7EDFD0"),
    ("🏰", "Istana", "#FFAFD4", "#CDB0FF"), ("🦄", "Unicorn", "#FFD1DC", "#CDB0FF"),
    ("🚂", "Kereta", "#FFE57A", "#9EE6A0"), ("🐼", "Panda", "#9EE6A0", "#E9F6FF"),
]
LEVELS = [("Mudah", 2), ("Sedang", 3), ("Sulit", 4)]


def puzzle_picture(emoji, c1, c2, size=600):
    pm = QPixmap(size, size)
    p = QPainter(pm)
    grad = QLinearGradient(0, 0, size, size)
    grad.setColorAt(0, QColor(c1))
    grad.setColorAt(1, QColor(c2))
    p.fillRect(pm.rect(), grad)
    for (fx, fy), deco in zip(((0.12, 0.12), (0.88, 0.14), (0.1, 0.86), (0.86, 0.86)),
                              ("✨", "⭐", "🌟", "✨")):
        small = emoji_pixmap(deco, size * 0.1)
        p.drawPixmap(int(fx * size - small.width() / 2),
                     int(fy * size - small.height() / 2), small)
    big = emoji_pixmap(emoji, size * 0.6)
    p.drawPixmap((size - big.width()) // 2, (size - big.height()) // 2, big)
    p.end()
    return pm


class PuzzleBoard(QWidget):
    """Kepingan acak; sentuh dua keping untuk menukar posisinya."""

    solved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.picture = None
        self.n = 3
        self.order = []
        self.selected = None
        self.done = False

    def start(self, picture, n):
        self.picture, self.n = picture, n
        self.order = list(range(n * n))
        while self.order == sorted(self.order):
            random.shuffle(self.order)
        self.selected = None
        self.done = False
        self.update()

    def _geometry(self):
        side = min(self.width(), self.height()) - 8
        return (self.width() - side) / 2, (self.height() - side) / 2, side / self.n

    def paintEvent(self, _event):
        if self.picture is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        ox, oy, tile = self._geometry()
        src = self.picture.width() / self.n
        gap = 0 if self.done else 3
        for pos, piece in enumerate(self.order):
            r, c = divmod(pos, self.n)
            pr, pc = divmod(piece, self.n)
            dst = QRectF(ox + c * tile + gap, oy + r * tile + gap,
                         tile - 2 * gap, tile - 2 * gap)
            p.drawPixmap(dst, self.picture, QRectF(pc * src, pr * src, src, src))
            if pos == self.selected:
                p.setPen(QPen(QColor("#FFD000"), 8))
                p.drawRect(dst.adjusted(4, 4, -4, -4))
        if self.done:
            p.setPen(QPen(QColor("#56B85B"), 8))
            p.drawRect(QRectF(ox, oy, tile * self.n, tile * self.n))
        p.end()

    def mousePressEvent(self, event):
        if self.done or self.picture is None:
            return
        ox, oy, tile = self._geometry()
        c = int((event.x() - ox) // tile)
        r = int((event.y() - oy) // tile)
        if not (0 <= r < self.n and 0 <= c < self.n):
            return
        pos = r * self.n + c
        if self.selected is None:
            self.selected = pos
        elif self.selected == pos:
            self.selected = None
        else:
            o = self.order
            o[self.selected], o[pos] = o[pos], o[self.selected]
            self.selected = None
            sounds.play("swap")
            if o == sorted(o):
                self.done = True
                self.solved.emit()
        self.update()


class PuzzleActivity(Activity):

    MUSIC = "puzzle"

    def __init__(self, scale, parent=None):
        super().__init__("🧩 Puzzle Seru", scale, parent)
        px = self.px
        self.level = 1
        self.current = 0

        chooser = QWidget()
        cl = QVBoxLayout(chooser)
        cl.setContentsMargins(px(20), 0, px(20), px(16))
        cl.setSpacing(px(16))
        lv = QHBoxLayout()
        lv.setSpacing(px(14))
        lv.addStretch(1)
        self.level_btns = []
        for i, (name, n) in enumerate(LEVELS):
            btn = kid_button(f"{name} {n}×{n}", GREY, px, font=22, height=60)
            btn.clicked.connect(lambda _c=False, k=i: self.set_level(k))
            lv.addWidget(btn)
            self.level_btns.append(btn)
        lv.addStretch(1)
        cl.addLayout(lv)
        grid = QGridLayout()
        grid.setSpacing(px(20))
        for i, (emoji, title, _c1, _c2) in enumerate(PUZZLE_PICTURES):
            tile = TileButton(emoji, title, "", PALETTE[i % len(PALETTE)], px)
            tile.clicked.connect(lambda _c=False, k=i: self.open_puzzle(k))
            grid.addWidget(tile, i // 4, i % 4)
        cl.addLayout(grid, 1)
        self.pages.addWidget(chooser)
        self.set_level(0)

        play = QWidget()
        pl = QHBoxLayout(play)
        pl.setContentsMargins(px(20), 0, px(20), px(10))
        pl.setSpacing(px(24))
        self.board = PuzzleBoard()
        self.board.solved.connect(self.on_solved)
        pl.addWidget(self.board, 3)
        side = QVBoxLayout()
        side.setSpacing(px(12))
        side.addWidget(make_label("Contoh:", px(24), 900))
        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignCenter)
        side.addWidget(self.preview)
        self.info = make_label("", px(24), 800)
        side.addWidget(self.info)
        again = kid_button("🔀 Acak Lagi", ORANGE, px, font=24, height=70)
        again.clicked.connect(lambda: self.open_puzzle(self.current))
        side.addWidget(again)
        side.addStretch(1)
        pl.addLayout(side, 1)
        self.play = play
        self.pages.addWidget(play)

    def set_level(self, k):
        self.level = k
        for i, btn in enumerate(self.level_btns):
            style_button(btn, GREEN if i == k else GREY, self.px, font=22)

    def open_puzzle(self, k):
        self.current = k
        emoji, title, c1, c2 = PUZZLE_PICTURES[k]
        picture = puzzle_picture(emoji, c1, c2)
        n = LEVELS[self.level][1]
        self.board.start(picture, n)
        self.preview.setPixmap(picture.scaled(self.px(220), self.px(220),
                                              Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.info.setText("Sentuh 2 keping untuk menukarnya 👆")
        self.show_page(self.play, f"🧩 {title}")

    def on_solved(self):
        self.add_star()
        self.info.setText("🎉 Hebat! Puzzlenya selesai!")
        sounds.play("tada")
        QTimer.singleShot(900, lambda: speak("Hebat! Puzzlenya selesai!"))


# ---------------------------------------------------------------------------
# 🎹 BERMAIN MUSIK
# ---------------------------------------------------------------------------

SONGS = [  # (judul, [(indeks nada, ketukan), ...]); melodi lagu rakyat/klasik bebas
    ("⭐ Bintang Berkelip", [
        (0, 1), (0, 1), (4, 1), (4, 1), (5, 1), (5, 1), (4, 2),
        (3, 1), (3, 1), (2, 1), (2, 1), (1, 1), (1, 1), (0, 2),
        (4, 1), (4, 1), (3, 1), (3, 1), (2, 1), (2, 1), (1, 2),
        (4, 1), (4, 1), (3, 1), (3, 1), (2, 1), (2, 1), (1, 2),
        (0, 1), (0, 1), (4, 1), (4, 1), (5, 1), (5, 1), (4, 2),
        (3, 1), (3, 1), (2, 1), (2, 1), (1, 1), (1, 1), (0, 2)]),
    ("😊 Lagu Gembira", [
        (2, 1), (2, 1), (3, 1), (4, 1), (4, 1), (3, 1), (2, 1), (1, 1),
        (0, 1), (0, 1), (1, 1), (2, 1), (2, 1.5), (1, 0.5), (1, 2),
        (2, 1), (2, 1), (3, 1), (4, 1), (4, 1), (3, 1), (2, 1), (1, 1),
        (0, 1), (0, 1), (1, 1), (2, 1), (1, 1.5), (0, 0.5), (0, 2)]),
    ("🪜 Do-Re-Mi", [(i, 1) for i in range(8)] + [(i, 1) for i in range(6, -1, -1)]),
]
KEY_COLORS = [RED, ORANGE, YELLOW, GREEN, TEAL, BLUE, PURPLE, PINK]
PIANO_KEYS = "ASDFGHJK"
BEAT_MS = 430


class MusicActivity(Activity):

    MUSIC = None       # anak sendiri yang bermain musik

    def __init__(self, scale, parent=None):
        super().__init__("🎹 Bermain Musik", scale, parent)
        px = self.px
        self.setFocusPolicy(Qt.StrongFocus)
        self.song = []
        self.step = 0

        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(px(20), 0, px(20), px(8))
        lay.setSpacing(px(14))

        songs = QHBoxLayout()
        songs.setSpacing(px(12))
        for title, notes in SONGS:
            btn = kid_button(f"▶ {title}", GREY, px, font=20, height=58)
            btn.clicked.connect(lambda _c=False, n=notes: self.play_song(n))
            songs.addWidget(btn)
        stop = kid_button("⏹ Berhenti", RED, px, font=20, height=58)
        stop.clicked.connect(self.stop_song)
        songs.addWidget(stop)
        lay.addLayout(songs)

        keys = QHBoxLayout()
        keys.setSpacing(px(10))
        self.keys = []
        for i, (sol, letter) in enumerate(NOTES):
            btn = kid_button(f"{sol}\n\n{PIANO_KEYS[i]}", KEY_COLORS[i], px,
                             font=30, height=260, radius=22)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            btn.setProperty("silent", True)     # tuts punya suaranya sendiri
            btn.pressed.connect(lambda k=i: self.play_note(k))
            keys.addWidget(btn)
            self.keys.append(btn)
        lay.addLayout(keys, 1)

        drums = QHBoxLayout()
        drums.setSpacing(px(14))
        for text, sound, colors in (("🥁 Dum", "kick", ORANGE), ("👏 Tak", "snare", BLUE),
                                    ("🔔 Ting", "bell", YELLOW)):
            btn = kid_button(text, colors, px, font=26, height=80)
            btn.setProperty("silent", True)
            btn.pressed.connect(lambda s=sound: sounds.play(s))
            drums.addWidget(btn)
        lay.addLayout(drums)
        self.hint = make_label("Sentuh tuts, atau tekan A S D F G H J K di keyboard 🎶",
                               px(20), 700)
        lay.addWidget(self.hint)
        self.pages.addWidget(page)

        self._song_timer = QTimer(self)
        self._song_timer.setSingleShot(True)
        self._song_timer.timeout.connect(self._song_step)
        QTimer.singleShot(0, self.setFocus)

    def play_note(self, k):
        sounds.play(f"note{k}")
        btn = self.keys[k]
        style_button(btn, ("#FFFFFF", KEY_COLORS[k][1]), self.px, font=30, radius=22)
        QTimer.singleShot(220, lambda: style_button(btn, KEY_COLORS[k], self.px,
                                                    font=30, radius=22))

    def play_song(self, notes):
        self.song, self.step = notes, 0
        self.hint.setText("Lihat tuts yang menyala, lalu coba mainkan sendiri! 🎵")
        self._song_timer.start(100)

    def _song_step(self):
        if self.step >= len(self.song):
            return
        note, beats = self.song[self.step]
        self.play_note(note)
        self.step += 1
        self._song_timer.start(int(beats * BEAT_MS))

    def stop_song(self):
        self._song_timer.stop()
        self.song = []

    def keyPressEvent(self, event):
        text = event.text().upper()
        if text and text in PIANO_KEYS and not event.isAutoRepeat():
            self.play_note(PIANO_KEYS.index(text))
        event.accept()

    def mousePressEvent(self, event):
        self.setFocus()
        super().mousePressEvent(event)

    def closing(self):
        self.stop_song()
        super().closing()


# ---------------------------------------------------------------------------
# 🦖 PETUALANGAN DINOSAURUS
# ---------------------------------------------------------------------------

class DinoGame(QWidget):
    """Lari otomatis; sentuh layar / tombol spasi untuk melompati kaktus.

    Fisika memakai satuan "u": tinggi widget = 100u, jadi terasa sama di
    semua ukuran layar.
    """

    TICK_MS = 20
    GROUND = 80.0          # posisi tanah dari atas (u)
    DINO = 16.0            # ukuran dino (u)
    GRAVITY = 0.36
    JUMP = 6.2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self.best = 0
        self._timer = QTimer(self)
        self._timer.setInterval(self.TICK_MS)
        self._timer.timeout.connect(self._tick)
        self.reset()

    # -- status ------------------------------------------------------------
    def reset(self):
        self.y = 0.0               # tinggi dino di atas tanah
        self.vy = 0.0
        self.things = []           # [x, jenis] jenis: "cactus" / "rock" / "star"
        self.clouds = [[random.uniform(0, 180), random.uniform(8, 35)] for _ in range(4)]
        self.score = 0
        self.speed = 1.3
        self.gap = 60.0            # jarak ke rintangan berikutnya
        self.ticks = 0
        self.started = False
        self.over = False

    def start(self):
        self._timer.start()

    def stop(self):
        self._timer.stop()

    def jump(self):
        if self.over:
            self.reset()
        self.started = True
        if self.y == 0:
            self.vy = self.JUMP
            sounds.play("jump")

    # -- simulasi ----------------------------------------------------------
    def _unit(self):
        return self.height() / 100.0

    def _tick(self):
        width_u = self.width() / max(1e-6, self._unit())
        for cloud in self.clouds:
            cloud[0] -= 0.15 + (0.25 if self.started and not self.over else 0)
            if cloud[0] < -20:
                cloud[0] = width_u + random.uniform(0, 40)
                cloud[1] = random.uniform(8, 35)
        if self.started and not self.over:
            self._advance(width_u)
        self.update()

    def _advance(self, width_u):
        self.ticks += 1
        self.vy -= self.GRAVITY
        self.y = max(0.0, self.y + self.vy)
        if self.y == 0:
            self.vy = 0.0

        for thing in self.things:
            thing[0] -= self.speed
        self.things = [t for t in self.things if t[0] > -20]

        self.gap -= self.speed
        if self.gap <= 0:
            kind = random.choice(["cactus", "cactus", "rock", "star"])
            self.things.append([width_u + 10, kind])
            self.gap = random.uniform(55, 95) + self.speed * 12

        if self.ticks % 6 == 0:
            self.score += 1
        self.speed = min(3.2, self.speed + 0.0006)

        dino_x = 12.0
        dx0, dx1 = dino_x + 3, dino_x + self.DINO - 3
        dy0, dy1 = self.GROUND - self.y - self.DINO + 3, self.GROUND - self.y
        for thing in list(self.things):
            x, kind = thing
            if kind == "star":
                sx0, sx1, sy0, sy1 = x, x + 8, self.GROUND - 42, self.GROUND - 34
            else:
                size = 11 if kind == "cactus" else 8
                sx0, sx1 = x + 2, x + size - 2
                sy0, sy1 = self.GROUND - size + 2, self.GROUND
            if dx0 < sx1 and dx1 > sx0 and dy0 < sy1 and dy1 > sy0:
                if kind == "star":
                    self.things.remove(thing)
                    self.score += 10
                    sounds.play("star")
                else:
                    self._game_over()
                    return

    def _game_over(self):
        self.over = True
        self.best = max(self.best, self.score)
        sounds.play("crash")
        QTimer.singleShot(500, lambda: speak("Yah, tertabrak! Ayo coba lagi!"))

    # -- gambar ------------------------------------------------------------
    def paintEvent(self, _event):
        u = self._unit()
        w, h = self.width(), self.height()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        sky = QLinearGradient(0, 0, 0, h)
        sky.setColorAt(0, QColor("#BDEBFF"))
        sky.setColorAt(1, QColor("#FFF6E5"))
        p.fillRect(self.rect(), sky)
        # Matahari & awan digambar sendiri: emoji ☀️/☁️ kadang tampil hitam-putih.
        sun_c = QPointF(w - 15 * u, 13 * u)
        p.setPen(QPen(QColor("#FFC93C"), 1.2 * u, Qt.SolidLine, Qt.RoundCap))
        for k in range(8):
            a = k * math.pi / 4
            p.drawLine(sun_c + QPointF(8 * u * math.cos(a), 8 * u * math.sin(a)),
                       sun_c + QPointF(11 * u * math.cos(a), 11 * u * math.sin(a)))
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFD93D"))
        p.drawEllipse(sun_c, 6 * u, 6 * u)
        p.setBrush(QColor(255, 255, 255, 235))
        for cx, cy in self.clouds:
            x, y = cx * u, cy * u
            p.drawEllipse(QRectF(x, y + 2 * u, 14 * u, 6 * u))
            p.drawEllipse(QRectF(x + 3 * u, y, 7 * u, 6 * u))
            p.drawEllipse(QRectF(x + 7 * u, y + 0.8 * u, 6 * u, 5 * u))

        ground_y = self.GROUND * u
        p.fillRect(QRectF(0, ground_y, w, h - ground_y), QColor("#9EE6A0"))
        p.fillRect(QRectF(0, ground_y, w, 1.5 * u), QColor("#56B85B"))

        for x, kind in self.things:
            if kind == "star":
                pm = emoji_pixmap("⭐", 8 * u)
                p.drawPixmap(int(x * u), int((self.GROUND - 42) * u), pm)
            else:
                size = 11 if kind == "cactus" else 8
                pm = emoji_pixmap("🌵" if kind == "cactus" else "🪨", size * u)
                p.drawPixmap(int(x * u), int((self.GROUND - size * 1.15) * u), pm)

        dino = emoji_pixmap("🦖", self.DINO * u)
        p.drawPixmap(int(12 * u), int((self.GROUND - self.y - self.DINO * 1.15) * u), dino)

        p.setPen(QColor(TEXT_DARK))
        font = QFont()
        font.setBold(True)
        font.setPixelSize(int(5 * u))
        p.setFont(font)
        p.drawText(QRectF(3 * u, 2 * u, w, 7 * u), Qt.AlignLeft,
                   f"⭐ {self.score}    🏆 {self.best}")
        if not self.started or self.over:
            box = QRectF(w * 0.15, h * 0.22, w * 0.7, h * 0.34)
            p.setBrush(QColor(255, 255, 255, 225))
            p.setPen(QPen(QColor("#7EDFD0"), 0.8 * u))
            p.drawRoundedRect(box, 5 * u, 5 * u)
            p.setPen(QColor(TEXT_DARK))
            font.setPixelSize(int(6 * u))
            p.setFont(font)
            text = ("Sentuh layar untuk mulai!\nLompati kaktus & ambil bintang ⭐"
                    if not self.over else
                    f"Yah, tertabrak! 😅  Skor: {self.score}\nSentuh untuk main lagi")
            p.drawText(box, Qt.AlignCenter, text)
        p.end()

    def mousePressEvent(self, _event):
        self.setFocus()
        self.jump()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Up) and not event.isAutoRepeat():
            self.jump()
        event.accept()


class DinoActivity(Activity):

    MUSIC = "dino"

    def __init__(self, scale, parent=None):
        super().__init__("🦖 Petualangan Dinosaurus", scale, parent)
        px = self.px
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(px(20), 0, px(20), px(8))
        lay.setSpacing(px(12))
        self.game = DinoGame()
        lay.addWidget(self.game, 1)
        jump = kid_button("⬆️ LOMPAT!", GREEN, px, font=34, height=90)
        jump.setProperty("silent", True)    # lompatan sudah bersuara
        jump.pressed.connect(self.game.jump)
        lay.addWidget(jump)
        self.pages.addWidget(page)
        self.game.start()
        QTimer.singleShot(0, self.game.setFocus)

    def closing(self):
        self.game.stop()
        super().closing()


# ---------------------------------------------------------------------------

GAMES = {
    "mewarnai": ColoringActivity,
    "puzzle": PuzzleActivity,
    "musik": MusicActivity,
    "dino": DinoActivity,
}
