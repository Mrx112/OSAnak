# -*- coding: utf-8 -*-
"""
Inti permainan: widget Qt, pengulangan waktu, masukan, simpanan, dan sesi
main bersama (tuan rumah = penentu keadaan dunia & pertarungan).

Alur pesan co-op:
  tamu --request--> tuan rumah --host_handle--> emit(pesan) --> semua apply()
Main sendiri = tuan rumah tanpa tamu (tanpa soket).
"""

import json
import os
import random
import time

from PyQt5.QtCore import Qt, QTimer, QRectF, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter
from PyQt5.QtWidgets import QSizePolicy, QWidget

from . import data, net, sprites, ui
from . import scenes as S
from .battle import Battle, random_group
from .battle_view import BattleScene
from .ui import LW, LH, UP, DOWN, LEFT, RIGHT, OK, CANCEL, MENU
from .world import WorldScene

try:
    import sounds
except ImportError:          # dijalankan tanpa KidsOS
    sounds = None

SAVE_DIR = os.path.expanduser("~/.local/share/kidsos/rpg")
SLOTS = 3

KEYMAP = {
    Qt.Key_Up: UP, Qt.Key_W: UP, Qt.Key_Down: DOWN, Qt.Key_S: DOWN,
    Qt.Key_Left: LEFT, Qt.Key_A: LEFT, Qt.Key_Right: RIGHT, Qt.Key_D: RIGHT,
    Qt.Key_Return: OK, Qt.Key_Enter: OK, Qt.Key_Space: OK, Qt.Key_Z: OK,
    Qt.Key_Escape: CANCEL, Qt.Key_X: CANCEL, Qt.Key_Backspace: CANCEL,
    Qt.Key_M: MENU, Qt.Key_C: MENU,
}
DIR_KEYS = (UP, DOWN, LEFT, RIGHT)

# flag yang boleh diminta tamu (hanya yang memang diberikan dialog)
STORY_FLAGS = {a[1] for n in data.NPCS.values() for t in n["talk"] for a in t.get("do", [])
               if a[0] == "flag"}
BOSS_FLAGS = {a[1]: a[2] for n in data.NPCS.values() for t in n["talk"] for a in t.get("do", [])
              if a[0] == "boss"}          # musuh -> flag menang


def _clean_text(s):
    """Buang emoji/simbol agar espeak tidak membacakan nama simbol."""
    return "".join(ch for ch in s if ord(ch) < 0x2000).strip()


def sanitize_hero(h):
    """Data pahlawan dari jaringan -> salinan aman (atau None)."""
    try:
        cls = h["cls"] if h["cls"] in data.CLASSES else "kesatria"
        look = h.get("look") or {}
        styles = [s for s, _ in data.HAIR_STYLES]
        hats = [x for x, _ in data.HATS]
        out = {
            "name": str(h.get("name", "Teman"))[:10] or "Teman", "cls": cls,
            "level": max(1, min(data.MAX_LEVEL, int(h.get("level", 1)))),
            "exp": 0, "gold": 0, "items": {}, "gear": [],
            "look": {"skin": int(look.get("skin", 0)) % len(data.SKINS),
                     "hair": look.get("hair") if look.get("hair") in styles else "pendek",
                     "hair_color": str(look.get("hair_color", "#6B4430"))[:9],
                     "outfit": str(look.get("outfit", "#E0405E"))[:9],
                     "hat": look.get("hat") if look.get("hat") in hats else None},
            "equip": {},
        }
        for slot in ("weapon", "armor", "acc"):
            it = (h.get("equip") or {}).get(slot)
            ok = it in data.EQUIPMENT and data.EQUIPMENT[it]["slot"] == slot
            out["equip"][slot] = it if ok and data.can_equip(cls, it) else None
        if out["equip"]["weapon"] is None:
            out["equip"]["weapon"] = data.STARTER_WEAPON[cls]
        if out["equip"]["armor"] is None:
            out["equip"]["armor"] = "baju_kain"
        st = data.derive_stats(out)
        out["hp"] = max(0, min(int(h.get("hp", st["hp"])), st["hp"]))
        out["mp"] = max(0, min(int(h.get("mp", st["mp"])), st["mp"]))
        return out
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


class RpgGame(QWidget):
    exit_requested = pyqtSignal()

    def __init__(self, parent=None, standalone=False):
        super().__init__(parent)
        self.standalone = standalone
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.canvas = QImage(LW, LH, QImage.Format_RGB32)
        self.stack = []
        self.clock = 0.0
        self.held_order = []
        self.mouse_pos = None
        self.settings = self._load_json(os.path.join(SAVE_DIR, "settings.json")) or {}
        self.toasts = []
        self._music_theme = None
        self._music_tick = 0.0
        self.reset_session()
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.tick)
        self._last = time.monotonic()
        self.push(S.TitleScene(self))

    # -- sesi ----------------------------------------------------------------
    def reset_session(self):
        self.mode = None           # solo / host / client
        self.pid = 0
        self.hero = None
        self.slot = None
        self.world_save = {}
        self.flags = set()
        self.chests = set()
        self.players = {}
        self.heroes = {}           # tuan rumah: pid -> data pahlawan (untuk pertarungan)
        self.server = None
        self.client = None
        self.finder = None
        self.hello_sent = False
        self.battle = None
        self.battle_end_at = None
        self.battle_boss = None
        self.battle_scene = None
        self.pending_after = None
        self.last_battle_end = -99.0
        self._snap_t = 0.0
        self.waiting_battle_text = ""
        self.connecting = None
        self.world = WorldScene(self)

    def me(self):
        if self.pid not in self.players:
            self.players[self.pid] = {"x": 0, "y": 0, "d": DOWN, "px": 0.0, "py": 0.0}
        return self.players[self.pid]

    def start(self):
        self._last = time.monotonic()
        self.timer.start()
        self.setFocus()

    def shutdown(self):
        self.timer.stop()
        if self.hero is not None:
            self.save_all()
        self.stop_speech()
        self._close_net()
        self.music(None)

    # -- tumpukan layar --------------------------------------------------------
    def push(self, scene):
        self.stack.append(scene)

    def pop(self, scene):
        if scene is not None and scene in self.stack:
            was_top = self.stack[-1] is scene
            self.stack.remove(scene)
            if scene is self.battle_scene:
                self.battle_scene = None
            if was_top and self.stack:
                self.stack[-1].on_top()

    def top(self):
        return self.stack[-1] if self.stack else None

    def in_battle(self):
        return self.battle_scene is not None and self.battle_scene in self.stack

    def _pop_overlays(self):
        """Tutup semua menu di atas peta (mis. saat pertarungan dimulai)."""
        while self.stack and self.stack[-1] is not self.world and \
                not isinstance(self.stack[-1], (BattleScene, S.StoryScene)):
            self.stack.pop()

    # -- waktu -----------------------------------------------------------------
    def tick(self):
        now = time.monotonic()
        dt = min(0.1, now - self._last)
        self._last = now
        self.clock += dt
        try:
            self.net_poll()
            if self.battle is not None:
                self.host_battle_tick(dt)
            for sc in list(self.stack):
                sc.update(dt)
        except Exception as e:           # jangan sampai anak melihat program mati
            import traceback
            traceback.print_exc()
            self.toast(f"Ups, ada kesalahan kecil: {e}")
        self.toasts = [t for t in self.toasts if t[1] > self.clock]
        self._music_tick += dt
        if self._music_tick > 1.0 and sounds is not None:
            self._music_tick = 0.0
            try:
                sounds.music.tick()
            except Exception:
                pass
        self.update()

    # -- gambar --------------------------------------------------------------
    def view(self):
        w, h = self.width(), self.height()
        s = min(w / LW, h / LH)
        return s, (w - LW * s) / 2, (h - LH * s) / 2

    def paintEvent(self, _event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#000000"))
        s, ox, oy = self.view()
        start = 0
        for i, sc in enumerate(self.stack):
            if sc.covers_world:
                start = i
        cp = QPainter(self.canvas)
        cp.fillRect(0, 0, LW, LH, QColor("#10101C"))
        for sc in self.stack[start:]:
            sc.draw_world(cp)
        cp.end()
        p.drawImage(QRectF(ox, oy, LW * s, LH * s), self.canvas)
        p.translate(ox, oy)
        p.scale(s, s)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)
        for i, sc in enumerate(self.stack[start:]):
            if i > 0 and sc.modal and not sc.covers_world:
                p.fillRect(QRectF(0, 0, LW, LH), QColor(0, 0, 20, 70))
            sc.draw_ui(p)
        y = 26
        for msg, _until in self.toasts[-3:]:
            w = min(LW - 20, ui.text_width(msg, 8) + 20)
            ui.window(p, LW / 2 - w / 2, y, w, 16, alpha=235,
                      color=(QColor("#3FAE5A"), QColor("#1E6E34")))
            ui.text(p, LW / 2, y + 1, msg, 8, ui.WHITE, align=Qt.AlignHCenter, w=None)
            y += 18
        p.end()

    # -- masukan -------------------------------------------------------------
    def keyPressEvent(self, e):
        e.accept()
        top = self.top()
        if top is None:
            return
        text = e.text()
        if e.key() == Qt.Key_Backspace:
            text = "\b"
        if text and not e.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
            if top.text_input(text):
                return
        k = KEYMAP.get(e.key())
        if k in DIR_KEYS:
            if e.isAutoRepeat():
                if top is not self.world:
                    top.key(k)
                return
            if k in self.held_order:
                self.held_order.remove(k)
            self.held_order.append(k)
        if top is self.world and Qt.Key_1 <= e.key() <= Qt.Key_6 and not e.isAutoRepeat():
            self.emote(e.key() - Qt.Key_1)
            return
        if k and not (e.isAutoRepeat() and k in (OK, CANCEL, MENU)):
            top.key(k)

    def keyReleaseEvent(self, e):
        e.accept()
        if e.isAutoRepeat():
            return
        k = KEYMAP.get(e.key())
        if k in self.held_order:
            self.held_order.remove(k)

    def focusOutEvent(self, e):
        self.held_order.clear()
        super().focusOutEvent(e)

    def _logical(self, e):
        s, ox, oy = self.view()
        return (e.x() - ox) / s, (e.y() - oy) / s

    def mousePressEvent(self, e):
        self.setFocus()
        x, y = self._logical(e)
        self.mouse_pos = (x, y)
        top = self.top()
        if top:
            top.mouse(x, y, "press")

    def mouseReleaseEvent(self, e):
        x, y = self._logical(e)
        self.world.mouse(x, y, "release")
        top = self.top()
        if top and top is not self.world:
            top.mouse(x, y, "release")

    def mouseMoveEvent(self, e):
        self.mouse_pos = self._logical(e)

    def wheelEvent(self, e):
        top = self.top()
        if top:
            top.wheel(e.angleDelta().y())

    # -- suara & teks ----------------------------------------------------------
    def sfx(self, name):
        if sounds is None or not self.settings.get("effects", True):
            return
        try:
            sounds.play(name)
        except Exception:
            pass

    def music(self, theme):
        self._music_theme = theme
        if sounds is None:
            return
        try:
            if theme and self.settings.get("music", True):
                sounds.music.play(theme)
            else:
                sounds.music.stop()
        except Exception:
            pass

    def apply_settings(self):
        self.music(self._music_theme)
        if not self.settings.get("tts", True):
            self.stop_speech()

    def speak(self, text):
        if not self.settings.get("tts", True):
            return
        try:
            from activities import speak
            speak(_clean_text(text))
        except Exception:
            pass

    def stop_speech(self):
        try:
            from activities import stop_speech
            stop_speech()
        except Exception:
            pass

    def toast(self, msg, secs=2.6):
        self.toasts.append((msg, self.clock + secs))

    # -- simpanan --------------------------------------------------------------
    @staticmethod
    def _load_json(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    @staticmethod
    def _write_json(path, obj):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(obj, f, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError:
            pass

    def save_settings(self):
        self._write_json(os.path.join(SAVE_DIR, "settings.json"), self.settings)

    def _slot_path(self, i):
        return os.path.join(SAVE_DIR, f"slot{i + 1}.json")

    def load_profiles(self):
        out = []
        for i in range(SLOTS):
            prof = self._load_json(self._slot_path(i))
            if prof and isinstance(prof.get("hero"), dict) and prof["hero"].get("cls") in data.CLASSES:
                out.append(prof)
            else:
                out.append(None)
        return out

    def create_profile(self, slot, name, cls, look):
        self._write_json(self._slot_path(slot), {"hero": data.new_hero(name, cls, look),
                                                 "world": {}})

    def delete_profile(self, slot):
        try:
            os.remove(self._slot_path(slot))
        except OSError:
            pass

    def save_all(self):
        if self.hero is None or self.slot is None:
            return
        if self.mode in ("solo", "host") and self.world.map is not None:
            self.world_save = {"flags": sorted(self.flags), "chests": sorted(self.chests),
                               "map": self.world.map.id, "x": self.world.x, "y": self.world.y,
                               "d": self.world.d}
        self._write_json(self._slot_path(self.slot), {"hero": self.hero, "world": self.world_save})

    # -- memulai permainan -------------------------------------------------------
    def begin(self, purpose, slot, new=False):
        prof = self.load_profiles()[slot]
        if prof is None:
            return
        self.reset_session()
        self.slot = slot
        self.hero = prof["hero"]
        self.hero.setdefault("seen", [])
        self.hero.setdefault("gear", [])
        data.clamp_hero(self.hero)
        self.world_save = prof.get("world") or {}
        if purpose == "join":
            self.finder = net.Finder()
            self.push(S.LobbyBrowserScene(self))
            return
        self.start_world(purpose == "host", new)

    def make_player(self, hero, x=0, y=0, d=DOWN):
        st = data.derive_stats(hero)
        return {"name": hero["name"], "look": data.look_of(hero), "level": hero["level"],
                "cls": hero["cls"], "hp": hero["hp"], "mhp": st["hp"], "x": x, "y": y, "d": d,
                "px": float(x * data.TILE), "py": float(y * data.TILE),
                "map": self.world.map.id if self.world.map else None}

    def start_world(self, host, new):
        self.mode = "host" if host else "solo"
        self.pid = 0
        ws = self.world_save
        self.flags = set(ws.get("flags", []))
        self.chests = set(ws.get("chests", []))
        if host:
            try:
                self.server = net.Server(f"Dunia {self.hero['name']}")
            except OSError:
                self.server = None
                self.mode = "solo"
                self.push(S.MessageScene(self, "Lobi tidak bisa dibuat (port jaringan sedang "
                                               "dipakai). Kamu main sendiri dulu, ya."))
        self.players = {0: self.make_player(self.hero)}
        self.heroes = {0: self.hero}
        from .world import WorldMap
        if self.mode == "host":
            map_id, marker = data.LOBBY_MAP
            m = WorldMap(map_id)
            pos, d = m.start_point(), UP
        elif ws.get("map") in data.MAPS:
            map_id = ws["map"]
            m = WorldMap(map_id)
            pos = (ws.get("x", 0), ws.get("y", 0))
            if m.blocked(pos[0], pos[1], self.flags) or m.warp_at(*pos) is not None:
                pos = m.nearest_free(pos[0], pos[1], self.flags)
            d = ws.get("d", DOWN)
        else:
            map_id = data.START_MAP[0]
            m = WorldMap(map_id)
            pos, d = m.start_point(), DOWN
        self.stack = [self.world]
        self.world.map = m
        self.world.banner = 2.6
        self.world.load(map_id, pos, d)
        self.me().update(self.make_player(self.hero, *pos, d))
        if new:
            cls = data.CLASSES[self.hero["cls"]]["name"]
            pages = [t.format(nama=self.hero["name"], kelas=cls) for t in data.PROLOGUE]
            self.push(S.StoryScene(self, pages))
        if self.mode == "host":
            self.toast("🌐 Lobi dibuka! Teman bisa pilih 'Gabung Lobi'.", 4)
        self.save_all()

    # -- keluar ----------------------------------------------------------------
    def _close_net(self):
        if self.server:
            try:
                self.server.broadcast({"t": "bye"})
                self.server.close()
            except Exception:
                pass
        if self.client:
            self.client.close()
        if self.finder:
            self.finder.close()
        self.server = self.client = self.finder = None

    def leave_to_title(self):
        self.save_all()
        self.stop_speech()
        self._close_net()
        self.reset_session()
        self.stack = [S.TitleScene(self)]

    def exit_game(self):
        self.shutdown()
        self.exit_requested.emit()

    # -- lobi (tamu) -----------------------------------------------------------
    def find_lobbies(self):
        if self.finder is None:
            self.finder = net.Finder()
        return self.finder.poll()

    def stop_finder(self):
        if self.finder:
            self.finder.close()
            self.finder = None
        if self.mode is None:
            self.hero = None
            self.slot = None

    def connect(self, ip, port):
        self.client = net.Client(ip, port or net.TCP_PORT)
        self.hello_sent = False
        self.connecting = S.ConnectingScene(self, ip)
        self.push(self.connecting)

    def cancel_connect(self):
        if self.client:
            self.client.close()
        self.client = None
        self._close_connecting()

    # -- jaringan ----------------------------------------------------------------
    def net_poll(self):
        if self.server:
            for pid, msg in self.server.poll():
                self.host_handle(pid, msg)
            self.server.players = len(self.players)
        if self.client:
            msgs = self.client.poll()
            if self.client.connected and not self.hello_sent:
                self.client.send({"t": "hello", "v": net.PROTOCOL, "hero": self.hero})
                self.hello_sent = True
            for m in msgs:
                if m.get("t") == "welcome":
                    self.on_welcome(m)
                elif m.get("t") == "full":
                    self.on_disconnect("Lobinya sudah penuh (maksimal 4 pemain).")
                    return
                elif m.get("t") == "bye":
                    self.on_disconnect("Tuan rumah menutup lobi.")
                    return
                elif self.mode == "client":
                    self.apply(m)
            if self.client and self.client.failed:
                self.on_disconnect()

    def on_disconnect(self, why=None):
        was_playing = self.mode == "client"
        if self.client:
            self.client.close()
        self.client = None
        if was_playing:
            self.save_all()
            msg = why or "Koneksi ke tuan rumah terputus."
            self.stack = [S.TitleScene(self)]
            self.reset_session()
            self.push(S.MessageScene(self, msg + " Karaktermu sudah disimpan."))
            return
        self._close_connecting()
        self.push(S.MessageScene(self, why or "Tidak bisa tersambung. Pastikan temanmu sudah "
                                              "membuat lobi dan kalian di jaringan yang sama."))

    def request(self, msg):
        if self.mode == "client":
            if self.client:
                self.client.send(msg)
        else:
            self.host_handle(self.pid, msg)

    def emit(self, msg, exclude=None):
        self.apply(msg)
        if self.server:
            self.server.broadcast(msg, exclude=exclude)

    def send_pos(self, x, y, d, moving):
        me = self.me()
        me.update(x=x, y=y, d=d)
        msg = {"t": "pos", "x": x, "y": y, "d": d, "m": bool(moving),
               "map": self.world.map.id if self.world.map else None}
        if self.mode == "client" and self.client:
            self.client.send(msg)
        elif self.server:
            msg["pid"] = self.pid
            self.server.broadcast(msg)

    def _close_connecting(self):
        if self.connecting is not None and self.connecting in self.stack:
            self.pop(self.connecting)
        self.connecting = None

    def on_welcome(self, m):
        self._close_connecting()
        if self.finder:
            self.finder.close()
            self.finder = None
        self.mode = "client"
        self.pid = int(m["pid"])
        self.flags = set(m.get("flags", []))
        self.chests = set(m.get("chests", []))
        self.players = {int(k): v for k, v in m.get("players", {}).items()}
        me = self.players.get(self.pid) or self.make_player(self.hero)
        self.players[self.pid] = me
        self.stack = [self.world]
        self.world.map = None
        self.world.load(m["map"], (me["x"], me["y"]), me.get("d", DOWN))
        self.toast(f"🤝 Bergabung dengan lobi!", 3)
        if m.get("battle"):
            self.start_battle_view(m["battle"])
            self.waiting_battle_text = ""

    # -- tuan rumah: menangani permintaan ---------------------------------------
    def host_handle(self, pid, msg):
        t = msg.get("t")
        if t == "_join":
            return
        if t == "hello":
            if msg.get("v") != net.PROTOCOL:
                return
            hero = sanitize_hero(msg.get("hero") or {})
            if hero is None:
                self.server.kick(pid)
                return
            self.heroes[pid] = hero
            me = self.me()
            k = len(self.players)
            x, y = self.world.map.nearest_free(me["x"], me["y"], self.flags, k=k)
            pl = self.make_player(hero, x, y, DOWN)
            self.players[pid] = pl
            welcome = {"t": "welcome", "pid": pid, "flags": sorted(self.flags),
                       "chests": sorted(self.chests), "map": self.world.map.id,
                       "players": {str(k2): v for k2, v in self.players.items()}}
            if self.battle is not None:
                welcome["battle"] = self.battle.snapshot()
            self.server.send(pid, welcome)
            self.server.broadcast({"t": "player", "pid": pid, "p": pl}, exclude=pid)
            self.toast(f"👋 {hero['name']} bergabung!", 3)
            self.sfx("bell")
            return
        if pid != self.pid and pid not in self.heroes:
            return                      # belum menyapa
        if t == "_leave":
            name = self.players.get(pid, {}).get("name", "Teman")
            self.players.pop(pid, None)
            self.heroes.pop(pid, None)
            if self.battle is not None:
                self.battle.remove_player(pid)
            self.emit({"t": "leave", "pid": pid})
            self.toast(f"👋 {name} keluar.", 3)
        elif t == "hero":
            hero = sanitize_hero(msg.get("hero") or {})
            if hero is None:
                return
            if pid == self.pid:
                hero = self.hero
            self.heroes[pid] = hero
            pl = self.players.get(pid)
            if pl:
                st = data.derive_stats(hero)
                pl.update(name=hero["name"], look=data.look_of(hero), level=hero["level"],
                          cls=hero["cls"], hp=hero["hp"], mhp=st["hp"])
                if self.server:
                    self.server.broadcast({"t": "player", "pid": pid, "p": pl}, exclude=pid)
        elif t == "pos":
            pl = self.players.get(pid)
            if pl is None or pid == self.pid:
                return
            try:
                pl.update(x=int(msg["x"]), y=int(msg["y"]), d=msg.get("d", DOWN),
                          map=msg.get("map"))
            except (KeyError, TypeError, ValueError):
                return
            if self.server:
                out = dict(msg, pid=pid)
                self.server.broadcast(out, exclude=pid)
        elif t == "warp":
            if self.battle is not None:
                return
            target = msg.get("map")
            if target not in data.MAPS:
                return
            self.emit({"t": "map", "map": target, "spawn": str(msg.get("spawn")),
                       "idx": int(msg.get("idx", 0)), "d": msg.get("d", DOWN)})
        elif t == "encounter":
            m = self.world.map
            if (self.battle is None and m.cfg.get("encounters")
                    and self.clock - self.last_battle_end > 3.0):
                group = random_group(m.id, len(self.heroes), random)
                self.start_battle(group)
        elif t == "flag":
            f = msg.get("f")
            if f in STORY_FLAGS and f not in self.flags:
                self.emit({"t": "flag", "f": f})
        elif t == "chest":
            cid = str(msg.get("id", ""))
            try:
                mid, idx = cid.split(":")
                data.MAPS[mid]["chests"][int(idx)]
            except (ValueError, KeyError, IndexError):
                return
            if cid not in self.chests:
                self.emit({"t": "chest", "id": cid, "pid": pid})
        elif t == "boss":
            eid = msg.get("eid")
            flag = BOSS_FLAGS.get(eid)
            if flag and flag not in self.flags and self.battle is None:
                self.start_battle([eid], boss=eid)
        elif t == "bcmd":
            if self.battle is not None and isinstance(msg.get("cmd"), dict):
                self.battle.submit(pid, msg["cmd"])
        elif t == "emote":
            try:
                i = int(msg.get("i", 0)) % len(data.EMOTES)
            except (TypeError, ValueError):
                return
            self.emit({"t": "emote", "pid": pid, "i": i})

    # -- tuan rumah: pertarungan -------------------------------------------------
    def start_battle(self, enemies, boss=None):
        heroes = {pid: self.heroes[pid] for pid in sorted(self.players) if pid in self.heroes}
        if not heroes:
            return
        bg = self.world.map.cfg.get("battle_bg", "padang")
        self.battle = Battle(heroes, enemies, bg=bg, boss=boss, coop=len(heroes) > 1)
        self.battle_boss = boss
        self.battle_end_at = None
        self._snap_t = 0.0
        self.emit({"t": "battle", "snap": self.battle.snapshot()})

    def host_battle_tick(self, dt):
        b = self.battle
        b.update(dt)
        for ev in b.events:
            self.emit({"t": "bev", "ev": ev})
        b.events.clear()
        self._snap_t += dt
        if self._snap_t >= 0.15:
            self._snap_t = 0.0
            self.emit({"t": "bsnap", "snap": b.snapshot()})
        if b.state != "run":
            if self.battle_end_at is None:
                self.battle_end_at = self.clock + max(0.0, b.busy) + 0.4
            elif self.clock >= self.battle_end_at:
                res = {str(pid): b.result_for(pid) for pid in self.heroes
                       if b.hero_of(pid) is not None}
                won_boss = self.battle_boss if b.state == "win" else None
                self.battle = None
                self.last_battle_end = self.clock
                self.emit({"t": "bend", "snap": b.snapshot(), "res": res, "boss": won_boss})
                if won_boss and BOSS_FLAGS.get(won_boss) not in self.flags:
                    self.emit({"t": "flag", "f": BOSS_FLAGS[won_boss]})
                if b.state == "lose":
                    self.emit({"t": "map", "map": data.INN_MAP[0], "spawn": "@", "idx": 0,
                               "d": DOWN, "inn": True})

    # -- semua pemain: menerapkan pesan -------------------------------------------
    def apply(self, msg):
        t = msg.get("t")
        if t == "player":
            pid = int(msg["pid"])
            old = self.players.get(pid, {})
            new = dict(msg["p"])
            if old:
                new["px"], new["py"] = old.get("px", new["px"]), old.get("py", new["py"])
            self.players[pid] = new
        elif t == "leave":
            self.players.pop(int(msg["pid"]), None)
        elif t == "pos":
            pid = int(msg.get("pid", -1))
            if pid == self.pid or pid not in self.players:
                return
            pl = self.players[pid]
            pl.update(x=msg["x"], y=msg["y"], d=msg.get("d", DOWN), map=msg.get("map"))
        elif t == "map":
            self.enter_map(msg)
        elif t == "flag":
            self.flags.add(msg["f"])
        elif t == "chest":
            self.chests.add(msg["id"])
            self.open_chest(msg["id"], int(msg.get("pid", -1)) == self.pid)
        elif t == "battle":
            self.start_battle_view(msg["snap"])
        elif t == "bsnap":
            if self.battle_scene:
                self.battle_scene.set_snap(msg["snap"])
        elif t == "bev":
            if self.battle_scene:
                self.battle_scene.add_event(msg["ev"])
        elif t == "bend":
            self.end_battle_view(msg)
        elif t == "emote":
            pl = self.players.get(int(msg["pid"]))
            if pl is not None:
                pl["emote"] = data.EMOTES[int(msg["i"]) % len(data.EMOTES)]
                pl["emote_t"] = self.clock + 3.0
                self.sfx("key")

    def enter_map(self, msg):
        from .world import WorldMap
        map_id = msg["map"]
        same = self.world.map is not None and self.world.map.id == map_id
        m = self.world.map if same else WorldMap(map_id)
        d = msg.get("d", DOWN)
        if msg.get("inn"):
            pos = m.start_point()
        else:
            pos = m.arrival(msg.get("spawn"), msg.get("idx", 0), d, self.flags)
        rank = sorted(self.players).index(self.pid) if self.pid in self.players else 0
        if rank:
            pos = m.nearest_free(pos[0], pos[1], self.flags, k=rank)
        self.world.map = m
        if not same:
            self.world.banner = 2.6
            self.world.npc_face = {}
        self.world.load(map_id, pos, d)
        for pid, pl in self.players.items():
            pl["map"] = map_id
            if pid != self.pid:
                pl["x"], pl["y"] = pos
                pl["px"], pl["py"] = pos[0] * data.TILE, pos[1] * data.TILE
        self.send_pos(pos[0], pos[1], d, False)
        if msg.get("inn"):
            self.heal_full(sync=False)
        self.save_all()

    def open_chest(self, cid, mine):
        mid, idx = cid.split(":")
        content, n = data.MAPS[mid]["chests"][int(idx)]
        shared = content == "senjata_pelangi" or content in data.EQUIPMENT
        if not (mine or shared):
            return
        hero = self.hero
        if content == "gold":
            hero["gold"] += n
            label = f"{n} 🪙"
        elif content in data.ITEMS:
            hero["items"][content] = hero["items"].get(content, 0) + n
            label = f"{data.ITEMS[content]['name']} ×{n}"
        else:
            item = data.RAINBOW_WEAPON[hero["cls"]] if content == "senjata_pelangi" else content
            hero["gear"].append(item)
            label = data.item_name(item)
        self.sfx("star")
        self.toast(f"📦 Dapat {label}!", 3)
        self.hero_changed()

    def start_battle_view(self, snap):
        self.stop_speech()
        self._pop_overlays()
        if self.battle_scene in self.stack:
            self.pop(self.battle_scene)
        self.world.mouse_hold = False
        self.held_order.clear()
        self.battle_scene = BattleScene(self, snap)
        self.push(self.battle_scene)

    def end_battle_view(self, msg):
        res = (msg.get("res") or {}).get(str(self.pid))
        scene = self.battle_scene
        if res:
            hero = self.hero
            st = data.derive_stats(hero)
            hero["hp"] = max(0, min(int(res["hp"]), st["hp"]))
            hero["mp"] = max(0, min(int(res["mp"]), st["mp"]))
            ups = []
            if res.get("state") == "win":
                hero["gold"] += int(res.get("gold", 0))
                for it in res.get("items", []):
                    if it in data.ITEMS:
                        hero["items"][it] = hero["items"].get(it, 0) + 1
                ups = data.gain_exp(hero, int(res.get("exp", 0)))
            res = dict(res, levelups=ups)
            self.hero_changed()
        else:
            res = {"state": msg["snap"]["state"], "exp": 0, "gold": 0, "items": []}
        self.pending_after = msg.get("boss")
        if scene is not None and scene in self.stack:
            scene.set_snap(msg["snap"])
            scene.set_result(res)
        else:
            self.after_battle(res)

    def after_battle(self, result):
        self.waiting_battle_text = ""
        if self.world.map:
            self.music(self.world.map.cfg.get("music"))
        boss = self.pending_after
        self.pending_after = None
        if boss and boss in data.BOSS_AFTER:
            lines = data.BOSS_AFTER[boss]
            then = None
            if boss == "ratu_bayangan":
                then = lambda: self.push(S.StoryScene(self, list(data.ENDING), ending=True))
            self.say(lines, then)
        self.save_all()

    # -- aksi pemain ---------------------------------------------------------------
    def hero_changed(self):
        hero = self.hero
        if hero is None:
            return
        data.clamp_hero(hero)
        st = data.derive_stats(hero)
        me = self.me()
        me.update(name=hero["name"], look=data.look_of(hero), level=hero["level"],
                  cls=hero["cls"], hp=hero["hp"], mhp=st["hp"])
        if self.mode == "client" and self.client:
            self.client.send({"t": "hero", "hero": hero})
        elif self.mode in ("host", "solo"):
            self.heroes[self.pid] = hero
            if self.server:
                self.server.broadcast({"t": "player", "pid": self.pid, "p": me})
        self.save_all()

    def heal_full(self, sync=True):
        st = data.derive_stats(self.hero)
        self.hero["hp"], self.hero["mp"] = st["hp"], st["mp"]
        if sync:
            self.hero_changed()
        else:
            self.me().update(hp=st["hp"], mhp=st["hp"])

    def use_item_count(self, iid):
        items = self.hero["items"]
        if items.get(iid, 0) <= 0:
            return False
        items[iid] -= 1
        if items[iid] <= 0:
            del items[iid]
        return True

    def use_item_field(self, iid):
        it = data.ITEMS[iid]
        hero = self.hero
        st = data.derive_stats(hero)
        kind = it["kind"]
        if kind == "revive":
            self.toast("Bulu Semangat dipakai saat bertarung.")
            return False
        if kind in ("hp", "hp_all") and hero["hp"] >= st["hp"]:
            self.toast("HP-mu sudah penuh.")
            return False
        if kind == "mp" and hero["mp"] >= st["mp"]:
            self.toast("MP-mu sudah penuh.")
            return False
        if kind == "full" and hero["hp"] >= st["hp"] and hero["mp"] >= st["mp"]:
            self.toast("HP & MP sudah penuh.")
            return False
        if not self.use_item_count(iid):
            return False
        if kind in ("hp", "hp_all"):
            hero["hp"] = min(st["hp"], hero["hp"] + it["power"])
        elif kind == "mp":
            hero["mp"] = min(st["mp"], hero["mp"] + it["power"])
        else:
            hero["hp"], hero["mp"] = st["hp"], st["mp"]
        self.sfx("heal")
        self.toast(f"{it['icon']} {it['name']} dipakai!")
        self.hero_changed()
        return True

    def emote(self, i):
        self.request({"t": "emote", "i": i})

    def open_menu(self):
        if self.top() is self.world:
            self.push(S.MenuScene(self))

    def open_emotes(self):
        if self.top() is self.world:
            self.push(S.EmoteScene(self))

    # -- dialog & NPC ------------------------------------------------------------
    def _fmt(self, s):
        cls = data.CLASSES[self.hero["cls"]]["name"] if self.hero else ""
        name = self.hero["name"] if self.hero else ""
        return s.replace("{nama}", name).replace("{kelas}", cls)

    def _portrait(self, speaker):
        if self.hero and speaker == "{nama}":
            return sprites.hero_frames(data.look_of(self.hero))["portrait"]
        for npc in data.NPCS.values():
            if npc["name"] == speaker and "look" in npc:
                return sprites.hero_frames(npc["look"])["portrait"]
        return None

    def say(self, lines, then=None):
        full = [(self._fmt(sp), self._fmt(tx), self._portrait(sp)) for sp, tx in lines]
        self.push(S.DialogScene(self, full, then))

    def _cond(self, entry):
        return (all(f in self.flags for f in entry.get("if", []))
                and not any(f in self.flags for f in entry.get("not", [])))

    def choose_talk(self, npc):
        talks = npc["talk"]
        seen = self.hero.setdefault("seen", [])
        # bagian cerita yang sudah terjadi di dunia ini tetapi belum didengar pemain ini
        for entry in reversed(talks):
            fl = [a[1] for a in entry.get("do", []) if a[0] == "flag"]
            if fl and all(f in self.flags for f in fl) and not all(f in seen for f in fl) \
                    and self._cond(entry):
                return entry
        for entry in talks:
            if self._cond(entry):
                return entry
        return talks[-1]

    def talk(self, npc_id):
        npc = data.NPCS[npc_id]
        entry = self.choose_talk(npc)
        self.sfx("pop")
        self.say(entry["lines"], lambda: self.run_actions(entry.get("do", [])))

    def run_actions(self, actions):
        changed = False
        hero = self.hero
        for act in actions:
            kind = act[0]
            if kind == "flag":
                if act[1] not in hero["seen"]:
                    hero["seen"].append(act[1])
                self.request({"t": "flag", "f": act[1]})
                changed = True
            elif kind == "item":
                hero["items"][act[1]] = hero["items"].get(act[1], 0) + act[2]
                self.toast(f"🎁 Dapat {data.item_name(act[1])} ×{act[2]}!", 3)
                self.sfx("star")
                changed = True
            elif kind == "gold":
                hero["gold"] += act[1]
                self.toast(f"🎁 Dapat {act[1]} 🪙!", 3)
                changed = True
            elif kind == "inn":
                self.heal_full(sync=False)
                self.sfx("tada")
                self.toast("😴 Tidur nyenyak... HP & MP pulih penuh!", 3)
                changed = True
            elif kind == "heal":
                self.heal_full(sync=False)
                self.sfx("heal")
                self.toast("✨ HP & MP pulih penuh!", 3)
                changed = True
            elif kind == "shop":
                self.push(S.ShopScene(self, act[1]))
            elif kind == "boss":
                self.request({"t": "boss", "eid": act[1]})
            elif kind == "class":
                self.push(S.ClassScene(self))
            elif kind == "board":
                self.push(S.BoardScene(self))
        if changed:
            self.hero_changed()

    # -- info ----------------------------------------------------------------------
    def lobby_info(self):
        if self.mode == "host":
            ips = ", ".join(net.local_ips())
            return (f"🌐 Lobi terbuka ({len(self.players)}/{data.MAX_PLAYERS} pemain). Teman "
                    f"di Wi-Fi yang sama pilih 'Gabung Lobi Teman'. Alamat komputer ini: {ips}")
        if self.mode == "client":
            host = self.players.get(0, {}).get("name", "temanmu")
            return f"🤝 Kamu bermain di dunia milik {host}. Kemajuan cerita disimpan di sana, " \
                   f"level & barangmu disimpan di komputermu."
        return ("Kamu main sendiri. Untuk main bareng teman, kembali ke layar judul lalu pilih "
                "'Buat Lobi'. Teman memilih 'Gabung Lobi Teman'.")

    def quest_hint(self):
        f = self.flags
        if "tamat" in f:
            return "🌈 Cerita tamat! Terus berpetualang & naikkan level."
        if "misi3" in f:
            return "Tujuan: Menara Awan (barat Padang Rumput). Temui Ratu Bayangan."
        if "pecahan_biru" in f:
            return "Tujuan: laporkan Pecahan Biru ke Tetua Bijak."
        if "misi2" in f:
            return "Tujuan: Gua Kristal di utara Padang Rumput."
        if "pecahan_hijau" in f:
            return "Tujuan: laporkan Pecahan Hijau ke Tetua Bijak."
        if "misi1" in f:
            return "Tujuan: Hutan Bisik di timur Padang Rumput."
        return "Tujuan: temui Tetua Bijak di dekat air mancur Desa Daun."
