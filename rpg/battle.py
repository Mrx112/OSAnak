# -*- coding: utf-8 -*-
"""
Logika pertarungan ala Final Fantasy (ATB: bar waktu aktif).

Murni Python (tanpa Qt), dijalankan oleh tuan rumah (host) saja. Pemain lain
mengirim perintah lewat jaringan dan menerima "snapshot" + "event" untuk
dianimasikan. Main sendiri = host tanpa tamu.
"""

import random

from . import data

ATB_FULL = 100.0
DUR_ATTACK = 0.95
DUR_SKILL = 1.25
DUR_MSG = 0.9


class Battle:
    def __init__(self, heroes, enemy_ids, bg="padang", boss=None, coop=False, seed=None):
        """heroes: {pid: data pahlawan}. boss: id musuh bos (tidak bisa kabur)."""
        self.rng = random.Random(seed)
        self.bg = bg
        self.boss = boss
        self.coop = coop
        self.units = []
        self.events = []          # event baru (diambil & disebar oleh host)
        self.busy = 0.0           # waktu animasi aksi yang sedang berjalan
        self.queue = []           # aksi menunggu giliran: (uid, cmd)
        self.state = "run"        # run / win / lose / fled
        self.rewards = {}
        self.flee_tries = 0
        self.elapsed = 0.0
        n = len(heroes)
        for pid, hero in heroes.items():
            self.add_hero(pid, hero)
        for i, eid in enumerate(enemy_ids):
            e = data.scale_enemy(eid, n)
            self.units.append({
                "uid": f"e{i}", "side": "enemy", "eid": eid, "name": e["name"],
                "hp": e["hp"], "mhp": e["hp"], "mp": 0, "mmp": 0,
                "atk": e["atk"], "dfn": e["dfn"], "mag": e["mag"], "spd": e["spd"],
                "weak": e.get("weak", []), "resist": e.get("resist", []),
                "skills": e.get("skills", []), "boss": bool(e.get("boss")),
                "atb": self.rng.uniform(0, 45), "ko": False, "st": {}, "ready": False,
            })
        # nama unik bila ada musuh kembar: "Slime Hijau A", "Slime Hijau B"
        names = {}
        for u in self.enemies():
            names.setdefault(u["name"], []).append(u)
        for same in names.values():
            if len(same) > 1:
                for k, u in enumerate(same):
                    u["name"] = f"{u['name']} {'ABCDE'[k]}"

    # -- pembantu -------------------------------------------------------------
    def add_hero(self, pid, hero):
        st = data.derive_stats(hero)
        self.units.append({
            "uid": f"h{pid}", "side": "hero", "pid": pid, "name": hero["name"],
            "cls": hero["cls"], "level": hero["level"], "look": data.look_of(hero),
            "hp": max(0, min(hero["hp"], st["hp"])), "mhp": st["hp"],
            "mp": max(0, min(hero["mp"], st["mp"])), "mmp": st["mp"],
            "atk": st["atk"], "dfn": st["dfn"], "mag": st["mag"], "spd": st["spd"],
            "skills": data.class_skills(hero["cls"], hero["level"]),
            "weak": [], "resist": [], "atb": self.rng.uniform(20, 60),
            "ko": hero["hp"] <= 0, "st": {}, "ready": False, "gone": False,
        })

    def unit(self, uid):
        for u in self.units:
            if u["uid"] == uid:
                return u
        return None

    def heroes(self):
        return [u for u in self.units if u["side"] == "hero" and not u.get("gone")]

    def enemies(self):
        return [u for u in self.units if u["side"] == "enemy"]

    def alive(self, side):
        pool = self.heroes() if side == "hero" else self.enemies()
        return [u for u in pool if not u["ko"]]

    def hero_of(self, pid):
        return self.unit(f"h{pid}")

    def remove_player(self, pid):
        u = self.hero_of(pid)
        if u:
            u["gone"] = True
            u["ready"] = False
            self.queue = [(uid, c) for uid, c in self.queue if uid != u["uid"]]
            self._check_end()

    def emit(self, ev):
        self.events.append(ev)

    # -- jalannya waktu -------------------------------------------------------
    def update(self, dt):
        if self.state != "run":
            return
        self.elapsed += dt
        if self.busy > 0:
            self.busy -= dt
            return
        if self.queue:
            uid, cmd = self.queue.pop(0)
            u = self.unit(uid)
            if u and not u["ko"] and not u.get("gone"):
                self._execute(u, cmd)
                self._check_end()
            return
        waiting = any(u["ready"] for u in self.heroes())
        if waiting and not self.coop:
            return                              # mode tunggu saat main sendiri
        speed = 0.85 if self.coop else 1.0
        for u in self.units:
            if u["ko"] or u.get("gone") or u["ready"]:
                continue
            u["atb"] += (u["spd"] + 26) * dt * speed
            if u["atb"] >= ATB_FULL:
                u["atb"] = ATB_FULL
                self._turn_start(u)
                if self.queue:
                    break

    def _turn_start(self, u):
        st = u["st"]
        st.pop("guard", None)
        if st.get("tidur"):
            st["tidur"] -= 1
            if st["tidur"] <= 0:
                st.pop("tidur")
                self.emit({"t": "msg", "text": f"{u['name']} bangun!", "dur": DUR_MSG})
            else:
                self.emit({"t": "msg", "text": f"{u['name']} masih tidur... 💤", "dur": DUR_MSG})
            u["atb"] = 0
            self.busy = DUR_MSG
            return
        for key in ("def", "atk"):
            if st.get(key):
                st[key] -= 1
                if st[key] <= 0:
                    st.pop(key)
        if u["side"] == "hero":
            u["ready"] = True
        else:
            self.queue.append((u["uid"], self._enemy_ai(u)))

    def _enemy_ai(self, u):
        for chance, sk in u["skills"]:
            if self.rng.random() < chance:
                return {"act": "eskill", "skill": sk}
        return {"act": "attack"}

    # -- perintah pemain ----------------------------------------------------
    def submit(self, pid, cmd):
        u = self.hero_of(pid)
        if not u or not u["ready"] or u["ko"] or self.state != "run":
            return False
        act = cmd.get("act")
        if act == "skill":
            sk = data.SKILLS.get(cmd.get("skill"))
            if not sk or cmd["skill"] not in u["skills"] or u["mp"] < sk["mp"]:
                return False
        elif act not in ("attack", "item", "guard", "flee"):
            return False
        u["ready"] = False
        self.queue.append((u["uid"], dict(cmd)))
        return True

    # -- menghitung aksi ----------------------------------------------------
    def _pick(self, side, want=None, allow_ko=False):
        if want:
            t = self.unit(want)
            if t and t["side"] == side and not t.get("gone") and t["ko"] == allow_ko:
                return t
        pool = [x for x in (self.heroes() if side == "hero" else self.enemies())
                if x["ko"] == allow_ko]
        return self.rng.choice(pool) if pool else None

    def _phys(self, src, dst, power, elem=None):
        atk = src["atk"] * (1.25 if src["st"].get("atk") else 1.0)
        dmg = atk * power * 28.0 / (28.0 + dst["dfn"]) * self.rng.uniform(0.9, 1.1)
        hit = {"dst": dst["uid"]}
        if self.rng.random() < 0.05 and src["side"] == "enemy":
            hit["miss"] = True
            return hit
        if self.rng.random() < 0.08:
            dmg *= 1.5
            hit["crit"] = True
        return self._finish_damage(dst, dmg, elem, hit, wake=True)

    def _magic(self, src, dst, power, elem=None):
        base = src["mag"] * 1.1 + power
        dmg = base * 30.0 / (30.0 + dst["dfn"] * 0.5) * self.rng.uniform(0.92, 1.08)
        return self._finish_damage(dst, dmg, elem, {"dst": dst["uid"]}, wake=False)

    def _finish_damage(self, dst, dmg, elem, hit, wake):
        if elem and elem in dst.get("weak", []):
            dmg *= 1.5
            hit["weak"] = True
        elif elem and elem in dst.get("resist", []):
            dmg *= 0.5
            hit["resist"] = True
        if dst["st"].get("guard"):
            dmg *= 0.5
        if dst["st"].get("def"):
            dmg *= 0.6
        dmg = max(1, int(round(dmg)))
        dst["hp"] = max(0, dst["hp"] - dmg)
        hit["dmg"] = dmg
        if wake and dst["st"].pop("tidur", None):
            hit["wake"] = True
        if dst["hp"] <= 0:
            dst["ko"] = True
            dst["ready"] = False
            dst["st"] = {}
            dst["atb"] = 0
            hit["ko"] = True
        return hit

    def _heal(self, dst, amount):
        amount = int(amount)
        before = dst["hp"]
        dst["hp"] = min(dst["mhp"], dst["hp"] + amount)
        return {"dst": dst["uid"], "heal": dst["hp"] - before}

    def _execute(self, u, cmd):
        act = cmd.get("act")
        u["atb"] = 0
        ev = {"t": "act", "src": u["uid"], "hits": [], "dur": DUR_ATTACK}
        if act == "attack":
            side = "enemy" if u["side"] == "hero" else "hero"
            t = self._pick(side, cmd.get("target"))
            if not t:
                return
            ev.update(name="Serang", fx="hit", kind="attack")
            ev["hits"].append(self._phys(u, t, 1.0))

        elif act == "guard":
            u["st"]["guard"] = 1
            ev.update(name="Bertahan", fx="shield", kind="guard", dur=DUR_MSG)
            ev["hits"].append({"dst": u["uid"], "buff": "guard"})

        elif act == "flee":
            ev.update(name="Kabur", fx="flee", kind="flee", dur=DUR_MSG)
            if self.boss:
                ev["text"] = "Tidak bisa kabur dari bos!"
            elif self.rng.random() < 0.6 + 0.15 * self.flee_tries:
                ev["text"] = "Berhasil kabur!"
                self.state = "fled"
            else:
                ev["text"] = "Gagal kabur!"
            self.flee_tries += 1

        elif act == "item":
            it = data.ITEMS.get(cmd.get("item"))
            if not it:
                return
            ev.update(name=it["name"], fx="heal", kind="item", dur=DUR_SKILL)
            if it["kind"] == "hp_all":
                for t in self.alive("hero"):
                    ev["hits"].append(self._heal(t, it["power"]))
            elif it["kind"] == "revive":
                t = self._pick("hero", cmd.get("target"), allow_ko=True)
                if t:
                    t["ko"] = False
                    t["hp"] = max(1, int(t["mhp"] * it["power"]))
                    t["atb"] = 0
                    ev["hits"].append({"dst": t["uid"], "heal": t["hp"], "revive": True})
                else:
                    ev["text"] = "Tidak ada yang pingsan."
            else:
                t = self._pick("hero", cmd.get("target"))
                if t:
                    if it["kind"] == "hp":
                        ev["hits"].append(self._heal(t, it["power"]))
                    elif it["kind"] == "mp":
                        before = t["mp"]
                        t["mp"] = min(t["mmp"], t["mp"] + it["power"])
                        ev["hits"].append({"dst": t["uid"], "mp": t["mp"] - before})
                    elif it["kind"] == "full":
                        h = self._heal(t, t["mhp"])
                        t["mp"] = t["mmp"]
                        ev["hits"].append(h)

        elif act == "skill":
            sk = data.SKILLS[cmd["skill"]]
            u["mp"] -= sk["mp"]
            ev.update(name=sk["name"], fx=sk["fx"], kind="skill", dur=DUR_SKILL)
            self._skill(u, sk, cmd.get("target"), ev, hero=True)

        elif act == "eskill":
            sk = data.ENEMY_SKILLS[cmd["skill"]]
            ev.update(name=sk["name"], fx=sk["fx"], kind="skill", dur=DUR_SKILL)
            self._skill(u, sk, None, ev, hero=False)
        else:
            return
        self.busy = ev["dur"]
        self.emit(ev)

    def _skill(self, u, sk, target, ev, hero):
        foe = "enemy" if hero else "hero"
        tgt = sk["target"]
        if tgt in ("enemy", "hero"):
            t = self._pick(foe, target)
            targets = [t] if t else []
        elif tgt in ("all_enemies", "all_heroes"):
            targets = self.alive(foe)
        elif tgt == "ally":
            t = self._pick("hero", target)
            targets = [t] if t else []
        elif tgt == "ally_ko":
            t = self._pick("hero", target, allow_ko=True)
            targets = [t] if t else []
        else:   # party
            targets = self.alive("hero")
        if not targets:
            ev["text"] = "Tidak ada sasaran."
            return
        kind = sk["kind"]
        for t in targets:
            if kind == "phys":
                for _ in range(sk.get("hits", 1)):
                    if not t["ko"]:
                        ev["hits"].append(self._phys(u, t, sk["power"], sk.get("elem")))
            elif kind == "magic":
                ev["hits"].append(self._magic(u, t, sk["power"], sk.get("elem")))
            elif kind == "heal":
                ev["hits"].append(self._heal(t, u["mag"] * 1.4 + sk["power"]))
            elif kind == "revive":
                t["ko"] = False
                t["hp"] = max(1, int(t["mhp"] * sk["power"]))
                t["atb"] = 0
                ev["hits"].append({"dst": t["uid"], "heal": t["hp"], "revive": True})
            elif kind == "buff":
                t["st"][sk["buff"]] = sk.get("turns", 3) + (1 if t is u else 0)
                ev["hits"].append({"dst": t["uid"], "buff": sk["buff"]})
            elif kind == "status":
                resist = t.get("boss") and sk["status"] == "tidur"
                chance = sk["chance"] * (0.35 if resist else 1.0)
                if self.rng.random() < chance:
                    t["st"]["tidur"] = self.rng.randint(1, 2) if t["side"] == "hero" else \
                        self.rng.randint(2, 3)
                    t["ready"] = False
                    if t["side"] == "hero":
                        t["atb"] = min(t["atb"], ATB_FULL - 1)
                        self.queue = [(q, c) for q, c in self.queue if q != t["uid"]]
                    ev["hits"].append({"dst": t["uid"], "status": "tidur"})
                else:
                    ev["hits"].append({"dst": t["uid"], "miss": True})

    # -- akhir pertarungan ----------------------------------------------------
    def _check_end(self):
        if self.state != "run":
            return
        if not self.alive("enemy"):
            self.state = "win"
            exp = sum(data.ENEMIES[e["eid"]]["exp"] for e in self.enemies())
            gold = sum(data.ENEMIES[e["eid"]]["gold"] for e in self.enemies())
            for h in self.heroes():
                items = []
                for e in self.enemies():
                    drop = data.ENEMIES[e["eid"]].get("drop")
                    if drop and self.rng.random() < drop[1]:
                        items.append(drop[0])
                self.rewards[h["pid"]] = {"exp": exp, "gold": gold, "items": items}
        elif not self.alive("hero"):
            self.state = "lose"

    def result_for(self, pid):
        """HP/MP akhir + hadiah untuk satu pemain."""
        u = self.hero_of(pid)
        if u is None:
            return None
        out = {"state": self.state, "hp": u["hp"], "mp": u["mp"]}
        if self.state == "win":
            out.update(self.rewards.get(pid, {"exp": 0, "gold": 0, "items": []}))
            if u["ko"]:
                out["hp"] = 1                      # pingsan -> bangun dengan 1 HP
        elif self.state == "lose":
            out["hp"] = u["mhp"]                   # dibawa pulang & disembuhkan
            out["mp"] = u["mmp"]
        return out

    # -- dikirim ke pemain ----------------------------------------------------
    def snapshot(self):
        units = []
        for u in self.units:
            s = {"uid": u["uid"], "side": u["side"], "name": u["name"], "hp": u["hp"],
                 "mhp": u["mhp"], "mp": u["mp"], "mmp": u["mmp"], "atb": round(u["atb"], 1),
                 "ko": u["ko"], "st": dict(u["st"]), "ready": u["ready"]}
            if u["side"] == "hero":
                s.update(pid=u["pid"], look=u["look"], skills=u["skills"], cls=u["cls"],
                         gone=u.get("gone", False))
            else:
                s.update(eid=u["eid"], boss=u["boss"])
            units.append(s)
        return {"units": units, "state": self.state, "bg": self.bg, "boss": self.boss,
                "coop": self.coop}


def random_group(map_id, n_heroes, rng):
    enc = data.MAPS[map_id]["encounters"]
    group = list(rng.choice(enc["groups"]))
    pool = sorted({e for g in enc["groups"] for e in g})
    for _ in range(max(0, n_heroes - 1)):
        if len(group) < 5:
            group.append(rng.choice(pool))
    return group
