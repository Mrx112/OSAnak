#!/usr/bin/env python3
"""
Siapkan aset boot KidsOS dari folder "Content Foto" (butuh Pillow).

    python3 packaging/make_boot_assets.py

Hasil (di-commit ke repo, jadi pemasangan di antiX tidak butuh Pillow):
    assets/boot/grub/        tema GRUB: background.jpg, theme.txt, select_*.png
    assets/boot/boot1.gif    animasi saat booting (diputar kidsos-bootanim)
    assets/boot/splash.gif   layar sambutan saat menu anak dibuka
"""

import os
import shutil

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "Content Foto")
OUT = os.path.join(ROOT, "assets", "boot")
GRUB = os.path.join(OUT, "grub")

W, H = 1280, 720          # cukup untuk semua resolusi & lebih ringan untuk GRUB
# Kartu menu (dalam persen layar) - harus cocok dengan theme.txt di bawah.
CARD = (0.27, 0.05, 0.73, 0.47)
TEXT = "#3B2F5C"

THEME = """# Tema GRUB KidsOS (dibuat oleh packaging/make_boot_assets.py)
title-text: ""
desktop-image: "background.jpg"
desktop-color: "#E9F6FF"
terminal-font: "Unifont Regular 16"
message-color: "#3B2F5C"

+ label {
    left = 27%
    width = 46%
    top = 8%
    align = "center"
    text = "KidsOS - Dunia Bermain & Belajar"
    font = "DejaVu Sans Bold 28"
    color = "#3B2F5C"
}

+ boot_menu {
    left = 28%
    width = 44%
    top = 16%
    height = 22%
    item_font = "DejaVu Sans Bold 22"
    selected_item_font = "DejaVu Sans Bold 22"
    item_color = "#3B2F5C"
    selected_item_color = "#3B2F5C"
    item_height = 42
    item_padding = 14
    item_spacing = 8
    selected_item_pixmap_style = "select_*.png"
    scrollbar = false
}

+ label {
    id = "__timeout__"
    left = 27%
    width = 46%
    top = 41%
    align = "center"
    text = "Mulai dalam %d detik - Enter = mulai"
    font = "DejaVu Sans Bold 18"
    color = "#6B5A93"
}
"""


def background():
    img = Image.open(os.path.join(SRC, "bootmenu.jpg")).convert("RGB")
    # Potong jadi 16:9, rata bawah (anak-anak & taman bermain tetap terlihat).
    crop_h = int(img.width * H / W)
    img = img.crop((0, img.height - crop_h, img.width, img.height))
    img = img.resize((W, H), Image.LANCZOS)

    x0, y0, x1, y1 = (int(CARD[0] * W), int(CARD[1] * H), int(CARD[2] * W), int(CARD[3] * H))
    # Bayangan lembut + kartu putih transparan agar tulisan menu terbaca.
    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle((x0 + 6, y0 + 8, x1 + 6, y1 + 8), 30, fill=90)
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    img = Image.composite(Image.new("RGB", (W, H), "#3B2F5C"), img, shadow)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    d.rounded_rectangle((x0, y0, x1, y1), 30, fill=(255, 255, 255, 222),
                        outline=(255, 175, 212, 255), width=6)
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img.save(os.path.join(GRUB, "background.jpg"), quality=90, optimize=True)


def selection_bar():
    """Sorotan menu terpilih: pil kuning, dipotong 3 bagian (w, c, e)."""
    h, r = 42, 21
    left = Image.new("RGBA", (r, h), (0, 0, 0, 0))
    ImageDraw.Draw(left).pieslice((0, 0, 2 * r, h - 1), 90, 270, fill="#FFE57A")
    left.save(os.path.join(GRUB, "select_w.png"))
    left.transpose(Image.FLIP_LEFT_RIGHT).save(os.path.join(GRUB, "select_e.png"))
    Image.new("RGBA", (4, h), "#FFE57A").save(os.path.join(GRUB, "select_c.png"))


def main():
    os.makedirs(GRUB, exist_ok=True)
    background()
    selection_bar()
    with open(os.path.join(GRUB, "theme.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(THEME)
    shutil.copyfile(os.path.join(SRC, "boot1.gif"), os.path.join(OUT, "boot1.gif"))
    shutil.copyfile(os.path.join(SRC, "boot2.gif"), os.path.join(OUT, "splash.gif"))
    for dirpath, _dirs, files in os.walk(OUT):
        for name in sorted(files):
            path = os.path.join(dirpath, name)
            print(f"{os.path.relpath(path, ROOT):40s} {os.path.getsize(path) // 1024:6d} KB")


if __name__ == "__main__":
    main()
