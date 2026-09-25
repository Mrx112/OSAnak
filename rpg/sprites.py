# -*- coding: utf-8 -*-
"""
Grafis pixel-art "Legenda Kristal Pelangi", semuanya dibuat lewat kode:
karakter (bisa dikustom: kulit, rambut, baju, topi, senjata), monster,
petak peta, dan latar pertarungan. Hasilnya di-cache sebagai QPixmap.
"""

import math
import random
from functools import lru_cache

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import (QColor, QImage, QLinearGradient, QPainter, QPixmap, QPolygonF,
                         QRadialGradient, QTransform)

from . import data

OUTLINE = "#2A1E3A"
EYE = "#2A1E3A"


# ---------------------------------------------------------------------------
# WARNA & KANVAS PIKSEL
# ---------------------------------------------------------------------------

@lru_cache(maxsize=4096)
def rgba(color):
    if color is None:
        return None
    if isinstance(color, tuple):
        return color
    c = QColor(color)
    return (c.red(), c.green(), c.blue(), c.alpha())


def shade(color, f):
    r, g, b, a = rgba(color)
    if f >= 1:
        r, g, b = (int(v + (255 - v) * (f - 1)) for v in (r, g, b))
    else:
        r, g, b = (int(v * f) for v in (r, g, b))
    return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)), a)


def mix(c1, c2, t):
    a, b = rgba(c1), rgba(c2)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(4))


RAINBOW = ["#FF5A5A", "#FFA03C", "#FFE14D", "#5CD66A", "#4DB4FF", "#8C6BFF"]


class Grid:
    """Kanvas piksel kecil; warna None = transparan."""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = [[None] * w for _ in range(h)]

    def set(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = rgba(c)

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return self.px[y][x]
        return None

    def rect(self, x, y, w, h, c):
        for yy in range(int(y), int(y + h)):
            for xx in range(int(x), int(x + w)):
                self.set(xx, yy, c)

    def hline(self, x0, x1, y, c):
        for x in range(int(x0), int(x1) + 1):
            self.set(x, y, c)

    def vline(self, x, y0, y1, c):
        for y in range(int(y0), int(y1) + 1):
            self.set(x, y, c)

    def ellipse(self, cx, cy, rx, ry, c):
        rx, ry = max(rx, 0.5), max(ry, 0.5)
        for y in range(int(cy - ry - 1), int(cy + ry + 2)):
            for x in range(int(cx - rx - 1), int(cx + rx + 2)):
                if ((x + 0.5 - cx) / rx) ** 2 + ((y + 0.5 - cy) / ry) ** 2 <= 1.0:
                    self.set(x, y, c)

    def line(self, x0, y0, x1, y1, c):
        x0, y0, x1, y1 = int(x0), int(y0), int(x1), int(y1)
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def poly(self, pts, c):
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        n = len(pts)
        for y in range(int(min(ys)), int(max(ys)) + 1):
            for x in range(int(min(xs)), int(max(xs)) + 1):
                px, py = x + 0.5, y + 0.5
                inside = False
                j = n - 1
                for i in range(n):
                    xi, yi = pts[i]
                    xj, yj = pts[j]
                    if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
                        inside = not inside
                    j = i
                if inside:
                    self.set(x, y, c)

    def mirrored(self):
        g = Grid(self.w, self.h)
        g.px = [list(reversed(row)) for row in self.px]
        return g

    def blit(self, other, ox, oy):
        for y in range(other.h):
            for x in range(other.w):
                c = other.px[y][x]
                if c is not None:
                    self.set(ox + x, oy + y, c)

    def outline(self, color=OUTLINE):
        col = rgba(color)
        add = []
        for y in range(self.h):
            row = self.px[y]
            for x in range(self.w):
                if row[x] is None:
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        c = self.get(x + dx, y + dy)
                        if c is not None and c != col and c[3] > 128:
                            add.append((x, y))
                            break
        for x, y in add:
            self.px[y][x] = col
        return self

    def image(self):
        buf = bytearray(self.w * self.h * 4)
        i = 0
        for row in self.px:
            for c in row:
                if c is not None:
                    r, g, b, a = c
                    buf[i] = b
                    buf[i + 1] = g
                    buf[i + 2] = r
                    buf[i + 3] = a
                i += 4
        img = QImage(bytes(buf), self.w, self.h, self.w * 4, QImage.Format_ARGB32)
        return img.copy()

    def pixmap(self):
        return QPixmap.fromImage(self.image())


# ---------------------------------------------------------------------------
# KARAKTER
# ---------------------------------------------------------------------------
# Kanvas 20x28, kaki di baris 26. Arah: down / up / left (right = cermin).

CW, CH = 20, 28


def hero_look(hero):
    return data.look_of(hero)


def look_key(look):
    w = look.get("weapon")
    return (look["skin"], look["hair"], look["hair_color"], look["outfit"], look["armor"],
            look.get("hat"), bool(look.get("beard")), tuple(w) if w else None)


def _palette(look):
    skin = data.SKINS[look["skin"] % len(data.SKINS)]
    hair = look["hair_color"]
    out = look["outfit"]
    style = look["armor"]
    P = {
        "skin": rgba(skin), "skin_d": shade(skin, 0.86),
        "hair": rgba(hair), "hair_d": shade(hair, 0.74), "hair_l": shade(hair, 1.25),
        "out": rgba(out), "out_d": shade(out, 0.72), "out_l": shade(out, 1.25),
        "torso": rgba(out), "torso_d": shade(out, 0.72), "torso_l": shade(out, 1.2),
        "sleeve": rgba(out), "sleeve_d": shade(out, 0.72),
        "pants": rgba("#4B3F5E"), "pants_d": rgba("#3A3049"),
        "boots": rgba("#7A4A26"), "boots_d": rgba("#5A3418"),
        "belt": rgba("#6B4226"), "trim": None, "robe": False, "cape": None,
        "stripes": None, "stars": False, "pad": None,
    }
    if style == "kulit":
        P.update(torso=rgba("#A0703E"), torso_d=rgba("#7A5230"), torso_l=rgba("#BA8A56"),
                 trim=rgba(out), pants=rgba("#5B4636"), pants_d=rgba("#46352A"))
    elif style in ("zirah", "zirah_kristal"):
        metal = "#C3CCDA" if style == "zirah" else "#9BE7FF"
        P.update(torso=rgba(metal), torso_d=shade(metal, 0.72), torso_l=shade(metal, 1.3),
                 sleeve=rgba(metal), sleeve_d=shade(metal, 0.72), trim=rgba(out),
                 pants=shade(metal, 0.78), pants_d=shade(metal, 0.6),
                 boots=shade(metal, 0.62), boots_d=shade(metal, 0.48), pad=rgba(metal),
                 belt=shade(metal, 0.55))
    elif style == "jubah":
        P.update(robe=True, trim=rgba("#F2C94C"))
    elif style == "jubah_bintang":
        P.update(robe=True, torso=rgba("#2E3A87"), torso_d=rgba("#1F2766"),
                 torso_l=rgba("#4352B0"), sleeve=rgba("#2E3A87"), sleeve_d=rgba("#1F2766"),
                 trim=rgba(out), stars=True)
    elif style == "pengembara":
        P.update(torso=rgba("#6B8E3A"), torso_d=rgba("#4F6E28"), torso_l=rgba("#86A850"),
                 sleeve=rgba("#6B8E3A"), sleeve_d=rgba("#4F6E28"), trim=rgba(out),
                 cape=rgba(out), pants=rgba("#5B4636"), pants_d=rgba("#46352A"))
    elif style == "pelangi":
        P.update(stripes=[rgba(c) for c in RAINBOW], sleeve=rgba("#FFFFFF"),
                 sleeve_d=rgba("#D8D8EE"), pants=rgba("#EDEDF7"), pants_d=rgba("#C8C8DE"),
                 cape=rgba("#FF8FC8"), trim=rgba("#FFE14D"), boots=rgba("#FF8FC8"),
                 boots_d=rgba("#D8609A"))
    return P


def _head(g, P, dx):
    s = P["skin"]
    g.hline(7 + dx, 12 + dx, 5, s)
    g.hline(6 + dx, 13 + dx, 6, s)
    g.rect(5 + dx, 7, 10, 7, s)
    g.hline(6 + dx, 13 + dx, 14, s)


def _face(g, P, direction, dx, eyes):
    if direction == "up":
        return
    blush = rgba("#FF9AA8")
    if direction == "down":
        xs = (7, 12)
        for x in xs:
            if eyes == "open":
                g.vline(x + dx, 10, 11, EYE)
            elif eyes == "happy":
                g.set(x - 1 + dx, 11, EYE)
                g.set(x + dx, 10, EYE)
                g.set(x + 1 + dx, 11, EYE)
            else:
                g.hline(x - 1 + dx, x + dx, 11, EYE)
        g.set(6 + dx, 12, blush)
        g.set(13 + dx, 12, blush)
        g.hline(9 + dx, 10 + dx, 13, P["skin_d"])
    else:   # left
        if eyes == "open":
            g.vline(6 + dx, 10, 11, EYE)
        elif eyes == "happy":
            g.set(5 + dx, 11, EYE)
            g.set(6 + dx, 10, EYE)
            g.set(7 + dx, 11, EYE)
        else:
            g.hline(5 + dx, 7 + dx, 11, EYE)
        g.set(7 + dx, 12, blush)
        g.set(5 + dx, 13, P["skin_d"])


def _hair(g, P, look, direction, dx, back_layer):
    """back_layer=True: rambut di belakang badan (panjang/kuncir)."""
    h, hd, hl = P["hair"], P["hair_d"], P["hair_l"]
    style = look["hair"]
    if back_layer:
        if style == "panjang":
            if direction == "down":
                g.rect(4 + dx, 8, 2, 12, hd)
                g.rect(14 + dx, 8, 2, 12, hd)
            elif direction == "left":
                g.rect(11 + dx, 8, 5, 12, hd)
            else:
                g.rect(5 + dx, 12, 10, 8, h)
                g.hline(5 + dx, 14 + dx, 19, hd)
        elif style == "kuncir":
            if direction == "down":
                g.rect(15 + dx, 6, 2, 8, hd)
                g.set(15 + dx, 14, hd)
            elif direction == "left":
                g.rect(15 + dx, 6, 2, 8, hd)
                g.rect(16 + dx, 9, 2, 5, hd)
        return

    if direction == "up":
        g.hline(7 + dx, 12 + dx, 4, h)
        g.hline(6 + dx, 13 + dx, 5, h)
        g.rect(5 + dx, 6, 10, 8, h)
        g.hline(6 + dx, 13 + dx, 14, hd)
        g.hline(7 + dx, 9 + dx, 5, hl)
        if style == "jabrik":
            for x, y in ((6, 2), (9, 1), (12, 2), (4, 5), (15, 5), (5, 3), (14, 3)):
                g.set(x + dx, y, h)
                g.set(x + dx, y + 1, h)
            g.rect(4 + dx, 3, 12, 2, h)
        elif style == "keriting":
            g.ellipse(10 + dx, 8, 7.5, 7, h)
            for x, y in ((6, 5), (11, 3), (14, 8), (8, 11)):
                g.set(x + dx, y, hl)
        elif style == "kuncir":
            g.rect(9 + dx, 12, 2, 6, hd)
            g.hline(9 + dx, 10 + dx, 11, rgba("#FF5C9A"))
        elif style == "panjang":
            g.rect(5 + dx, 12, 10, 8, h)
            g.hline(5 + dx, 14 + dx, 19, hd)
        return

    if direction == "down":
        g.hline(7 + dx, 12 + dx, 4, h)
        g.hline(6 + dx, 13 + dx, 5, h)
        g.rect(5 + dx, 6, 10, 2, h)
        for x in (5, 6, 8, 9, 11, 13, 14):
            g.set(x + dx, 8, h)
        g.vline(5 + dx, 9, 11, h)
        g.vline(14 + dx, 9, 11, h)
        g.hline(7 + dx, 9 + dx, 5, hl)
        g.set(8 + dx, 6, hl)
        if style == "jabrik":
            for x, y in ((6, 2), (9, 1), (12, 2), (4, 5), (15, 5), (5, 3), (14, 3)):
                g.set(x + dx, y, h)
                g.set(x + dx, y + 1, h)
            g.rect(4 + dx, 3, 12, 2, h)
            g.set(4 + dx, 7, h)
            g.set(15 + dx, 7, h)
            g.set(7 + dx, 9, h)
            g.set(12 + dx, 9, h)
        elif style == "keriting":
            g.ellipse(10 + dx, 6.5, 7.5, 5, h)
            g.rect(3 + dx, 7, 3, 6, h)
            g.rect(14 + dx, 7, 3, 6, h)
            for x, y in ((6, 3), (11, 2), (15, 6), (4, 8), (9, 4)):
                g.set(x + dx, y, hl)
            for x in (5, 7, 8, 10, 12, 14):
                g.set(x + dx, 8, h)
        elif style == "kuncir":
            g.set(15 + dx, 5, rgba("#FF5C9A"))
            g.set(15 + dx, 6, rgba("#FF5C9A"))
        elif style == "panjang":
            g.vline(5 + dx, 9, 13, h)
            g.vline(14 + dx, 9, 13, h)
        return

    # left
    g.hline(7 + dx, 12 + dx, 4, h)
    g.hline(6 + dx, 13 + dx, 5, h)
    g.rect(5 + dx, 6, 10, 2, h)
    g.rect(10 + dx, 8, 5, 5, h)
    g.hline(5 + dx, 7 + dx, 8, h)
    g.set(5 + dx, 9, h)
    g.set(11 + dx, 13, hd)
    g.hline(7 + dx, 9 + dx, 5, hl)
    g.set(12 + dx, 10, hd)
    if style == "jabrik":
        for x, y in ((7, 2), (10, 1), (13, 2), (15, 5), (15, 8), (16, 6)):
            g.set(x + dx, y, h)
            g.set(x + dx, y + 1, h)
        g.rect(5 + dx, 3, 11, 2, h)
        g.set(4 + dx, 7, h)
    elif style == "keriting":
        g.ellipse(10.5 + dx, 6.5, 7, 5, h)
        g.rect(10 + dx, 7, 7, 7, h)
        for x, y in ((7, 3), (12, 2), (15, 8), (13, 11)):
            g.set(x + dx, y, hl)
    elif style == "kuncir":
        g.set(15 + dx, 6, rgba("#FF5C9A"))
        g.set(15 + dx, 7, rgba("#FF5C9A"))
    elif style == "panjang":
        g.rect(11 + dx, 8, 4, 7, h)


def _hat(g, P, look, direction, dx):
    hat = look.get("hat")
    if not hat:
        return
    if hat == "pita":
        c, cd = rgba("#FF5C9A"), rgba("#D8407A")
        ox = 5 if direction != "left" else 7
        g.rect(ox + dx, 3, 2, 2, c)
        g.set(ox + 2 + dx, 4, cd)
        g.rect(ox + 3 + dx, 3, 2, 2, c)
    elif hat == "topi_penyihir":
        c, cd, band = rgba("#5B3FA8"), rgba("#43298A"), P["out"]
        g.hline(3 + dx, 16 + dx, 7, cd)
        g.hline(4 + dx, 15 + dx, 6, c)
        g.hline(6 + dx, 13 + dx, 5, band)
        g.hline(7 + dx, 12 + dx, 4, c)
        g.hline(8 + dx, 11 + dx, 3, c)
        g.hline(9 + dx, 11 + dx, 2, c)
        g.hline(10 + dx, 11 + dx, 1, c)
        tip = 12 if direction != "left" else 13
        g.set(tip + dx, 0, c)
        g.set(tip - 1 + dx, 1, cd)
        g.set(9 + dx, 3, rgba("#FFE14D"))
    elif hat == "bandana":
        c = rgba("#E0405E") if look["outfit"] != "#E0405E" else rgba("#3E7BE0")
        cd = shade(c, 0.75)
        g.hline(5 + dx, 14 + dx, 6, c)
        g.hline(5 + dx, 14 + dx, 7, cd)
        if direction == "down":
            g.set(15 + dx, 7, c)
            g.set(16 + dx, 8, cd)
        elif direction == "left":
            g.set(15 + dx, 7, c)
            g.set(16 + dx, 8, c)
            g.set(16 + dx, 9, cd)
        else:
            g.rect(9 + dx, 8, 2, 2, cd)
    elif hat == "mahkota_bunga":
        leaf = rgba("#4FAF4A")
        g.hline(5 + dx, 14 + dx, 5, leaf)
        for i, x in enumerate((6, 9, 12)):
            col = rgba(("#FF8FC8", "#FFE14D", "#FFFFFF")[i])
            g.set(x + dx, 4, col)
            g.set(x - 1 + dx, 5, col)
            g.set(x + 1 + dx, 5, col)
            g.set(x + dx, 5, rgba("#FFB02E"))
    elif hat == "helm":
        m, md, ml = rgba("#C3CCDA"), rgba("#8791A3"), rgba("#EEF2F8")
        g.hline(7 + dx, 12 + dx, 3, m)
        g.hline(6 + dx, 13 + dx, 4, m)
        g.rect(5 + dx, 5, 10, 3, m)
        g.hline(5 + dx, 14 + dx, 8, md)
        g.hline(7 + dx, 9 + dx, 4, ml)
        if direction == "down":
            g.vline(5 + dx, 9, 11, md)
            g.vline(14 + dx, 9, 11, md)
            g.set(10 + dx, 2, rgba("#E0405E"))
            g.set(9 + dx, 2, rgba("#E0405E"))
        elif direction == "left":
            g.rect(11 + dx, 9, 4, 3, md)
            g.set(12 + dx, 2, rgba("#E0405E"))
        else:
            g.rect(5 + dx, 9, 10, 3, md)


def _beard(g, P, look, direction, dx):
    if not look.get("beard") or direction == "up":
        return
    c = P["hair"]
    if direction == "down":
        g.rect(6 + dx, 12, 8, 2, c)
        g.rect(7 + dx, 14, 6, 2, c)
        g.hline(8 + dx, 11 + dx, 16, c)
        g.hline(9 + dx, 10 + dx, 12, P["skin_d"])
    else:
        g.rect(5 + dx, 12, 5, 3, c)
        g.rect(6 + dx, 15, 3, 1, c)


def _torso(g, P, direction, dx):
    t, td, tl = P["torso"], P["torso_d"], P["torso_l"]
    if direction in ("down", "up"):
        x0, w = 7, 6
    else:
        x0, w = 8, 4
    if P["stripes"]:
        for i, y in enumerate(range(15, 21)):
            g.hline(x0 + dx, x0 + w - 1 + dx, y, P["stripes"][i % 6])
    else:
        g.rect(x0 + dx, 15, w, 6, t)
        g.vline(x0 + w - 1 + dx, 15, 20, td)
        if direction == "down":
            g.vline(x0 + dx, 16, 18, tl)
    if P["trim"] and direction != "up":
        g.hline(x0 + dx, x0 + w - 1 + dx, 15, P["trim"])
        if P["pad"] is None and not P["robe"] and direction == "down":
            g.vline(9 + dx, 16, 18, P["trim"])
    if P["pad"] is not None:
        tr = P["trim"]
        if direction == "down":
            g.rect(9 + dx, 16, 2, 4, tr)
        elif direction == "left":
            g.rect(8 + dx, 16, 1, 4, tr)
    if P["stars"] and direction != "up":
        g.set(x0 + 1 + dx, 17, rgba("#FFE14D"))
        g.set(x0 + w - 2 + dx, 19, rgba("#FFE14D"))
    if not P["robe"]:
        belt = P["belt"]
        g.hline(x0 + dx, x0 + w - 1 + dx, 20, belt)
        if direction == "down":
            g.set(9 + dx, 20, rgba("#F2C94C"))
            g.set(10 + dx, 20, rgba("#F2C94C"))


def _cape(g, P, direction, dx):
    c = P["cape"]
    if c is None:
        return
    cd = shade(c, 0.72)
    if direction == "up":
        g.rect(6 + dx, 15, 8, 9, c)
        g.vline(13 + dx, 15, 23, cd)
        g.hline(6 + dx, 13 + dx, 23, cd)
    elif direction == "left":
        g.rect(12 + dx, 15, 2, 8, c)
        g.set(14 + dx, 21, cd)
        g.set(14 + dx, 22, cd)
    else:
        g.set(6 + dx, 15, c)
        g.set(13 + dx, 15, c)


def _legs(g, P, direction, legs):
    p, pd, b, bd = P["pants"], P["pants_d"], P["boots"], P["boots_d"]
    if P["robe"]:
        t, td = P["torso"], P["torso_d"]
        trim = P["trim"]
        if direction in ("down", "up"):
            g.rect(7, 21, 6, 2, t)
            g.rect(6, 23, 8, 3, t)
            g.vline(12, 21, 22, td)
            g.vline(13, 23, 25, td)
            if trim:
                g.hline(6, 13, 25, trim)
                if direction == "down":
                    g.vline(9, 21, 24, trim)
            if P["stars"] and direction == "down":
                g.set(7, 23, rgba("#FFE14D"))
                g.set(12, 24, rgba("#FFE14D"))
            lift_l = 1 if legs == "stride" else 0
            lift_r = 1 if legs == "stride2" else 0
            g.rect(7, 26 - lift_l, 2, 1, b)
            g.rect(11, 26 - lift_r, 2, 1, b)
        else:
            g.rect(8, 21, 4, 2, t)
            g.rect(7, 23, 6, 3, t)
            g.vline(12, 23, 25, td)
            if trim:
                g.hline(7, 12, 25, trim)
            if legs in ("stride", "stride2"):
                g.hline(6, 8, 26, b)
                g.hline(11, 12, 26, bd)
            else:
                g.hline(7, 10, 26, b)
        return

    if direction in ("down", "up"):
        g.hline(7, 12, 21, p)
        lift_l = 1 if legs == "stride" else 0
        lift_r = 1 if legs == "stride2" else 0
        g.rect(7, 22, 2, 3 - lift_l, p)
        g.rect(11, 22, 2, 3 - lift_r, p)
        g.set(8, 22, pd)
        g.set(12, 22, pd)
        g.rect(6 if direction == "down" else 7, 25 - lift_l, 3, 2, b)
        g.rect(11, 25 - lift_r, 3 if direction == "down" else 2, 2, b)
        g.hline(6 if direction == "down" else 7, 8, 26 - lift_l, bd)
        g.hline(11, 13 if direction == "down" else 12, 26 - lift_r, bd)
    else:
        g.hline(8, 11, 21, p)
        if legs == "stride":
            g.rect(6, 22, 3, 3, p)
            g.rect(10, 22, 2, 2, pd)
            g.hline(5, 8, 25, b)
            g.hline(5, 8, 26, bd)
            g.hline(10, 12, 24, bd)
            g.hline(10, 12, 25, bd)
        elif legs == "stride2":
            g.rect(7, 22, 2, 3, p)
            g.rect(10, 22, 2, 3, pd)
            g.hline(6, 8, 25, b)
            g.hline(6, 8, 26, bd)
            g.hline(10, 12, 25, bd)
            g.hline(10, 12, 26, bd)
        else:
            g.rect(8, 22, 3, 3, p)
            g.vline(10, 22, 24, pd)
            g.hline(7, 10, 25, b)
            g.hline(7, 10, 26, bd)


def _arms(g, P, direction, arms, dx):
    s, sd = P["sleeve"], P["sleeve_d"]
    skin = P["skin"]
    if direction in ("down", "up"):
        for side, x in (("l", 6), ("r", 13)):
            off = 0
            if arms == "swing":
                off = 1 if side == "l" else -1
            elif arms == "swing2":
                off = -1 if side == "l" else 1
            if arms == "cast":
                g.rect(x + dx, 11, 1, 5, s)
                g.set(x + dx, 10, skin)
                continue
            g.rect(x + dx, 15 + max(0, off), 1, 5, s if side == "l" else sd)
            g.set(x + dx, 20 + off, skin)
        return
    # left
    if arms == "attack":
        g.hline(4 + dx, 9 + dx, 17, s)
        g.hline(5 + dx, 9 + dx, 16, sd)
        g.set(3 + dx, 17, skin)
        g.set(3 + dx, 16, skin)
    elif arms == "cast":
        g.rect(8 + dx, 11, 2, 5, s)
        g.rect(8 + dx, 10, 2, 1, skin)
    elif arms == "win":
        g.rect(8 + dx, 11, 2, 5, s)
        g.rect(8 + dx, 10, 2, 1, skin)
    elif arms == "hurt":
        g.rect(11 + dx, 15, 2, 4, s)
        g.set(12 + dx, 19, skin)
    else:
        ox = {"swing": -1, "swing2": 1}.get(arms, 0)
        g.rect(9 + ox + dx, 15, 2, 5, sd)
        g.rect(9 + ox + dx, 20, 2, 1, skin)


def _weapon(g, look, direction, pose, dx):
    wp = look.get("weapon")
    if not wp:
        return
    kind, col = wp
    rainbow = col == "rainbow"
    c = rgba(RAINBOW[4] if rainbow else col)
    cl = shade(c, 1.35)
    wood, wood_d = rgba("#8B5A2B"), rgba("#6A4220")
    gold = rgba("#F2C94C")

    def blade_color(i):
        return rgba(RAINBOW[i % 6]) if rainbow else (cl if i % 3 == 0 else c)

    if direction == "up" and pose == "hold":        # di punggung
        if kind == "pedang":
            g.line(7, 20, 13, 12, c)
            g.line(8, 20, 14, 12, cl)
            g.set(6, 21, wood)
            g.hline(5, 7, 19, gold)
        elif kind == "busur":
            g.line(6, 13, 13, 22, c)
            g.line(7, 13, 14, 22, shade(c, 0.7))
        else:
            g.line(6, 23, 14, 9, wood)
            g.ellipse(14.5, 8.5, 1.5, 1.5, c)
        return

    if pose == "hold":
        if direction == "down":
            x = 5 + dx
            if kind == "pedang":
                for i, y in enumerate(range(13, 20)):
                    g.set(x, y, blade_color(i))
                g.hline(x - 1, x + 1, 20, gold)
                g.set(x, 21, wood)
            elif kind == "busur":
                g.set(x, 13, c)
                g.vline(x - 1, 14, 20, c)
                g.set(x, 21, c)
                g.vline(x + 1, 14, 20, rgba("#EDEDED"))
            elif kind == "tongkat":
                g.vline(x, 11, 24, wood)
                g.ellipse(x + 0.5, 9.5, 1.6, 1.6, c)
                g.set(x - 1, 9, cl)
            else:   # tongkat suci
                g.vline(x, 12, 24, rgba("#E8D9B0"))
                for ddx, ddy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
                    g.set(x + ddx, 10 + ddy, c)
                g.set(x, 10, gold)
        else:       # left
            x = 8 + dx
            if kind == "pedang":
                for i, y in enumerate(range(12, 19)):
                    g.set(x - 1, y, blade_color(i))
                g.hline(x - 2, x, 19, gold)
                g.set(x - 1, 20, wood)
            elif kind == "busur":
                g.set(x - 1, 13, c)
                g.vline(x - 2, 14, 20, c)
                g.set(x - 1, 21, c)
                g.vline(x - 1, 14, 20, rgba("#EDEDED"))
            elif kind == "tongkat":
                g.vline(x - 1, 10, 25, wood)
                g.ellipse(x - 0.5, 8.5, 1.6, 1.6, c)
            else:
                g.vline(x - 1, 11, 25, rgba("#E8D9B0"))
                for ddx, ddy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
                    g.set(x - 1 + ddx, 9 + ddy, c)
                g.set(x - 1, 9, gold)
        return

    if pose == "attack":           # arah kiri, lengan terjulur
        if kind == "pedang":
            for i, x in enumerate(range(-6, 2)):
                g.set(x + dx + 4, 16, blade_color(i))
                g.set(x + dx + 4, 17, blade_color(i + 1))
            g.vline(3 + dx + 2, 15, 18, gold)
        elif kind == "busur":
            g.set(2 + dx, 11, c)
            g.vline(1 + dx, 12, 22, c)
            g.set(2 + dx, 23, c)
            g.line(2 + dx, 12, 4 + dx, 17, rgba("#EDEDED"))
            g.line(2 + dx, 22, 4 + dx, 17, rgba("#EDEDED"))
            g.hline(0 + dx, 8 + dx, 17, wood)
            g.set(0 + dx, 16, rgba("#DDDDDD"))
            g.set(0 + dx, 18, rgba("#DDDDDD"))
        elif kind == "tongkat":
            g.line(2 + dx, 9, 6 + dx, 22, wood)
            g.ellipse(1.5 + dx, 7.5, 2, 2, c)
        else:
            g.line(2 + dx, 10, 6 + dx, 22, rgba("#E8D9B0"))
            g.ellipse(1.5 + dx, 8.5, 1.8, 1.8, c)
            g.set(1 + dx, 8, gold)
        return

    if pose in ("cast", "win"):
        x = 8 + dx
        if kind == "pedang":
            for i, y in enumerate(range(1, 9)):
                g.set(x, y, blade_color(i))
                g.set(x + 1, y, blade_color(i + 2))
            g.hline(x - 1, x + 2, 9, gold)
        elif kind == "busur":
            g.line(x - 2, 2, x + 3, 2, c)
            g.line(x - 3, 3, x - 3, 8, c)
            g.line(x + 4, 3, x + 4, 8, c)
        elif kind == "tongkat":
            g.vline(x, 3, 12, wood)
            g.ellipse(x + 0.5, 1.5, 2, 2, c)
        else:
            g.vline(x, 4, 12, rgba("#E8D9B0"))
            g.ellipse(x + 0.5, 2.5, 2, 2, c)
            g.set(x, 2, gold)


def draw_character(look, direction, legs="stand", arms="stand", pose="hold", eyes="open",
                   dx=0):
    P = _palette(look)
    g = Grid(CW, CH)
    base = "left" if direction == "left" else direction
    _hair(g, P, look, base, dx, back_layer=True)
    if base == "up":
        _legs(g, P, base, legs)
        _torso(g, P, base, dx)
        _arms(g, P, base, arms, dx)
        _cape(g, P, base, dx)
        _weapon(g, look, base, pose, dx)
        _head(g, P, dx)
        _hair(g, P, look, base, dx, back_layer=False)
        _hat(g, P, look, base, dx)
    else:
        _cape(g, P, base, dx)
        _legs(g, P, base, legs)
        _torso(g, P, base, dx)
        if base == "left" and pose == "hold":
            _weapon(g, look, base, pose, dx)
        _arms(g, P, base, arms, dx)
        if base == "down":
            _weapon(g, look, base, pose, dx)
        _head(g, P, dx)
        _face(g, P, base, dx, eyes)
        _hair(g, P, look, base, dx, back_layer=False)
        _beard(g, P, look, base, dx)
        _hat(g, P, look, base, dx)
        if base == "left" and pose != "hold":
            _weapon(g, look, base, pose, dx)
    return g.outline()


@lru_cache(maxsize=256)
def _frames_for_key(key):
    skin, hair, hair_color, outfit, armor, hat, beard, weapon = key
    look = {"skin": skin, "hair": hair, "hair_color": hair_color, "outfit": outfit,
            "armor": armor, "hat": hat, "beard": beard, "weapon": weapon}
    frames = {}
    for d in ("down", "up", "left"):
        seq = [draw_character(look, d, "stand", "stand"),
               draw_character(look, d, "stride", "swing"),
               draw_character(look, d, "stride2", "swing2")]
        for i, gr in enumerate(seq):
            frames[(d, i)] = gr.pixmap()
            if d == "left":
                frames[("right", i)] = gr.mirrored().pixmap()
    # pose pertarungan (menghadap kiri)
    frames["b_idle"] = frames[("left", 0)]
    frames["b_walk"] = frames[("left", 1)]
    frames["b_attack"] = draw_character(look, "left", "stride", "attack", "attack").pixmap()
    frames["b_cast"] = draw_character(look, "left", "stand", "cast", "cast").pixmap()
    frames["b_win"] = draw_character(look, "left", "stand", "win", "win", "happy").pixmap()
    hurt = draw_character(look, "left", "stand", "hurt", "none", "closed", dx=1)
    frames["b_hurt"] = hurt.pixmap()
    frames["b_ko"] = hurt.pixmap().transformed(QTransform().rotate(-90))
    frames["b_sleep"] = draw_character(look, "left", "stand", "stand", "hold", "closed").pixmap()
    # potret (kepala) untuk dialog & menu
    down = draw_character(look, "down", "stand", "stand")
    head = Grid(16, 16)
    for y in range(16):
        for x in range(16):
            head.px[y][x] = down.get(x + 2, y + 1)
    frames["portrait"] = head.pixmap()
    return frames


def hero_frames(look):
    return _frames_for_key(look_key(look))


# ---------------------------------------------------------------------------
# MONSTER
# ---------------------------------------------------------------------------

def _eyes(g, x1, x2, y, h=3, color=EYE):
    for x in (x1, x2):
        g.rect(x, y, 2, h, color)
        g.set(x, y, "#FFFFFF")


def _m_slime(g, col, f):
    c, cd, cl = rgba(col), shade(col, 0.72), shade(col, 1.35)
    squash = 1 if f else 0
    g.ellipse(16, 22 + squash * 0.5, 12 + squash, 8.5 - squash * 0.5, cd)
    g.ellipse(16, 21 + squash * 0.5, 11.5 + squash, 8 - squash * 0.5, c)
    g.ellipse(16, 15 + squash, 6, 5.5, c)
    g.ellipse(16, 11 + squash * 1.5, 2.5, 3, c)
    g.ellipse(11, 16 + squash, 2, 2.5, cl)
    g.set(10, 20 + squash, "#FFFFFF")
    _eyes(g, 12, 18, 19 + squash)
    y = 24 + squash
    g.set(14, y, EYE)
    g.hline(15, 17, y + 1, EYE)
    g.set(18, y, EYE)
    g.hline(9, 10, y, "#FF9AA8")
    g.hline(22, 23, y, "#FF9AA8")


def _m_jamur(g, col, f):
    c, cd = rgba(col), shade(col, 0.7)
    hop = -2 if f else 0
    stem, stem_d = rgba("#F3E3C3"), rgba("#D8C4A0")
    g.rect(10, 18 + hop, 12, 10, stem)
    g.vline(21, 18 + hop, 27 + hop, stem_d)
    g.rect(9, 28 + hop, 4, 2, "#8B5A2B")
    g.rect(19, 28 + hop, 4, 2, "#8B5A2B")
    g.ellipse(16, 13 + hop, 14.5, 8.5, cd)
    g.ellipse(16, 12 + hop, 14, 8, c)
    for x, y, r in ((9, 10, 2), (17, 7, 2.5), (24, 12, 2), (13, 15, 1.5), (21, 16, 1.5)):
        g.ellipse(x, y + hop, r, r, "#FFFFFF")
    g.hline(5, 27, 19 + hop, cd)
    _eyes(g, 12, 18, 21 + hop)
    g.hline(15, 17, 25 + hop, EYE)


def _m_lebah(g, col, f):
    c, cd = rgba(col), shade(col, 0.72)
    wing = rgba((220, 240, 255, 230))
    wy = -2 if f else 0
    g.ellipse(15, 8 + wy, 4, 5, wing)
    g.ellipse(21, 9 + wy, 3.5, 4.5, wing)
    g.ellipse(18, 19, 10, 7.5, cd)
    g.ellipse(18, 18, 9.5, 7, c)
    for x in (14, 15, 20, 21):
        g.vline(x, 12, 24, EYE)
    g.poly([(27, 17), (31, 19), (27, 21)], "#3A3049")
    g.ellipse(8, 17, 5.5, 5.5, cd)
    g.ellipse(8, 16.5, 5, 5, c)
    g.rect(5, 15, 2, 3, EYE)
    g.set(5, 15, "#FFFFFF")
    g.hline(6, 8, 20, EYE)
    g.line(7, 11, 5, 6, EYE)
    g.line(10, 11, 11, 6, EYE)
    g.set(5, 5, EYE)
    g.set(11, 5, EYE)


def _m_kelinci(g, col, f):
    c, cd = rgba(col), shade(col, 0.82)
    pink = rgba("#FFB0C8")
    hop = -2 if f else 0
    ear = 1 if f else 0
    g.rect(11 - ear, 2 + hop, 3, 9, c)
    g.rect(18 + ear, 2 + hop, 3, 9, c)
    g.vline(12 - ear, 4 + hop, 9 + hop, pink)
    g.vline(19 + ear, 4 + hop, 9 + hop, pink)
    g.ellipse(16, 23 + hop, 9, 7, cd)
    g.ellipse(16, 22 + hop, 8.5, 6.5, c)
    g.ellipse(16, 14 + hop, 7, 6, c)
    g.rect(12, 13 + hop, 2, 2, "#E0405E")
    g.rect(19, 13 + hop, 2, 2, "#E0405E")
    g.set(16, 16 + hop, pink)
    g.hline(15, 17, 17 + hop, EYE)
    g.ellipse(11, 29 + hop, 3, 1.5, cd)
    g.ellipse(21, 29 + hop, 3, 1.5, cd)
    g.ellipse(24, 22 + hop, 2, 2, "#FFFFFF")


def _m_kelelawar(g, col, f):
    c, cd = rgba(col), shade(col, 0.7)
    if f:
        left = [(10, 14), (1, 8), (2, 14), (4, 13), (5, 18), (7, 16), (10, 20)]
    else:
        left = [(10, 14), (1, 20), (4, 19), (5, 23), (7, 20), (9, 24), (11, 20)]
    right = [(32 - x, y) for x, y in left]
    g.poly(left, cd)
    g.poly(right, cd)
    g.ellipse(16, 16, 7, 7, c)
    g.poly([(10, 12), (11, 5), (14, 10)], c)
    g.poly([(22, 12), (21, 5), (18, 10)], c)
    g.rect(12, 14, 3, 3, "#FFFFFF")
    g.rect(18, 14, 3, 3, "#FFFFFF")
    g.set(13, 15, EYE)
    g.set(19, 15, EYE)
    g.hline(14, 18, 19, EYE)
    g.set(14, 20, "#FFFFFF")
    g.set(18, 20, "#FFFFFF")


def _m_kristal(g, col, f):
    c, cd, cl = rgba(col), shade(col, 0.62), shade(col, 1.45)
    b = -1 if f else 0
    g.poly([(16, 1 + b), (28, 14 + b), (16, 30 + b), (4, 14 + b)], c)
    g.poly([(16, 1 + b), (16, 14 + b), (4, 14 + b)], cl)
    g.poly([(16, 30 + b), (28, 14 + b), (16, 14 + b)], cd)
    g.line(10, 8 + b, 14, 4 + b, "#FFFFFF")
    g.rect(11, 15 + b, 2, 3, EYE)
    g.rect(19, 15 + b, 2, 3, EYE)
    g.line(10, 13 + b, 13, 14 + b, EYE)
    g.line(22, 13 + b, 19, 14 + b, EYE)
    g.hline(14, 18, 21 + b, EYE)


def _m_batu(g, col, f):
    c, cd, cl = rgba(col), shade(col, 0.7), shade(col, 1.25)
    s = 1 if f else 0
    g.rect(8, 27 - s, 4, 3 + s, cd)
    g.rect(20, 26 + s, 4, 4 - s, cd)
    g.ellipse(16, 18, 13, 10.5, cd)
    g.ellipse(15.5, 17, 12.5, 10, c)
    g.ellipse(11, 11, 4, 3, cl)
    g.ellipse(16, 8, 7, 2.5, "#6FB35A")
    g.line(20, 12, 24, 18, cd)
    g.line(24, 18, 22, 22, cd)
    g.hline(10, 13, 16, "#FFD23F")
    g.hline(18, 21, 16, "#FFD23F")
    g.line(10, 14, 13, 15, EYE)
    g.line(21, 14, 18, 15, EYE)
    g.hline(12, 19, 21, cd)


def _m_hantu(g, col, f):
    c, cd = rgba(col), rgba("#C9C0EE")
    b = -1 if f else 0
    g.ellipse(16, 13 + b, 10, 10, cd)
    g.ellipse(15.5, 12.5 + b, 9.5, 9.5, c)
    g.rect(6, 13 + b, 20, 11, c)
    g.vline(25, 13 + b, 24 + b, cd)
    for i, x in enumerate(range(7, 26, 4)):
        g.ellipse(x + 1, 24 + b + (1 if (i + f) % 2 else 0), 2.2, 2.2, c)
    g.ellipse(12, 13 + b, 1.6, 3, EYE)
    g.ellipse(20, 13 + b, 1.6, 3, EYE)
    g.set(11, 11 + b, "#FFFFFF")
    g.set(19, 11 + b, "#FFFFFF")
    g.ellipse(16, 19 + b, 1.5, 2, "#6B3FA0")
    g.hline(8, 9, 17 + b, "#FF9AA8")
    g.hline(23, 24, 17 + b, "#FF9AA8")
    g.set(4, 16 + b + f, c)
    g.set(5, 16 + b + f, c)
    g.set(27, 15 + b, c)


def _m_bayangan(g, col, f):
    c, cd = rgba(col), shade(col, 0.6)
    flick = 2 if f else 0
    g.poly([(5, 28), (4, 14), (8, 5 + flick), (11, 12), (14, 2), (18, 11), (22, 4 - flick + 2),
            (25, 12), (28, 8 + flick), (28, 28)], cd)
    g.ellipse(16, 20, 11, 9, c)
    g.poly([(11, 16), (15, 18), (11, 19)], "#FFE14D")
    g.poly([(21, 16), (17, 18), (21, 19)], "#FFE14D")
    for x in range(10, 23, 2):
        g.set(x, 23, "#FFFFFF")
    g.hline(10, 22, 24, EYE)


def _m_naga(g, col, f):
    c, cd, cl = rgba(col), shade(col, 0.7), shade(col, 1.3)
    belly = rgba("#F5E6A8")
    wing = -2 if f else 0
    g.poly([(18, 14), (29, 3 + wing), (27, 10 + wing), (31, 12 + wing), (24, 18)], cd)
    g.poly([(24, 21), (31, 27), (30, 29), (22, 26)], c)
    g.ellipse(18, 21, 8, 7, c)
    g.ellipse(16, 23, 5, 4.5, belly)
    g.rect(12, 26, 3, 4, cd)
    g.rect(20, 26, 3, 4, cd)
    g.ellipse(9, 12, 6, 5.5, c)
    g.rect(1, 11, 6, 5, c)
    g.hline(1, 6, 15, cl)
    g.set(2, 12, EYE)
    g.poly([(10, 7), (12, 1), (13, 7)], "#F5E6A8")
    g.poly([(6, 7), (7, 2), (9, 7)], "#F5E6A8")
    g.rect(8, 9, 3, 3, "#FFFFFF")
    g.rect(9, 10, 2, 2, EYE)
    g.set(15, 17, cl)
    g.set(19, 16, cl)


def _m_mata(g, col, f):
    c = rgba(col)
    wing = rgba("#8E6BD8")
    fy = -3 if f else 0
    g.poly([(8, 15), (1, 8 + fy), (2, 14 + fy), (0, 18), (6, 19)], wing)
    g.poly([(24, 15), (31, 8 + fy), (30, 14 + fy), (32, 18), (26, 19)], wing)
    g.ellipse(16, 16, 10, 10, "#E8D8E8")
    g.ellipse(15.5, 15.5, 9.5, 9.5, "#FFF6FA")
    g.line(7, 12, 10, 14, "#FF9AA8")
    g.line(25, 19, 22, 18, "#FF9AA8")
    g.ellipse(16, 16, 5.5, 5.5, c)
    g.ellipse(16, 16, 2.5, 2.5, EYE)
    g.rect(13, 13, 2, 2, "#FFFFFF")


def _m_raja_jamur(g, col, f):
    c, cd = rgba(col), shade(col, 0.7)
    hop = -2 if f else 0
    stem, stem_d = rgba("#F3E3C3"), rgba("#D8C4A0")
    g.rect(15, 28 + hop, 26, 24, stem)
    g.vline(40, 28 + hop, 51 + hop, stem_d)
    g.rect(12, 51 + hop, 10, 4, "#8B5A2B")
    g.rect(34, 51 + hop, 10, 4, "#8B5A2B")
    g.rect(10, 34 + hop, 6, 8, stem)
    g.rect(40, 34 + hop, 6, 8, stem)
    g.ellipse(28, 22 + hop, 27, 15, cd)
    g.ellipse(28, 21 + hop, 26.5, 14.5, c)
    for x, y, r in ((12, 18, 4), (27, 12, 5), (43, 20, 4), (19, 28, 3), (36, 29, 3), (50, 26, 2)):
        g.ellipse(x, y + hop, r, r, "#FFFFFF")
    gold, gold_d = rgba("#F2C94C"), rgba("#C99A1E")
    g.poly([(18, 9 + hop), (18, 1 + hop), (23, 5 + hop), (28, -1 + hop), (33, 5 + hop),
            (38, 1 + hop), (38, 9 + hop)], gold)
    g.hline(18, 38, 8 + hop, gold_d)
    g.ellipse(28, 4 + hop, 1.5, 1.5, "#E0405E")
    g.hline(3, 53, 35 + hop, cd)
    _eyes(g, 21, 32, 38 + hop, 4)
    g.poly([(18, 45 + hop), (28, 43 + hop), (38, 45 + hop), (36, 47 + hop), (28, 45 + hop),
            (20, 47 + hop)], "#6B4430")
    g.hline(25, 31, 49 + hop, EYE)


def _m_golem(g, col, f):
    stone, sd, sl = rgba("#8D96AE"), rgba("#636C85"), rgba("#AEB6CB")
    c = rgba(col)
    s = 1 if f else 0
    g.rect(3, 17 + s, 10, 22, sd)
    g.rect(43, 17 - s, 10, 22, sd)
    g.rect(2, 36 + s, 12, 8, stone)
    g.rect(42, 36 - s, 12, 8, stone)
    g.rect(16, 44, 10, 11, sd)
    g.rect(30, 44, 10, 11, sd)
    g.rect(11, 14, 34, 32, stone)
    g.rect(11, 14, 34, 3, sl)
    g.vline(44, 14, 45, sd)
    g.rect(19, 1 + s, 18, 15, stone)
    g.rect(19, 1 + s, 18, 2, sl)
    g.hline(22, 26, 8 + s, c)
    g.hline(30, 34, 8 + s, c)
    g.hline(24, 32, 12 + s, sd)
    g.poly([(28, 20), (36, 29), (28, 40), (20, 29)], c)
    g.poly([(28, 20), (28, 29), (20, 29)], shade(col, 1.4))
    g.line(14, 20, 18, 26, sd)
    g.line(39, 36, 42, 41, sd)
    for x, y in ((6, 20), (48, 24), (15, 40)):
        g.poly([(x, y + 4), (x + 2, y), (x + 4, y + 4)], c)


def _m_ratu(g, col, f):
    c, cd, cl = rgba(col), shade(col, 0.6), shade(col, 1.3)
    skin = rgba("#E8D8F5")
    hair = rgba("#3A2466")
    glow = 1 if f else 0
    g.poly([(28, 12), (2, 55), (54, 55)], shade(col, 0.45))
    g.poly([(28, 18), (9, 55), (47, 55)], c)
    g.poly([(28, 18), (20, 55), (36, 55)], cd)
    g.hline(9, 47, 54, "#F2C94C")
    g.rect(22, 18, 12, 12, cd)
    g.poly([(22, 18), (28, 26), (34, 18)], cl)
    g.rect(16, 13, 6, 22, hair)
    g.rect(34, 13, 6, 22, hair)
    g.ellipse(28, 12, 7, 8, skin)
    g.rect(21, 4, 14, 5, hair)
    g.rect(20, 6, 3, 10, hair)
    g.rect(33, 6, 3, 10, hair)
    g.poly([(21, 5), (21, -1), (24, 3), (28, -2), (32, 3), (35, -1), (35, 5)], "#F2C94C")
    g.set(28, 1, "#E0405E")
    g.rect(24, 11, 2, 2, "#FFD23F")
    g.rect(31, 11, 2, 2, "#FFD23F")
    g.hline(26, 30, 16, "#8E3A6A")
    g.rect(14, 28, 5, 4, skin)
    g.ellipse(12, 26, 4 + glow, 4 + glow, "#8C4FE0")
    g.ellipse(12, 26, 2, 2, "#E6D0FF")
    g.rect(38, 28, 5, 4, skin)


MONSTER_ART = {
    "slime": (_m_slime, 32), "jamur": (_m_jamur, 32), "lebah": (_m_lebah, 32),
    "kelinci": (_m_kelinci, 32), "kelelawar": (_m_kelelawar, 32), "kristal": (_m_kristal, 32),
    "batu": (_m_batu, 32), "hantu": (_m_hantu, 32), "bayangan": (_m_bayangan, 32),
    "naga": (_m_naga, 32), "mata": (_m_mata, 32),
    "raja_jamur": (_m_raja_jamur, 56), "golem": (_m_golem, 56), "ratu": (_m_ratu, 56),
}


@lru_cache(maxsize=128)
def monster_frames(art, color):
    fn, size = MONSTER_ART[art]
    out = []
    for f in (0, 1):
        g = Grid(size, size)
        fn(g, color, f)
        out.append(g.outline().pixmap())
    return out


def enemy_frames(enemy_id):
    art, color = data.ENEMIES[enemy_id]["art"]
    return monster_frames(art, color)


# ---------------------------------------------------------------------------
# BENDA DI PETA (NPC khusus, peti, mata air)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=64)
def prop_frames(kind):
    frames = []
    for f in (0, 1):
        g = Grid(16, 20)
        if kind == "board":
            g.rect(1, 3, 14, 11, "#8B5A2B")
            g.rect(2, 4, 12, 9, "#C8955C")
            g.rect(3, 5, 4, 3, "#FFFFFF")
            g.rect(8, 5, 5, 4, "#FFF3B0")
            g.rect(4, 9, 5, 3, "#CDEBFF")
            g.set(5, 5, "#E0405E")
            g.set(10, 5, "#E0405E")
            g.vline(3, 14, 19, "#6A4220")
            g.vline(12, 14, 19, "#6A4220")
        elif kind == "rock":
            g.ellipse(8, 13, 8, 6.5, "#7C7468")
            g.ellipse(7.5, 12.5, 7.5, 6, "#9C9486")
            g.ellipse(5, 10, 3, 2, "#B8B0A2")
            g.line(10, 9, 12, 14, "#7C7468")
        elif kind == "door":
            g.rect(2, 4, 12, 16, "#7A4A22")
            g.rect(3, 5, 10, 15, "#9B6A3C")
            g.vline(8, 5, 19, "#7A4A22")
            g.set(11, 13, "#F2C94C")
        elif kind == "fairy":
            wy = 1 if f else 0
            wing = (200, 240, 255, 200)
            g.ellipse(4, 8 + wy, 3, 4, wing)
            g.ellipse(12, 8 + wy, 3, 4, wing)
            g.ellipse(8, 7 + wy, 3, 3, "#FFE3C8")
            g.rect(5, 3 + wy, 6, 3, "#6FD66A")
            g.rect(6, 10 + wy, 4, 5, "#6FD66A")
            g.poly([(5, 15 + wy), (8, 11 + wy), (11, 15 + wy)], "#4FAF4A")
            g.set(7, 7 + wy, EYE)
            g.set(9, 7 + wy, EYE)
            g.set(8, 1 + wy, "#FFE14D")
        elif kind == "cat":
            t = 1 if f else 0
            g.ellipse(8, 14, 5, 4, "#EDEDF2")
            g.ellipse(8, 9, 4.5, 4, "#EDEDF2")
            g.poly([(4, 7), (4, 3), (7, 6)], "#EDEDF2")
            g.poly([(12, 7), (12, 3), (9, 6)], "#EDEDF2")
            g.set(6, 9, EYE)
            g.set(10, 9, EYE)
            g.set(8, 11, "#FF9AA8")
            g.line(13, 16, 15, 12 - t, "#EDEDF2")
        g.outline()
        frames.append(g.pixmap())
    return frames


@lru_cache(maxsize=4)
def chest_pixmap(opened):
    g = Grid(16, 16)
    wood, wood_d, gold = "#B0703A", "#7A4A22", "#F2C94C"
    if opened:
        g.rect(1, 7, 14, 8, wood_d)
        g.rect(2, 8, 12, 3, "#3A2418")
        g.rect(1, 3, 14, 4, wood)
        g.rect(1, 11, 14, 4, wood)
        g.hline(1, 14, 11, gold)
    else:
        g.rect(1, 5, 14, 10, wood)
        g.rect(1, 5, 14, 4, shade(wood, 1.15))
        g.hline(1, 14, 9, wood_d)
        g.vline(3, 5, 14, gold)
        g.vline(12, 5, 14, gold)
        g.rect(7, 8, 2, 3, gold)
    return g.outline().pixmap()


@lru_cache(maxsize=4)
def spring_pixmap(f):
    g = Grid(16, 16)
    g.ellipse(8, 9, 7.5, 5.5, "#9C9486")
    g.ellipse(8, 9, 6, 4, "#7FE9FF")
    g.ellipse(7, 8, 3, 1.5, "#D8FBFF")
    for x, y in (((4, 6), (11, 5)) if f else ((6, 4), (12, 7))):
        g.set(x, y, "#FFFFFF")
    return g.pixmap()


# ---------------------------------------------------------------------------
# PETAK PETA
# ---------------------------------------------------------------------------

def _speckle(g, rng, n, colors, area=(0, 0, 16, 16)):
    x0, y0, w, h = area
    for _ in range(n):
        g.set(x0 + rng.randrange(w), y0 + rng.randrange(h), rng.choice(colors))


def _t_grass(g, rng, base="#7CCB5A"):
    g.rect(0, 0, 16, 16, base)
    _speckle(g, rng, 12, [shade(base, 0.86), shade(base, 0.9)])
    _speckle(g, rng, 5, [shade(base, 1.2)])
    for _ in range(3):
        x, y = rng.randrange(1, 15), rng.randrange(2, 15)
        g.set(x, y, shade(base, 0.75))
        g.set(x, y - 1, shade(base, 0.8))


def _t_flowers(g, rng):
    for _ in range(3):
        x, y = rng.randrange(2, 14), rng.randrange(2, 14)
        petal = rng.choice(["#FF8FC8", "#FFFFFF", "#FF6B6B", "#B08CFF"])
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            g.set(x + dx, y + dy, petal)
        g.set(x, y, "#FFE14D")


def _t_tallgrass(g, rng):
    _t_grass(g, rng, "#5FB348")
    for _ in range(7):
        x, y = rng.randrange(1, 15), rng.randrange(3, 16)
        g.set(x, y, "#3F8A34")
        g.set(x - 1, y - 1, "#4E9A3C")
        g.set(x + 1, y - 1, "#4E9A3C")
        g.set(x - 1, y - 2, "#8AD66A")
        g.set(x + 1, y - 2, "#8AD66A")


def _t_tree(g, rng):
    g.rect(6, 11, 4, 5, "#7A4A22")
    g.vline(6, 11, 15, "#5A3418")
    g.ellipse(8, 6.5, 7.8, 6.8, "#23693A")
    g.ellipse(8, 6, 7, 6, "#3E9A4A")
    g.ellipse(6, 4, 3.5, 2.5, "#5CBB5A")
    g.set(4, 3, "#86D67A")
    g.set(11, 8, "#2E7A3A")
    g.set(9, 10, "#2E7A3A")


def _t_bush(g, rng):
    g.ellipse(8, 9.5, 7.5, 5.8, "#2E7A3A")
    g.ellipse(8, 9, 7, 5.2, "#4AA84E")
    g.ellipse(6, 7, 3, 2, "#6FC866")
    for x, y in ((5, 10), (10, 8), (11, 11)):
        g.set(x, y, "#E0405E")


def _t_water(g, rng, f):
    g.rect(0, 0, 16, 16, "#4AA3E8")
    _speckle(g, rng, 6, ["#3F92D6"])
    r2 = random.Random(7 + f)
    for _ in range(3):
        x, y = r2.randrange(0, 12), r2.randrange(1, 15)
        g.hline(x, x + 3, y, "#8FD0FF")


def _t_path(g, rng):
    g.rect(0, 0, 16, 16, "#D9B77E")
    _speckle(g, rng, 10, ["#C49A5E", "#CCA56C"])
    _speckle(g, rng, 5, ["#E8CB98"])


def _t_sand(g, rng):
    g.rect(0, 0, 16, 16, "#F0DC9A")
    _speckle(g, rng, 10, ["#DCC47E", "#FFF0BC"])


def _t_stonewall(g, rng, base="#8C8C9C", mortar="#6C6C7C"):
    g.rect(0, 0, 16, 16, base)
    for y in (3, 7, 11, 15):
        g.hline(0, 15, y, mortar)
    for row, y in enumerate((0, 4, 8, 12)):
        off = 0 if row % 2 else 4
        for x in range(off, 16, 8):
            g.vline(x, y, y + 2, mortar)
    _speckle(g, rng, 6, [shade(base, 1.15)])


def _t_woodwall(g, rng):
    g.rect(0, 0, 16, 16, "#B07A45")
    for x in (0, 5, 10, 15):
        g.vline(x, 0, 15, "#8B5A2B")
    g.rect(0, 0, 16, 2, "#7A4A22")
    _speckle(g, rng, 5, ["#C08A55"])


def _t_window(g, rng):
    _t_woodwall(g, rng)
    g.rect(3, 4, 10, 8, "#6A4220")
    g.rect(4, 5, 8, 6, "#9FD8FF")
    g.vline(8, 5, 10, "#6A4220")
    g.hline(4, 11, 8, "#6A4220")
    g.set(5, 6, "#FFFFFF")


def _t_roof(g, rng, base):
    g.rect(0, 0, 16, 16, base)
    for y in (3, 7, 11, 15):
        g.hline(0, 15, y, shade(base, 0.72))
    for row, y in enumerate((0, 4, 8, 12)):
        off = 2 if row % 2 else 6
        for x in range(off, 16, 8):
            g.vline(x, y, y + 2, shade(base, 0.82))
    g.hline(0, 15, 0, shade(base, 1.2))


def _t_door(g, rng):
    _t_woodwall(g, rng)
    g.rect(3, 2, 10, 14, "#5A3418")
    g.rect(4, 3, 8, 13, "#8B5A2B")
    g.vline(8, 3, 15, "#5A3418")
    g.set(10, 10, "#F2C94C")
    g.set(5, 10, "#F2C94C")


def _t_floor(g, rng):
    g.rect(0, 0, 16, 16, "#C8955C")
    for y in (3, 7, 11, 15):
        g.hline(0, 15, y, "#A87640")
    for row, y in enumerate((0, 4, 8, 12)):
        x = (rng.randrange(3, 13))
        g.vline(x, y, y + 2, "#A87640")
    _speckle(g, rng, 4, ["#D8A56C"])


def _t_carpet(g, rng):
    g.rect(0, 0, 16, 16, "#C4404A")
    for x in range(1, 16, 4):
        for y in range(1, 16, 4):
            g.set(x, y, "#F2C94C")
    _speckle(g, rng, 4, ["#B03440"])


def _t_table(g, rng):
    g.rect(1, 3, 14, 9, "#7A4A22")
    g.rect(1, 3, 14, 7, "#A8703A")
    g.hline(2, 13, 4, "#C08A55")
    g.rect(2, 12, 2, 4, "#5A3418")
    g.rect(12, 12, 2, 4, "#5A3418")
    g.set(5, 6, "#FFFFFF")
    g.set(10, 5, "#FFE14D")


def _t_counter(g, rng):
    g.rect(0, 2, 16, 14, "#7A4A22")
    g.rect(0, 2, 16, 5, "#B07A45")
    g.hline(0, 15, 2, "#C8955C")
    for x in (3, 8, 13):
        g.vline(x, 8, 15, "#5A3418")


def _t_shelf(g, rng):
    g.rect(0, 0, 16, 16, "#6A4220")
    for y in (1, 8):
        for x in range(1, 15, 2):
            col = rng.choice(["#E0405E", "#3E7BE0", "#3FAE5A", "#F2B632", "#9A5BE0"])
            g.rect(x, y, 2, 6, col)
    g.hline(0, 15, 7, "#5A3418")
    g.hline(0, 15, 14, "#5A3418")


def _t_barrel(g, rng):
    g.ellipse(8, 9, 6, 7, "#8B5A2B")
    g.ellipse(8, 9, 5, 6.5, "#A8703A")
    g.hline(3, 13, 5, "#5A5A6A")
    g.hline(2, 14, 12, "#5A5A6A")
    g.ellipse(8, 3.5, 4.5, 1.6, "#C08A55")


def _t_innerwall(g, rng):
    g.rect(0, 0, 16, 16, "#8B5A2B")
    g.rect(0, 11, 16, 5, "#A8703A")
    g.hline(0, 15, 11, "#6A4220")
    g.hline(0, 15, 0, "#6A4220")
    for x in (4, 12):
        g.vline(x, 12, 15, "#8B5A2B")


def _t_cavefloor(g, rng):
    g.rect(0, 0, 16, 16, "#5A4A5E")
    _speckle(g, rng, 12, ["#4A3C4E", "#6E5E72"])


def _t_cavewall(g, rng):
    g.rect(0, 0, 16, 16, "#3A2E40")
    for _ in range(4):
        x, y = rng.randrange(0, 13), rng.randrange(0, 13)
        g.rect(x, y, 3 + rng.randrange(3), 2 + rng.randrange(2), "#4E4058")
        g.hline(x, x + 2, y, "#64566E")


def _t_crystal(g, rng):
    g.poly([(3, 15), (5, 4), (8, 15)], "#3FB0D8")
    g.poly([(6, 15), (9, 1), (12, 15)], "#7FE9FF")
    g.poly([(10, 15), (13, 7), (15, 15)], "#5CCDF0")
    g.line(9, 3, 9, 10, "#E0FCFF")
    g.set(5, 6, "#E0FCFF")


def _t_bridge(g, rng, f=0):
    _t_water(g, rng, f)
    g.rect(0, 2, 16, 12, "#B07A45")
    for x in (0, 4, 8, 12):
        g.vline(x, 2, 13, "#8B5A2B")
    g.hline(0, 15, 2, "#6A4220")
    g.hline(0, 15, 13, "#6A4220")


def _t_fence(g, rng):
    for x in (2, 12):
        g.rect(x, 3, 2, 12, "#8B5A2B")
        g.set(x, 3, "#B07A45")
    g.rect(0, 6, 16, 2, "#A8703A")
    g.rect(0, 11, 16, 2, "#A8703A")


def _t_towerfloor(g, rng):
    g.rect(0, 0, 16, 16, "#D8D0E8")
    g.hline(0, 15, 7, "#B8AED0")
    g.hline(0, 15, 15, "#B8AED0")
    g.vline(7, 0, 6, "#B8AED0")
    g.vline(15, 8, 15, "#B8AED0")
    g.set(2, 2, "#F0EAFA")
    g.set(10, 10, "#F0EAFA")


def _t_towerwall(g, rng):
    _t_stonewall(g, rng, "#9C8CC8", "#7A6AA8")
    g.hline(0, 15, 0, "#C0B4E8")


def _t_cloud(g, rng, f=0):
    g.rect(0, 0, 16, 16, "#A8D8FF")
    for _ in range(3):
        x, y = rng.randrange(0, 16), rng.randrange(0, 16)
        g.ellipse(x, y, 3 + rng.randrange(3), 2 + rng.randrange(2), "#FFFFFF")
    _speckle(g, rng, 4, ["#E6F4FF"])


def _t_forest(g, rng):
    _t_grass(g, rng, "#5E9A48")
    _speckle(g, rng, 6, ["#7A6A3A", "#8C7A48"])
    if rng.random() < 0.15:
        g.rect(6, 9, 2, 3, "#F3E3C3")
        g.hline(5, 8, 8, "#E8494F")


def _fountain_big(f):
    """Air mancur utuh 32x32 (dipotong jadi 4 petak)."""
    tile = Grid(16, 16)
    _t_path(tile, random.Random(1))
    big = Grid(32, 32)
    for qy in (0, 16):
        for qx in (0, 16):
            big.blit(tile, qx, qy)
    big.ellipse(16, 17, 15.5, 13.5, "#8C8478")
    big.ellipse(16, 16, 15, 13, "#C8C0B2")
    big.ellipse(16, 16, 12.5, 10.5, "#4AA3E8")
    for i in range(6):
        a = i * math.pi / 3 + f * 0.5
        big.set(16 + math.cos(a) * 9, 16 + math.sin(a) * 7, "#8FD0FF")
    big.ellipse(16, 15, 4.5, 3.5, "#B8B0A2")
    big.rect(14, 7, 4, 8, "#C8C0B2")
    big.vline(16, 2 - f, 7, "#BFE8FF")
    big.set(15, 3 + f, "#FFFFFF")
    big.set(17, 4 - f, "#FFFFFF")
    big.set(13 + f, 5, "#8FD0FF")
    big.set(19 - f, 5, "#8FD0FF")
    return big


def _t_fountain(g, rng, f=0, quad=0):
    big = _fountain_big(f)
    ox, oy = (quad % 2) * 16, (quad // 2) * 16
    for y in range(16):
        for x in range(16):
            g.px[y][x] = big.px[oy + y][ox + x]


def _t_mountain(g, rng):
    g.poly([(8, 0), (-1, 16), (17, 16)], "#8C7A6A")
    g.poly([(8, 0), (-1, 16), (8, 16)], "#A89684")
    g.poly([(8, 0), (5, 5), (11, 5)], "#FFFFFF")
    g.line(8, 5, 10, 10, "#76665A")


def _t_pillar(g, rng):
    g.rect(3, 13, 10, 3, "#B8AED0")
    g.rect(4, 2, 8, 11, "#E8E0F5")
    g.vline(10, 2, 12, "#C4BAE0")
    g.vline(5, 2, 12, "#FFFFFF")
    g.rect(3, 0, 10, 2, "#B8AED0")


# nama -> (fungsi, butuh latar lantai peta?, animasi air)
TILE_ART = {
    "rumput": (_t_grass, False), "bunga": (lambda g, r: (_t_grass(g, r), _t_flowers(g, r)), False),
    "rumput_tinggi": (_t_tallgrass, False), "pohon": (_t_tree, True), "semak": (_t_bush, True),
    "air": (None, False), "jalan": (_t_path, False), "pasir": (_t_sand, False),
    "tembok": (_t_stonewall, False), "dinding_kayu": (_t_woodwall, False),
    "jendela": (_t_window, False), "atap_merah": (lambda g, r: _t_roof(g, r, "#D9544A"), False),
    "atap_biru": (lambda g, r: _t_roof(g, r, "#4A7AD9"), False), "pintu": (_t_door, False),
    "lantai_kayu": (_t_floor, False), "karpet": (_t_carpet, False), "meja": (_t_table, True),
    "konter": (_t_counter, True), "rak": (_t_shelf, False), "tong": (_t_barrel, True),
    "dinding_dalam": (_t_innerwall, False), "lantai_gua": (_t_cavefloor, False),
    "dinding_gua": (_t_cavewall, False), "kristal": (_t_crystal, True),
    "jembatan": (None, False), "pagar": (_t_fence, True), "lantai_menara": (_t_towerfloor, False),
    "dinding_menara": (_t_towerwall, False), "awan": (_t_cloud, False),
    "tanah_hutan": (_t_forest, False), "air_mancur": (None, False), "gunung": (_t_mountain, True),
    "pilar": (_t_pillar, True),
}
ANIMATED = {"air": _t_water, "jembatan": _t_bridge, "air_mancur": _t_fountain}


def tile_image(name, floor_name, variant, frame=0):
    """QImage 16x16 satu petak (latar lantai peta bila perlu)."""
    rng = random.Random(hash((name, variant)) & 0xFFFF)
    g = Grid(16, 16)
    if name == "air_mancur":
        _t_fountain(g, rng, frame, variant % 4)
    elif name in ANIMATED:
        ANIMATED[name](g, rng, frame)
    else:
        fn, overlay = TILE_ART[name]
        if overlay:
            bg_fn = TILE_ART[floor_name][0]
            bg_fn(g, random.Random(hash((floor_name, variant)) & 0xFFFF))
        fn(g, rng)
    return g.image()


# ---------------------------------------------------------------------------
# LATAR PERTARUNGAN
# ---------------------------------------------------------------------------

@lru_cache(maxsize=8)
def battle_background(kind, w=320, h=240):
    img = QImage(w, h, QImage.Format_RGB32)
    p = QPainter(img)
    rng = random.Random(5)
    ground = int(h * 0.42)
    if kind == "hutan":
        sky = QLinearGradient(0, 0, 0, ground)
        sky.setColorAt(0, QColor("#1E4A34"))
        sky.setColorAt(1, QColor("#3E7A48"))
        p.fillRect(0, 0, w, ground, sky)
        for i in range(9):
            x = i * 40 + rng.randrange(-8, 8)
            p.fillRect(x, 0, 10 + rng.randrange(6), ground + 10, QColor("#2A3A22"))
            p.setBrush(QColor("#2E6A3A"))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(x + 6, rng.randrange(0, 30)), 30, 22)
        p.setBrush(QColor(255, 255, 200, 30))
        p.drawPolygon(QPolygonF([QPointF(120, 0), QPointF(160, 0), QPointF(220, ground),
                                 QPointF(150, ground)]))
        gr = QLinearGradient(0, ground, 0, h)
        gr.setColorAt(0, QColor("#4E8A3E"))
        gr.setColorAt(1, QColor("#2E5A28"))
        p.fillRect(0, ground, w, h - ground, gr)
        for _ in range(40):
            p.fillRect(rng.randrange(w), rng.randrange(ground, h), 2, 1, QColor("#6AAA4E"))
    elif kind == "gua":
        sky = QLinearGradient(0, 0, 0, ground)
        sky.setColorAt(0, QColor("#140E1E"))
        sky.setColorAt(1, QColor("#3A2A4E"))
        p.fillRect(0, 0, w, ground, sky)
        p.setPen(Qt.NoPen)
        for i in range(14):
            x = i * 24 + rng.randrange(-6, 6)
            ln = rng.randrange(15, 50)
            p.setBrush(QColor("#2A2036"))
            p.drawPolygon(QPolygonF([QPointF(x, 0), QPointF(x + 16, 0), QPointF(x + 8, ln)]))
        for i in range(6):
            x = rng.randrange(0, w)
            glow = QRadialGradient(QPointF(x, ground - 4), 30)
            glow.setColorAt(0, QColor(127, 233, 255, 90))
            glow.setColorAt(1, QColor(127, 233, 255, 0))
            p.setBrush(glow)
            p.drawEllipse(QPointF(x, ground - 4), 30, 30)
            p.setBrush(QColor("#7FE9FF"))
            p.drawPolygon(QPolygonF([QPointF(x - 5, ground + 2), QPointF(x, ground - 16),
                                     QPointF(x + 5, ground + 2)]))
        gr = QLinearGradient(0, ground, 0, h)
        gr.setColorAt(0, QColor("#4A3C58"))
        gr.setColorAt(1, QColor("#241C2E"))
        p.fillRect(0, ground, w, h - ground, gr)
        for _ in range(30):
            p.fillRect(rng.randrange(w), rng.randrange(ground, h), 3, 2, QColor("#5E4E6E"))
    elif kind == "menara":
        sky = QLinearGradient(0, 0, 0, ground)
        sky.setColorAt(0, QColor("#6B4FB0"))
        sky.setColorAt(1, QColor("#F2A8D8"))
        p.fillRect(0, 0, w, ground, sky)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 170))
        for _ in range(7):
            x, y = rng.randrange(w), rng.randrange(10, ground - 10)
            p.drawEllipse(QPointF(x, y), 26, 8)
            p.drawEllipse(QPointF(x + 14, y - 4), 14, 8)
        for x in (30, 290):
            p.fillRect(x - 10, 0, 20, ground, QColor("#D8D0E8"))
            p.fillRect(x + 6, 0, 4, ground, QColor("#B8AED0"))
        gr = QLinearGradient(0, ground, 0, h)
        gr.setColorAt(0, QColor("#D8D0E8"))
        gr.setColorAt(1, QColor("#9C8CC8"))
        p.fillRect(0, ground, w, h - ground, gr)
        p.setPen(QColor("#B8AED0"))
        for i in range(-8, 9):
            p.drawLine(QPointF(w / 2 + i * 12, ground), QPointF(w / 2 + i * 60, h))
        for k in range(1, 6):
            y = ground + (h - ground) * (k / 6) ** 1.4
            p.drawLine(QPointF(0, y), QPointF(w, y))
    else:   # padang
        sky = QLinearGradient(0, 0, 0, ground)
        sky.setColorAt(0, QColor("#6EC0FF"))
        sky.setColorAt(1, QColor("#CDEBFF"))
        p.fillRect(0, 0, w, ground, sky)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 220))
        for _ in range(4):
            x, y = rng.randrange(w), rng.randrange(8, 50)
            p.drawEllipse(QPointF(x, y), 22, 7)
            p.drawEllipse(QPointF(x + 10, y - 4), 12, 7)
        p.setBrush(QColor("#8FD07A"))
        p.drawEllipse(QPointF(60, ground + 18), 120, 40)
        p.drawEllipse(QPointF(250, ground + 22), 140, 44)
        gr = QLinearGradient(0, ground, 0, h)
        gr.setColorAt(0, QColor("#7CCB5A"))
        gr.setColorAt(1, QColor("#4E9A3C"))
        p.fillRect(0, ground, w, h - ground, gr)
        for _ in range(50):
            p.fillRect(rng.randrange(w), rng.randrange(ground, h), 2, 2,
                       QColor(rng.choice(["#9BE07A", "#FF8FC8", "#FFFFFF", "#FFE14D"])))
    p.end()
    return QPixmap.fromImage(img)
