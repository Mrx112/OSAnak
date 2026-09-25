# -*- coding: utf-8 -*-
"""Layar-layar menu: judul, slot, buat karakter, lobi, dialog, menu jeda, toko, dll."""

import math
import random

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QLinearGradient, QPainter, QPen, QPolygonF, QRadialGradient

from . import data, sprites, ui
from .ui import LW, LH, UP, DOWN, LEFT, RIGHT, OK, CANCEL, MENU


def draw_sprite(p, pm, x, y, scale):
    p.drawPixmap(QRectF(x, y, pm.width() * scale, pm.height() * scale), pm, QRectF(pm.rect()))


# ---------------------------------------------------------------------------
# JUDUL
# ---------------------------------------------------------------------------

class TitleScene(ui.Scene):
    covers_world = True

    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu(["🗡️ Main Sendiri", "🏰 Buat Lobi (Tuan Rumah)",
                                 "🤝 Gabung Lobi Teman", "🚪 Keluar"], 96, 142, 128,
                                row_h=17, size=9)
        rng = random.Random(3)
        self.party = []
        for i, cls in enumerate(data.CLASS_ORDER):
            look = {"skin": rng.randrange(4), "hair": data.HAIR_STYLES[i][0],
                    "hair_color": data.HAIR_COLORS[(i * 3) % 8][1],
                    "outfit": data.OUTFIT_COLORS[(i * 2 + 1) % 8][1], "hat": None}
            hero = data.new_hero("x", cls, look)
            self.party.append(data.look_of(hero))
        self.stars = [(rng.uniform(0, LW), rng.uniform(0, 90), rng.uniform(0.5, 1.5))
                      for _ in range(40)]
        game.music("rpg_judul")

    def on_top(self):
        self.game.music("rpg_judul")

    def key(self, k):
        r = self.menu.key(k)
        if r == "ok":
            self.choose(self.menu.index)
        elif r == "move":
            self.game.sfx("key")

    def mouse(self, x, y, kind):
        if kind == "press" and self.menu.mouse((x, y)) == "ok":
            self.choose(self.menu.index)

    def choose(self, i):
        self.game.sfx("pop")
        if i == 0:
            self.game.push(SlotScene(self.game, "solo"))
        elif i == 1:
            self.game.push(SlotScene(self.game, "host"))
        elif i == 2:
            self.game.push(SlotScene(self.game, "join"))
        else:
            self.game.exit_game()

    def draw_world(self, p):
        g = QLinearGradient(0, 0, 0, LH)
        g.setColorAt(0, QColor("#2B1F66"))
        g.setColorAt(0.55, QColor("#E27AB5"))
        g.setColorAt(1, QColor("#FFD59A"))
        p.fillRect(0, 0, LW, LH, g)
        p.setPen(Qt.NoPen)
        for x, y, s in self.stars:
            a = int(150 + 100 * math.sin(self.t * 2 + x))
            p.setBrush(QColor(255, 255, 255, max(0, min(255, a))))
            p.drawEllipse(QPointF(x, y), s * 0.6, s * 0.6)
        # pelangi
        for i, c in enumerate(sprites.RAINBOW):
            col = QColor(c)
            col.setAlpha(120)
            p.setPen(QPen(col, 4))
            p.setBrush(Qt.NoBrush)
            r = 150 - i * 4
            p.drawArc(QRectF(LW / 2 - r, 150 - r, 2 * r, 2 * r), 0, 180 * 16)
        # menara & bukit
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#6A4FA0"))
        p.drawRect(QRectF(250, 70, 22, 100))
        p.drawPolygon(QPolygonF([QPointF(246, 72), QPointF(261, 48), QPointF(276, 72)]))
        p.setBrush(QColor("#FFE9A8"))
        p.drawRect(QRectF(258, 84, 6, 8))
        for i, (col, base, amp, speed) in enumerate(((QColor("#7A5AB8"), 175, 16, 6),
                                                    (QColor("#4E9A5C"), 192, 12, 14),
                                                    (QColor("#3E7A48"), 208, 10, 24))):
            p.setBrush(col)
            off = (self.t * speed) % 80
            path = []
            for x in range(-80, LW + 81, 8):
                path.append(QPointF(x - off, base - amp * math.sin((x) / 40.0 + i)))
            path += [QPointF(LW + 80, LH), QPointF(-80, LH)]
            p.drawPolygon(QPolygonF(path))
        # regu berjalan
        for i, look in enumerate(self.party):
            fr = sprites.hero_frames(look)
            k = int(self.t * 6 + i) % 4
            pm = fr[("right", (0, 1, 0, 2)[k])]
            draw_sprite(p, pm, 10 + i * 19, 196, 1.0)

    def draw_ui(self, p):
        # logo pelangi
        title = "Legenda"
        ui.text(p, LW / 2, 14, title, 12, QColor("#FFF6C0"), align=Qt.AlignHCenter)
        big = "Kristal Pelangi"
        w = ui.text_width(big, 22)
        x = LW / 2 - w / 2
        p.setFont(ui.font(22))
        for i, ch in enumerate(big):
            cw = ui.text_width(ch, 22) if ch != " " else 6
            y = 30 + math.sin(self.t * 3 + i * 0.5) * 1.5
            ui.text(p, x, y, ch, 22, QColor(sprites.RAINBOW[i % 6]))
            x += cw
        ui.text(p, LW / 2, 64, "Petualangan RPG • Main sendiri atau bareng teman (LAN)", 7,
                ui.WHITE, align=Qt.AlignHCenter)
        ui.window(p, 88, 136, 144, 76)
        self.menu.draw(p, self.t)
        ui.text(p, LW - 4, LH - 11, "Panah/klik = pilih • Enter = OK", 6, ui.WHITE,
                align=Qt.AlignRight)


# ---------------------------------------------------------------------------
# SLOT KARAKTER
# ---------------------------------------------------------------------------

class SlotScene(ui.Scene):
    covers_world = False

    def __init__(self, game, purpose):
        super().__init__(game)
        self.purpose = purpose
        self.refresh()

    def refresh(self):
        self.slots = self.game.load_profiles()
        rows = []
        for i, prof in enumerate(self.slots):
            if prof:
                h = prof["hero"]
                rows.append(f"{h['name']}")
            else:
                rows.append("➕ Buat Karakter Baru")
        rows.append("◀ Kembali")
        self.menu = ui.ListMenu(rows, 44, 60, 232, row_h=38, size=9)

    def on_top(self):
        self.refresh()

    def key(self, k):
        r = self.menu.key(k)
        if r == "ok":
            self.choose(self.menu.index)
        elif r == "cancel":
            self.close()
        elif r == "move":
            self.game.sfx("key")

    def text_input(self, s):
        if s in ("d", "D") and self.menu.index < 3 and self.slots[self.menu.index]:
            self.ask_delete(self.menu.index)
            return True
        return False

    def ask_delete(self, i):
        name = self.slots[i]["hero"]["name"]
        self.game.push(ConfirmScene(self.game, f"Hapus karakter {name}? Tidak bisa dibatalkan!",
                                    lambda: (self.game.delete_profile(i), self.refresh())))

    def mouse(self, x, y, kind):
        if kind != "press":
            return
        for i in range(3):
            if self.slots[i] and ui.inside((x, y), (254, 60 + i * 38 + 10, 18, 16)):
                self.ask_delete(i)
                return
        if self.menu.mouse((x, y)) == "ok":
            self.choose(self.menu.index)

    def choose(self, i):
        self.game.sfx("pop")
        if i == 3:
            self.close()
            return
        if self.slots[i] is None:
            self.game.push(CreateScene(self.game, i, self.purpose))
        else:
            self.game.begin(self.purpose, i)

    def draw_ui(self, p):
        ui.window(p, 36, 16, 248, 212)
        label = {"solo": "Main Sendiri", "host": "Buat Lobi", "join": "Gabung Lobi"}[self.purpose]
        ui.text(p, LW / 2, 22, f"Pilih Karakter • {label}", 10, ui.YELLOW, align=Qt.AlignHCenter)
        ui.text(p, LW / 2, 40, "Karakter disimpan di komputer ini (3 slot)", 7, ui.GREY,
                align=Qt.AlignHCenter)
        for i in range(3):
            x, y, w, h = self.menu.item_rect(i)
            p.setPen(QPen(QColor(255, 255, 255, 60), 0.6))
            p.setBrush(QColor(0, 0, 0, 50) if i != self.menu.index else QColor(255, 255, 255, 30))
            p.drawRoundedRect(QRectF(x, y + 2, w, h - 4), 3, 3)
            prof = self.slots[i]
            if prof:
                hero = prof["hero"]
                fr = sprites.hero_frames(data.look_of(hero))["portrait"]
                draw_sprite(p, fr, x + 16, y + 4, 1.9)
                cls = data.CLASSES[hero["cls"]]
                ui.text(p, x + 52, y + 5, hero["name"], 9, ui.WHITE)
                ui.text(p, x + 52, y + 19, f"{cls['icon']} {cls['name']}  •  Lv {hero['level']}"
                        f"  •  🪙 {hero['gold']}", 7, ui.GREY)
                ui.text(p, x + w - 22, y + 10, "🗑", 9, ui.WHITE)
        # teks baris tetap digambar oleh ListMenu (nama/tombol)
        saved = self.menu.items
        self.menu.items = ["", "", "", "◀ Kembali"]
        for i in range(3):
            if self.slots[i] is None:
                self.menu.items[i] = "➕ Buat Karakter Baru"
        self.menu.draw(p, self.t)
        self.menu.items = saved
        ui.text(p, LW / 2, 212, "Tombol D = hapus karakter", 6, ui.GREY, align=Qt.AlignHCenter)


class ConfirmScene(ui.Scene):
    def __init__(self, game, question, yes, no=None):
        super().__init__(game)
        self.question = question
        self.yes, self.no = yes, no
        self.menu = ui.ListMenu(["Ya", "Tidak"], 110, 130, 100, row_h=15, cols=2)
        self.menu.index = 1

    def key(self, k):
        r = self.menu.key(k)
        if r == "ok":
            self.answer(self.menu.index == 0)
        elif r == "cancel":
            self.answer(False)

    def mouse(self, x, y, kind):
        if kind == "press" and self.menu.mouse((x, y)) == "ok":
            self.answer(self.menu.index == 0)

    def answer(self, yes):
        self.close()
        cb = self.yes if yes else self.no
        if cb:
            cb()

    def draw_ui(self, p):
        ui.window(p, 60, 88, 200, 66)
        ui.paragraph(p, 70, 94, 180, self.question, 8)
        self.menu.draw(p, self.t)


# ---------------------------------------------------------------------------
# BUAT KARAKTER
# ---------------------------------------------------------------------------

class CreateScene(ui.Scene):
    covers_world = True

    ROWS = ["Nama", "Kelas", "Kulit", "Rambut", "Warna Rambut", "Warna Baju", "Topi"]

    def __init__(self, game, slot, purpose):
        super().__init__(game)
        self.slot, self.purpose = slot, purpose
        rng = random.Random()
        self.name = rng.choice(data.RANDOM_NAMES)
        self.vals = {"Kelas": 0, "Kulit": rng.randrange(4), "Rambut": rng.randrange(5),
                     "Warna Rambut": rng.randrange(8), "Warna Baju": rng.randrange(8), "Topi": 0}
        self.row = 0
        self.rows = self.ROWS + ["✔ Mulai Petualangan", "◀ Batal"]
        self.typed = False

    def options(self, row):
        return {"Kelas": len(data.CLASS_ORDER), "Kulit": len(data.SKINS),
                "Rambut": len(data.HAIR_STYLES), "Warna Rambut": len(data.HAIR_COLORS),
                "Warna Baju": len(data.OUTFIT_COLORS), "Topi": len(data.HATS)}.get(row, 0)

    def value_text(self, row):
        v = self.vals.get(row)
        if row == "Nama":
            return self.name + ("▏" if int(self.t * 2) % 2 and self.row == 0 else "")
        if row == "Kelas":
            c = data.CLASSES[data.CLASS_ORDER[v]]
            return f"{c['icon']} {c['name']}"
        if row == "Kulit":
            return f"Warna {v + 1}"
        if row == "Rambut":
            return data.HAIR_STYLES[v][1]
        if row == "Warna Rambut":
            return data.HAIR_COLORS[v][0]
        if row == "Warna Baju":
            return data.OUTFIT_COLORS[v][0]
        if row == "Topi":
            return data.HATS[v][1]
        return ""

    def look(self):
        return {"skin": self.vals["Kulit"], "hair": data.HAIR_STYLES[self.vals["Rambut"]][0],
                "hair_color": data.HAIR_COLORS[self.vals["Warna Rambut"]][1],
                "outfit": data.OUTFIT_COLORS[self.vals["Warna Baju"]][1],
                "hat": data.HATS[self.vals["Topi"]][0]}

    def cls(self):
        return data.CLASS_ORDER[self.vals["Kelas"]]

    def change(self, row, delta):
        if row == "Nama":
            self.name = random.choice([n for n in data.RANDOM_NAMES if n != self.name])
        elif row in self.vals:
            self.vals[row] = (self.vals[row] + delta) % self.options(row)
        self.game.sfx("key")

    def key(self, k):
        name = self.rows[self.row]
        if k == UP:
            self.row = (self.row - 1) % len(self.rows)
            self.game.sfx("key")
        elif k == DOWN:
            self.row = (self.row + 1) % len(self.rows)
            self.game.sfx("key")
        elif k in (LEFT, RIGHT):
            self.change(name, -1 if k == LEFT else 1)
        elif k == OK:
            if name.startswith("✔"):
                self.finish()
            elif name.startswith("◀"):
                self.close()
            elif name == "Nama":
                self.row += 1
            else:
                self.change(name, 1)
        elif k == CANCEL:
            if self.row == 0 and self.name and self.typed:
                self.name = self.name[:-1]
            else:
                self.close()

    def text_input(self, s):
        if self.row != 0:
            return False
        if s == "\b":
            self.name = self.name[:-1]
            self.typed = True
            return True
        if s.isprintable() and (s.isalnum() or s in " -'") and len(s) == 1:
            if not self.typed:
                self.name = ""
                self.typed = True
            if len(self.name) < 10:
                self.name += s
                self.game.sfx("key")
            return True
        return False

    def row_rect(self, i):
        return (14, 30 + i * 18, 170, 16)

    def mouse(self, x, y, kind):
        if kind != "press":
            return
        for i, name in enumerate(self.rows):
            rx, ry, rw, rh = self.row_rect(i)
            if ui.inside((x, y), (rx, ry, rw, rh)):
                self.row = i
                if name.startswith("✔"):
                    self.finish()
                elif name.startswith("◀"):
                    self.close()
                elif x < rx + 80 + 14:
                    self.change(name, -1)
                else:
                    self.change(name, 1)
                return

    def finish(self):
        name = self.name.strip() or random.choice(data.RANDOM_NAMES)
        self.game.sfx("tada")
        self.game.create_profile(self.slot, name, self.cls(), self.look())
        self.close()
        self.game.begin(self.purpose, self.slot, new=True)

    def draw_world(self, p):
        g = QLinearGradient(0, 0, 0, LH)
        g.setColorAt(0, QColor("#2E3A87"))
        g.setColorAt(1, QColor("#7A5AB8"))
        p.fillRect(0, 0, LW, LH, g)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 30))
        p.drawEllipse(QPointF(252, 118), 52, 16)
        hero = data.new_hero(self.name, self.cls(), self.look())
        fr = sprites.hero_frames(data.look_of(hero))
        dirs = ["down", "left", "up", "right"]
        d = dirs[int(self.t / 1.6) % 4]
        fi = (0, 1, 0, 2)[int(self.t * 6) % 4]
        draw_sprite(p, fr[(d, fi)], 222, 34, 3.0)

    def draw_ui(self, p):
        ui.text(p, 12, 6, "Buat Karakter", 12, ui.YELLOW)
        ui.window(p, 8, 26, 182, 208)
        for i, name in enumerate(self.rows):
            x, y, w, h = self.row_rect(i)
            active = i == self.row
            if name in self.ROWS:
                ui.text(p, x + 10, y + 2, name, 7, ui.GREY)
                val = self.value_text(name)
                ui.text(p, x + 80, y + 1, "◀", 8, ui.WHITE if active else ui.GREY)
                ui.text(p, x + 94, y + 1, val, 8, ui.WHITE if active else ui.GREY)
                ui.text(p, x + w - 2, y + 1, "▶", 8, ui.WHITE if active else ui.GREY,
                        align=Qt.AlignRight)
                if name == "Warna Rambut":
                    p.setBrush(QColor(data.HAIR_COLORS[self.vals[name]][1]))
                    p.setPen(QPen(ui.WHITE, 0.6))
                    p.drawEllipse(QPointF(x + 72, y + 8), 3, 3)
                elif name == "Warna Baju":
                    p.setBrush(QColor(data.OUTFIT_COLORS[self.vals[name]][1]))
                    p.setPen(QPen(ui.WHITE, 0.6))
                    p.drawEllipse(QPointF(x + 72, y + 8), 3, 3)
                elif name == "Kulit":
                    p.setBrush(QColor(data.SKINS[self.vals[name]]))
                    p.setPen(QPen(ui.WHITE, 0.6))
                    p.drawEllipse(QPointF(x + 72, y + 8), 3, 3)
            else:
                ui.button(p, x + 8, y, w - 16, h, name, 8, active)
            if active:
                ui.cursor(p, x + 8, y + 8, self.t)
        cls = data.CLASSES[self.cls()]
        ui.window(p, 196, 132, 118, 102)
        ui.text(p, 202, 135, f"{cls['icon']} {cls['name']}", 9, ui.YELLOW)
        ui.paragraph(p, 202, 150, 108, cls["desc"], 7)
        b = cls["base"]
        ui.text(p, 202, 184, f"HP {b['hp']}   MP {b['mp']}", 7)
        ui.text(p, 202, 195, f"Serang {b['atk']}  Sihir {b['mag']}", 7)
        ui.text(p, 202, 206, f"Tahan {b['dfn']}  Cepat {b['spd']}", 7)
        ui.text(p, 202, 218, f"Senjata: {data.WEAPON_TYPE_NAMES[cls['weapon']]}", 7, ui.GREY)
        if self.row == 0:
            ui.text(p, 252, 120, "Ketik nama • ◀▶ = acak", 6, ui.WHITE, align=Qt.AlignHCenter)


# ---------------------------------------------------------------------------
# LOBI
# ---------------------------------------------------------------------------

class LobbyBrowserScene(ui.Scene):
    covers_world = True

    def __init__(self, game):
        super().__init__(game)
        self.lobbies = []
        self.menu = ui.ListMenu([], 30, 64, 260, row_h=18, size=8, visible=6)
        self._rebuild()

    def _rebuild(self):
        items = []
        for lb in self.lobbies:
            items.append((f"🏰 {lb['name']}", f"{lb.get('players', 1)}/{lb.get('max', 4)} • "
                                                f"{lb['ip']}"))
        items.append("✏️ Ketik alamat IP tuan rumah")
        items.append("◀ Kembali")
        self.menu.set_items(items)

    def update(self, dt):
        super().update(dt)
        lobbies = self.game.find_lobbies()
        keys = [(lb["ip"], lb.get("port"), lb.get("players")) for lb in lobbies]
        if keys != [(lb["ip"], lb.get("port"), lb.get("players")) for lb in self.lobbies]:
            self.lobbies = lobbies
            self._rebuild()

    def choose(self, i):
        self.game.sfx("pop")
        if i < len(self.lobbies):
            lb = self.lobbies[i]
            self.game.connect(lb["ip"], lb.get("port"))
        elif i == len(self.lobbies):
            self.game.push(IPEntryScene(self.game))
        else:
            self.game.stop_finder()
            self.close()

    def key(self, k):
        r = self.menu.key(k)
        if r == "ok":
            self.choose(self.menu.index)
        elif r == "cancel":
            self.game.stop_finder()
            self.close()
        elif r == "move":
            self.game.sfx("key")

    def mouse(self, x, y, kind):
        if kind == "press" and self.menu.mouse((x, y)) == "ok":
            self.choose(self.menu.index)

    def draw_world(self, p):
        g = QLinearGradient(0, 0, 0, LH)
        g.setColorAt(0, QColor("#1F3A5A"))
        g.setColorAt(1, QColor("#3E7BE0"))
        p.fillRect(0, 0, LW, LH, g)

    def draw_ui(self, p):
        ui.window(p, 20, 14, 280, 212)
        ui.text(p, LW / 2, 20, "🤝 Gabung Lobi Teman", 11, ui.YELLOW, align=Qt.AlignHCenter)
        dots = "." * (1 + int(self.t * 2) % 3)
        msg = (f"Mencari lobi di jaringan{dots}" if not self.lobbies
               else "Pilih lobi temanmu:")
        ui.text(p, LW / 2, 40, msg, 8, ui.WHITE, align=Qt.AlignHCenter)
        self.menu.draw(p, self.t)
        ui.paragraph(p, 32, 180, 256, "Temanmu harus memilih 'Buat Lobi' dulu. Komputer "
                     "kalian harus tersambung ke Wi-Fi/router yang sama.", 6, ui.GREY)


class IPEntryScene(ui.Scene):
    KEYS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", ".", "0", "⌫"]

    def __init__(self, game):
        super().__init__(game)
        self.ip = self.game.settings.get("last_ip", "192.168.1.")
        self.sel = 0

    def text_input(self, s):
        if s == "\b":
            self.ip = self.ip[:-1]
        elif s in "0123456789." and len(s) == 1 and len(self.ip) < 15:
            self.ip += s
        else:
            return False
        self.game.sfx("key")
        return True

    def key(self, k):
        if k == OK:
            self.submit()
        elif k == CANCEL:
            self.close()

    def submit(self):
        ip = self.ip.strip()
        if ip.count(".") != 3:
            self.game.sfx("wrong")
            return
        self.game.settings["last_ip"] = ip
        self.game.save_settings()
        self.close()
        self.game.connect(ip, None)

    def key_rect(self, i):
        r, c = divmod(i, 3)
        return (112 + c * 34, 100 + r * 22, 30, 19)

    def mouse(self, x, y, kind):
        if kind != "press":
            return
        for i, kname in enumerate(self.KEYS):
            if ui.inside((x, y), self.key_rect(i)):
                self.text_input("\b" if kname == "⌫" else kname)
                return
        if ui.inside((x, y), (112, 190, 64, 18)):
            self.submit()
        elif ui.inside((x, y), (180, 190, 30, 18)):
            self.close()

    def draw_ui(self, p):
        ui.window(p, 90, 40, 140, 176)
        ui.text(p, LW / 2, 46, "Alamat IP tuan rumah", 8, ui.YELLOW, align=Qt.AlignHCenter)
        ui.window(p, 102, 64, 116, 20, color=(QColor("#FFFFFF"), QColor("#E8E8F8")))
        ui.text(p, LW / 2, 67, self.ip + ("▏" if int(self.t * 2) % 2 else ""), 9, ui.DARK,
                align=Qt.AlignHCenter, shadow=False)
        for i, kname in enumerate(self.KEYS):
            ui.button(p, *self.key_rect(i), kname, 9)
        ui.button(p, 112, 190, 64, 18, "Sambung", 8, True)
        ui.button(p, 180, 190, 30, 18, "◀", 8)


class ConnectingScene(ui.Scene):
    def __init__(self, game, where):
        super().__init__(game)
        self.where = where

    def key(self, k):
        if k == CANCEL:
            self.game.cancel_connect()

    def draw_ui(self, p):
        ui.window(p, 60, 96, 200, 44)
        dots = "." * (1 + int(self.t * 3) % 3)
        ui.text(p, LW / 2, 102, f"Menyambung ke {self.where}{dots}", 8, ui.WHITE,
                align=Qt.AlignHCenter)
        ui.text(p, LW / 2, 120, "Esc = batal", 6, ui.GREY, align=Qt.AlignHCenter)


class MessageScene(ui.Scene):
    """Pesan penting yang harus ditutup (mis. koneksi terputus)."""

    def __init__(self, game, msg, then=None):
        super().__init__(game)
        self.msg = msg
        self.then = then

    def key(self, k):
        if k in (OK, CANCEL) and self.t > 0.3:
            self.done()

    def mouse(self, x, y, kind):
        if kind == "press" and self.t > 0.3:
            self.done()

    def done(self):
        self.close()
        if self.then:
            self.then()

    def draw_ui(self, p):
        lines = ui.wrap(self.msg, 8, 180)
        h = 30 + len(lines) * 11
        ui.window(p, 60, LH / 2 - h / 2, 200, h)
        ui.paragraph(p, 70, LH / 2 - h / 2 + 6, 180, self.msg, 8)
        ui.text(p, LW / 2, LH / 2 + h / 2 - 14, "OK", 8, ui.YELLOW, align=Qt.AlignHCenter)


# ---------------------------------------------------------------------------
# DIALOG & CERITA
# ---------------------------------------------------------------------------

class DialogScene(ui.Scene):
    CPS = 45

    def __init__(self, game, lines, then=None):
        """lines: [(nama, teks, potret_pixmap_atau_None)]"""
        super().__init__(game)
        self.lines = lines
        self.i = 0
        self.shown = 0.0
        self.then = then
        self._start_line()

    def _start_line(self):
        self.shown = 0.0
        speaker, txt, _ = self.lines[self.i]
        self.game.speak(txt)

    def update(self, dt):
        super().update(dt)
        self.shown += dt * self.CPS

    def advance(self):
        txt = self.lines[self.i][1]
        if self.shown < len(txt):
            self.shown = len(txt)
            return
        self.i += 1
        self.game.sfx("key")
        if self.i >= len(self.lines):
            self.game.stop_speech()
            self.close()
            if self.then:
                self.then()
            return
        self._start_line()

    def key(self, k):
        if k in (OK, CANCEL):
            self.advance()

    def mouse(self, x, y, kind):
        if kind == "press":
            self.advance()

    def draw_ui(self, p):
        speaker, txt, portrait = self.lines[self.i]
        y0 = LH - 68
        ui.window(p, 6, y0, LW - 12, 62)
        tx = 14
        if portrait is not None:
            ui.window(p, 12, y0 + 8, 42, 42, color=(QColor("#FFF6E5"), QColor("#E9D8C0")))
            draw_sprite(p, portrait, 13, y0 + 9, 2.5)
            tx = 60
        if speaker:
            ui.text(p, tx, y0 + 4, speaker, 8, ui.YELLOW)
        shown = txt[:int(self.shown)]
        ui.paragraph(p, tx, y0 + (17 if speaker else 8), LW - tx - 20, shown, 8)
        if self.shown >= len(txt) and int(self.t * 3) % 2:
            ui.text(p, LW - 18, y0 + 48, "▼", 7, ui.WHITE)


class StoryScene(ui.Scene):
    """Halaman-halaman cerita (prolog / tamat)."""

    covers_world = True

    def __init__(self, game, pages, then=None, ending=False):
        super().__init__(game)
        self.pages = pages
        self.i = 0
        self.shown = 0.0
        self.then = then
        self.ending = ending
        game.speak(pages[0])
        game.music("rpg_tamat" if ending else "rpg_cerita")

    def update(self, dt):
        super().update(dt)
        self.shown += dt * 38

    def advance(self):
        if self.shown < len(self.pages[self.i]):
            self.shown = len(self.pages[self.i])
            return
        self.i += 1
        self.shown = 0.0
        if self.i >= len(self.pages):
            self.game.stop_speech()
            self.close()
            if self.then:
                self.then()
            return
        self.game.sfx("page")
        self.game.speak(self.pages[self.i])

    def key(self, k):
        if k in (OK, CANCEL):
            self.advance()

    def mouse(self, x, y, kind):
        if kind == "press":
            self.advance()

    def draw_world(self, p):
        g = QLinearGradient(0, 0, 0, LH)
        if self.ending:
            g.setColorAt(0, QColor("#6EC0FF"))
            g.setColorAt(1, QColor("#FFE6F4"))
        else:
            g.setColorAt(0, QColor("#0E0A24"))
            g.setColorAt(1, QColor("#3A2466"))
        p.fillRect(0, 0, LW, LH, g)
        # kristal di tengah
        k = self.i / max(1, len(self.pages) - 1)
        cx, cy = LW / 2, 84
        glow = 30 + 6 * math.sin(self.t * 2)
        rg = QRadialGradient(QPointF(cx, cy), glow)
        rg.setColorAt(0, QColor(255, 255, 255, 180))
        rg.setColorAt(1, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(rg)
        p.drawEllipse(QPointF(cx, cy), glow, glow)
        broken = not self.ending and 1 <= self.i <= 3
        parts = [(-1, sprites.RAINBOW[3]), (0, sprites.RAINBOW[4]), (1, sprites.RAINBOW[0])]
        for off, col in parts:
            dx = off * (14 * min(1.0, self.t) if broken else 0)
            p.setBrush(QColor(col))
            w = 8
            p.drawPolygon(QPolygonF([QPointF(cx + off * w + dx, cy - 22), QPointF(cx + off * w + w + dx, cy),
                                     QPointF(cx + off * w + dx, cy + 22),
                                     QPointF(cx + off * w - w + dx, cy)]))
        if self.ending:
            for i, c in enumerate(sprites.RAINBOW):
                col = QColor(c)
                col.setAlpha(170)
                p.setPen(QPen(col, 5))
                p.setBrush(Qt.NoBrush)
                r = 180 - i * 5
                p.drawArc(QRectF(LW / 2 - r, 180 - r, 2 * r, 2 * r), 0, 180 * 16)

    def draw_ui(self, p):
        txt = self.pages[self.i]
        ui.window(p, 20, 140, LW - 40, 80, alpha=210)
        ui.paragraph(p, 30, 148, LW - 60, txt[:int(self.shown)], 9)
        ui.text(p, LW - 26, 206, f"{self.i + 1}/{len(self.pages)} ▶", 7, ui.GREY,
                align=Qt.AlignRight)


# ---------------------------------------------------------------------------
# MENU JEDA
# ---------------------------------------------------------------------------

class MenuScene(ui.Scene):
    ITEMS = ["📊 Status", "🎒 Barang", "🗡️ Perlengkapan", "💾 Simpan", "⚙️ Pengaturan",
             "🚪 Keluar"]

    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu(self.ITEMS, 10, 14, 96, row_h=17, size=8)
        game.sfx("open")

    def key(self, k):
        r = self.menu.key(k)
        if r == "ok":
            self.choose(self.menu.index)
        elif r in ("cancel",):
            self.close()
        elif r == "move":
            self.game.sfx("key")
        if k == MENU:
            self.close()

    def mouse(self, x, y, kind):
        if kind != "press":
            return
        r = self.menu.mouse((x, y))
        if r == "ok":
            self.choose(self.menu.index)
        elif not ui.inside((x, y), (4, 8, 312, 226)):
            self.close()

    def choose(self, i):
        self.game.sfx("pop")
        g = self.game
        if i == 0:
            g.push(StatusScene(g))
        elif i == 1:
            g.push(ItemScene(g))
        elif i == 2:
            g.push(EquipScene(g))
        elif i == 3:
            if g.in_battle():
                return
            g.save_all()
            g.toast("💾 Tersimpan!")
        elif i == 4:
            g.push(SettingsScene(g))
        else:
            g.push(QuitScene(g))

    def draw_ui(self, p):
        ui.window(p, 4, 8, 108, 112)
        self.menu.draw(p, self.t)
        g = self.game
        hero = g.hero
        st = data.derive_stats(hero)
        cls = data.CLASSES[hero["cls"]]
        ui.window(p, 116, 8, 200, 112)
        fr = sprites.hero_frames(data.look_of(hero))
        draw_sprite(p, fr[("down", (0, 1, 0, 2)[int(self.t * 4) % 4])], 122, 16, 2.4)
        ui.text(p, 176, 14, hero["name"], 11, ui.YELLOW)
        ui.text(p, 176, 32, f"{cls['icon']} {cls['name']}  •  Level {hero['level']}", 8)
        ui.text(p, 176, 48, f"HP {hero['hp']}/{st['hp']}", 8)
        ui.bar(p, 176, 61, 130, 4, hero["hp"] / max(1, st["hp"]), ui.GREEN)
        ui.text(p, 176, 67, f"MP {hero['mp']}/{st['mp']}", 8)
        ui.bar(p, 176, 80, 130, 4, hero["mp"] / max(1, st["mp"]), ui.BLUE)
        need = data.exp_to_next(hero["level"])
        ui.text(p, 176, 86, f"EXP {hero['exp']}/{need}", 7, ui.GREY)
        ui.bar(p, 176, 98, 130, 3, hero["exp"] / max(1, need), ui.YELLOW)
        ui.text(p, 176, 103, f"🪙 {hero['gold']}", 8, ui.YELLOW)
        where = data.MAPS[g.world.map.id]["name"] if g.world.map else ""
        ui.text(p, 310, 103, where, 6, ui.GREY, align=Qt.AlignRight)
        # pecahan
        ui.window(p, 4, 124, 312, 42)
        ui.text(p, 12, 128, "Pecahan Kristal:", 8, ui.WHITE)
        for i, (flag, name, col) in enumerate((("pecahan_hijau", "Hijau", "#5CD66A"),
                                               ("pecahan_biru", "Biru", "#4DB4FF"),
                                               ("tamat", "Merah", "#FF5A5A"))):
            have = flag in g.flags
            x = 110 + i * 66
            p.setPen(QPen(ui.WHITE, 0.6))
            p.setBrush(QColor(col) if have else QColor(60, 60, 90))
            p.drawPolygon(QPolygonF([QPointF(x, 128), QPointF(x + 6, 136), QPointF(x, 144),
                                     QPointF(x - 6, 136)]))
            ui.text(p, x + 10, 131, name, 8, ui.WHITE if have else ui.GREY)
        ui.text(p, 12, 150, g.quest_hint(), 7, ui.YELLOW)
        ui.window(p, 4, 170, 312, 64)
        ui.paragraph(p, 12, 175, 296, "Kontrol: Panah/WASD = jalan • Enter/Spasi/Z = bicara & "
                     "OK • Esc/X = menu & kembali • Angka 1-6 = sapa teman. Mouse: tahan klik "
                     "untuk berjalan, klik orang/peti di sebelahmu untuk bicara/membuka.", 7,
                     ui.GREY)


class StatusScene(ui.Scene):
    def key(self, k):
        if k in (OK, CANCEL, MENU):
            self.close()

    def mouse(self, x, y, kind):
        if kind == "press":
            self.close()

    def draw_ui(self, p):
        hero = self.game.hero
        st = data.derive_stats(hero)
        cls = data.CLASSES[hero["cls"]]
        ui.window(p, 4, 4, 312, 232)
        fr = sprites.hero_frames(data.look_of(hero))
        draw_sprite(p, fr[("down", 0)], 14, 14, 3.0)
        ui.text(p, 82, 10, f"{hero['name']}", 12, ui.YELLOW)
        ui.text(p, 82, 30, f"{cls['icon']} {cls['name']} • Level {hero['level']}", 8)
        rows = [("HP", f"{hero['hp']}/{st['hp']}"), ("MP", f"{hero['mp']}/{st['mp']}"),
                ("Serang", st["atk"]), ("Tahan", st["dfn"]), ("Sihir", st["mag"]),
                ("Cepat", st["spd"])]
        for i, (k, v) in enumerate(rows):
            x = 82 + (i % 2) * 110
            y = 46 + (i // 2) * 13
            ui.text(p, x, y, k, 8, ui.GREY)
            ui.text(p, x + 100, y, str(v), 8, ui.WHITE, align=Qt.AlignRight)
        y = 90
        ui.text(p, 14, y, "Perlengkapan", 8, ui.YELLOW)
        for slot in ("weapon", "armor", "acc"):
            y += 12
            item = hero["equip"].get(slot)
            ui.text(p, 20, y, data.SLOT_NAMES[slot], 7, ui.GREY)
            ui.text(p, 80, y, data.item_name(item) if item else "-", 7)
        y += 16
        ui.text(p, 14, y, "Jurus", 8, ui.YELLOW)
        for lv, s in cls["skills"]:
            y += 11
            sk = data.SKILLS[s]
            have = hero["level"] >= lv
            ui.text(p, 20, y, f"{sk['name']}", 7, ui.WHITE if have else ui.GREY)
            ui.text(p, 150, y, f"{sk['mp']} MP", 7, ui.BLUE if have else ui.GREY)
            ui.text(p, 200, y, "✔" if have else f"Level {lv}", 7,
                    ui.GREEN if have else ui.GREY)
        ui.text(p, LW / 2, 222, "OK / Esc = kembali", 6, ui.GREY, align=Qt.AlignHCenter)


class ItemScene(ui.Scene):
    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu([], 12, 30, 190, row_h=14, size=8, visible=11)
        self.refresh()

    def refresh(self):
        hero = self.game.hero
        self.ids = [i for i in data.ITEM_ORDER if hero["items"].get(i, 0) > 0]
        self.menu.set_items([(f"{data.ITEMS[i]['icon']} {data.ITEMS[i]['name']}",
                              f"×{hero['items'][i]}") for i in self.ids])

    def use(self):
        if not self.ids:
            return
        iid = self.ids[self.menu.index]
        if self.game.use_item_field(iid):
            self.refresh()

    def key(self, k):
        r = self.menu.key(k)
        if r == "ok":
            self.use()
        elif r == "cancel":
            self.close()
        elif r == "move":
            self.game.sfx("key")

    def mouse(self, x, y, kind):
        if kind != "press":
            return
        r = self.menu.mouse((x, y))
        if r == "ok":
            self.use()
        elif r is None and not ui.inside((x, y), (4, 4, 312, 232)):
            self.close()

    def draw_ui(self, p):
        hero = self.game.hero
        st = data.derive_stats(hero)
        ui.window(p, 4, 4, 204, 232)
        ui.text(p, 12, 10, "🎒 Barang", 10, ui.YELLOW)
        self.menu.draw(p, self.t)
        if not self.ids:
            ui.text(p, 20, 34, "Tas kosong. Beli ramuan di toko!", 8, ui.GREY)
        ui.window(p, 212, 4, 104, 232)
        ui.text(p, 218, 10, f"HP {hero['hp']}/{st['hp']}", 8)
        ui.text(p, 218, 24, f"MP {hero['mp']}/{st['mp']}", 8)
        if self.ids:
            it = data.ITEMS[self.ids[self.menu.index]]
            ui.paragraph(p, 218, 44, 92, it["desc"], 7)
            ui.paragraph(p, 218, 90, 92, "OK = pakai" if it["kind"] != "revive"
                         else "Dipakai saat bertarung.", 7, ui.GREY)


class EquipScene(ui.Scene):
    def __init__(self, game):
        super().__init__(game)
        self.slots = ["weapon", "armor", "acc"]
        self.slot_menu = ui.ListMenu([], 12, 30, 190, row_h=16, size=8)
        self.pick = None
        self.pick_menu = None
        self.refresh()

    def refresh(self):
        hero = self.game.hero
        self.slot_menu.set_items([(data.SLOT_NAMES[s], data.item_name(hero["equip"][s])
                                   if hero["equip"].get(s) else "-") for s in self.slots])

    def candidates(self, slot):
        hero = self.game.hero
        out = []
        seen = set()
        for it in hero["gear"]:
            if it in seen:
                continue
            seen.add(it)
            if data.EQUIPMENT[it]["slot"] == slot:
                out.append(it)
        if slot == "acc" and hero["equip"].get("acc"):
            out.append(None)
        return out

    def open_pick(self):
        slot = self.slots[self.slot_menu.index]
        cands = self.candidates(slot)
        if not cands:
            self.game.sfx("wrong")
            self.game.toast("Belum punya perlengkapan lain untuk slot ini.")
            return
        hero = self.game.hero
        self.pick = cands
        self.pick_menu = ui.ListMenu(
            [("(Lepas)" if c is None else data.item_name(c)) for c in cands], 12, 96, 190,
            row_h=14, size=8, visible=9,
            enabled=lambda i: cands[i] is None or data.can_equip(hero["cls"], cands[i]))

    def equip(self, i):
        item = self.pick[i]
        slot = self.slots[self.slot_menu.index]
        hero = self.game.hero
        old = hero["equip"].get(slot)
        if item is not None:
            hero["gear"].remove(item)
        if old:
            hero["gear"].append(old)
        hero["equip"][slot] = item
        data.clamp_hero(hero)
        self.game.sfx("buff")
        self.game.hero_changed()
        self.pick = None
        self.pick_menu = None
        self.refresh()

    def key(self, k):
        if self.pick_menu:
            r = self.pick_menu.key(k)
            if r == "ok":
                self.equip(self.pick_menu.index)
            elif r == "cancel":
                self.pick_menu = None
            elif r == "bad":
                self.game.sfx("wrong")
                self.game.toast("Kelasmu tidak bisa memakai ini.")
            elif r == "move":
                self.game.sfx("key")
            return
        r = self.slot_menu.key(k)
        if r == "ok":
            self.open_pick()
        elif r == "cancel":
            self.close()
        elif r == "move":
            self.game.sfx("key")

    def mouse(self, x, y, kind):
        if kind != "press":
            return
        if self.pick_menu:
            r = self.pick_menu.mouse((x, y))
            if r == "ok":
                self.equip(self.pick_menu.index)
            elif r is None:
                self.pick_menu = None
            return
        r = self.slot_menu.mouse((x, y))
        if r == "ok":
            self.open_pick()
        elif r is None and not ui.inside((x, y), (4, 4, 312, 232)):
            self.close()

    def draw_ui(self, p):
        hero = self.game.hero
        ui.window(p, 4, 4, 204, 232)
        ui.text(p, 12, 10, "🗡️ Perlengkapan", 10, ui.YELLOW)
        self.slot_menu.draw(p, self.t, focus=self.pick_menu is None)
        preview = None
        if self.pick_menu:
            ui.text(p, 12, 84, "Pilih:", 8, ui.GREY)
            self.pick_menu.draw(p, self.t)
            preview = self.pick[self.pick_menu.index]
        ui.window(p, 212, 4, 104, 232)
        before = data.derive_stats(hero)
        after = before
        look_hero = hero
        if self.pick_menu:
            slot = self.slots[self.slot_menu.index]
            tmp = {**hero, "equip": dict(hero["equip"])}
            tmp["equip"][slot] = preview
            if preview is None or data.can_equip(hero["cls"], preview):
                after = data.derive_stats(tmp)
                look_hero = tmp
        fr = sprites.hero_frames(data.look_of(look_hero))
        draw_sprite(p, fr[("down", (0, 1, 0, 2)[int(self.t * 4) % 4])], 240, 10, 2.2)
        y = 76
        for k, label in (("hp", "HP"), ("mp", "MP"), ("atk", "Serang"), ("dfn", "Tahan"),
                         ("mag", "Sihir"), ("spd", "Cepat")):
            b, a = before[k], after[k]
            ui.text(p, 218, y, label, 7, ui.GREY)
            color = ui.GREEN if a > b else ui.RED if a < b else ui.WHITE
            ui.text(p, 310, y, f"{a}" + (f" ({a - b:+d})" if a != b else ""), 7, color,
                    align=Qt.AlignRight)
            y += 12
        if self.pick_menu and preview:
            eq = data.EQUIPMENT[preview]
            ok = data.can_equip(hero["cls"], preview)
            ui.paragraph(p, 218, 156, 92, "Bisa dipakai ✔" if ok else "Tidak cocok dengan "
                         "kelasmu ✘", 7, ui.GREEN if ok else ui.RED)


class SettingsScene(ui.Scene):
    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu([], 70, 70, 180, row_h=18, size=8)
        self.refresh()

    def refresh(self):
        s = self.game.settings
        on = lambda v: "Nyala ✔" if v else "Mati"
        self.menu.set_items([("🎵 Musik", on(s.get("music", True))),
                             ("🔔 Efek suara", on(s.get("effects", True))),
                             ("🗣️ Bacakan dialog", on(s.get("tts", True))),
                             "◀ Kembali"])

    def toggle(self, i):
        s = self.game.settings
        key = ["music", "effects", "tts"][i] if i < 3 else None
        if key is None:
            self.close()
            return
        s[key] = not s.get(key, True)
        self.game.apply_settings()
        self.game.save_settings()
        self.refresh()
        self.game.sfx("pop")

    def key(self, k):
        r = self.menu.key(k)
        if r == "ok":
            self.toggle(self.menu.index)
        elif r == "cancel":
            self.close()

    def mouse(self, x, y, kind):
        if kind == "press" and self.menu.mouse((x, y)) == "ok":
            self.toggle(self.menu.index)

    def draw_ui(self, p):
        ui.window(p, 60, 50, 200, 100)
        ui.text(p, LW / 2, 54, "⚙️ Pengaturan", 9, ui.YELLOW, align=Qt.AlignHCenter)
        self.menu.draw(p, self.t)


class QuitScene(ui.Scene):
    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu(["🏠 Kembali ke Layar Judul", "🚪 Keluar Permainan",
                                 "◀ Batal"], 70, 84, 180, row_h=18, size=8)

    def choose(self, i):
        if i == 0:
            self.game.leave_to_title()
        elif i == 1:
            self.game.exit_game()
        else:
            self.close()

    def key(self, k):
        r = self.menu.key(k)
        if r == "ok":
            self.choose(self.menu.index)
        elif r == "cancel":
            self.close()

    def mouse(self, x, y, kind):
        if kind == "press" and self.menu.mouse((x, y)) == "ok":
            self.choose(self.menu.index)

    def draw_ui(self, p):
        ui.window(p, 60, 60, 200, 96)
        ui.text(p, LW / 2, 64, "Keluar? (otomatis disimpan)", 8, ui.YELLOW,
                align=Qt.AlignHCenter)
        self.menu.draw(p, self.t)


# ---------------------------------------------------------------------------
# TOKO, GANTI KELAS, PAPAN PESTA, SAPA
# ---------------------------------------------------------------------------

class ShopScene(ui.Scene):
    def __init__(self, game, shop):
        super().__init__(game)
        self.shop = shop
        self.mode = "beli"
        self.menu = ui.ListMenu([], 12, 42, 196, row_h=14, size=8, visible=12)
        self.refresh()

    def refresh(self):
        hero = self.game.hero
        if self.mode == "beli":
            self.ids = data.shop_stock(self.shop, self.game.flags)
            rows = []
            for i in self.ids:
                price = (data.ITEMS.get(i) or data.EQUIPMENT.get(i))["price"]
                rows.append((data.item_name(i), f"{price} 🪙"))
        else:
            self.ids = [i for i in data.ITEM_ORDER if hero["items"].get(i, 0) > 0]
            self.ids += sorted(set(hero["gear"]), key=data.item_name)
            rows = []
            for i in self.ids:
                rows.append((data.item_name(i), f"{self.sell_price(i)} 🪙"))
        self.menu.set_items(rows)

    def sell_price(self, i):
        price = (data.ITEMS.get(i) or data.EQUIPMENT.get(i))["price"]
        return max(1, price // 2)

    def act(self):
        if not self.ids:
            return
        i = self.ids[self.menu.index]
        hero = self.game.hero
        if self.mode == "beli":
            price = (data.ITEMS.get(i) or data.EQUIPMENT.get(i))["price"]
            if hero["gold"] < price:
                self.game.sfx("wrong")
                self.game.toast("Uangnya belum cukup.")
                return
            hero["gold"] -= price
            if i in data.ITEMS:
                hero["items"][i] = hero["items"].get(i, 0) + 1
            else:
                hero["gear"].append(i)
            self.game.sfx("star")
            self.game.toast(f"Membeli {data.item_name(i)}!")
        else:
            hero["gold"] += self.sell_price(i)
            if i in data.ITEMS:
                hero["items"][i] -= 1
                if hero["items"][i] <= 0:
                    del hero["items"][i]
            else:
                hero["gear"].remove(i)
            self.game.sfx("star")
        self.game.hero_changed()
        self.refresh()

    def key(self, k):
        if k in (LEFT, RIGHT):
            self.mode = "jual" if self.mode == "beli" else "beli"
            self.menu.index = 0
            self.refresh()
            self.game.sfx("key")
            return
        r = self.menu.key(k)
        if r == "ok":
            self.act()
        elif r == "cancel":
            self.close()
        elif r == "move":
            self.game.sfx("key")

    def mouse(self, x, y, kind):
        if kind != "press":
            return
        if ui.inside((x, y), (12, 24, 60, 14)):
            self.mode = "beli"
            self.refresh()
            return
        if ui.inside((x, y), (76, 24, 60, 14)):
            self.mode = "jual"
            self.refresh()
            return
        r = self.menu.mouse((x, y))
        if r == "ok":
            self.act()
        elif r is None and not ui.inside((x, y), (4, 4, 312, 232)):
            self.close()

    def wheel(self, delta):
        self.menu.wheel(delta)

    def draw_ui(self, p):
        hero = self.game.hero
        ui.window(p, 4, 4, 210, 232)
        ui.text(p, 12, 8, "🏪 Toko Serba Ada", 9, ui.YELLOW)
        ui.button(p, 12, 24, 60, 14, "Beli", 7, self.mode == "beli")
        ui.button(p, 76, 24, 60, 14, "Jual", 7, self.mode == "jual")
        ui.text(p, 206, 26, "◀▶ ganti", 6, ui.GREY, align=Qt.AlignRight)
        self.menu.draw(p, self.t)
        ui.window(p, 218, 4, 98, 232)
        ui.text(p, 224, 10, f"🪙 {hero['gold']}", 9, ui.YELLOW)
        if not self.ids:
            return
        i = self.ids[self.menu.index]
        y = 30
        if i in data.ITEMS:
            it = data.ITEMS[i]
            ui.text(p, 224, y, f"{it['icon']} Punya: {hero['items'].get(i, 0)}", 7)
            ui.paragraph(p, 224, y + 14, 88, it["desc"], 7)
        else:
            eq = data.EQUIPMENT[i]
            owned = hero["gear"].count(i) + list(hero["equip"].values()).count(i)
            ui.text(p, 224, y, f"Punya: {owned}", 7)
            y += 13
            names = {"atk": "Serang", "dfn": "Tahan", "mag": "Sihir", "spd": "Cepat",
                     "hp": "HP", "mp": "MP"}
            for k, v in eq["bonus"].items():
                ui.text(p, 224, y, f"{names[k]} +{v}", 7, ui.GREEN)
                y += 11
            ok = data.can_equip(hero["cls"], i)
            y += 4
            if eq["slot"] == "weapon":
                who = [c["name"] for c in data.CLASSES.values() if c["weapon"] == eq["type"]]
            elif eq["slot"] == "armor":
                who = [c["name"] for c in data.CLASSES.values() if eq["type"] in c["armor"]]
            else:
                who = ["Semua kelas"]
            ui.paragraph(p, 224, y, 88, "Untuk: " + ", ".join(who), 7,
                         ui.GREEN if ok else ui.RED)


class ClassScene(ui.Scene):
    def __init__(self, game):
        super().__init__(game)
        rows = []
        for cid in data.CLASS_ORDER:
            c = data.CLASSES[cid]
            rows.append((f"{c['icon']} {c['name']}", "sekarang" if cid == game.hero["cls"] else ""))
        rows.append("◀ Batal")
        self.menu = ui.ListMenu(rows, 20, 40, 150, row_h=18, size=8)
        self.menu.index = data.CLASS_ORDER.index(game.hero["cls"])

    def choose(self, i):
        if i >= len(data.CLASS_ORDER):
            self.close()
            return
        cid = data.CLASS_ORDER[i]
        if cid == self.game.hero["cls"]:
            self.close()
            return
        data.change_class(self.game.hero, cid)
        self.game.hero_changed()
        self.game.sfx("tada")
        self.game.toast(f"Sekarang kamu seorang {data.CLASSES[cid]['name']}!")
        self.close()

    def key(self, k):
        r = self.menu.key(k)
        if r == "ok":
            self.choose(self.menu.index)
        elif r == "cancel":
            self.close()
        elif r == "move":
            self.game.sfx("key")

    def mouse(self, x, y, kind):
        if kind == "press" and self.menu.mouse((x, y)) == "ok":
            self.choose(self.menu.index)

    def draw_ui(self, p):
        ui.window(p, 12, 16, 296, 150)
        ui.text(p, 20, 20, "🎓 Ganti Kelas", 10, ui.YELLOW)
        self.menu.draw(p, self.t)
        i = self.menu.index
        if i < len(data.CLASS_ORDER):
            c = data.CLASSES[data.CLASS_ORDER[i]]
            ui.paragraph(p, 180, 42, 120, c["desc"], 7)
            ui.text(p, 180, 90, f"Senjata: {data.WEAPON_TYPE_NAMES[c['weapon']]}", 7, ui.GREY)
            ui.paragraph(p, 180, 104, 120, "Perlengkapan yang tidak cocok akan dilepas "
                         "(tetap ada di tas).", 6, ui.GREY)


class BoardScene(ui.Scene):
    def key(self, k):
        if k in (OK, CANCEL, MENU):
            self.close()

    def mouse(self, x, y, kind):
        if kind == "press":
            self.close()

    def draw_ui(self, p):
        g = self.game
        ui.window(p, 20, 16, 280, 200, color=(QColor("#C8955C"), QColor("#8B5A2B")))
        ui.text(p, LW / 2, 20, "📋 Papan Pesta", 11, ui.WHITE, align=Qt.AlignHCenter)
        y = 42
        for pid in sorted(g.players):
            pl = g.players[pid]
            look = pl.get("look")
            if look:
                draw_sprite(p, sprites.hero_frames(look)["portrait"], 32, y - 2, 1.2)
            cls = data.CLASSES.get(pl.get("cls"), {})
            tag = " (kamu)" if pid == g.pid else (" (tuan rumah)" if pid == 0 else "")
            ui.text(p, 56, y, f"{pl.get('name', '?')}{tag}", 8, ui.YELLOW if pid == g.pid
                    else ui.WHITE)
            ui.text(p, 290, y, f"{cls.get('icon', '')} {cls.get('name', '')} Lv {pl.get('level', 1)}",
                    7, ui.WHITE, align=Qt.AlignRight)
            y += 22
        info = g.lobby_info()
        ui.paragraph(p, 32, 150, 256, info, 7)


class EmoteScene(ui.Scene):
    def __init__(self, game):
        super().__init__(game)
        self.menu = ui.ListMenu(data.EMOTES, LW - 118, 110, 110, row_h=14, size=8)

    def key(self, k):
        r = self.menu.key(k)
        if r == "ok":
            self.game.emote(self.menu.index)
            self.close()
        elif r == "cancel":
            self.close()

    def mouse(self, x, y, kind):
        if kind != "press":
            return
        if self.menu.mouse((x, y)) == "ok":
            self.game.emote(self.menu.index)
        self.close()

    def draw_ui(self, p):
        ui.window(p, LW - 122, 104, 116, 94)
        self.menu.draw(p, self.t)
