# -*- coding: utf-8 -*-
"""Peta dunia: render petak, kamera, gerak per petak, NPC, peti, pintu, dan HUD."""

import math
import random
from collections import deque

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QImage, QPainter, QPen

from . import data, sprites, ui
from .ui import LW, LH, DIRS, UP, DOWN, LEFT, RIGHT, OK, CANCEL, MENU

T = data.TILE
WALK_SPEED = 5.5          # petak per detik
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}

_tile_cache = {}


def _tile(name, floor, variant, frame=0):
    key = (name, floor, variant, frame)
    if key not in _tile_cache:
        _tile_cache[key] = sprites.tile_image(name, floor, variant, frame)
    return _tile_cache[key]


class WorldMap:
    def __init__(self, map_id):
        self.id = map_id
        self.cfg = data.MAPS[map_id]
        p = data.parse_map(map_id)
        self.grid = p["grid"]
        self.w, self.h = p["w"], p["h"]
        self.npcs = {(x, y): n for x, y, n in p["npcs"]}
        self.warps = p["warps"]
        self.chests = {(x, y): i for x, y, i in p["chests"]}
        self.springs = set(p["springs"])
        self.starts = p["starts"]
        self.floor_name = data.TILES[self.cfg["floor"]][0]
        self.anim = []
        self.image = QImage(self.w * T, self.h * T, QImage.Format_RGB32)
        painter = QPainter(self.image)
        for y, row in enumerate(self.grid):
            for x, ch in enumerate(row):
                name = data.TILES[ch][0]
                variant = (x * 7 + y * 13) % 3
                if name == "air_mancur":    # 2x2 petak = satu air mancur
                    variant = (1 if x > 0 and self.grid[y][x - 1] == ch else 0) +                               (2 if y > 0 and self.grid[y - 1][x] == ch else 0)
                if name in sprites.ANIMATED:
                    self.anim.append((x, y, name, variant))
                painter.drawImage(x * T, y * T, _tile(name, self.floor_name, variant))
        painter.end()

    # -- pertanyaan tentang petak -----------------------------------------
    def inside(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def tile_char(self, x, y):
        return self.grid[y][x] if self.inside(x, y) else "#"

    def solid_tile(self, x, y):
        if not self.inside(x, y):
            return True
        return data.TILES[self.grid[y][x]][1]

    def npc_visible(self, npc_id, flags):
        npc = data.NPCS.get(npc_id, {})
        if npc.get("hide_if") and npc["hide_if"] in flags:
            return False
        if npc.get("show_if") and npc["show_if"] not in flags:
            return False
        return True

    def npc_at(self, x, y, flags):
        n = self.npcs.get((x, y))
        if n and self.npc_visible(n, flags):
            return n
        return None

    def blocked(self, x, y, flags):
        return (self.solid_tile(x, y) or self.npc_at(x, y, flags) is not None
                or (x, y) in self.chests or (x, y) in self.springs)

    def warp_at(self, x, y):
        for wx, wy, wid in self.warps:
            if (wx, wy) == (x, y):
                return wid
        return None

    def warp_index(self, x, y):
        wid = self.warp_at(x, y)
        same = [(wx, wy) for wx, wy, i in self.warps if i == wid]
        return same.index((x, y)) if (x, y) in same else 0

    def in_zone(self, x, y):
        enc = self.cfg.get("encounters")
        return bool(enc) and self.grid[y][x] == enc["zone"]

    def free(self, x, y, flags):
        return not self.blocked(x, y, flags) and self.warp_at(x, y) is None

    def arrival(self, spawn_id, idx, d, flags):
        """Petak kedatangan lewat pintu spawn_id (lanjut satu langkah ke arah d)."""
        same = [(x, y) for x, y, i in self.warps if i == spawn_id]
        if not same:
            return self.start_point()
        wx, wy = same[min(idx, len(same) - 1)]
        dx, dy = DIRS.get(d, (0, 1))
        if self.free(wx + dx, wy + dy, flags):
            return wx + dx, wy + dy
        return self.nearest_free(wx, wy, flags)

    def start_point(self, marker="@"):
        if self.starts:
            return self.starts[0]
        wx, wy, _ = self.warps[0]
        return self.nearest_free(wx, wy, set())

    def nearest_free(self, x, y, flags, k=0):
        """Petak bebas ke-k terdekat dari (x, y) (menyebar pemain co-op)."""
        seen = {(x, y)}
        q = deque([(x, y)])
        found = []
        while q:
            cx, cy = q.popleft()
            if self.free(cx, cy, flags):
                found.append((cx, cy))
                if len(found) > k:
                    return found[k]
            for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1)):
                nx, ny = cx + dx, cy + dy
                if self.inside(nx, ny) and (nx, ny) not in seen and not self.solid_tile(nx, ny):
                    seen.add((nx, ny))
                    q.append((nx, ny))
        return found[-1] if found else (x, y)


def draw_npc(p, npc_id, px, py, facing, t):
    """Gambar NPC dengan kaki di dasar petak (px, py = pojok kiri-atas petak)."""
    npc = data.NPCS[npc_id]
    if "look" in npc:
        fr = sprites.hero_frames(npc["look"])[(facing, 0)]
        bob = 0
        p.drawPixmap(int(px - 2), int(py + T - sprites.CH + 1 + bob), fr)
        return
    art = npc.get("art")
    if art in sprites.MONSTER_ART:
        _fn, size = sprites.MONSTER_ART[art]
        color = data.ENEMIES.get(art, {}).get("art", (art, "#E8494F"))[1]
        pm = sprites.monster_frames(art, color)[int(t * 2) % 2]
        target = 30 if size > 32 else 22
        p.drawPixmap(QRectF(px + 8 - target / 2, py + T - target + 1, target, target), pm,
                     QRectF(pm.rect()))
    else:
        frames = sprites.prop_frames(art)
        pm = frames[int(t * 3) % 2] if art in ("fairy", "cat") else frames[0]
        p.drawPixmap(int(px), int(py + T - 20), pm)


class WorldScene(ui.Scene):
    covers_world = True
    modal = False

    def __init__(self, game):
        super().__init__(game)
        self.map = None
        self.x = self.y = 0
        self.fx = self.fy = 0
        self.d = DOWN
        self.prog = 0.0
        self.moving = False
        self.steps = 0
        self.banner = 0.0
        self.freeze = 0.0
        self.npc_face = {}
        self.mouse_hold = False
        self.anim_frame = 0
        self.walk_t = 0.0

    # -- memuat peta -------------------------------------------------------
    def load(self, map_id, pos, d=DOWN):
        if self.map is None or self.map.id != map_id:
            self.map = WorldMap(map_id)
            self.banner = 2.6
            self.npc_face = {}
        self.x, self.y = pos
        self.fx, self.fy = pos
        self.d = d
        self.moving = False
        self.prog = 0.0
        self.freeze = 0.25
        self.steps = 0
        me = self.game.me()
        me.update(x=self.x, y=self.y, d=self.d, px=self.x * T, py=self.y * T, m=0)
        self.game.music(self.map.cfg.get("music"))

    def on_top(self):
        if self.map is not None:
            self.game.music(self.map.cfg.get("music"))

    # -- gerak ---------------------------------------------------------------
    def wanted_dir(self):
        g = self.game
        if g.top() is not self:
            return None
        if g.held_order:
            return g.held_order[-1]          # arah yang terakhir ditekan
        if self.mouse_hold and g.mouse_pos:
            mx, my = g.mouse_pos
            cx, cy = self.camera()
            sx = self.x * T + 8 - cx
            sy = self.y * T + 8 - cy
            dx, dy = mx - sx, my - sy
            if abs(dx) < 7 and abs(dy) < 7:
                return None
            if abs(dx) > abs(dy):
                return RIGHT if dx > 0 else LEFT
            return DOWN if dy > 0 else UP
        return None

    def update(self, dt):
        super().update(dt)
        g = self.game
        self.banner = max(0.0, self.banner - dt)
        self.freeze = max(0.0, self.freeze - dt)
        for pid, pl in g.players.items():
            if pid == g.pid:
                continue
            tx, ty = pl["x"] * T, pl["y"] * T
            dist = math.hypot(tx - pl["px"], ty - pl["py"])
            if dist > T * 3:
                pl["px"], pl["py"] = tx, ty
            elif dist > 0.1:
                step = min(dist, WALK_SPEED * T * dt * (1.3 if dist > T else 1.0))
                pl["px"] += (tx - pl["px"]) / dist * step
                pl["py"] += (ty - pl["py"]) / dist * step
                pl["walk"] = pl.get("walk", 0) + dt
            else:
                pl["walk"] = 0
        if self.map is None:
            return
        me = g.me()
        if self.moving:
            self.prog += dt * WALK_SPEED
            self.walk_t += dt
            if self.prog >= 1.0:
                self.moving = False
                self.prog = 0.0
                self._arrived()
        if not self.moving and self.freeze <= 0 and not g.in_battle():
            d = self.wanted_dir()
            if d:
                self.d = d
                dx, dy = DIRS[d]
                nx, ny = self.x + dx, self.y + dy
                if not self.map.blocked(nx, ny, g.flags):
                    self.fx, self.fy = self.x, self.y
                    self.x, self.y = nx, ny
                    self.moving = True
                    self.prog = 0.0
                    g.send_pos(self.x, self.y, self.d, True)
                else:
                    me["d"] = d
                    self.walk_t = 0
            else:
                self.walk_t = 0
        t = self.prog if self.moving else 1.0
        me["px"] = (self.fx + (self.x - self.fx) * t) * T
        me["py"] = (self.fy + (self.y - self.fy) * t) * T
        me["x"], me["y"], me["d"] = self.x, self.y, self.d
        me["walk"] = self.walk_t

    def _arrived(self):
        g = self.game
        g.send_pos(self.x, self.y, self.d, False)
        wid = self.map.warp_at(self.x, self.y)
        if wid is not None:
            target = self.map.cfg["warps"].get(wid)
            if target:
                self.freeze = 3.0
                g.request({"t": "warp", "map": target[0], "spawn": target[1],
                           "idx": self.map.warp_index(self.x, self.y), "d": self.d})
            return
        if self.map.in_zone(self.x, self.y):
            self.steps += 1
            rate = self.map.cfg["encounters"]["rate"]
            if self.steps >= 5 and random.random() < 1.0 / rate:
                self.steps = 0
                g.request({"t": "encounter"})

    # -- aksi ----------------------------------------------------------------
    def facing_tile(self):
        dx, dy = DIRS[self.d]
        return self.x + dx, self.y + dy

    def interact(self):
        if self.moving or self.map is None:
            return
        g = self.game
        tx, ty = self.facing_tile()
        npc = self.map.npc_at(tx, ty, g.flags)
        if npc is None and self.map.tile_char(tx, ty) in data.COUNTERS:
            dx, dy = DIRS[self.d]
            npc = self.map.npc_at(tx + dx, ty + dy, g.flags)
            if npc:
                tx, ty = tx + dx, ty + dy
        if npc:
            self.npc_face[(tx, ty)] = OPPOSITE[self.d]
            g.talk(npc)
            return
        if (tx, ty) in self.map.chests:
            key = f"{self.map.id}:{self.map.chests[(tx, ty)]}"
            if key in g.chests:
                g.toast("Petinya sudah kosong.")
            else:
                g.request({"t": "chest", "id": key})
            return
        if (tx, ty) in self.map.springs:
            g.heal_full()
            g.sfx("heal")
            g.toast("💧 Mata air penyembuh! HP & MP pulih penuh.")

    def key(self, k):
        if k == OK:
            self.interact()
        elif k in (CANCEL, MENU):
            self.game.open_menu()

    def hud_buttons(self):
        return {"menu": (LW - 44, 4, 40, 16), "emote": (LW - 44, LH - 22, 40, 18),
                "act": (LW - 88, LH - 22, 40, 18)}

    def mouse(self, x, y, kind):
        if kind == "release":
            self.mouse_hold = False
            return
        if kind != "press":
            return
        b = self.hud_buttons()
        if ui.inside((x, y), b["menu"]):
            self.game.open_menu()
            return
        if ui.inside((x, y), b["emote"]):
            self.game.open_emotes()
            return
        if ui.inside((x, y), b["act"]):
            self.interact()
            return
        if self.map is None:
            return
        cx, cy = self.camera()
        tx, ty = int((x + cx) // T), int((y + cy) // T)
        if abs(tx - self.x) + abs(ty - self.y) == 1 and not self.moving:
            target = (tx, ty)
            if (self.map.npc_at(tx, ty, self.game.flags) or target in self.map.chests
                    or target in self.map.springs):
                for d, (dx, dy) in DIRS.items():
                    if (self.x + dx, self.y + dy) == target:
                        self.d = d
                self.interact()
                return
        self.mouse_hold = True

    # -- gambar --------------------------------------------------------------
    def camera(self):
        me = self.game.me()
        mw, mh = self.map.w * T, self.map.h * T
        if mw <= LW:
            cx = (mw - LW) / 2
        else:
            cx = max(0, min(mw - LW, me["px"] + 8 - LW / 2))
        if mh <= LH:
            cy = (mh - LH) / 2
        else:
            cy = max(0, min(mh - LH, me["py"] + 8 - LH / 2))
        return int(round(cx)), int(round(cy))

    def draw_world(self, p):
        p.fillRect(0, 0, LW, LH, QColor("#10101C"))
        if self.map is None:
            return
        g = self.game
        cx, cy = self.camera()
        m = self.map
        sx0, sy0 = max(0, cx), max(0, cy)
        sx1, sy1 = min(m.w * T, cx + LW), min(m.h * T, cy + LH)
        if sx1 > sx0 and sy1 > sy0:
            p.drawImage(QRectF(sx0 - cx, sy0 - cy, sx1 - sx0, sy1 - sy0), m.image,
                        QRectF(sx0, sy0, sx1 - sx0, sy1 - sy0))
        frame = int(self.t * 2) % 2
        for x, y, name, var in m.anim:
            px, py = x * T - cx, y * T - cy
            if -T < px < LW and -T < py < LH:
                p.drawImage(int(px), int(py), _tile(name, m.floor_name, var, frame))

        items = []
        for (x, y), i in m.chests.items():
            opened = f"{m.id}:{i}" in g.chests
            items.append((y * T, "chest", x * T - cx, y * T - cy, opened))
        for (x, y) in m.springs:
            items.append((y * T, "spring", x * T - cx, y * T - cy, None))
        for (x, y), n in m.npcs.items():
            if m.npc_visible(n, g.flags):
                face = self.npc_face.get((x, y), DOWN)
                items.append((y * T + 1, "npc", x * T - cx, y * T - cy, (n, face)))
        for pid, pl in g.players.items():
            if pl.get("map") not in (None, m.id) and pid != g.pid:
                continue
            items.append((pl["py"] + 2, "player", pl["px"] - cx, pl["py"] - cy, pid))
        items.sort(key=lambda it: it[0])

        shadow = QColor(0, 0, 0, 60)
        for _, kind, px, py, extra in items:
            if px < -32 or px > LW + 16 or py < -40 or py > LH + 16:
                continue
            if kind == "chest":
                p.drawPixmap(int(px), int(py), sprites.chest_pixmap(bool(extra)))
            elif kind == "spring":
                p.drawPixmap(int(px), int(py), sprites.spring_pixmap(int(self.t * 3) % 2))
            elif kind == "npc":
                p.setPen(Qt.NoPen)
                p.setBrush(shadow)
                p.drawEllipse(QRectF(px + 2, py + 12, 12, 5))
                draw_npc(p, extra[0], px, py, extra[1], self.t)
            else:
                pl = g.players[extra]
                look = pl.get("look")
                if not look:
                    continue
                p.setPen(Qt.NoPen)
                p.setBrush(shadow)
                p.drawEllipse(QRectF(px + 2, py + 12, 12, 5))
                walking = pl.get("walk", 0) > 0
                fi = (1 + int(pl.get("walk", 0) * 7) % 2) if walking else 0
                if walking and int(pl.get("walk", 0) * 7) % 4 in (1, 3):
                    fi = 0
                fr = sprites.hero_frames(look)[(pl.get("d", DOWN), fi)]
                p.drawPixmap(int(px - 2), int(py + T - sprites.CH + 1), fr)

    def draw_ui(self, p):
        if self.map is None:
            return
        g = self.game
        cx, cy = self.camera()
        # nama & emote pemain lain
        for pid, pl in g.players.items():
            if pl.get("look") is None:
                continue
            x = pl["px"] - cx + 8
            y = pl["py"] - cy + T - sprites.CH
            if pid != g.pid and g.mode != "solo":
                ui.text(p, x, y - 9, pl.get("name", "?"), 6, ui.YELLOW, align=Qt.AlignHCenter)
            em = pl.get("emote")
            if em and pl.get("emote_t", 0) > g.clock:
                w = ui.text_width(em, 8) + 10
                ui.window(p, x - w / 2, y - 26, w, 15, alpha=240,
                          color=(QColor("#FFFFFF"), QColor("#E8E8F8")))
                ui.text(p, x, y - 25, em, 8, ui.DARK, align=Qt.AlignHCenter, shadow=False)
        # panel regu
        y = 4
        order = sorted(g.players)
        for pid in order[:4]:
            pl = g.players[pid]
            ui.window(p, 4, y, 92, 19, alpha=190)
            name = pl.get("name", "?")
            cls = data.CLASSES.get(pl.get("cls"), {}).get("icon", "")
            ui.text(p, 8, y + 1, f"{cls}{name}", 7, ui.YELLOW if pid == g.pid else ui.WHITE)
            ui.text(p, 92, y + 1, f"Lv{pl.get('level', 1)}", 6, ui.WHITE, align=Qt.AlignRight)
            hp, mhp = pl.get("hp", 1), max(1, pl.get("mhp", 1))
            ui.bar(p, 8, y + 13, 84, 3.5, hp / mhp,
                   ui.GREEN if hp > mhp * 0.3 else ui.RED)
            y += 21
        # tombol
        b = self.hud_buttons()
        ui.button(p, *b["menu"], "☰ Menu", 7)
        ui.button(p, *b["emote"], "💬 Sapa", 7)
        ui.button(p, *b["act"], "✋ Aksi", 7)
        if g.mode == "host":
            n = len(g.players)
            ui.text(p, LW - 48, 6, f"🌐 Lobi {n}/{data.MAX_PLAYERS}", 7, ui.WHITE,
                    align=Qt.AlignRight)
        elif g.mode == "client":
            ui.text(p, LW - 48, 6, f"🌐 Co-op {len(g.players)}", 7, ui.WHITE, align=Qt.AlignRight)
        if self.banner > 0:
            a = min(1.0, self.banner / 0.5, (2.6 - self.banner) / 0.3)
            name = self.map.cfg["name"]
            w = ui.text_width(name, 11) + 30
            p.setOpacity(max(0.0, a))
            ui.window(p, LW / 2 - w / 2, 40, w, 22)
            ui.text(p, LW / 2, 42, name, 11, ui.WHITE, align=Qt.AlignHCenter)
            p.setOpacity(1.0)
        if g.waiting_battle_text:
            ui.window(p, LW / 2 - 90, LH - 44, 180, 18, alpha=200)
            ui.text(p, LW / 2, LH - 42, g.waiting_battle_text, 7, ui.WHITE,
                    align=Qt.AlignHCenter)
