# -*- coding: utf-8 -*-
"""Layar pertarungan: animasi, angka kerusakan, menu perintah & hasil."""

import math
import random

from PyQt5.QtCore import Qt, QPointF, QRectF
from PyQt5.QtGui import QColor, QPen, QPolygonF

from . import data, sprites, ui
from .ui import LW, LH, UP, DOWN, LEFT, RIGHT, OK, CANCEL

FX_SOUND = {"hit": "hit", "slash": "slash", "arrow": "slash", "fire": "magic", "ice": "magic",
            "bolt": "magic", "holy": "magic", "star": "magic", "wind": "magic", "dark": "magic",
            "spore": "magic", "quake": "hit", "heal": "heal", "shield": "buff", "buff": "buff",
            "sleep": "magic", "flee": "page"}
FX_COLOR = {"fire": "#FF8A3D", "ice": "#8FE3FF", "bolt": "#FFE14D", "holy": "#FFF6C0",
            "star": "#FFE14D", "wind": "#9BE07A", "dark": "#9A5BE0", "spore": "#C58CFF",
            "heal": "#7CF08A", "shield": "#7FC8FF", "buff": "#FF9E4D", "sleep": "#C8C8FF"}

HERO_SLOTS = {1: [(250, 128)], 2: [(240, 104), (262, 146)],
              3: [(236, 88), (252, 122), (268, 156)],
              4: [(230, 78), (244, 106), (258, 134), (272, 162)]}
ENEMY_SLOTS = {1: [(78, 132)], 2: [(58, 104), (98, 146)], 3: [(46, 96), (98, 106), (66, 152)],
               4: [(42, 96), (96, 96), (54, 150), (108, 150)],
               5: [(40, 90), (92, 86), (136, 118), (50, 150), (100, 156)]}


class BattleScene(ui.Scene):
    covers_world = True

    def __init__(self, game, snap):
        super().__init__(game)
        self.snap = snap
        self.disp = {}
        self.hurt_t = {}
        self.ko_t = {}
        self.events = []
        self.cur = None
        self.cur_t = 0.0
        self.cur_hit = False
        self.popups = []           # [x, y, teks, warna, umur]
        self.banner = ("Musuh muncul!", 1.4)
        self.menu = None           # None / cmd / skill / item / target
        self.cmd_menu = None
        self.sub_menu = None
        self.pending = None        # perintah yang menunggu sasaran
        self.targets = []
        self.target_i = 0
        self.submitted = False
        self.result = None
        self.result_t = 0.0
        self.shake = 0.0
        self.sparkles = []
        for u in snap["units"]:
            self.disp[u["uid"]] = float(u["hp"])
        boss = snap.get("boss")
        game.music("rpg_boss" if boss else "rpg_battle")
        game.sfx("crash" if boss else "open")

    # -- data dari host ------------------------------------------------------
    def set_snap(self, snap):
        self.snap = snap
        me = self.my_unit()
        if me and not me["ready"]:
            self.submitted = False
        if me and (me["ko"] or me["st"].get("tidur")) and self.menu:
            self.menu = None
        for u in snap["units"]:
            self.disp.setdefault(u["uid"], float(u["hp"]))
            if u["ko"] and u["uid"] not in self.ko_t:
                self.ko_t[u["uid"]] = self.t
            elif not u["ko"]:
                self.ko_t.pop(u["uid"], None)

    def add_event(self, ev):
        self.events.append(ev)

    def set_result(self, res):
        self.result = res
        self.result_t = 0.0
        self.menu = None
        st = res.get("state")
        if st == "win":
            self.game.music(None)
            self.game.sfx("tada")
        elif st == "lose":
            self.game.music(None)
            self.game.sfx("wrong")

    # -- pembantu ------------------------------------------------------------
    def units(self, side):
        return [u for u in self.snap["units"] if u["side"] == side and not u.get("gone")]

    def unit(self, uid):
        for u in self.snap["units"]:
            if u["uid"] == uid:
                return u
        return None

    def my_unit(self):
        return self.unit(f"h{self.game.pid}")

    def pos(self, u):
        if u["side"] == "hero":
            heroes = self.units("hero")
            slots = HERO_SLOTS[min(4, max(1, len(heroes)))]
            i = heroes.index(u) if u in heroes else 0
            x, y = slots[min(i, len(slots) - 1)]
            if u["ready"] and not u["ko"]:
                x -= 10
            return x, y
        enemies = self.units("enemy")
        if self.snap.get("boss") and len(enemies) == 1:
            return 80, 158
        slots = ENEMY_SLOTS[min(5, max(1, len(enemies)))]
        i = enemies.index(u) if u in enemies else 0
        return slots[min(i, len(slots) - 1)]

    def enemy_scale(self, u):
        size = sprites.MONSTER_ART[data.ENEMIES[u["eid"]]["art"][0]][1]
        return 1.9 if size > 32 else 1.6

    def body_rect(self, u):
        x, y = self.pos(u)
        if u["side"] == "hero":
            return (x - 20, y - 50, 40, 50)
        size = sprites.MONSTER_ART[data.ENEMIES[u["eid"]]["art"][0]][1] * self.enemy_scale(u)
        return (x - size / 2, y - size, size, size)

    def center(self, u):
        x, y, w, h = self.body_rect(u)
        return x + w / 2, y + h / 2

    # -- update ----------------------------------------------------------------
    def update(self, dt):
        super().update(dt)
        speed = 1.0 + 0.6 * max(0, len(self.events) - 1)
        if self.cur is None and self.events:
            self.cur = self.events.pop(0)
            self.cur_t = 0.0
            self.cur_hit = False
            name = self.cur.get("text") if self.cur["t"] == "msg" else self.cur.get("name")
            if name:
                self.banner = (name, self.cur.get("dur", 1.0))
        if self.cur is not None:
            self.cur_t += dt * speed
            dur = self.cur.get("dur", 1.0)
            if not self.cur_hit and self.cur_t >= dur * 0.38:
                self.cur_hit = True
                self._apply_hits(self.cur)
            if self.cur_t >= dur:
                if self.cur.get("text") and self.cur["t"] == "act":
                    self.banner = (self.cur["text"], 1.0)
                self.cur = None
        name, left = self.banner
        self.banner = (name, left - dt)
        for u in self.snap["units"]:
            d = self.disp.get(u["uid"], u["hp"])
            target = float(u["hp"])
            if abs(d - target) > 0.1 and (self.cur is None or self.cur_hit):
                step = max(1.0, u["mhp"] * dt * 1.4)
                d = target if abs(target - d) <= step else d + step * (1 if target > d else -1)
                self.disp[u["uid"]] = d
        for pop in self.popups:
            pop[4] += dt
        self.popups = [pp for pp in self.popups if pp[4] < 1.3]
        self.shake = max(0.0, self.shake - dt)
        for s in self.sparkles:
            s[4] += dt
        self.sparkles = [s for s in self.sparkles if s[4] < s[5]]
        if self.result:
            self.result_t += dt
        me = self.my_unit()
        if (self.menu is None and self.result is None and me and me["ready"] and not me["ko"]
                and not self.submitted and self.snap["state"] == "run"):
            self.open_commands()

    def _apply_hits(self, ev):
        if ev["t"] != "act":
            return
        fx = ev.get("fx", "hit")
        self.game.sfx(FX_SOUND.get(fx, "hit"))
        if fx == "quake":
            self.shake = 0.5
        for hit in ev.get("hits", []):
            u = self.unit(hit["dst"])
            if not u:
                continue
            x, y = self.center(u)
            y -= 6
            if hit.get("miss"):
                self.popups.append([x, y, "Meleset", ui.GREY, 0.0])
                continue
            if "dmg" in hit:
                self.hurt_t[u["uid"]] = self.t
                color = ui.YELLOW if hit.get("crit") else ui.WHITE
                self.popups.append([x, y, str(hit["dmg"]), color, 0.0])
                if hit.get("weak"):
                    self.popups.append([x, y - 12, "Lemah!", ui.YELLOW, -0.1])
                elif hit.get("resist"):
                    self.popups.append([x, y - 12, "Tahan", ui.GREY, -0.1])
                if hit.get("ko"):
                    self.game.sfx("crash")
            if hit.get("heal"):
                self.popups.append([x, y, f"+{hit['heal']}", ui.GREEN, 0.0])
            if hit.get("mp"):
                self.popups.append([x, y, f"+{hit['mp']} MP", ui.BLUE, 0.0])
            if hit.get("revive"):
                self.popups.append([x, y - 12, "Bangun!", ui.GREEN, -0.1])
            if hit.get("status") == "tidur":
                self.popups.append([x, y, "Zzz 💤", QColor("#C8C8FF"), 0.0])
            if hit.get("buff"):
                label = {"def": "Pertahanan ↑", "atk": "Serangan ↑",
                         "guard": "Bertahan"}.get(hit["buff"], "")
                self.popups.append([x, y, label, ui.BLUE, 0.0])
            color = QColor(FX_COLOR.get(fx, "#FFFFFF"))
            for _ in range(8):
                self.sparkles.append([x + random.uniform(-14, 14), y + random.uniform(-14, 14),
                                      random.uniform(-20, 20), random.uniform(-40, -10), 0.0,
                                      random.uniform(0.4, 0.8), color])

    # -- menu perintah ----------------------------------------------------------
    def open_commands(self):
        me = self.my_unit()
        items = ["⚔️ Serang", "✨ Skill", "🎒 Barang", "🛡️ Bertahan", "🏃 Kabur"]
        self.cmd_menu = ui.ListMenu(items, 8, 158, 96, row_h=15, size=8,
                                    enabled=lambda i: i != 1 or bool(me and me["skills"]))
        self.menu = "cmd"
        self.game.sfx("key")

    def _skill_items(self):
        me = self.my_unit()
        out = []
        for s in me["skills"]:
            sk = data.SKILLS[s]
            out.append((sk["name"], f"{sk['mp']} MP"))
        return out

    def _item_list(self):
        hero = self.game.hero
        return [i for i in data.ITEM_ORDER if hero["items"].get(i, 0) > 0]

    def key(self, k):
        if self.result is not None:
            if k in (OK, CANCEL) and self.result_t > 0.6:
                self.finish()
            return
        if self.menu == "cmd":
            r = self.cmd_menu.key(k)
            if r == "ok":
                self.choose_cmd(self.cmd_menu.index)
            elif r == "move":
                self.game.sfx("key")
        elif self.menu in ("skill", "item"):
            r = self.sub_menu.key(k)
            if r == "ok":
                self.choose_sub(self.sub_menu.index)
            elif r == "cancel":
                self.menu = "cmd"
            elif r == "bad":
                self.game.sfx("wrong")
            elif r == "move":
                self.game.sfx("key")
        elif self.menu == "target":
            if k in (UP, LEFT):
                self.target_i = (self.target_i - 1) % len(self.targets)
                self.game.sfx("key")
            elif k in (DOWN, RIGHT):
                self.target_i = (self.target_i + 1) % len(self.targets)
                self.game.sfx("key")
            elif k == OK:
                self.submit(self.pending, self.targets[self.target_i]["uid"])
            elif k == CANCEL:
                self.menu = self.pending.get("_back", "cmd")

    def choose_cmd(self, i):
        if i == 0:
            self.ask_target({"act": "attack", "_back": "cmd"}, "enemy")
        elif i == 1:
            me = self.my_unit()
            self.sub_menu = ui.ListMenu(self._skill_items(), 10, 118, 190, row_h=14, size=8,
                                        visible=7,
                                        enabled=lambda j: me["mp"] >= data.SKILLS[
                                            me["skills"][j]]["mp"])
            self.menu = "skill"
        elif i == 2:
            items = self._item_list()
            if not items:
                self.game.sfx("wrong")
                self.banner = ("Tidak punya barang.", 1.0)
                return
            hero = self.game.hero
            self.sub_menu = ui.ListMenu(
                [(f"{data.ITEMS[it]['icon']} {data.ITEMS[it]['name']}", f"×{hero['items'][it]}")
                 for it in items], 10, 118, 190, row_h=14, size=8, visible=7)
            self.sub_items = items
            self.menu = "item"
        elif i == 3:
            self.submit({"act": "guard"}, None)
        elif i == 4:
            self.submit({"act": "flee"}, None)

    def choose_sub(self, j):
        if self.menu == "skill":
            sid = self.my_unit()["skills"][j]
            tgt = data.SKILLS[sid]["target"]
            cmd = {"act": "skill", "skill": sid, "_back": "skill"}
            if tgt == "enemy":
                self.ask_target(cmd, "enemy")
            elif tgt == "ally":
                self.ask_target(cmd, "ally")
            elif tgt == "ally_ko":
                self.ask_target(cmd, "ko")
            else:
                self.submit(cmd, None)
        else:
            iid = self.sub_items[j]
            kind = data.ITEMS[iid]["kind"]
            cmd = {"act": "item", "item": iid, "_back": "item"}
            if kind == "hp_all":
                self.submit(cmd, None)
            else:
                self.ask_target(cmd, "ko" if kind == "revive" else "ally")

    def ask_target(self, cmd, kind):
        if kind == "enemy":
            pool = [u for u in self.units("enemy") if not u["ko"]]
        elif kind == "ko":
            pool = [u for u in self.units("hero") if u["ko"]]
        else:
            pool = [u for u in self.units("hero") if not u["ko"]]
        if not pool:
            self.game.sfx("wrong")
            self.banner = ("Tidak ada sasaran.", 1.0)
            return
        self.pending = cmd
        self.targets = pool
        me = self.my_unit()
        self.target_i = pool.index(me) if me in pool else 0
        self.menu = "target"

    def submit(self, cmd, target):
        cmd = {k: v for k, v in cmd.items() if not k.startswith("_")}
        if target:
            cmd["target"] = target
        if cmd["act"] == "item":
            if not self.game.use_item_count(cmd["item"]):
                self.game.sfx("wrong")
                return
        self.game.request({"t": "bcmd", "cmd": cmd})
        self.submitted = True
        self.menu = None
        self.pending = None
        self.game.sfx("pop")

    def mouse(self, x, y, kind):
        if kind != "press":
            return
        if self.result is not None:
            if self.result_t > 0.6:
                self.finish()
            return
        if self.menu == "cmd":
            if self.cmd_menu.mouse((x, y)) == "ok":
                self.choose_cmd(self.cmd_menu.index)
            return
        if self.menu in ("skill", "item"):
            r = self.sub_menu.mouse((x, y))
            if r == "ok":
                self.choose_sub(self.sub_menu.index)
            elif r is None:
                self.menu = "cmd"
            return
        if self.menu == "target":
            for i, u in enumerate(self.targets):
                if ui.inside((x, y), self.body_rect(u)):
                    self.submit(self.pending, u["uid"])
                    return
            self.menu = self.pending.get("_back", "cmd")

    def wheel(self, delta):
        if self.menu in ("skill", "item"):
            self.sub_menu.wheel(delta)

    def finish(self):
        self.game.pop(self)
        self.game.after_battle(self.result)

    # -- gambar ----------------------------------------------------------------
    def actor_offset(self, u):
        ev = self.cur
        if ev is None or ev.get("t") != "act" or ev.get("src") != u["uid"]:
            return 0, None
        dur = ev.get("dur", 1.0)
        k = self.cur_t / dur
        kind = ev.get("kind")
        if kind in ("attack",) or (kind == "skill" and ev.get("fx") in ("slash", "arrow")):
            step = math.sin(min(1.0, k / 0.75) * math.pi) * 22
            return (-step if u["side"] == "hero" else step), "attack"
        if kind in ("skill", "item"):
            return 0, "cast"
        return 0, None

    def draw_world(self, p):
        sx = random.uniform(-3, 3) if self.shake > 0 else 0
        p.drawPixmap(QRectF(sx, 0, LW, LH), sprites.battle_background(self.snap.get("bg", "padang")),
                     QRectF(0, 0, LW, LH))
        # musuh
        for u in self.units("enemy"):
            ko_at = self.ko_t.get(u["uid"])
            if ko_at is not None and self.t - ko_at > 0.7:
                continue
            x, y = self.pos(u)
            dx, _pose = self.actor_offset(u)
            frames = sprites.enemy_frames(u["eid"])
            pm = frames[int(self.t * 2.2) % 2]
            sc = self.enemy_scale(u)
            w, h = pm.width() * sc, pm.height() * sc
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 50))
            p.drawEllipse(QRectF(x - w * 0.35 + dx + sx, y - 5, w * 0.7, 8))
            op = 1.0
            if ko_at is not None:
                op = max(0.0, 1 - (self.t - ko_at) / 0.7)
            hurt = self.t - self.hurt_t.get(u["uid"], -9) < 0.35
            if hurt and int(self.t * 20) % 2:
                op *= 0.35
            p.setOpacity(op)
            p.drawPixmap(QRectF(x - w / 2 + dx + sx + (2 if hurt else 0), y - h, w, h), pm,
                         QRectF(pm.rect()))
            p.setOpacity(1.0)
            if u["st"].get("tidur"):
                self._zzz(p, x + w / 3, y - h)
        # pahlawan
        for u in self.units("hero"):
            x, y = self.pos(u)
            dx, pose = self.actor_offset(u)
            fr = sprites.hero_frames(u["look"])
            hurt = self.t - self.hurt_t.get(u["uid"], -9) < 0.35
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 55))
            p.drawEllipse(QRectF(x - 13 + dx, y - 5, 26, 7))
            if u["ko"]:
                pm = fr["b_ko"]
                p.drawPixmap(QRectF(x - 28, y - 36, 56, 40), pm, QRectF(pm.rect()))
                continue
            if self.snap["state"] == "win" or (self.result and self.result.get("state") == "win"):
                key = "b_win"
            elif pose == "attack":
                key = "b_attack"
            elif pose == "cast":
                key = "b_cast"
            elif hurt or u["hp"] < u["mhp"] * 0.25:
                key = "b_hurt"
            elif u["st"].get("tidur"):
                key = "b_sleep"
            elif u["ready"]:
                key = "b_walk" if int(self.t * 4) % 2 else "b_idle"
            else:
                key = "b_idle"
            pm = fr[key]
            if hurt and int(self.t * 20) % 2:
                p.setOpacity(0.4)
            p.drawPixmap(QRectF(x - 20 + dx + sx, y - 55, 40, 56), pm, QRectF(pm.rect()))
            p.setOpacity(1.0)
            if u["st"].get("tidur"):
                self._zzz(p, x + 10, y - 56)
            if u["st"].get("def"):
                p.setPen(QPen(QColor(127, 200, 255, 160), 1.2))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(QRectF(x - 22, y - 58, 44, 60))
        self._draw_fx(p)
        for s in self.sparkles:
            x, y, vx, vy, age, life, color = s
            c = QColor(color)
            c.setAlpha(int(255 * (1 - age / life)))
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            size = 2.5 * (1 - age / life) + 0.8
            p.drawEllipse(QPointF(x + vx * age, y + vy * age), size, size)

    def _zzz(self, p, x, y):
        k = (self.t * 1.5) % 1.0
        c = QColor("#E8E8FF")
        c.setAlpha(int(255 * (1 - k)))
        p.setPen(c)
        p.setFont(ui.font(8))
        p.drawText(QPointF(x + k * 6, y - k * 10), "z")
        p.drawText(QPointF(x + 5 + k * 6, y - 6 - k * 10), "Z")

    def _draw_fx(self, p):
        ev = self.cur
        if ev is None or ev.get("t") != "act" or not self.cur_hit:
            return
        dur = ev.get("dur", 1.0)
        k = (self.cur_t - dur * 0.38) / max(0.01, dur * 0.62)
        if k > 1:
            return
        fx = ev.get("fx", "hit")
        src = self.unit(ev.get("src"))
        color = QColor(FX_COLOR.get(fx, "#FFFFFF"))
        for hit in ev.get("hits", []):
            u = self.unit(hit["dst"])
            if not u:
                continue
            x, y = self.center(u)
            a = int(255 * (1 - k))
            if fx in ("hit", "slash", "quake"):
                p.setPen(QPen(QColor(255, 255, 255, a), 2.2))
                r = 6 + k * 14
                p.drawLine(QPointF(x - r, y - r), QPointF(x + r, y + r))
                if fx == "slash":
                    p.drawLine(QPointF(x + r, y - r * 0.6), QPointF(x - r, y + r * 0.6))
                p.setBrush(QColor(255, 240, 180, a))
                p.setPen(Qt.NoPen)
                p.drawEllipse(QPointF(x, y), 4 * (1 - k) + 1, 4 * (1 - k) + 1)
            elif fx == "arrow" and src:
                sx_, sy_ = self.center(src)
                kk = min(1.0, k * 2.2)
                ax, ay = sx_ + (x - sx_) * kk, sy_ + (y - sy_) * kk
                p.setPen(QPen(QColor("#8B5A2B"), 2))
                p.drawLine(QPointF(ax, ay), QPointF(ax + 10, ay))
                p.setPen(QPen(QColor("#DDDDDD"), 2))
                p.drawLine(QPointF(ax - 3, ay), QPointF(ax, ay))
            elif fx == "fire":
                for i in range(6):
                    ang = i * 1.05 + self.t * 6
                    rr = 4 + k * 12
                    c = QColor("#FF8A3D" if i % 2 else "#FFD23F")
                    c.setAlpha(a)
                    p.setPen(Qt.NoPen)
                    p.setBrush(c)
                    p.drawEllipse(QPointF(x + math.cos(ang) * rr, y + math.sin(ang) * rr - k * 10),
                                  5 * (1 - k) + 2, 5 * (1 - k) + 2)
            elif fx == "ice":
                p.setPen(QPen(QColor(200, 245, 255, a), 1))
                for i in range(5):
                    ang = i * 1.26
                    rr = 5 + k * 10
                    cx, cy = x + math.cos(ang) * rr, y + math.sin(ang) * rr
                    c = QColor("#8FE3FF")
                    c.setAlpha(a)
                    p.setBrush(c)
                    p.drawPolygon(QPolygonF([QPointF(cx, cy - 6), QPointF(cx + 3, cy),
                                             QPointF(cx, cy + 6), QPointF(cx - 3, cy)]))
            elif fx == "bolt":
                p.setPen(QPen(QColor(255, 240, 120, a), 2.5))
                pts, yy = [], y - 80
                xx = x
                while yy < y:
                    pts.append(QPointF(xx, yy))
                    yy += 12
                    xx = x + random.uniform(-7, 7)
                pts.append(QPointF(x, y))
                for i in range(len(pts) - 1):
                    p.drawLine(pts[i], pts[i + 1])
            elif fx in ("holy", "heal", "shield", "buff"):
                c = QColor(color)
                c.setAlpha(int(a * 0.6))
                p.setPen(Qt.NoPen)
                p.setBrush(c)
                if fx == "holy":
                    p.drawRect(QRectF(x - 9, y - 60 + k * 10, 18, 80))
                elif fx == "shield":
                    p.setBrush(Qt.NoBrush)
                    p.setPen(QPen(c, 2))
                    p.drawEllipse(QPointF(x, y), 14 + k * 6, 18 + k * 6)
                else:
                    for i in range(5):
                        yy = y + 14 - ((k * 30 + i * 7) % 30)
                        p.drawEllipse(QPointF(x - 10 + i * 5, yy), 2.2, 2.2)
            elif fx == "star":
                p.setPen(Qt.NoPen)
                for i in range(5):
                    kk = (k * 1.6 + i * 0.13) % 1.0
                    c = QColor("#FFE14D")
                    c.setAlpha(a)
                    p.setBrush(c)
                    sx_ = x - 30 + i * 14 + kk * 20
                    sy_ = y - 70 + kk * 70
                    self._star(p, sx_, sy_, 4)
            elif fx in ("dark", "spore", "sleep", "wind"):
                c = QColor(color)
                c.setAlpha(a)
                p.setPen(Qt.NoPen)
                p.setBrush(c)
                for i in range(8):
                    ang = i * 0.785 + k * 5 * (1 if fx != "wind" else 2)
                    rr = 18 * (1 - k) + 3
                    p.drawEllipse(QPointF(x + math.cos(ang) * rr, y + math.sin(ang) * rr), 2.4, 2.4)

    def _star(self, p, x, y, r):
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else r * 0.45
            pts.append(QPointF(x + math.cos(ang) * rr, y + math.sin(ang) * rr))
        p.drawPolygon(QPolygonF(pts))

    def draw_ui(self, p):
        # angka kerusakan
        for x, y, s, color, age in self.popups:
            if age < 0:
                continue
            lift = min(age, 0.3) * 40 - max(0, age - 0.3) * 4
            p.setOpacity(max(0.0, min(1.0, (1.3 - age) / 0.4)))
            ui.text(p, x, y - lift, s, 10 if s[0].isdigit() else 8, color, align=Qt.AlignHCenter)
            p.setOpacity(1.0)
        name, left = self.banner
        if left > 0 and name:
            w = ui.text_width(name, 9) + 24
            ui.window(p, LW / 2 - w / 2, 4, w, 18)
            ui.text(p, LW / 2, 5, name, 9, ui.WHITE, align=Qt.AlignHCenter)
        # panel musuh
        ui.window(p, 4, 168, 110, 68)
        ey = 172
        for u in self.units("enemy"):
            if u["ko"]:
                continue
            color = ui.WHITE
            ui.text(p, 10, ey, u["name"], 7, color)
            if u.get("boss"):
                ui.bar(p, 10, ey + 11, 96, 3, self.disp.get(u["uid"], u["hp"]) / u["mhp"],
                       ui.RED)
                ey += 4
            ey += 12
        # panel regu
        ui.window(p, 116, 168, 200, 68)
        hy = 172
        me_pid = self.game.pid
        for u in self.units("hero"):
            mine = u.get("pid") == me_pid
            ui.text(p, 122, hy, u["name"], 7, ui.YELLOW if mine else ui.WHITE)
            hp = int(round(self.disp.get(u["uid"], u["hp"])))
            color = ui.RED if u["ko"] or hp < u["mhp"] * 0.25 else ui.WHITE
            ui.text(p, 214, hy, f"{hp}/{u['mhp']}", 7, color, align=Qt.AlignRight)
            ui.text(p, 250, hy, f"{u['mp']}", 7, ui.BLUE, align=Qt.AlignRight)
            full = u["atb"] >= 100
            ui.bar(p, 256, hy + 4, 54, 4, u["atb"] / 100.0,
                   ui.YELLOW if full else QColor("#E0E0F0"))
            hy += 15
        ui.text(p, 214, 159, "HP", 6, ui.GREY, align=Qt.AlignRight)
        ui.text(p, 250, 159, "MP", 6, ui.GREY, align=Qt.AlignRight)
        ui.text(p, 283, 159, "ATB", 6, ui.GREY, align=Qt.AlignHCenter)

        if self.menu in ("cmd", "skill", "item", "target") and self.cmd_menu:
            ui.window(p, 4, 150, 112, 86)
            self.cmd_menu.draw(p, self.t, focus=self.menu == "cmd")
        if self.menu in ("skill", "item"):
            ui.window(p, 4, 112, 204, 108)
            self.sub_menu.draw(p, self.t)
        if self.menu == "target" and self.targets:
            u = self.targets[self.target_i % len(self.targets)]
            x, y, w, h = self.body_rect(u)
            if u["side"] == "hero":
                ui.cursor(p, x + 2, y + h / 2, self.t)
            else:
                ui.cursor(p, x + w + 10, y + h / 2, self.t)
            ui.window(p, LW / 2 - 70, 26, 140, 16, alpha=200)
            ui.text(p, LW / 2, 27, f"Sasaran: {u['name']}", 7, ui.WHITE, align=Qt.AlignHCenter)
        me = self.my_unit()
        if me is None and self.result is None:
            ui.window(p, LW / 2 - 90, 26, 180, 16, alpha=200)
            ui.text(p, LW / 2, 27, "Kamu menonton pertarungan temanmu", 7, ui.WHITE,
                    align=Qt.AlignHCenter)
        elif me and me["ready"] and self.submitted:
            pass
        if self.result is not None:
            self._draw_result(p)

    def _draw_result(self, p):
        r = self.result
        st = r.get("state")
        k = min(1.0, self.result_t / 0.3)
        p.setOpacity(k)
        ui.window(p, 50, 44, 220, 110)
        if st == "win":
            ui.text(p, LW / 2, 50, "🎉 MENANG! 🎉", 12, ui.YELLOW, align=Qt.AlignHCenter)
            y = 70
            ui.text(p, 62, y, f"EXP  +{r.get('exp', 0)}", 8)
            ui.text(p, 160, y, f"Uang +{r.get('gold', 0)} 🪙", 8)
            y += 13
            items = r.get("items") or []
            if items:
                names = ", ".join(data.item_name(i) for i in items)
                y = ui.paragraph(p, 62, y, 196, f"Dapat: {names}", 8)
            for lv, learned in r.get("levelups", []):
                ui.text(p, 62, y, f"⭐ Naik ke Level {lv}!", 8, ui.YELLOW)
                y += 12
                for s in learned:
                    ui.text(p, 72, y, f"✨ Jurus baru: {data.SKILLS[s]['name']}", 7, ui.GREEN)
                    y += 11
        elif st == "fled":
            ui.text(p, LW / 2, 70, "🏃 Kalian berhasil kabur!", 11, ui.WHITE, align=Qt.AlignHCenter)
        else:
            ui.text(p, LW / 2, 58, "😵 Semua pingsan...", 11, ui.WHITE, align=Qt.AlignHCenter)
            ui.paragraph(p, 64, 82, 192, "Peri Daun membawa kalian pulang ke kedai. "
                         "HP pulih penuh. Ayo coba lagi!", 8)
        if self.result_t > 0.6:
            ui.text(p, LW / 2, 136, "Tekan OK / sentuh untuk lanjut", 7, ui.GREY,
                    align=Qt.AlignHCenter)
        p.setOpacity(1.0)
