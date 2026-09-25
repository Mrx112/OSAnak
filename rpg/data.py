# -*- coding: utf-8 -*-
"""
Data permainan "Legenda Kristal Pelangi": kelas, perlengkapan, barang,
musuh, peta dunia, dan cerita. Tidak ada kode Qt di sini.
"""

import math

GAME_TITLE = "Legenda Kristal Pelangi"
MAX_LEVEL = 30
MAX_PLAYERS = 4
TILE = 16

# ---------------------------------------------------------------------------
# TAMPILAN KARAKTER
# ---------------------------------------------------------------------------

SKINS = ["#FFE3C8", "#F3C49C", "#D39A6A", "#9A6440"]
HAIR_COLORS = [
    ("Cokelat", "#6B4430"), ("Hitam", "#2A2433"), ("Pirang", "#F0CB5C"),
    ("Merah", "#D9542B"), ("Biru", "#5C86F2"), ("Merah Muda", "#FF8FC8"),
    ("Perak", "#E3E3EE"), ("Hijau", "#5CC870"),
]
OUTFIT_COLORS = [
    ("Merah", "#E0405E"), ("Biru", "#3E7BE0"), ("Hijau", "#3FAE5A"),
    ("Kuning", "#F2B632"), ("Ungu", "#9A5BE0"), ("Oranye", "#FF8A3D"),
    ("Toska", "#2FB5A0"), ("Merah Muda", "#F07FB8"),
]
HAIR_STYLES = [("pendek", "Pendek"), ("jabrik", "Jabrik"), ("panjang", "Panjang"),
               ("kuncir", "Kuncir"), ("keriting", "Keriting")]
HATS = [(None, "Tanpa Topi"), ("pita", "Pita"), ("topi_penyihir", "Topi Penyihir"),
        ("bandana", "Bandana"), ("mahkota_bunga", "Mahkota Bunga"), ("helm", "Helm")]

RANDOM_NAMES = ["Arga", "Bintang", "Citra", "Dimas", "Eka", "Fajar", "Gita", "Hana",
                "Intan", "Jaka", "Kirana", "Laras", "Mega", "Nara", "Oka", "Putri",
                "Raka", "Sekar", "Tara", "Wulan", "Yuda", "Zahra"]

# ---------------------------------------------------------------------------
# KELAS
# ---------------------------------------------------------------------------
# stat: hp mp atk dfn mag spd. "grow" = tambahan per level.

CLASSES = {
    "kesatria": {
        "name": "Kesatria", "icon": "🛡️", "weapon": "pedang",
        "armor": ("ringan", "berat"),
        "desc": "Kuat & tahan pukulan. Pelindung teman-temannya.",
        "base": {"hp": 62, "mp": 10, "atk": 12, "dfn": 10, "mag": 4, "spd": 7},
        "grow": {"hp": 13, "mp": 2, "atk": 2.6, "dfn": 2.2, "mag": 0.8, "spd": 1.0},
        "skills": [(1, "tebasan"), (3, "perisai"), (6, "putaran"), (10, "tebasan_cahaya"),
                   (15, "benteng")],
    },
    "penyihir": {
        "name": "Penyihir", "icon": "🔮", "weapon": "tongkat",
        "armor": ("ringan", "jubah"),
        "desc": "Menguasai sihir api, es & petir. Musuh takut!",
        "base": {"hp": 40, "mp": 24, "atk": 5, "dfn": 5, "mag": 13, "spd": 8},
        "grow": {"hp": 8, "mp": 5, "atk": 1.0, "dfn": 1.2, "mag": 3.0, "spd": 1.2},
        "skills": [(1, "api"), (2, "es"), (4, "petir"), (8, "badai_api"), (12, "hujan_bintang")],
    },
    "pemanah": {
        "name": "Pemanah", "icon": "🏹", "weapon": "busur",
        "armor": ("ringan",),
        "desc": "Cepat & jitu. Panahnya bisa menidurkan musuh.",
        "base": {"hp": 50, "mp": 12, "atk": 10, "dfn": 7, "mag": 6, "spd": 12},
        "grow": {"hp": 10.5, "mp": 2.5, "atk": 2.5, "dfn": 1.6, "mag": 1.2, "spd": 2.0},
        "skills": [(1, "panah_ganda"), (3, "panah_tidur"), (7, "hujan_panah"),
                   (11, "panah_angin")],
    },
    "penyembuh": {
        "name": "Penyembuh", "icon": "💖", "weapon": "tongkat_suci",
        "armor": ("ringan", "jubah"),
        "desc": "Menyembuhkan & membangunkan teman yang pingsan.",
        "base": {"hp": 46, "mp": 22, "atk": 6, "dfn": 6, "mag": 11, "spd": 9},
        "grow": {"hp": 9.5, "mp": 4.5, "atk": 1.2, "dfn": 1.5, "mag": 2.6, "spd": 1.3},
        "skills": [(1, "sembuh"), (2, "cahaya"), (4, "bangkit"), (6, "sembuh_semua"),
                   (9, "berkat")],
    },
}
CLASS_ORDER = ["kesatria", "penyihir", "pemanah", "penyembuh"]

# kind: phys (pakai atk) / magic (pakai mag) / heal / revive / buff / status
# target: enemy, all_enemies, ally, ally_ko, party
SKILLS = {
    "tebasan": {"name": "Tebasan Kuat", "mp": 3, "kind": "phys", "power": 1.7,
                "target": "enemy", "fx": "slash"},
    "perisai": {"name": "Perisai", "mp": 4, "kind": "buff", "buff": "def",
                "target": "party", "fx": "shield"},
    "putaran": {"name": "Putaran Pedang", "mp": 6, "kind": "phys", "power": 1.15,
                "target": "all_enemies", "fx": "slash"},
    "tebasan_cahaya": {"name": "Tebasan Cahaya", "mp": 10, "kind": "phys", "power": 2.7,
                       "elem": "cahaya", "target": "enemy", "fx": "holy"},
    "benteng": {"name": "Benteng Baja", "mp": 12, "kind": "buff", "buff": "def",
                "target": "party", "fx": "shield", "turns": 6},
    "api": {"name": "Api", "mp": 3, "kind": "magic", "power": 14, "elem": "api",
            "target": "enemy", "fx": "fire"},
    "es": {"name": "Es", "mp": 3, "kind": "magic", "power": 14, "elem": "es",
           "target": "enemy", "fx": "ice"},
    "petir": {"name": "Petir", "mp": 5, "kind": "magic", "power": 20, "elem": "petir",
              "target": "enemy", "fx": "bolt"},
    "badai_api": {"name": "Badai Api", "mp": 9, "kind": "magic", "power": 22, "elem": "api",
                  "target": "all_enemies", "fx": "fire"},
    "hujan_bintang": {"name": "Hujan Bintang", "mp": 16, "kind": "magic", "power": 42,
                      "target": "all_enemies", "fx": "star"},
    "panah_ganda": {"name": "Panah Ganda", "mp": 3, "kind": "phys", "power": 0.85, "hits": 2,
                    "target": "enemy", "fx": "arrow"},
    "panah_tidur": {"name": "Panah Tidur", "mp": 4, "kind": "status", "status": "tidur",
                    "chance": 0.75, "target": "enemy", "fx": "sleep"},
    "hujan_panah": {"name": "Hujan Panah", "mp": 7, "kind": "phys", "power": 0.95,
                    "target": "all_enemies", "fx": "arrow"},
    "panah_angin": {"name": "Panah Angin", "mp": 9, "kind": "phys", "power": 2.4,
                    "elem": "angin", "target": "enemy", "fx": "wind"},
    "sembuh": {"name": "Sembuh", "mp": 3, "kind": "heal", "power": 30,
               "target": "ally", "fx": "heal"},
    "cahaya": {"name": "Cahaya Suci", "mp": 4, "kind": "magic", "power": 16, "elem": "cahaya",
               "target": "enemy", "fx": "holy"},
    "bangkit": {"name": "Bangkit", "mp": 8, "kind": "revive", "power": 0.5,
                "target": "ally_ko", "fx": "heal"},
    "sembuh_semua": {"name": "Sembuh Semua", "mp": 9, "kind": "heal", "power": 26,
                     "target": "party", "fx": "heal"},
    "berkat": {"name": "Berkat", "mp": 7, "kind": "buff", "buff": "atk",
               "target": "party", "fx": "buff"},
}

ELEMENT_NAMES = {"api": "Api", "es": "Es", "petir": "Petir", "angin": "Angin",
                 "cahaya": "Cahaya"}

# ---------------------------------------------------------------------------
# BARANG & PERLENGKAPAN
# ---------------------------------------------------------------------------

ITEMS = {
    "ramuan": {"name": "Ramuan", "icon": "🧪", "kind": "hp", "power": 60, "price": 12,
               "desc": "Pulihkan 60 HP satu teman."},
    "ramuan_besar": {"name": "Ramuan Besar", "icon": "🍶", "kind": "hp", "power": 200,
                     "price": 45, "desc": "Pulihkan 200 HP satu teman."},
    "eter": {"name": "Eter", "icon": "💧", "kind": "mp", "power": 25, "price": 35,
             "desc": "Pulihkan 25 MP satu teman."},
    "bulu": {"name": "Bulu Semangat", "icon": "🪶", "kind": "revive", "power": 0.4,
             "price": 70, "desc": "Bangunkan teman yang pingsan."},
    "permen": {"name": "Permen Pelangi", "icon": "🍬", "kind": "hp_all", "power": 80,
               "price": 90, "desc": "Pulihkan 80 HP semua teman."},
    "apel": {"name": "Apel Emas", "icon": "🍎", "kind": "full", "power": 1,
             "price": 250, "desc": "Pulihkan HP & MP penuh satu teman."},
}
ITEM_ORDER = ["ramuan", "ramuan_besar", "eter", "bulu", "permen", "apel"]

# slot: weapon / armor / acc. "look" = cara digambar di sprite.
EQUIPMENT = {
    # --- pedang (Kesatria)
    "pedang_kayu": {"name": "Pedang Kayu", "slot": "weapon", "type": "pedang",
                    "bonus": {"atk": 3}, "price": 0, "look": "#B98A55"},
    "pedang_besi": {"name": "Pedang Besi", "slot": "weapon", "type": "pedang",
                    "bonus": {"atk": 8}, "price": 90, "look": "#C9D3E6"},
    "pedang_kristal": {"name": "Pedang Kristal", "slot": "weapon", "type": "pedang",
                       "bonus": {"atk": 16}, "price": 380, "look": "#8FE3FF"},
    "pedang_pelangi": {"name": "Pedang Pelangi", "slot": "weapon", "type": "pedang",
                       "bonus": {"atk": 28, "mag": 5}, "price": 0, "look": "rainbow"},
    # --- tongkat (Penyihir)
    "tongkat_kayu": {"name": "Tongkat Kayu", "slot": "weapon", "type": "tongkat",
                     "bonus": {"mag": 3, "atk": 1}, "price": 0, "look": "#E0405E"},
    "tongkat_bintang": {"name": "Tongkat Bintang", "slot": "weapon", "type": "tongkat",
                        "bonus": {"mag": 8, "atk": 2}, "price": 90, "look": "#FFD93D"},
    "tongkat_kristal": {"name": "Tongkat Kristal", "slot": "weapon", "type": "tongkat",
                        "bonus": {"mag": 15, "atk": 3}, "price": 380, "look": "#8FE3FF"},
    "tongkat_pelangi": {"name": "Tongkat Pelangi", "slot": "weapon", "type": "tongkat",
                        "bonus": {"mag": 26, "atk": 5, "mp": 20}, "price": 0, "look": "rainbow"},
    # --- busur (Pemanah)
    "busur_kayu": {"name": "Busur Kayu", "slot": "weapon", "type": "busur",
                   "bonus": {"atk": 3}, "price": 0, "look": "#B98A55"},
    "busur_pemburu": {"name": "Busur Pemburu", "slot": "weapon", "type": "busur",
                      "bonus": {"atk": 8, "spd": 1}, "price": 90, "look": "#6B8E3A"},
    "busur_angin": {"name": "Busur Angin", "slot": "weapon", "type": "busur",
                    "bonus": {"atk": 15, "spd": 3}, "price": 380, "look": "#8FE3FF"},
    "busur_pelangi": {"name": "Busur Pelangi", "slot": "weapon", "type": "busur",
                      "bonus": {"atk": 27, "spd": 5}, "price": 0, "look": "rainbow"},
    # --- tongkat suci (Penyembuh)
    "tongkat_bunga": {"name": "Tongkat Bunga", "slot": "weapon", "type": "tongkat_suci",
                      "bonus": {"mag": 2, "atk": 2}, "price": 0, "look": "#FF8FC8"},
    "tongkat_doa": {"name": "Tongkat Doa", "slot": "weapon", "type": "tongkat_suci",
                    "bonus": {"mag": 7, "atk": 4}, "price": 90, "look": "#FFFFFF"},
    "tongkat_cahaya": {"name": "Tongkat Cahaya", "slot": "weapon", "type": "tongkat_suci",
                       "bonus": {"mag": 13, "atk": 6}, "price": 380, "look": "#FFE57A"},
    "tongkat_pelangi_suci": {"name": "Tongkat Pelangi Suci", "slot": "weapon",
                             "type": "tongkat_suci", "bonus": {"mag": 22, "atk": 9, "hp": 40},
                             "price": 0, "look": "rainbow"},
    # --- baju
    "baju_kain": {"name": "Baju Kain", "slot": "armor", "type": "ringan",
                  "bonus": {"dfn": 2}, "price": 0, "look": "tunik"},
    "baju_kulit": {"name": "Baju Kulit", "slot": "armor", "type": "ringan",
                   "bonus": {"dfn": 5}, "price": 60, "look": "kulit"},
    "baju_pengembara": {"name": "Baju Pengembara", "slot": "armor", "type": "ringan",
                        "bonus": {"dfn": 10, "spd": 3}, "price": 260, "look": "pengembara"},
    "zirah_besi": {"name": "Zirah Besi", "slot": "armor", "type": "berat",
                   "bonus": {"dfn": 11}, "price": 150, "look": "zirah"},
    "zirah_kristal": {"name": "Zirah Kristal", "slot": "armor", "type": "berat",
                      "bonus": {"dfn": 19, "hp": 30}, "price": 450, "look": "zirah_kristal"},
    "jubah_murid": {"name": "Jubah Murid", "slot": "armor", "type": "jubah",
                    "bonus": {"dfn": 3, "mag": 3}, "price": 70, "look": "jubah"},
    "jubah_bintang": {"name": "Jubah Bintang", "slot": "armor", "type": "jubah",
                      "bonus": {"dfn": 8, "mag": 8, "mp": 15}, "price": 300,
                      "look": "jubah_bintang"},
    "baju_pelangi": {"name": "Baju Pelangi", "slot": "armor", "type": "ringan",
                     "bonus": {"dfn": 22, "mag": 6, "spd": 4}, "price": 0, "look": "pelangi"},
    # --- aksesori
    "gelang_angin": {"name": "Gelang Angin", "slot": "acc", "type": "acc",
                     "bonus": {"spd": 4}, "price": 120, "look": None},
    "kalung_kekuatan": {"name": "Kalung Kekuatan", "slot": "acc", "type": "acc",
                        "bonus": {"atk": 5}, "price": 140, "look": None},
    "cincin_bintang": {"name": "Cincin Bintang", "slot": "acc", "type": "acc",
                       "bonus": {"mag": 5, "mp": 12}, "price": 150, "look": None},
    "jimat_pelindung": {"name": "Jimat Pelindung", "slot": "acc", "type": "acc",
                        "bonus": {"dfn": 5, "hp": 25}, "price": 150, "look": None},
}
SLOT_NAMES = {"weapon": "Senjata", "armor": "Baju", "acc": "Aksesori"}
STARTER_WEAPON = {"kesatria": "pedang_kayu", "penyihir": "tongkat_kayu",
                  "pemanah": "busur_kayu", "penyembuh": "tongkat_bunga"}
WEAPON_TYPE_NAMES = {"pedang": "Pedang", "tongkat": "Tongkat", "busur": "Busur",
                     "tongkat_suci": "Tongkat Suci"}


def can_equip(cls_id, item_id):
    eq = EQUIPMENT[item_id]
    cls = CLASSES[cls_id]
    if eq["slot"] == "weapon":
        return eq["type"] == cls["weapon"]
    if eq["slot"] == "armor":
        return eq["type"] in cls["armor"]
    return True


def item_name(item_id):
    if item_id in ITEMS:
        return ITEMS[item_id]["name"]
    if item_id in EQUIPMENT:
        return EQUIPMENT[item_id]["name"]
    return item_id


# Toko: daftar barang bertambah sesuai kemajuan cerita.
SHOPS = {
    "toko": [
        (None, ["ramuan", "eter", "bulu", "pedang_besi", "tongkat_bintang",
                "busur_pemburu", "tongkat_doa", "baju_kulit", "jubah_murid"]),
        ("pecahan_hijau", ["ramuan_besar", "zirah_besi", "gelang_angin",
                           "kalung_kekuatan"]),
        ("pecahan_biru", ["permen", "pedang_kristal", "tongkat_kristal", "busur_angin",
                          "tongkat_cahaya", "baju_pengembara", "jubah_bintang",
                          "zirah_kristal", "cincin_bintang", "jimat_pelindung", "apel"]),
    ],
}


def shop_stock(shop, flags):
    out = []
    for need, items in SHOPS[shop]:
        if need is None or need in flags:
            out.extend(items)
    return out


# ---------------------------------------------------------------------------
# STATISTIK PAHLAWAN
# ---------------------------------------------------------------------------

def exp_to_next(level):
    return int(10 * level ** 1.6)


def class_skills(cls_id, level):
    return [s for lv, s in CLASSES[cls_id]["skills"] if level >= lv]


def derive_stats(hero):
    """Stat akhir (level + kelas + perlengkapan)."""
    cls = CLASSES[hero["cls"]]
    lv = hero["level"]
    st = {k: int(cls["base"][k] + cls["grow"][k] * (lv - 1)) for k in cls["base"]}
    for slot in ("weapon", "armor", "acc"):
        item = hero["equip"].get(slot)
        if item in EQUIPMENT:
            for k, v in EQUIPMENT[item]["bonus"].items():
                st[k] = st.get(k, 0) + v
    return st


def new_hero(name, cls_id, look):
    hero = {
        "name": name[:10] or "Pahlawan", "cls": cls_id, "level": 1, "exp": 0,
        "gold": 60, "look": dict(look),
        "equip": {"weapon": STARTER_WEAPON[cls_id], "armor": "baju_kain", "acc": None},
        "items": {"ramuan": 3},
        "gear": [],        # perlengkapan yang dimiliki tetapi tidak dipakai
    }
    st = derive_stats(hero)
    hero["hp"], hero["mp"] = st["hp"], st["mp"]
    return hero


def look_of(hero):
    """Tampilan sprite dari data pahlawan (kustomisasi + perlengkapan)."""
    lk = hero["look"]
    armor = EQUIPMENT.get(hero["equip"].get("armor") or "", {}).get("look") or "tunik"
    weapon = hero["equip"].get("weapon")
    wp = None
    if weapon in EQUIPMENT:
        wp = [EQUIPMENT[weapon]["type"], EQUIPMENT[weapon]["look"]]
    return {"skin": lk.get("skin", 0), "hair": lk.get("hair", "pendek"),
            "hair_color": lk.get("hair_color", "#6B4430"), "outfit": lk.get("outfit", "#E0405E"),
            "armor": armor, "hat": lk.get("hat"), "beard": False, "weapon": wp}


def clamp_hero(hero):
    st = derive_stats(hero)
    hero["hp"] = max(0, min(hero["hp"], st["hp"]))
    hero["mp"] = max(0, min(hero["mp"], st["mp"]))


def gain_exp(hero, amount):
    """Tambah EXP; kembalikan daftar (level_baru, [skill_baru])."""
    ups = []
    hero["exp"] += amount
    while hero["level"] < MAX_LEVEL and hero["exp"] >= exp_to_next(hero["level"]):
        hero["exp"] -= exp_to_next(hero["level"])
        before = set(class_skills(hero["cls"], hero["level"]))
        old = derive_stats(hero)
        hero["level"] += 1
        new = derive_stats(hero)
        hero["hp"] += new["hp"] - old["hp"]
        hero["mp"] += new["mp"] - old["mp"]
        learned = [s for s in class_skills(hero["cls"], hero["level"]) if s not in before]
        ups.append((hero["level"], learned))
    if hero["level"] >= MAX_LEVEL:
        hero["exp"] = 0
    return ups


def change_class(hero, cls_id):
    hero["cls"] = cls_id
    for slot in ("weapon", "armor"):
        item = hero["equip"].get(slot)
        if item and not can_equip(cls_id, item):
            hero["gear"].append(item)
            hero["equip"][slot] = None
    if hero["equip"]["weapon"] is None:
        want = STARTER_WEAPON[cls_id]
        if want in hero["gear"]:
            hero["gear"].remove(want)
        hero["equip"]["weapon"] = want
    if hero["equip"]["armor"] is None:
        if "baju_kain" in hero["gear"]:
            hero["gear"].remove("baju_kain")
        hero["equip"]["armor"] = "baju_kain"
    clamp_hero(hero)


# ---------------------------------------------------------------------------
# MUSUH
# ---------------------------------------------------------------------------
# weak/resist: elemen. skills: (peluang, id serangan musuh). art: cara digambar.

ENEMIES = {
    "slime_hijau": {"name": "Slime Hijau", "art": ("slime", "#6CD65A"), "hp": 24, "atk": 8,
                    "dfn": 3, "mag": 3, "spd": 6, "exp": 5, "gold": 5, "weak": ["api"],
                    "drop": ("ramuan", 0.15)},
    "lebah": {"name": "Lebah Nakal", "art": ("lebah", "#FFD23F"), "hp": 22, "atk": 9,
              "dfn": 3, "mag": 3, "spd": 12, "exp": 6, "gold": 6, "weak": ["angin"],
              "drop": ("ramuan", 0.12)},
    "kelinci": {"name": "Kelinci Iseng", "art": ("kelinci", "#F5EDE0"), "hp": 30, "atk": 10,
                "dfn": 4, "mag": 2, "spd": 10, "exp": 8, "gold": 7, "weak": [],
                "drop": ("ramuan", 0.2)},
    "jamur": {"name": "Jamur Loncat", "art": ("jamur", "#E8494F"), "hp": 42, "atk": 12,
              "dfn": 5, "mag": 8, "spd": 6, "exp": 12, "gold": 10, "weak": ["api"],
              "skills": [(0.25, "spora")], "drop": ("ramuan", 0.2)},
    "kelelawar": {"name": "Kelelawar", "art": ("kelelawar", "#8E6BD8"), "hp": 36, "atk": 13,
                  "dfn": 4, "mag": 5, "spd": 13, "exp": 13, "gold": 9, "weak": ["angin", "cahaya"],
                  "drop": ("eter", 0.1)},
    "slime_biru": {"name": "Slime Biru", "art": ("slime", "#5CB8FF"), "hp": 70, "atk": 18,
                   "dfn": 9, "mag": 10, "spd": 8, "exp": 26, "gold": 18, "weak": ["petir"],
                   "resist": ["es"], "skills": [(0.2, "semburan_es")], "drop": ("ramuan", 0.25)},
    "kristal_nakal": {"name": "Kristal Nakal", "art": ("kristal", "#7FE9FF"), "hp": 60,
                      "atk": 17, "dfn": 18, "mag": 14, "spd": 7, "exp": 30, "gold": 24,
                      "weak": ["petir"], "skills": [(0.3, "sinar_kristal")],
                      "drop": ("eter", 0.2)},
    "batu_jalan": {"name": "Batu Berjalan", "art": ("batu", "#9C9486"), "hp": 95, "atk": 21,
                   "dfn": 15, "mag": 4, "spd": 5, "exp": 32, "gold": 22, "weak": ["es"],
                   "drop": ("ramuan_besar", 0.1)},
    "kelelawar_es": {"name": "Kelelawar Es", "art": ("kelelawar", "#7FD3F0"), "hp": 62,
                     "atk": 19, "dfn": 8, "mag": 12, "spd": 15, "exp": 28, "gold": 20,
                     "weak": ["api"], "resist": ["es"], "drop": ("eter", 0.15)},
    "hantu": {"name": "Hantu Iseng", "art": ("hantu", "#F2F0FF"), "hp": 110, "atk": 24,
              "dfn": 12, "mag": 22, "spd": 12, "exp": 55, "gold": 35, "weak": ["cahaya"],
              "skills": [(0.3, "cilukba")], "drop": ("eter", 0.2)},
    "bayangan": {"name": "Bayangan Kecil", "art": ("bayangan", "#5A3C8C"), "hp": 125,
                 "atk": 28, "dfn": 14, "mag": 20, "spd": 13, "exp": 60, "gold": 40,
                 "weak": ["cahaya", "api"], "skills": [(0.25, "bola_gelap")],
                 "drop": ("ramuan_besar", 0.2)},
    "naga_kecil": {"name": "Naga Kecil", "art": ("naga", "#58C77E"), "hp": 160, "atk": 31,
                   "dfn": 17, "mag": 18, "spd": 11, "exp": 75, "gold": 55, "weak": ["es"],
                   "resist": ["api"], "skills": [(0.3, "napas_api")], "drop": ("permen", 0.1)},
    "mata_terbang": {"name": "Mata Terbang", "art": ("mata", "#FF7A9C"), "hp": 105, "atk": 25,
                     "dfn": 11, "mag": 24, "spd": 16, "exp": 58, "gold": 38,
                     "weak": ["angin", "petir"], "skills": [(0.3, "tatapan_tidur")],
                     "drop": ("eter", 0.2)},
    # --- bos
    "raja_jamur": {"name": "Raja Jamur", "art": ("raja_jamur", "#E8494F"), "boss": True,
                   "hp": 300, "atk": 15, "dfn": 7, "mag": 12, "spd": 7, "exp": 90, "gold": 120,
                   "weak": ["api"], "skills": [(0.25, "spora"), (0.25, "hujan_spora")],
                   "drop": ("ramuan_besar", 1.0)},
    "golem": {"name": "Golem Kristal", "art": ("golem", "#8FE3FF"), "boss": True,
              "hp": 600, "atk": 25, "dfn": 18, "mag": 15, "spd": 7, "exp": 260, "gold": 300,
              "weak": ["petir"], "resist": ["es"],
              "skills": [(0.3, "gempa"), (0.2, "sinar_kristal")], "drop": ("apel", 1.0)},
    "ratu_bayangan": {"name": "Ratu Bayangan", "art": ("ratu", "#6B3FA0"), "boss": True,
                      "hp": 1250, "atk": 32, "dfn": 20, "mag": 27, "spd": 12, "exp": 800,
                      "gold": 1000, "weak": ["cahaya"],
                      "skills": [(0.25, "gelombang_gelap"), (0.2, "bola_gelap"),
                                 (0.12, "lagu_tidur")],
                      "drop": ("apel", 1.0)},
}

# Serangan khusus musuh.
ENEMY_SKILLS = {
    "spora": {"name": "Spora Ngantuk", "kind": "status", "status": "tidur", "chance": 0.45,
              "target": "hero", "fx": "sleep"},
    "hujan_spora": {"name": "Hujan Spora", "kind": "magic", "power": 10, "target": "all_heroes",
                    "fx": "spore"},
    "semburan_es": {"name": "Semburan Es", "kind": "magic", "power": 16, "elem": "es",
                    "target": "hero", "fx": "ice"},
    "sinar_kristal": {"name": "Sinar Kristal", "kind": "magic", "power": 18, "target": "hero",
                      "fx": "bolt"},
    "gempa": {"name": "Gempa Bumi", "kind": "phys", "power": 0.85, "target": "all_heroes",
              "fx": "quake"},
    "cilukba": {"name": "Cilukba!", "kind": "status", "status": "tidur", "chance": 0.5,
                "target": "hero", "fx": "sleep"},
    "bola_gelap": {"name": "Bola Gelap", "kind": "magic", "power": 26, "target": "hero",
                   "fx": "dark"},
    "napas_api": {"name": "Napas Api", "kind": "magic", "power": 20, "elem": "api",
                  "target": "all_heroes", "fx": "fire"},
    "tatapan_tidur": {"name": "Tatapan Ngantuk", "kind": "status", "status": "tidur",
                      "chance": 0.45, "target": "hero", "fx": "sleep"},
    "gelombang_gelap": {"name": "Gelombang Gelap", "kind": "magic", "power": 30,
                        "target": "all_heroes", "fx": "dark"},
    "lagu_tidur": {"name": "Lagu Nina Bobo", "kind": "status", "status": "tidur",
                   "chance": 0.35, "target": "all_heroes", "fx": "sleep"},
}

# ---------------------------------------------------------------------------
# PETA
# ---------------------------------------------------------------------------
# Satu karakter = satu petak 16x16. Angka = pintu/jalan keluar ke peta lain,
# "@" = titik mulai, "$" = peti harta, "+" = mata air penyembuh.
# Huruf lain yang bukan petak = karakter (NPC) dari "legend" peta.

TILES = {
    ".": ("rumput", False), ",": ("bunga", False), ";": ("rumput_tinggi", False),
    "T": ("pohon", True), "t": ("semak", True), "~": ("air", True), "=": ("jalan", False),
    ":": ("pasir", False), "#": ("tembok", True), "H": ("dinding_kayu", True),
    "W": ("jendela", True), "R": ("atap_merah", True), "r": ("atap_biru", True),
    "_": ("lantai_kayu", False), "k": ("karpet", False), "m": ("meja", True),
    "n": ("konter", True), "l": ("rak", True), "x": ("tong", True), "w": ("dinding_dalam", True),
    "c": ("lantai_gua", False), "%": ("dinding_gua", True), "C": ("kristal", True),
    "B": ("jembatan", False), "f": ("pagar", True), "s": ("lantai_menara", False),
    "S": ("dinding_menara", True), "o": ("awan", True), "g": ("tanah_hutan", False),
    "F": ("air_mancur", True), "^": ("gunung", True), "p": ("pilar", True),
    "D": ("pintu", False),
}
COUNTERS = set("nm")   # bisa bicara melewati konter/meja

MAPS = {}

MAPS["desa"] = {
    "name": "Desa Daun", "music": "rpg_desa", "floor": ".", "battle_bg": "padang",
    "rows": [
        "TTTTTTTTTTTTTT11TTTTTTTTTTTTTT",
        "T,..T.........==.........,..TT",
        "T..RRRRRRR....==....rrrrrr...T",
        "T..RRRRRRR....==....rrrrrr.,.T",
        "T..HWHHHWH....==....HWHHWH...T",
        "T..HHH2HHH..N.==....HHHdHH...T",
        "T.....=@......==.......=.....T",
        "T,....======================.T",
        "T.........,...FF......xK.....T",
        "T..f.f.f......FF...E..mmm....T",
        "T,.....,......==......,......T",
        "T.....O.......==.............T",
        "T..~~~~~......==....ttt.....,T",
        "T..~~~~~~.....==.............T",
        "T...~~~~......==...ff.f.f....T",
        "T.............==...f,,,,f....T",
        "T..U..........==...ffffff....T",
        "T.,......TT...==.......,..TT.T",
        "TT....TTTTTT......TTTT......TT",
        "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
    ],
    "warps": {"1": ("padang", "1"), "2": ("kedai", "2")},
    "legend": {
        "E": "tetua", "K": "pedagang", "N": "bu_tani", "O": "dodo", "U": "kakek_ikan",
        "d": "pintu_tetua",
    },
}

MAPS["kedai"] = {
    "name": "Kedai Petualang (Lobi)", "music": "rpg_kedai", "floor": "_", "indoor": True,
    "rows": [
        "wwwwwwwwwwwwwwww",
        "wlxlwwwPwwwlxlww",
        "w_I____________w",
        "wnnn_______Q___w",
        "w_________kkk__w",
        "w__mm_____kkk__w",
        "w__mm__A__kkk__w",
        "w____@____kkk__w",
        "w_mm______kkk_mw",
        "w_mm__J________w",
        "w______________w",
        "wwwwwww22wwwwwww",
    ],
    "warps": {"2": ("desa", "2")},
    "legend": {"I": "pemilik_kedai", "Q": "guru_kelas", "P": "papan_pesta", "A": "pemusik",
               "J": "petualang"},
}

MAPS["padang"] = {
    "name": "Padang Rumput Ceria", "music": "rpg_padang", "floor": ".", "battle_bg": "padang",
    "rows": [
        "TTTTTTTTTTTTTTTTTTT44TTTTTTTTTTTTTTTTTTT",
        "T^^^^^^^^^^^^^^^^^^==^^^^^^^^^^^^^^^^^^T",
        "T^^^^^^^^^^^^^^^^^^GG^^^^^^^^^^^^^^^^^^T",
        "T^^^^...;;;;......==.....;;;;;...^^^^^^T",
        "T^^...;;;;;;;.....==....;;;;;;;;...^^^^T",
        "T^...;;;;;;;;.....==.....;;;;;;;.....^^T",
        "T....;;;;;;.......==.......;;;;.......TT",
        "T..........,......==..............,...TT",
        "T~~~~.............==..................TT",
        "T~~~~~~...TT......==.......TTT..;;;;..TT",
        "T~~~~~~~..TTT.....==......TTTTT.;;;;;.TT",
        "T~~~~~~~~.........==.......TTT..;;;;;..T",
        "5BBBBYBB=========================......T",
        "T~~~~~~~=====.....==.........=========33",
        "T~~~~~~~~..;;;;...==.........=.........T",
        "T~~~~~~~..;;;;;;..==..;;;;...=...;;;...T",
        "T~~~~~~..;;;;;;;..==.;;;;;;..=..;;;;;..T",
        "T~~~~.....;;;;;...==..;;;;...=...;;;...T",
        "T..........$......==.........=.........T",
        "TT.....,..........==.....V...=..,......T",
        "TTT...TTT.........==.........=....TTT..T",
        "TTTT.TTTTT....;;;;==;;;;.....=...TTTTT.T",
        "TTTTTTTTTTT..;;;;;==;;;;;;...$..TTTTTTTT",
        "TTTTTTTTTTTT..;;;;==;;;;;;.....TTTTTTTTT",
        "TTTTTTTTTTTTT.....==.......TTTTTTTTTTTTT",
        "TTTTTTTTTTTTTTTTTT11TTTTTTTTTTTTTTTTTTTT",
    ],
    "warps": {"1": ("desa", "1"), "3": ("hutan", "3"), "4": ("gua", "4"), "5": ("menara", "5")},
    "legend": {"G": "batu_gua", "Y": "tukang_jembatan", "V": "pengelana"},
    "chests": [("ramuan", 2), ("gold", 80)],
    "encounters": {"zone": ";", "rate": 11,
                   "groups": [["slime_hijau"], ["slime_hijau", "slime_hijau"], ["lebah"],
                              ["lebah", "slime_hijau"], ["kelinci"], ["kelinci", "slime_hijau"]]},
}

MAPS["hutan"] = {
    "name": "Hutan Bisik", "music": "rpg_hutan", "floor": "g", "battle_bg": "hutan",
    "rows": [
        "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
        "TggggTTTTTggggggTTTTTTTTTTgggggg$gTT",
        "Tg$ggTTTTggTTTTggTTTTTTTTggTTTTTggTT",
        "TgggggTTggTTTTTTgggggTTTggTTTTTTTgTT",
        "TTTgggggggTTTTTTTTTTggggggggXgggggTT",
        "TTTTTTggTTTTTgggggTTggTTTTTTTTTTTTTT",
        "TTTTTTgTTTTTggTTTggggggTTTTTTTTTTTTT",
        "TgggggggTTTggTTTTTTTTgTTTTTgggggTTTT",
        "TgTTTTTgggggTTTggg+ggggggggggTTggTTT",
        "TgTTTTTTTTTTTTTgggggTTTTTTTTTTTTggTT",
        "TgggTTTTTTTTTTTTTgTTTTTgggggggTTTgTT",
        "TTTgTTTTTTgggggggggTTTggTTTTTggTTgTT",
        "3ggggggggggTTTTTTTgggggTTTTTTTgggggT",
        "3ggggggTTTTTTgggTTTTTTTTT$gTTTTTTTTT",
        "TTTTTggggTTTTgPgTTTTTTTTTgggTTTTTTTT",
        "TTTTTTTTgggggggggggTTTTTTTTgTTTTTTTT",
        "TTTTTTTTTTTTTTTTTTgggggggggggTTTTTTT",
        "TTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTTT",
    ],
    "warps": {"3": ("padang", "3")},
    "legend": {"X": "raja_jamur", "P": "peri_daun"},
    "chests": [("ramuan", 3), ("eter", 2), ("jimat_pelindung", 1)],
    "encounters": {"zone": "g", "rate": 14,
                   "groups": [["jamur"], ["jamur", "slime_hijau"], ["kelelawar"],
                              ["kelelawar", "jamur"], ["lebah", "lebah"], ["kelinci", "jamur"]]},
}

MAPS["gua"] = {
    "name": "Gua Kristal", "music": "rpg_gua", "floor": "c", "battle_bg": "gua",
    "rows": [
        "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%",
        "%%%%%%%%%%%%%%%cccc%%%%%%%%%%%%%%%",
        "%%$cc%%%%%%%%%ccXccc%%%%%%%cc$c%%%",
        "%%cccC%%%%%%%%%ccccc%%%%%%ccccc%%%",
        "%%ccccccc%%%%%%%%cc%%%%%%%ccCcc%%%",
        "%%%%cCcccccc%%%%%cc%%%%%ccccc%%%%%",
        "%%%%%%%%%cccc%%%cccc%%cccc%%%%%%%%",
        "%%%%%%%%%%%cccccc+cccccc%%%%%%%%%%",
        "%%%%$ccc%%%%%%%cccc%%%%%%%%%cccc%%",
        "%%%cccCcc%%%%%cccc%%%%%%%%ccccccc%",
        "%%%cc%%cccc%%cccc%%%%%%%cccc%%cc%%",
        "%%%cc%%%%ccccccc%%%%%%%ccc%%%%$c%%",
        "%%%ccc%%%%%%ccccc%%%%cccc%%%%%%%%%",
        "%%%%ccc%%%%%%%cccccccc%%%%%%%%%%%%",
        "%%%%%cccc%%%%%%cccc%%%%%%%%%%%%%%%",
        "%%%%%%%cccccccMcc%%%%%%%%%%%%%%%%%",
        "%%%%%%%%%%%%ccccc%%%%%%%%%%%%%%%%%",
        "%%%%%%%%%%%%%%44%%%%%%%%%%%%%%%%%%",
    ],
    "warps": {"4": ("padang", "4")},
    "legend": {"X": "golem", "M": "penambang"},
    "chests": [("eter", 3), ("ramuan_besar", 2), ("cincin_bintang", 1), ("gold", 400)],
    "encounters": {"zone": "c", "rate": 14,
                   "groups": [["slime_biru"], ["slime_biru", "kelelawar_es"],
                              ["kristal_nakal"], ["batu_jalan"],
                              ["kelelawar_es", "kelelawar_es"], ["kristal_nakal", "slime_biru"]]},
}

MAPS["menara"] = {
    "name": "Menara Awan", "music": "rpg_menara", "floor": "s", "battle_bg": "menara",
    "rows": [
        "oooooooooooooooooooooooooooooo",
        "oooooooooSSSSSSSSSSSSooooooooo",
        "oooooooooSsssssXsssssSoooooooo",
        "oooooooooSssspsssspssSoooooooo",
        "oooooooooSsssssssssssSoooooooo",
        "oooooooooSSSSSSssSSSSSoooooooo",
        "ooooSSSSSSSssssssssSSSSSSSSooo",
        "ooooS$ssssspssssssssssps$sSooo",
        "ooooSsspsssssSSssSSsssssssSooo",
        "ooooSSSSSSsssSSssSSssSSSSSSooo",
        "ooooooooooSsssssssssSooooooooo",
        "ooooSSSSSSSssssLssssSSSSSSSooo",
        "ooooSsssssssssssssssssssssSooo",
        "ooooSsspsss+sssSSsssssspssSooo",
        "ooooS$sssssssssSSssssssss$Sooo",
        "ooooSSSSSSSSSssssssSSSSSSSSooo",
        "ooooooooooooSssssssSoooooooooo",
        "ooooooooooooSSSss55ooooooooooo",
    ],
    "warps": {"5": ("padang", "5")},
    "legend": {"X": "ratu_bayangan", "L": "kucing_awan"},
    "chests": [("baju_pelangi", 1), ("senjata_pelangi", 1), ("apel", 2), ("permen", 3)],
    "encounters": {"zone": "s", "rate": 13,
                   "groups": [["hantu"], ["bayangan"], ["naga_kecil"], ["mata_terbang"],
                              ["hantu", "mata_terbang"], ["bayangan", "hantu"]]},
}

MAP_ORDER = ["desa", "kedai", "padang", "hutan", "gua", "menara"]
START_MAP = ("desa", "@")
LOBBY_MAP = ("kedai", "@")
INN_MAP = ("kedai", "@")

# ---------------------------------------------------------------------------
# KARAKTER DI PETA (NPC) & CERITA
# ---------------------------------------------------------------------------
# look: tampilan sprite (lihat sprites.hero_frames); "art": gambar monster.
# talk: daftar pilihan; yang pertama cocok dipakai.
#   if: flag yang wajib ada, not: flag yang wajib belum ada
#   lines: [(pembicara, teks)] ; {nama} & {kelas} diganti nama pemain.
#   do: aksi setelah dialog selesai:
#       ("flag", f) ("item", id, n) ("gold", n) ("inn",) ("shop", toko)
#       ("boss", musuh, flag_menang) ("class",) ("board",) ("heal",)
# hide_if / show_if: sembunyikan karakter berdasarkan flag.

def _look(skin, hair, hair_color, outfit, armor="tunik", hat=None, beard=False, weapon=None):
    return {"skin": skin, "hair": hair, "hair_color": hair_color, "outfit": outfit,
            "armor": armor, "hat": hat, "beard": beard, "weapon": weapon}


NPCS = {
    "tetua": {
        "name": "Tetua Bijak", "look": _look(1, "panjang", "#EDEDF2", "#7A5BC8", "jubah",
                                             beard=True, weapon=("tongkat", "#B98A55")),
        "talk": [
            {"if": ["tamat"], "lines": [
                ("Tetua Bijak", "Lihat, {nama}! Pelangi kembali menghiasi langit!"),
                ("Tetua Bijak", "Kamu dan teman-temanmu adalah pahlawan sejati. Terima kasih!")]},
            {"if": ["pecahan_biru"], "lines": [
                ("Tetua Bijak", "Pecahan Biru! Luar biasa, {nama}!"),
                ("Tetua Bijak", "Pecahan terakhir, yang Merah, dibawa Ratu Bayangan ke Menara Awan."),
                ("Tetua Bijak", "Jembatan ke barat sudah diperbaiki Pak Tukang. Hati-hati ya!"),
                ("Tetua Bijak", "Oh ya, tokonya sekarang menjual perlengkapan kristal. Mampirlah!")],
             "do": [("flag", "misi3")]},
            {"if": ["pecahan_hijau"], "lines": [
                ("Tetua Bijak", "Kamu menemukan Pecahan Hijau! Warna hutan mulai kembali!"),
                ("Tetua Bijak", "Pecahan Biru ada di Gua Kristal, di utara Padang Rumput."),
                ("Tetua Bijak", "Batu besar yang menutup gua sudah kami singkirkan untukmu."),
                ("Tetua Bijak", "Ambil ini sebagai bekal.")],
             "do": [("flag", "misi2"), ("item", "ramuan_besar", 2)]},
            {"if": ["misi1"], "lines": [
                ("Tetua Bijak", "Pecahan Hijau jatuh di Hutan Bisik, di sebelah timur Padang Rumput."),
                ("Tetua Bijak", "Kalau lelah, istirahat saja di Kedai Petualang.")]},
            {"lines": [
                ("Tetua Bijak", "Oh, {nama}! Syukurlah kamu datang. Ada kabar buruk..."),
                ("Tetua Bijak", "Semalam, Ratu Bayangan memecahkan Kristal Pelangi menjadi tiga!"),
                ("Tetua Bijak", "Tanpa kristal itu, warna dunia akan memudar sedikit demi sedikit."),
                ("Tetua Bijak", "Kamu seorang {kelas} yang berani. Maukah kamu menolong kami?"),
                ("{nama}", "Tentu saja! Serahkan padaku!"),
                ("Tetua Bijak", "Pecahan Hijau jatuh di Hutan Bisik, di timur Padang Rumput."),
                ("Tetua Bijak", "Bawa ramuan dan uang ini. Belilah perlengkapan di toko sebelah."),
                ("Tetua Bijak", "Ajak juga teman-temanmu! Kalian bisa bertemu di Kedai Petualang.")],
             "do": [("flag", "misi1"), ("item", "ramuan", 3), ("gold", 80)]},
        ],
    },
    "pintu_tetua": {
        "name": "Pintu", "art": "door",
        "talk": [{"lines": [("", "Rumah Tetua Bijak. Pintunya terkunci."),
                            ("", "Tetua sedang ada di alun-alun dekat air mancur.")]}],
    },
    "pedagang": {
        "name": "Bu Sari", "look": _look(0, "kuncir", "#6B4430", "#FF8A3D", "tunik",
                                         hat="bandana"),
        "talk": [{"lines": [("Bu Sari", "Selamat datang di Toko Serba Ada! Mau beli apa?")],
                  "do": [("shop", "toko")]}],
    },
    "bu_tani": {
        "name": "Bu Tani", "look": _look(2, "panjang", "#2A2433", "#3FAE5A", "tunik",
                                         hat="mahkota_bunga"),
        "talk": [
            {"if": ["tamat"], "lines": [("Bu Tani", "Bunga-bungaku berwarna lagi! Hore!")]},
            {"lines": [("Bu Tani", "Bunga-bungaku mulai pucat... warnanya memudar."),
                       ("Bu Tani", "Semoga Kristal Pelangi cepat utuh kembali.")]},
        ],
    },
    "dodo": {
        "name": "Dodo", "look": _look(0, "jabrik", "#D9542B", "#3E7BE0", "tunik"),
        "talk": [
            {"lines": [("Dodo", "Kak {nama}! Tahu tidak? Musuh di rumput tinggi itu banyak!"),
                       ("Dodo", "Kalau musuhnya kuat, kabur saja. Atau ajak teman main bareng!"),
                       ("Dodo", "Tekan tombol MENU untuk memakai ramuan dan mengganti senjata.")]},
        ],
    },
    "kakek_ikan": {
        "name": "Kakek Nelayan", "look": _look(1, "pendek", "#E3E3EE", "#2FB5A0", "kulit",
                                               beard=True),
        "talk": [
            {"if": ["hadiah_kakek"], "lines": [
                ("Kakek Nelayan", "Hari ini ikannya malu-malu. Hohoho!")]},
            {"lines": [
                ("Kakek Nelayan", "Hohoho, anak muda. Mau jadi pahlawan ya?"),
                ("Kakek Nelayan", "Ingat: slime takut api, dan hantu takut cahaya!"),
                ("Kakek Nelayan", "Ini, bawalah Bulu Semangat. Bisa membangunkan teman yang pingsan.")],
             "do": [("flag", "hadiah_kakek"), ("item", "bulu", 1)]},
        ],
    },
    "pemilik_kedai": {
        "name": "Pak Kumis", "look": _look(1, "pendek", "#2A2433", "#E0405E", "tunik",
                                           beard=True),
        "talk": [{"lines": [("Pak Kumis", "Selamat datang di Kedai Petualang!"),
                            ("Pak Kumis", "Istirahat di sini gratis. Tidur yang nyenyak ya...")],
                  "do": [("inn",)]}],
    },
    "guru_kelas": {
        "name": "Guru Kelas", "look": _look(3, "keriting", "#2A2433", "#9A5BE0", "jubah_bintang",
                                            hat="topi_penyihir"),
        "talk": [{"lines": [("Guru Kelas", "Aku bisa mengajarimu kelas yang berbeda."),
                            ("Guru Kelas", "Levelmu tetap sama. Mau ganti kelas?")],
                  "do": [("class",)]}],
    },
    "papan_pesta": {
        "name": "Papan Pesta", "art": "board",
        "talk": [{"lines": [("", "Papan Pesta: daftar petualang yang sedang bermain.")],
                  "do": [("board",)]}],
    },
    "pemusik": {
        "name": "Mbak Lala", "look": _look(0, "panjang", "#FF8FC8", "#F2B632", "tunik",
                                           hat="pita"),
        "talk": [
            {"lines": [("Mbak Lala", "La la la~ Ini Kedai Petualang, tempat para pahlawan bertemu!"),
                       ("Mbak Lala", "Kalau temanmu membuat Lobi di komputernya,"),
                       ("Mbak Lala", "pilih 'Gabung Lobi' di layar judul, lalu kalian bertemu di sini!")]},
        ],
    },
    "petualang": {
        "name": "Bang Joko", "look": _look(2, "jabrik", "#2A2433", "#6B8E3A", "zirah",
                                           hat="helm", weapon=("pedang", "#C9D3E6")),
        "talk": [
            {"if": ["pecahan_hijau"], "lines": [
                ("Bang Joko", "Golem di Gua Kristal lemah terhadap petir!"),
                ("Bang Joko", "Penyihir bisa memakai sihir Petir mulai level 4.")]},
            {"lines": [("Bang Joko", "Raja Jamur di Hutan Bisik suka menidurkan lawan dengan spora."),
                       ("Bang Joko", "Naikkan levelmu sampai kira-kira level 5 dulu, ya!")]},
        ],
    },
    "batu_gua": {
        "name": "Batu Besar", "art": "rock", "hide_if": "misi2",
        "talk": [{"lines": [("", "Batu besar menutup jalan ke Gua Kristal."),
                            ("", "Mungkin Tetua Bijak bisa membantu menyingkirkannya...")]}],
    },
    "tukang_jembatan": {
        "name": "Pak Tukang", "look": _look(2, "pendek", "#2A2433", "#F2B632", "kulit",
                                            hat="bandana"),
        "hide_if": "misi3",
        "talk": [{"lines": [("Pak Tukang", "Maaf, jembatan ke Menara Awan sedang diperbaiki."),
                            ("Pak Tukang", "Kata Tetua, kamu butuh dua pecahan dulu sebelum ke sana.")]}],
    },
    "pengelana": {
        "name": "Pengelana", "look": _look(1, "kuncir", "#5C86F2", "#2FB5A0", "pengembara"),
        "talk": [{"lines": [
            ("Pengelana", "Rumput tinggi itu tempat monster bersembunyi."),
            ("Pengelana", "Hutan Bisik di timur, Gua Kristal di utara, Menara Awan di barat."),
            ("Pengelana", "Semakin jauh, semakin kuat monsternya!")]}],
    },
    "peri_daun": {
        "name": "Peri Daun", "art": "fairy",
        "talk": [
            {"if": ["pecahan_hijau"], "lines": [
                ("Peri Daun", "Terima kasih! Hutan jadi hijau lagi~")]},
            {"lines": [("Peri Daun", "Hihi! Kamu mencari Pecahan Hijau?"),
                       ("Peri Daun", "Raja Jamur menyimpannya di ujung timur laut hutan."),
                       ("Peri Daun", "Biar kusembuhkan dulu lukamu. Semangat!")],
             "do": [("heal",)]},
        ],
    },
    "raja_jamur": {
        "name": "Raja Jamur", "art": "raja_jamur",
        "talk": [
            {"if": ["pecahan_hijau"], "lines": [
                ("Raja Jamur", "Hmph! Aku cuma suka barang yang berkilau..."),
                ("Raja Jamur", "Maaf ya sudah nakal. Mau jadi temanku?")]},
            {"lines": [("Raja Jamur", "Hoho! Siapa kalian? Ini Pecahan Hijau milikku!"),
                       ("Raja Jamur", "Berkilau, cantik, dan... hmm, rasanya enak! Eh?"),
                       ("Raja Jamur", "Kalau mau, rebut saja dariku! Jamur-jamurku, SERANG!")],
             "do": [("boss", "raja_jamur", "pecahan_hijau")]},
        ],
    },
    "golem": {
        "name": "Golem Kristal", "art": "golem",
        "talk": [
            {"if": ["pecahan_biru"], "lines": [
                ("Golem Kristal", "GOLEM... SUDAH... BANGUN. TERIMA... KASIH."),
                ("Golem Kristal", "RATU... BAYANGAN... SEDIH... DI... MENARA.")]},
            {"lines": [("Golem Kristal", "GRRR... SIAPA... BERANI... MASUK..."),
                       ("Golem Kristal", "RATU... BILANG... JAGA... PECAHAN... BIRU!")],
             "do": [("boss", "golem", "pecahan_biru")]},
        ],
    },
    "penambang": {
        "name": "Pak Tambang", "look": _look(1, "pendek", "#6B4430", "#FF8A3D", "kulit",
                                             hat="helm", beard=True),
        "talk": [{"lines": [("Pak Tambang", "Hati-hati, Golem Kristal ada di ujung utara gua."),
                            ("Pak Tambang", "Mata air di tengah gua bisa memulihkan tenaga.")]}],
    },
    "kucing_awan": {
        "name": "Kucing Awan", "art": "cat",
        "talk": [{"lines": [("Kucing Awan", "Meong~ Ratu Bayangan ada di puncak menara."),
                            ("Kucing Awan", "Sebenarnya dia kesepian... tidak ada yang mau bermain dengannya."),
                            ("Kucing Awan", "Meong. Kalian kuat. Tapi hatinya juga butuh teman.")],
                  "do": [("heal",)]}],
    },
    "ratu_bayangan": {
        "name": "Ratu Bayangan", "art": "ratu",
        "talk": [
            {"if": ["tamat"], "lines": [
                ("Ratu Bayangan", "Aku tidak menyangka... kalian mau berteman denganku."),
                ("Ratu Bayangan", "Kapan-kapan main lagi ke sini, ya!")]},
            {"lines": [("Ratu Bayangan", "Jadi kalian yang mengumpulkan pecahan kristal itu..."),
                       ("Ratu Bayangan", "Kenapa dunia harus berwarna? Di dunia berwarna,"),
                       ("Ratu Bayangan", "tidak ada yang mau bermain dengan bayangan sepertiku!"),
                       ("{nama}", "Itu tidak benar! Kita bisa jadi teman!"),
                       ("Ratu Bayangan", "Bohong! Kalau begitu, buktikan kekuatan kalian!")],
             "do": [("boss", "ratu_bayangan", "tamat")]},
        ],
    },
}

# Kalimat setelah bos dikalahkan (tampil untuk semua pemain).
BOSS_AFTER = {
    "raja_jamur": [("Raja Jamur", "Aduh, aduh! Aku menyerah!"),
                   ("Raja Jamur", "Ini, ambil Pecahan Hijau-nya. Maaf ya..."),
                   ("", "Kalian mendapatkan PECAHAN HIJAU! Hutan kembali berwarna."),
                   ("", "Kembalilah ke Desa Daun dan temui Tetua Bijak.")],
    "golem": [("Golem Kristal", "GOLEM... KALAH... GOLEM... SENANG... BISA... BANGUN."),
              ("", "Kalian mendapatkan PECAHAN BIRU! Gua bersinar indah."),
              ("", "Kembalilah ke Desa Daun dan temui Tetua Bijak.")],
    "ratu_bayangan": [("Ratu Bayangan", "Kalian... masih mau berteman denganku? Walaupun aku nakal?"),
                      ("{nama}", "Tentu saja! Teman itu saling memaafkan."),
                      ("Ratu Bayangan", "Terima kasih... ini, Pecahan Merah. Maafkan aku."),
                      ("", "Kalian mendapatkan PECAHAN MERAH!")],
}

PROLOGUE = [
    "Dahulu kala, di negeri Nusantara Ceria, berdiri sebuah Kristal Pelangi.",
    "Kristal itu membuat langit, bunga, dan laut penuh warna.",
    "Suatu malam, Ratu Bayangan datang dan memecahkannya menjadi tiga pecahan:",
    "Hijau, Biru, dan Merah. Sejak itu, warna dunia mulai memudar...",
    "Di Desa Daun, seorang {kelas} muda bernama {nama} terbangun oleh bunyi lonceng.",
    "Petualangan pun dimulai!",
]

ENDING = [
    "Tiga pecahan bersatu kembali. Kristal Pelangi bersinar terang!",
    "Warna kembali ke langit, bunga, laut, dan hati semua orang.",
    "Ratu Bayangan kini punya banyak teman. Dia tidak kesepian lagi.",
    "Terima kasih, para pahlawan!",
    "~ TAMAT ~",
    "(Kamu masih bisa berpetualang dan menaikkan level. Main lagi bersama teman, ya!)",
]

EMOTES = ["Halo! 👋", "Ayo! ⚔️", "Tunggu! ✋", "Hore! 🎉", "Tolong! 🆘", "Terima kasih! 💖"]

# Isi peti di Menara: "senjata_pelangi" diganti senjata pelangi sesuai kelas.
RAINBOW_WEAPON = {"kesatria": "pedang_pelangi", "penyihir": "tongkat_pelangi",
                  "pemanah": "busur_pelangi", "penyembuh": "tongkat_pelangi_suci"}


def parse_map(map_id):
    """Pecah baris peta -> (grid petak, entitas, pintu, peti, mata air, titik mulai)."""
    m = MAPS[map_id]
    rows = m["rows"]
    width = len(rows[0])
    for y, row in enumerate(rows):
        if len(row) != width:
            raise ValueError(f"peta {map_id} baris {y}: panjang {len(row)} != {width}")
    grid, npcs, warps, chests, springs, starts = [], [], [], [], [], []
    chest_i = 0
    for y, row in enumerate(rows):
        line = []
        for x, ch in enumerate(row):
            tile = ch
            if ch in TILES:
                pass
            elif ch.isdigit():
                warps.append((x, y, ch))
                tile = "D" if m.get("indoor") else ("=" if m["floor"] == "." else m["floor"])
            elif ch == "@":
                starts.append((x, y))
                tile = m["floor"]
            elif ch == "$":
                chests.append((x, y, chest_i))
                chest_i += 1
                tile = m["floor"]
            elif ch == "+":
                springs.append((x, y))
                tile = m["floor"]
            elif ch in m.get("legend", {}):
                npcs.append((x, y, m["legend"][ch]))
                tile = m["floor"]
            else:
                raise ValueError(f"peta {map_id}: karakter tak dikenal {ch!r} di {x},{y}")
            line.append(tile)
        grid.append(line)
    return {"grid": grid, "npcs": npcs, "warps": warps, "chests": chests,
            "springs": springs, "starts": starts, "w": width, "h": len(rows)}


def scale_enemy(eid, n_heroes):
    """Stat musuh; bos lebih kuat bila pemainnya banyak."""
    e = dict(ENEMIES[eid])
    if e.get("boss") and n_heroes > 1:
        e["hp"] = int(e["hp"] * (1 + 0.55 * (n_heroes - 1)))
    return e


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])
