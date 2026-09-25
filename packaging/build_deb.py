#!/usr/bin/env python3
"""
Buat paket Debian KidsOS (kidsos_<versi>_all.deb) tanpa dpkg-deb.

Hanya butuh Python 3, jadi bisa dijalankan di Windows maupun di antiX:
    python3 packaging/build_deb.py            -> dist/kidsos_<versi>_all.deb

Pasang di antiX:
    sudo apt install ./kidsos_<versi>_all.deb
"""

import gzip
import hashlib
import io
import os
import tarfile
import time

VERSION = "1.2.1"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "packaging")

CONTROL = f"""Package: kidsos
Version: {VERSION}
Architecture: all
Maintainer: KidsOS <https://github.com/Mrx112/OSAnak>
Depends: python3, python3-pyqt5, xinit, xserver-xorg, x11-xserver-utils, x11-xkb-utils, matchbox-window-manager, fonts-noto-color-emoji, fonts-dejavu-core, alsa-utils, espeak-ng, sudo, adduser, libpam-modules-bin, curl | wget
Recommends: icewm, xterm
Section: misc
Priority: optional
Homepage: https://github.com/Mrx112/OSAnak
Description: KidsOS - antiX menjadi sistem operasi khusus anak
 Setelah komputer menyala, langsung tampil menu bermain & belajar anak
 (tanpa login, tanpa desktop). 10 aktivitas bawaan siap pakai: Buku
 Cerita, Belajar Membaca, Ayo Berhitung, Suara Hewan, Bentuk & Warna,
 Mewarnai, Puzzle, Bermain Musik, Belajar Mengetik, Petualangan Dinosaurus.
 Mode Admin berpassword untuk desktop admin, terminal, repository menu,
 serta update & upgrade (dengan login akun admin Linux).
"""

# (sumber relatif ROOT, tujuan di sistem, mode)
FILES = [
    ("main.py", "opt/kidsos/main.py", 0o755),
    ("activities.py", "opt/kidsos/activities.py", 0o644),
    ("games.py", "opt/kidsos/games.py", 0o644),
    ("sounds.py", "opt/kidsos/sounds.py", 0o644),
    ("content/cerita.json", "opt/kidsos/content/cerita.json", 0o644),
    ("packaging/kidsos-session", "usr/lib/kidsos/kidsos-session", 0o755),
    ("packaging/kidsos-pkg", "usr/lib/kidsos/kidsos-pkg", 0o755),
    ("packaging/kidsos-setup", "usr/sbin/kidsos-setup", 0o755),
    ("packaging/kidsos-bootanim", "usr/lib/kidsos/kidsos-bootanim", 0o755),
]
# Aset boot (tema GRUB, animasi boot, layar sambutan) - dibuat make_boot_assets.py.
for _dir, _subdirs, _files in sorted(os.walk(os.path.join(ROOT, "assets"))):
    for _name in sorted(_files):
        _rel = os.path.relpath(os.path.join(_dir, _name), ROOT).replace(os.sep, "/")
        FILES.append((_rel, "opt/kidsos/" + _rel, 0o644))
SCRIPTS = ["postinst", "prerm", "postrm"]


def read(rel):
    with open(os.path.join(ROOT, rel), "rb") as f:
        data = f.read()
    if rel.endswith((".jpg", ".png", ".gif")):
        return data
    # Skrip & teks wajib berakhiran baris Unix (repo bisa ter-checkout CRLF di Windows).
    return data.replace(b"\r\n", b"\n")


def add(tar, name, data=None, mode=0o644, mtime=None):
    info = tarfile.TarInfo(name)
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    info.mtime = mtime
    if data is None:
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        tar.addfile(info)
    else:
        info.mode = mode
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))


def targz(entries):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar:
            for entry in entries:
                add(tar, *entry)
    return buf.getvalue()


def ar_member(name, data, mtime):
    header = (f"{name:<16}{mtime:<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}`\n")
    assert len(header) == 60
    return header.encode("ascii") + data + (b"\n" if len(data) % 2 else b"")


def main():
    now = int(time.time())

    # data.tar.gz: direktori induk dulu, lalu file.
    dirs, files, md5sums, size = set(), [], [], 0
    for src, dst, mode in FILES:
        data = read(src)
        parts = dst.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            dirs.add("./" + "/".join(parts[:i]) + "/")
        files.append(("./" + dst, data, mode, now))
        md5sums.append(f"{hashlib.md5(data).hexdigest()}  {dst}\n")
        size += len(data)
    data_tar = targz([("./", None, 0, now)]
                     + [(d, None, 0, now) for d in sorted(dirs)] + files)

    control = CONTROL.replace("Section:", f"Installed-Size: {size // 1024 + 1}\nSection:")
    control_entries = [
        ("./", None, 0, now),
        ("./control", control.encode("utf-8"), 0o644, now),
        ("./md5sums", "".join(md5sums).encode("utf-8"), 0o644, now),
    ]
    for script in SCRIPTS:
        control_entries.append((f"./{script}", read(f"packaging/debian/{script}"), 0o755, now))
    control_tar = targz(control_entries)

    out_dir = os.path.join(ROOT, "dist")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"kidsos_{VERSION}_all.deb")
    with open(out, "wb") as f:
        f.write(b"!<arch>\n")
        f.write(ar_member("debian-binary", b"2.0\n", now))
        f.write(ar_member("control.tar.gz", control_tar, now))
        f.write(ar_member("data.tar.gz", data_tar, now))
    print(f"Paket dibuat: {out} ({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
