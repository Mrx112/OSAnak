# -*- coding: utf-8 -*-
"""Pembantu antarmuka: jendela biru ala RPG klasik, teks, bar, dan daftar pilihan.

Semua koordinat memakai satuan logis layar 320x240 (dikalikan otomatis).
"""

from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtGui import QColor, QFont, QFontMetricsF, QLinearGradient, QPainter, QPen

LW, LH = 320, 240

UP, DOWN, LEFT, RIGHT, OK, CANCEL, MENU = "up", "down", "left", "right", "ok", "cancel", "menu"
DIRS = {UP: (0, -1), DOWN: (0, 1), LEFT: (-1, 0), RIGHT: (1, 0)}

WHITE = QColor("#FFFFFF")
GREY = QColor("#B8B8D0")
YELLOW = QColor("#FFE14D")
GREEN = QColor("#7CF08A")
RED = QColor("#FF7A7A")
BLUE = QColor("#7FC8FF")
DARK = QColor("#1B1633")

_fonts = {}


def font(size, bold=True):
    key = (size, bold)
    if key not in _fonts:
        f = QFont("DejaVu Sans")
        f.setPixelSize(max(1, int(round(size))))
        f.setBold(bold)
        f.setHintingPreference(QFont.PreferNoHinting)
        _fonts[key] = f
    return _fonts[key]


def text_width(text, size, bold=True):
    return QFontMetricsF(font(size, bold)).horizontalAdvance(text)


def window(p, x, y, w, h, alpha=255, color=None):
    """Jendela biru bergradasi dengan bingkai putih (gaya RPG klasik)."""
    r = QRectF(x, y, w, h)
    grad = QLinearGradient(x, y, x, y + h)
    top, bottom = (QColor("#3B52C4"), QColor("#161E66")) if color is None else color
    top.setAlpha(alpha)
    bottom.setAlpha(alpha)
    grad.setColorAt(0, top)
    grad.setColorAt(1, bottom)
    p.setPen(Qt.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(r, 3, 3)
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QColor(20, 16, 40, 200), 1.6))
    p.drawRoundedRect(r.adjusted(-0.4, -0.4, 0.4, 0.4), 3, 3)
    p.setPen(QPen(QColor("#F4F4FF"), 1.0))
    p.drawRoundedRect(r.adjusted(0.9, 0.9, -0.9, -0.9), 2.5, 2.5)


def text(p, x, y, s, size=9, color=WHITE, bold=True, align=Qt.AlignLeft, w=None, shadow=True):
    """Teks satu baris; (x, y) = kiri-atas kotak teks."""
    f = font(size, bold)
    p.setFont(f)
    h = size * 1.45
    if w is None:
        w = max(1.0, text_width(s, size, bold) + 4)
        if align & Qt.AlignHCenter:
            x -= w / 2
        elif align & Qt.AlignRight:
            x -= w
    rect = QRectF(x, y, w, h)
    flags = align | Qt.AlignVCenter
    if shadow:
        p.setPen(QColor(10, 8, 30, 200))
        p.drawText(rect.translated(0.6, 0.6), flags, s)
    p.setPen(color)
    p.drawText(rect, flags, s)
    return rect


def wrap(s, size, width, bold=True):
    fm = QFontMetricsF(font(size, bold))
    lines = []
    for para in s.split("\n"):
        cur = ""
        for word in para.split(" "):
            test = (cur + " " + word).strip()
            if fm.horizontalAdvance(test) <= width or not cur:
                cur = test
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def paragraph(p, x, y, w, s, size=9, color=WHITE, spacing=1.35, bold=True):
    ys = y
    for line in wrap(s, size, w, bold):
        text(p, x, ys, line, size, color, bold)
        ys += size * spacing
    return ys


def bar(p, x, y, w, h, frac, color, back=QColor(10, 10, 30, 200)):
    frac = max(0.0, min(1.0, frac))
    p.setPen(Qt.NoPen)
    p.setBrush(back)
    p.drawRoundedRect(QRectF(x, y, w, h), h / 2, h / 2)
    if frac > 0:
        p.setBrush(color)
        p.drawRoundedRect(QRectF(x, y, max(h, w * frac), h), h / 2, h / 2)


def cursor(p, x, y, t=0.0):
    """Tangan penunjuk (segitiga) yang bergoyang."""
    import math
    dx = math.sin(t * 8) * 1.2
    p.setPen(QPen(DARK, 0.8))
    p.setBrush(WHITE)
    from PyQt5.QtGui import QPolygonF
    p.drawPolygon(QPolygonF([QPointF(x + dx, y), QPointF(x + dx - 6, y - 4),
                             QPointF(x + dx - 6, y + 4)]))


def button(p, x, y, w, h, label, size=9, active=False):
    window(p, x, y, w, h, alpha=230,
           color=(QColor("#FF9E4D"), QColor("#C0561E")) if active else None)
    text(p, x, y + (h - size * 1.45) / 2, label, size, WHITE, align=Qt.AlignHCenter, w=w)


def inside(pt, rect):
    x, y = pt
    rx, ry, rw, rh = rect
    return rx <= x <= rx + rw and ry <= y <= ry + rh


class ListMenu:
    """Daftar pilihan vertikal (bisa beberapa kolom), keyboard & mouse."""

    def __init__(self, items, x, y, w, row_h=13, cols=1, visible=None, size=9,
                 enabled=None):
        self.items = list(items)           # teks (str) atau (teks, kanan)
        self.x, self.y, self.w = x, y, w
        self.row_h = row_h
        self.cols = cols
        self.visible = visible or len(self.items)
        self.size = size
        self.index = 0
        self.top = 0
        self.enabled = enabled             # fungsi(i) -> bool

    def set_items(self, items):
        self.items = list(items)
        self.index = max(0, min(self.index, len(self.items) - 1))
        self._scroll()

    def col_w(self):
        return self.w / self.cols

    def rows(self):
        return (len(self.items) + self.cols - 1) // self.cols

    def _scroll(self):
        row = self.index // self.cols
        if row < self.top:
            self.top = row
        elif row >= self.top + self.visible:
            self.top = row - self.visible + 1

    def key(self, k):
        """-> "ok" (dengan self.index), "cancel", atau None."""
        n = len(self.items)
        if k == OK:
            if n and (self.enabled is None or self.enabled(self.index)):
                return "ok"
            return "bad"
        if k == CANCEL:
            return "cancel"
        if not n:
            return None
        if k == UP:
            self.index = (self.index - self.cols) % (self.rows() * self.cols)
        elif k == DOWN:
            self.index = (self.index + self.cols) % (self.rows() * self.cols)
        elif k == LEFT and self.cols > 1:
            self.index -= 1
        elif k == RIGHT and self.cols > 1:
            self.index += 1
        else:
            return None
        self.index = max(0, min(self.index % max(1, self.rows() * self.cols), n - 1))
        self._scroll()
        return "move"

    def item_rect(self, i):
        row, col = divmod(i, self.cols)
        return (self.x + col * self.col_w(), self.y + (row - self.top) * self.row_h,
                self.col_w(), self.row_h)

    def hit(self, pt):
        for i in range(len(self.items)):
            row = i // self.cols
            if self.top <= row < self.top + self.visible and inside(pt, self.item_rect(i)):
                return i
        return None

    def mouse(self, pt):
        """Klik: pilih baris; klik kedua pada baris yang sama = ok."""
        i = self.hit(pt)
        if i is None:
            return None
        if self.enabled is not None and not self.enabled(i):
            self.index = i
            return "bad"
        self.index = i
        return "ok"

    def wheel(self, delta):
        self.key(UP if delta > 0 else DOWN)

    def draw(self, p, t=0.0, focus=True):
        for i, item in enumerate(self.items):
            row = i // self.cols
            if not (self.top <= row < self.top + self.visible):
                continue
            x, y, w, h = self.item_rect(i)
            ok = self.enabled is None or self.enabled(i)
            color = WHITE if ok else GREY
            left, right = (item, None) if isinstance(item, str) else item
            text(p, x + 9, y + (h - self.size * 1.45) / 2, left, self.size, color)
            if right:
                text(p, x + w - 4, y + (h - self.size * 1.45) / 2, right, self.size, color,
                     align=Qt.AlignRight)
            if i == self.index and focus:
                cursor(p, x + 7, y + h / 2, t)
        if self.top > 0:
            text(p, self.x + self.w - 8, self.y - 9, "▲", 7, WHITE)
        if self.top + self.visible < self.rows():
            text(p, self.x + self.w - 8, self.y + self.visible * self.row_h - 3, "▼", 7, WHITE)


class Scene:
    """Dasar semua layar. covers_world=True: gambar dunia di bawahnya tidak perlu."""

    covers_world = False
    modal = True

    def __init__(self, game):
        self.game = game
        self.t = 0.0

    def update(self, dt):
        self.t += dt

    def draw_world(self, p):
        pass

    def draw_ui(self, p):
        pass

    def key(self, k):
        pass

    def text_input(self, s):
        return False

    def mouse(self, x, y, kind):
        pass

    def wheel(self, delta):
        pass

    def close(self):
        self.game.pop(self)

    def on_top(self):
        """Dipanggil saat layar ini kembali paling atas."""
