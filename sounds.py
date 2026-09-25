#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Suara KidsOS
============
Semua suara DISINTESIS sendiri (tanpa file audio berlisensi):

  * efek tombol & permainan  : pop, correct, wrong, tada, page, fill, ...
  * nada piano & drum        : note0..note7, kick, snare, bell
  * suara hewan              : animal-sapi, animal-kucing, ...
  * musik latar tiap menu    : music-menu, music-cerita, ... (diputar berulang)

File WAV dibuat sekali saat paket dipasang:
    python3 /opt/kidsos/sounds.py --generate
lalu disimpan di /opt/kidsos/sounds. Jika belum ada, dibuat saat pertama
dipakai di ~/.cache/kidsos/sounds. Diputar dengan aplay (alsa-utils).
"""

import math
import os
import random
import shutil
import subprocess
import sys
import threading
import wave
from array import array

VERSION = "v2"             # naikkan jika suara diubah -> file lama diabaikan
RATE = 22050
HERE = os.path.dirname(os.path.abspath(__file__))
SYSTEM_DIR = os.path.join(HERE, "sounds")
USER_DIR = os.path.expanduser("~/.cache/kidsos/sounds")

# Diatur launcher dari pengaturan (tombol 🎵).
enabled = {"music": True, "effects": True}

TWO_PI = 2 * math.pi


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


# ---------------------------------------------------------------------------
# BAHAN DASAR SINTESIS
# ---------------------------------------------------------------------------

def _buf(seconds):
    return [0.0] * int(RATE * seconds)


def _add(buf, start, samples, gain=1.0):
    i0 = int(start * RATE)
    n = min(len(samples), len(buf) - i0)
    for i in range(max(0, n)):
        buf[i0 + i] += samples[i] * gain


def tone(freq, dur, kind="sine", decay=3.0, attack=0.01, harmonics=(1.0,)):
    """Nada sederhana dengan envelope (sine/tri/box/soft)."""
    n = int(RATE * dur)
    out = [0.0] * n
    step = TWO_PI * freq / RATE
    rel = int(RATE * 0.03)
    for i in range(n):
        t = i / RATE
        env = min(1.0, t / attack) * math.exp(-decay * t)
        if i > n - rel:
            env *= (n - i) / rel
        ph = step * i
        if kind == "tri":
            x = (ph / TWO_PI) % 1.0
            v = 4 * abs(x - 0.5) - 1
        else:
            v = 0.0
            for h, amp in enumerate(harmonics, 1):
                v += amp * math.sin(ph * h)
        out[i] = v * env
    return out


def pluck(freq, dur, bright=0.5):
    """Petikan senar (Karplus-Strong) - banjo/gitar kecil."""
    n = int(RATE * dur)
    period = max(2, int(RATE / freq))
    rng = random.Random(int(freq * 100))
    ring = [rng.uniform(-1, 1) for _ in range(period)]
    out = [0.0] * n
    idx = 0
    damp = 0.496 + 0.003 * bright
    for i in range(n):
        nxt = (idx + 1) % period
        v = ring[idx]
        ring[idx] = damp * (v + ring[nxt])
        out[i] = v
        idx = nxt
    return out


def pulse(freq, dur, width=0.25, decay=2.5, lowpass=0.35):
    """Gelombang kotak lembut ala game jadul (chiptune)."""
    n = int(RATE * dur)
    out = [0.0] * n
    y = 0.0
    rel = int(RATE * 0.02)
    for i in range(n):
        t = i / RATE
        x = 1.0 if (freq * t) % 1.0 < width else -1.0
        y += lowpass * (x - y)
        env = min(1.0, t / 0.005) * math.exp(-decay * t)
        if i > n - rel:
            env *= (n - i) / rel
        out[i] = y * env
    return out


def sweep(f0, f1, dur, decay=10.0, kind="sine", curve=1.0):
    """Nada meluncur dari f0 ke f1 (efek pop, lompat, dll.)."""
    n = int(RATE * dur)
    out = [0.0] * n
    phase = 0.0
    for i in range(n):
        t = i / RATE
        k = (t / dur) ** curve
        f = f0 + (f1 - f0) * k
        phase += TWO_PI * f / RATE
        v = math.sin(phase) if kind == "sine" else (4 * abs((phase / TWO_PI) % 1 - 0.5) - 1)
        out[i] = v * min(1.0, t / 0.003) * math.exp(-decay * t)
    return out


def noise(dur, decay=15.0, lowpass=1.0, seed=1, rise=None):
    rng = random.Random(seed)
    n = int(RATE * dur)
    out = [0.0] * n
    y = 0.0
    for i in range(n):
        t = i / RATE
        a = lowpass if rise is None else min(1.0, lowpass + rise * t / dur)
        y += a * (rng.uniform(-1, 1) - y)
        out[i] = y * math.exp(-decay * t)
    return out


def voice(dur, contour, vib_rate=5.0, vib_depth=0.02, lowpass=0.2, noise_amt=0.0,
          attack=0.05, release=0.2, am_rate=0.0, am_depth=0.0, width=None, seed=3):
    """'Suara makhluk': gergaji/pulsa dengan kontur nada, vibrato & filter.

    contour(x) -> Hz, x = 0..1 sepanjang durasi.
    """
    rng = random.Random(seed)
    n = int(RATE * dur)
    out = [0.0] * n
    phase = 0.0
    y1 = y2 = 0.0
    for i in range(n):
        t = i / RATE
        x = i / n
        f = contour(x) * (1 + vib_depth * math.sin(TWO_PI * vib_rate * t))
        phase = (phase + f / RATE) % 1.0
        v = (1.0 if phase < width else -1.0) if width else (2 * phase - 1)
        if noise_amt:
            v = (1 - noise_amt) * v + noise_amt * rng.uniform(-1, 1)
        y1 += lowpass * (v - y1)          # dua tahap lowpass = lebih "bulat"
        y2 += lowpass * (y1 - y2)
        env = min(1.0, t / attack) * min(1.0, (dur - t) / release)
        if am_rate:
            env *= 1 - am_depth * (0.5 + 0.5 * math.sin(TWO_PI * am_rate * t))
        out[i] = y2 * env
    return out


def _seq(parts, gap=0.0):
    """Gabungkan beberapa potongan suara berurutan dengan jeda."""
    out = []
    for part in parts:
        out += part + [0.0] * int(RATE * gap)
    return out


def _lin(*points):
    """Kontur nada linear dari titik-titik (x, Hz)."""
    def f(x):
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if x <= x1:
                return y0 + (y1 - y0) * (x - x0) / max(1e-9, x1 - x0)
        return points[-1][1]
    return f


def _mix(*layers):
    n = max(len(layer) for layer, _g in layers)
    out = [0.0] * n
    for layer, g in layers:
        for i, v in enumerate(layer):
            out[i] += v * g
    return out


# ---------------------------------------------------------------------------
# EFEK
# ---------------------------------------------------------------------------

def _box(n, dur=0.35):
    return tone(midi(n), dur, decay=7, harmonics=(1.0, 0.0, 0.25))


def _arp(notes, step, dur=0.4):
    buf = _buf(step * len(notes) + dur)
    for k, n in enumerate(notes):
        _add(buf, k * step, _box(n, dur))
    return buf


EFFECTS = {
    "pop": lambda: _mix((sweep(900, 260, 0.09, decay=35), 1.0),
                        (noise(0.012, decay=200, seed=4), 0.3)),
    "open": lambda: _arp([72, 76, 79, 84], 0.07),
    "correct": lambda: _arp([79, 84, 88], 0.09, 0.5),
    "wrong": lambda: _seq([tone(330, 0.16, kind="tri", decay=6),
                           tone(262, 0.24, kind="tri", decay=6)], 0.03),
    "tada": lambda: _mix((_arp([72, 76, 79, 84, 88], 0.08, 0.9), 1.0),
                         (_seq([[0.0] * int(RATE * 0.4),
                                tone(midi(72), 0.9, decay=3, harmonics=(1, 0.3)),
                                ]), 0.5)),
    "star": lambda: _mix((tone(1568, 0.5, decay=7, harmonics=(1, 0, 0.3)), 1.0),
                         (tone(2350, 0.5, decay=9), 0.4)),
    "page": lambda: noise(0.3, decay=6, lowpass=0.05, rise=0.5, seed=9),
    "fill": lambda: sweep(280, 720, 0.14, decay=14, curve=0.6),
    "swap": lambda: _mix((sweep(1300, 900, 0.05, decay=60), 1.0),
                         (noise(0.01, decay=300, seed=2), 0.3)),
    "key": lambda: tone(1320, 0.07, decay=35),
    "jump": lambda: sweep(320, 880, 0.2, decay=8, curve=0.7),
    "crash": lambda: _mix((sweep(180, 55, 0.35, decay=8), 1.0),
                          (noise(0.25, decay=14, lowpass=0.3, seed=5), 0.5)),
    "bell": lambda: _mix((tone(1568, 0.5, decay=7), 1.0), (tone(2350, 0.5, decay=9), 0.5)),
    "kick": lambda: [math.sin(TWO_PI * (45 * t + 5 * (1 - math.exp(-18 * t)))) * math.exp(-7 * t)
                     for t in (i / RATE for i in range(int(RATE * 0.4)))],
    "snare": lambda: _mix((noise(0.3, decay=16, seed=7), 0.7),
                          (tone(190, 0.3, decay=22), 0.3)),
    "hat": lambda: noise(0.06, decay=60, lowpass=0.9, seed=11),
    # --- RPG Legenda Kristal Pelangi
    "slash": lambda: _mix((noise(0.16, decay=18, lowpass=0.8, seed=13, rise=0.3), 0.8),
                          (sweep(1400, 500, 0.12, decay=20), 0.35)),
    "hit": lambda: _mix((sweep(260, 90, 0.14, decay=18), 1.0),
                        (noise(0.08, decay=40, lowpass=0.5, seed=17), 0.6)),
    "magic": lambda: _mix((_arp([76, 83, 88, 95], 0.05, 0.35), 0.8),
                          (sweep(600, 1800, 0.35, decay=6, curve=0.5), 0.3)),
    "heal": lambda: _arp([72, 79, 84, 88, 91], 0.07, 0.6),
    "buff": lambda: _mix((sweep(300, 900, 0.3, decay=5, curve=0.6), 0.8),
                         (_arp([67, 71, 74], 0.08, 0.3), 0.5)),
}
PIANO = [60, 62, 64, 65, 67, 69, 71, 72]
for _k, _n in enumerate(PIANO):
    EFFECTS[f"note{_k}"] = (lambda n=_n: tone(midi(n), 0.8, decay=3.2,
                                                harmonics=(1.0, 0.35, 0.12)))


# ---------------------------------------------------------------------------
# SUARA HEWAN (tiruan sederhana; nama hewan dibacakan espeak sesudahnya)
# ---------------------------------------------------------------------------

def _bark():
    return voice(0.17, _lin((0, 520), (0.3, 420), (1, 260)), lowpass=0.35,
                 noise_amt=0.3, attack=0.01, release=0.06)


def _quack():
    return voice(0.16, _lin((0, 330), (1, 230)), lowpass=0.45, width=0.2,
                 attack=0.01, release=0.05, vib_depth=0.0)


def _croak():
    return voice(0.2, _lin((0, 95), (1, 80)), lowpass=0.3, width=0.15,
                 am_rate=32, am_depth=0.9, attack=0.01, release=0.05)


def _chirp(f0, f1, d=0.07):
    return sweep(f0, f1, d, decay=12)


ANIMAL_SOUNDS = {
    "sapi": lambda: voice(1.4, _lin((0, 105), (0.3, 128), (1, 95)), lowpass=0.07,
                          attack=0.15, release=0.35),
    "kucing": lambda: voice(0.85, _lin((0, 420), (0.4, 820), (1, 480)), lowpass=0.22,
                            attack=0.05, release=0.25),
    "anjing": lambda: _seq([_bark(), _bark(), [0.0] * int(RATE * 0.15), _bark(), _bark()], 0.1),
    "ayam": lambda: _seq([voice(0.14, _lin((0, 520), (1, 560)), lowpass=0.3),
                          voice(0.14, _lin((0, 600), (1, 640)), lowpass=0.3),
                          voice(0.14, _lin((0, 700), (1, 720)), lowpass=0.3),
                          voice(0.6, _lin((0, 950), (0.3, 1000), (1, 600)), lowpass=0.3,
                                vib_depth=0.03, release=0.3)], 0.03),
    "bebek": lambda: _seq([_quack(), _quack(), _quack()], 0.08),
    "kambing": lambda: voice(1.0, _lin((0, 300), (1, 270)), vib_rate=7, vib_depth=0.07,
                             lowpass=0.2, release=0.3),
    "domba": lambda: voice(0.9, _lin((0, 390), (1, 360)), vib_rate=8, vib_depth=0.06,
                           lowpass=0.25, release=0.3),
    "kuda": lambda: voice(1.2, _lin((0, 900), (0.25, 1250), (1, 650)), vib_rate=13,
                          vib_depth=0.1, lowpass=0.3, release=0.4),
    "singa": lambda: voice(1.3, _lin((0, 80), (0.4, 120), (1, 70)), noise_amt=0.55,
                           lowpass=0.08, attack=0.3, release=0.5),
    "gajah": lambda: voice(0.9, _lin((0, 300), (0.5, 700), (1, 650)), lowpass=0.6,
                           vib_depth=0.03, attack=0.08, release=0.25),
    "katak": lambda: _seq([_croak(), _croak(), _croak()], 0.12),
    "burung": lambda: _seq([_chirp(2500, 3600), _chirp(2700, 3800), _chirp(2500, 3600),
                            _chirp(3000, 2400, 0.12)], 0.05),
    "lebah": lambda: voice(1.2, _lin((0, 210), (0.5, 230), (1, 200)), lowpass=0.15,
                           am_rate=7, am_depth=0.5, attack=0.2, release=0.3),
    "harimau": lambda: _seq([voice(0.5, _lin((0, 90), (1, 95)), noise_amt=0.4, lowpass=0.08,
                                   am_rate=26, am_depth=0.8, release=0.1),
                             voice(0.9, _lin((0, 90), (0.4, 130), (1, 75)), noise_amt=0.5,
                                   lowpass=0.09, attack=0.2, release=0.4)], 0.05),
    "monyet": lambda: _seq([voice(0.25, _lin((0, 450), (1, 520)), lowpass=0.12),
                            voice(0.25, _lin((0, 450), (1, 520)), lowpass=0.12),
                            voice(0.25, _lin((0, 700), (1, 800)), lowpass=0.5),
                            voice(0.3, _lin((0, 700), (1, 820)), lowpass=0.5)], 0.06),
    "tikus": lambda: _seq([_chirp(3000, 3900, 0.08), _chirp(3100, 4000, 0.08),
                           _chirp(3000, 3800, 0.1)], 0.07),
}


# ---------------------------------------------------------------------------
# MUSIK LATAR (komposisi otomatis dengan seed tetap -> lagu yang sama tiap kali)
# ---------------------------------------------------------------------------

MAJOR = [0, 2, 4, 5, 7, 9, 11]
RHYTHMS = {
    4: [[1, 1, 1, 1], [0.5, 0.5, 1, 2], [1.5, 0.5, 1, 1], [1, 0.5, 0.5, 2],
        [0.5, 0.5, 0.5, 0.5, 1, 1], [2, 1, 1]],
    3: [[1, 1, 1], [2, 1], [1, 0.5, 0.5, 1], [1.5, 0.5, 1]],
}

# nama: (tempo, ketukan/bar, progresi derajat, nada dasar, melodi, bass, drum, pad, seed)
MUSIC_THEMES = {
    "menu":      (112, 4, [0, 4, 5, 3], 60, "pluck", True, "light", False, 11),
    "cerita":    (84, 3, [0, 5, 3, 4], 65, "box", False, None, True, 21),
    "membaca":   (104, 4, [0, 3, 4, 0], 62, "box", True, "hat", False, 31),
    "berhitung": (116, 4, [0, 3, 0, 4], 60, "pulse", True, "march", False, 41),
    "hewan":     (120, 4, [0, 0, 3, 4], 67, "pluck", True, "light", False, 51),
    "bentuk":    (100, 4, [0, 2, 3, 4], 62, "box", True, "hat", False, 61),
    "mewarnai":  (76, 3, [0, 3, 5, 4], 60, "box", False, None, True, 71),
    "puzzle":    (92, 4, [5, 3, 0, 4], 57, "box", True, None, True, 81),
    "mengetik":  (110, 4, [0, 5, 3, 4], 60, "pulse", True, "hat", False, 91),
    "dino":      (138, 4, [0, 4, 5, 3], 64, "pulse", True, "full", False, 101),
    # --- RPG Legenda Kristal Pelangi
    "rpg_judul":  (96, 4, [0, 5, 3, 4], 62, "pluck", True, None, True, 111),
    "rpg_cerita": (72, 3, [5, 3, 0, 4], 57, "box", False, None, True, 121),
    "rpg_desa":   (108, 4, [0, 3, 4, 0], 60, "pluck", True, "light", False, 131),
    "rpg_kedai":  (120, 3, [0, 4, 0, 3], 62, "box", True, "hat", False, 141),
    "rpg_padang": (124, 4, [0, 4, 3, 4], 64, "pulse", True, "light", False, 151),
    "rpg_hutan":  (88, 4, [5, 4, 3, 4], 57, "pluck", True, "hat", True, 161),
    "rpg_gua":    (80, 4, [5, 1, 3, 4], 55, "box", True, None, True, 171),
    "rpg_menara": (100, 3, [5, 3, 4, 2], 59, "box", True, "hat", True, 181),
    "rpg_battle": (150, 4, [5, 3, 4, 4], 57, "pulse", True, "full", False, 191),
    "rpg_boss":   (160, 4, [5, 5, 3, 4], 52, "pulse", True, "march", True, 201),
    "rpg_tamat":  (92, 4, [0, 4, 5, 3], 60, "pluck", True, "light", True, 211),
}


def _degree_note(root, degree, octave=0):
    return root + MAJOR[degree % 7] + 12 * (degree // 7 + octave)


def compose(theme):
    tempo, meter, prog, root, lead, bass, drums, pad, seed = MUSIC_THEMES[theme]
    rng = random.Random(seed)
    beat = 60.0 / tempo
    bars = 8
    total = bars * meter * beat
    buf = _buf(total + 0.05)

    # Motif 2 bar, diulang dengan variasi: bentuk A A' A A'' (akhir di tonika).
    motif = []
    last = 7                                   # derajat skala (oktaf melodi)
    for b in range(2):
        rhythm = rng.choice(RHYTHMS[meter])
        chord = prog[b % len(prog)]
        for k, d in enumerate(rhythm):
            if k == 0:                         # ketukan kuat: nada akor
                choices = [chord, chord + 2, chord + 4, chord + 7]
                last = min(choices, key=lambda c: abs(c - last) + rng.random() * 2)
            else:
                last = max(3, min(12, last + rng.choice([-2, -1, -1, 1, 1, 2])))
            motif.append((last, d))

    def lead_note(freq, dur):
        if lead == "pluck":
            return pluck(freq, dur + 0.3, bright=0.6)
        if lead == "pulse":
            return pulse(freq, dur * 0.9, width=0.25, decay=3)
        return tone(freq, dur + 0.25, decay=4, harmonics=(1.0, 0.0, 0.25))

    t = 0.0
    for rep in range(bars // 2):
        shift = [0, 1, 0, -1][rep % 4] if rep % 2 else 0
        notes = list(motif)
        if rep == bars // 2 - 1:               # frasa terakhir berhenti di tonika
            notes[-1] = (7, notes[-1][1])
        for deg, d in notes:
            f = midi(_degree_note(root, deg + shift))
            _add(buf, t, lead_note(f, d * beat), 0.5)
            t += d * beat

    for bar in range(bars):
        chord = prog[bar % len(prog)]
        start = bar * meter * beat
        if bass:
            f = midi(_degree_note(root - 24, chord))
            for k in (0, 2) if meter == 4 else (0,):
                _add(buf, start + k * beat, tone(f, beat * 1.8, kind="tri", decay=2.5), 0.35)
        if pad:
            for off in (0, 2, 4):
                f = midi(_degree_note(root - 12, chord + off))
                _add(buf, start, tone(f, meter * beat, decay=0.6, attack=0.3), 0.07)
        if drums:
            for k in range(meter * 2):         # per setengah ketukan
                at = start + k * beat / 2
                if drums in ("hat", "light", "full") and k % 2 == 1:
                    _add(buf, at, _cached_fx("hat"), 0.12)
                if drums in ("light", "full", "march") and k % (4 if meter == 4 else 6) == 0:
                    _add(buf, at, _cached_fx("kick"), 0.5)
                if drums in ("full", "march") and k % 4 == 2:
                    _add(buf, at, _cached_fx("snare"), 0.25)
                if drums == "march" and k % 2 == 1:
                    _add(buf, at, _cached_fx("hat"), 0.08)
    return buf[:int(total * RATE)]


_fx_cache = {}


def _cached_fx(name):
    if name not in _fx_cache:
        _fx_cache[name] = EFFECTS[name]()
    return _fx_cache[name]


# ---------------------------------------------------------------------------
# FILE & PEMUTAR
# ---------------------------------------------------------------------------

def all_names():
    return (list(EFFECTS) + [f"animal-{a}" for a in ANIMAL_SOUNDS]
            + [f"music-{m}" for m in MUSIC_THEMES])


def render(name):
    if name.startswith("music-"):
        return compose(name[6:]), 0.55
    if name.startswith("animal-"):
        return ANIMAL_SOUNDS[name[7:]](), 0.85
    return EFFECTS[name](), 0.8


def write_wav(name, folder):
    samples, peak_target = render(name)
    peak = max(1e-6, max(abs(s) for s in samples))
    gain = 32767 * peak_target / peak
    fade = min(len(samples) // 4, int(RATE * 0.01))
    data = array("h", [0]) * len(samples)
    for i, s in enumerate(samples):
        g = gain
        if i < fade:
            g *= i / fade
        elif i >= len(samples) - fade:
            g *= (len(samples) - i) / fade
        data[i] = int(max(-32767, min(32767, s * g)))
    if sys.byteorder == "big":
        data.byteswap()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{VERSION}-{name}.wav")
    tmp = path + ".tmp"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())
    os.replace(tmp, path)
    return path


def find(name):
    for folder in (SYSTEM_DIR, USER_DIR):
        path = os.path.join(folder, f"{VERSION}-{name}.wav")
        if os.path.exists(path):
            return path
    return None


def path_for(name):
    """Path WAV; buat dulu (di cache user) jika belum ada."""
    return find(name) or write_wav(name, USER_DIR)


_players = []


def _spawn(path):
    _players[:] = [p for p in _players if p.poll() is None]   # bereskan zombie
    if sys.platform == "win32":                               # uji di Windows
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        return None
    for exe, args in (("aplay", ["-q"]), ("paplay", [])):
        found = shutil.which(exe)
        if found:
            try:
                proc = subprocess.Popen([found, *args, path], stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL)
            except OSError:
                return None
            _players.append(proc)
            return proc
    return None


def play(name):
    """Putar efek/hewan/nada tanpa memblokir."""
    if not enabled["effects"]:
        return
    try:
        _spawn(path_for(name))
    except (OSError, KeyError):
        pass


class Music:
    """Musik latar berulang. Satu lagu pada satu waktu."""

    def __init__(self):
        self.theme = None
        self.proc = None
        self._lock = threading.Lock()

    def play(self, theme):
        if theme == self.theme and self.proc is not None and self.proc.poll() is None:
            return
        self.stop()
        self.theme = theme
        if not theme or not enabled["music"]:
            return
        path = find(f"music-{theme}")
        if path:
            self.proc = _spawn(path)
        else:   # belum dibuat saat install: buat di latar, lalu putar
            threading.Thread(target=self._make_then_play, args=(theme,), daemon=True).start()

    def _make_then_play(self, theme):
        try:
            write_wav(f"music-{theme}", USER_DIR)
        except OSError:
            return
        with self._lock:
            if self.theme == theme and self.proc is None and enabled["music"]:
                self.proc = _spawn(find(f"music-{theme}"))

    def tick(self):
        """Panggil berkala (±1 detik): ulangi lagu yang sudah selesai."""
        if (self.theme and enabled["music"] and self.proc is not None
                and self.proc.poll() is not None):
            self.proc = _spawn(find(f"music-{self.theme}"))

    def stop(self):
        with self._lock:
            if self.proc is not None and self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc = None
            if sys.platform == "win32":
                import winsound
                winsound.PlaySound(None, 0)


music = Music()


def shutdown():
    music.stop()
    for p in _players:
        if p.poll() is None:
            p.terminate()


def generate_all(folder=SYSTEM_DIR, verbose=True):
    names = all_names()
    for k, name in enumerate(names, 1):
        if verbose:
            print(f"[KidsOS] membuat suara {k}/{len(names)}: {name}", flush=True)
        write_wav(name, folder)
    # buang versi lama
    for f in os.listdir(folder):
        if f.endswith(".wav") and not f.startswith(VERSION + "-"):
            os.remove(os.path.join(folder, f))


if __name__ == "__main__":
    if "--generate" in sys.argv:
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        generate_all(args[0] if args else SYSTEM_DIR)
    else:
        print(__doc__)
