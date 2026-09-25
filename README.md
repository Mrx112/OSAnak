# 🌈 KidsOS: antiX Linux untuk Anak

**KidsOS** mengubah [antiX Linux](https://antixlinux.com) menjadi sistem operasi khusus anak.
Setelah komputer dinyalakan, anak langsung melihat menu **Dunia Bermain & Belajar**.
Tidak ada layar login, desktop, atau terminal yang bisa dibuka anak.
Orang tua tetap bisa mengatur sistem lewat **Mode Admin** berpassword.

![Menu utama KidsOS](docs/screenshots/01-menu-utama.png)

## ✨ Fitur

- **Langsung ke menu anak** setelah boot: login otomatis, tanpa desktop, dengan `Alt+Tab`, `Alt+F4`, `Ctrl+Alt+F1..F12` dan kombinasi sejenis diblokir.
- **10 aktivitas bawaan**, semuanya jalan tanpa internet dan tanpa aplikasi tambahan.
- **Suara di mana-mana**: bunyi "pop" di setiap tombol, musik latar yang berbeda di tiap menu, efek benar/salah, suara hewan, dan teks dibacakan dalam bahasa Indonesia (espeak-ng). Musik bisa dimatikan dengan tombol 🎵.
- **Menu boot dan animasi boot** bertema anak.
- **Mode Admin**: Desktop Admin (IceWM), terminal, repository menu, update dan upgrade.
- **Update aman**: update dan upgrade wajib memakai login akun admin Linux (root atau anggota grup `sudo`).
- **Menu bisa ditambah dari repository**: cukup edit `menu.json` dan `content/` di repo ini, lalu tekan **Update Menu**.

## 📸 Tampilan

### Saat komputer menyala

| Menu boot (GRUB) | Animasi boot | Layar sambutan |
|---|---|---|
| ![](docs/screenshots/00-boot-menu-grub.png) | ![](docs/screenshots/00-boot-animasi.png) | ![](docs/screenshots/00-layar-sambutan.png) |

### Aktivitas

| | | |
|---|---|---|
| **📖 Buku Cerita** ![](docs/screenshots/03-buku-cerita-baca.png) | **🔤 Kenal Huruf** ![](docs/screenshots/04-kenal-huruf.png) | **🧩 Tebak Kata** ![](docs/screenshots/05-tebak-kata.png) |
| **🔢 Ayo Berhitung** ![](docs/screenshots/06-berhitung.png) | **🐮 Suara Hewan** ![](docs/screenshots/07-suara-hewan.png) | **🔷 Bentuk & Warna** ![](docs/screenshots/09-tebak-bentuk.png) |
| **🖍️ Mewarnai** ![](docs/screenshots/12-mewarnai.png) | **🧩 Puzzle Seru** ![](docs/screenshots/14-puzzle.png) | **🎹 Bermain Musik** ![](docs/screenshots/15-musik.png) |
| **⌨️ Belajar Mengetik** ![](docs/screenshots/16-mengetik.png) | **🦖 Petualangan Dinosaurus** ![](docs/screenshots/18-dino.png) | **📚 Rak Cerita** ![](docs/screenshots/02-buku-cerita.png) |

### Mode Admin

| Password Mode Admin | Panel Admin | Repository menu | Login untuk update |
|---|---|---|---|
| ![](docs/screenshots/19-mode-admin.png) | ![](docs/screenshots/20-panel-admin.png) | ![](docs/screenshots/21-repository.png) | ![](docs/screenshots/22-login-linux.png) |

## 🎮 Isi aktivitas

| Menu | Isi |
|---|---|
| 📖 Buku Cerita | 5 cerita bergambar (Kura-kura dan Kelinci, Kancil dan Buaya, Semut dan Belalang, dan lainnya) dengan tombol 🔊 Bacakan |
| 🔤 Belajar Membaca | Kenal Huruf A–Z bergambar, dan kuis Tebak Kata |
| 🔢 Ayo Berhitung | Menghitung benda (1–10) dan penjumlahan sampai 10 |
| 🐮 Suara Hewan | 16 hewan dengan suaranya, dan kuis Tebak Hewan dari suara |
| 🔷 Bentuk & Warna | Tebak Bentuk dan Tebak Warna |
| 🖍️ Mewarnai | 6 gambar untuk diwarnai dengan sentuhan, Gambar Bebas pakai kuas, lalu bisa disimpan ke `~/Gambar` |
| 🧩 Puzzle Seru | 8 gambar, level 2×2, 3×3, dan 4×4 |
| 🎹 Bermain Musik | Piano Do–Do' (juga dengan tombol `A S D F G H J K`), drum, dan 3 lagu contoh dengan tuts yang menyala |
| ⌨️ Belajar Mengetik | Cari Huruf di keyboard dan Ketik Kata, dengan keyboard di layar sebagai petunjuk |
| 🦖 Petualangan Dinosaurus | Lari, lompati kaktus, dan kumpulkan bintang |

Setiap jawaban benar memberi ⭐, dan setiap kelipatan 5 bintang ada perayaan kecil 🎉.

## 💾 Instalasi (antiX Linux)

```sh
git clone https://github.com/Mrx112/OSAnak.git
cd OSAnak
python3 packaging/build_deb.py                  # -> dist/kidsos_1.1.1_all.deb
sudo apt install ./dist/kidsos_1.1.1_all.deb
sudo reboot
```

Selama instalasi kamu akan diminta membuat **password Mode Admin**. Installer akan:

1. Membuat user `anak` (tanpa password dan tanpa sudo) yang login otomatis di tty1.
2. Mematikan layar login dan desktop, lalu menjalankan menu anak sebagai satu-satunya tampilan.
3. Membuat semua suara dan musik (sekali saja, sekitar 1 menit).
4. Memasang tema menu boot GRUB dan animasi boot.

> Semua perubahan bisa dikembalikan dengan `sudo kidsos-setup disable` atau `sudo apt remove kidsos`.

### Perintah admin

| Perintah | Fungsi |
|---|---|
| `sudo kidsos-setup status` | Lihat status KidsOS |
| `sudo kidsos-setup log` | Diagnosa jika menu anak tidak muncul |
| `sudo kidsos-setup password` | Ganti password Mode Admin |
| `sudo kidsos-setup boot` | Pasang ulang tema GRUB dan animasi boot (misalnya setelah ganti monitor) |
| `sudo kidsos-setup disable` | Kembalikan antiX seperti semula |

**Jalan darurat:** di menu GRUB tekan `e`, tambahkan `kidsos=off` di akhir baris `linux`, lalu tekan
`Ctrl+X`. Komputer akan masuk ke login teks biasa.

## 🆘 Jika macet setelah menu boot

1. Di menu GRUB tekan `e`, lalu edit teksnya:
   - hapus baris `set gfxpayload=keep` (kalau ada),
   - di baris yang diawali `linux`, hapus `quiet loglevel=3 vt.global_cursor_default=0`, lalu
     tambahkan `kidsos=off` di akhir baris.

   Tekan `Ctrl+X`. Pesan boot akan terlihat, dan komputer berhenti di login teks.
2. Tekan `Ctrl+Alt+F2`, login dengan akun admin, lalu jalankan `sudo kidsos-setup log`. Perintah
   ini menampilkan penyebabnya: error tampilan (Xorg), display manager yang bentrok, dan lainnya.
3. Perbarui ke versi terbaru:
   ```sh
   wget https://raw.githubusercontent.com/Mrx112/OSAnak/main/kidsos_1.1.1_all.deb
   sudo apt install ./kidsos_1.1.1_all.deb && sudo reboot
   ```
   Untuk kembali ke antiX biasa: `sudo kidsos-setup disable && sudo reboot`.

Sejak versi 1.1.1, kalau tampilan menu gagal 3 kali berturut-turut, layar menampilkan petunjuk ini
(tidak lagi terlihat macet).

## 🔒 Mode Admin

Tekan **🔒 Mode Admin** di kiri atas, lalu masukkan password untuk membuka **Panel Admin**:

- **🖥️ Desktop Admin**: membuka desktop IceWM. Setelah logout, kembali ke menu anak.
- **💻 Terminal**
- **📦 Repository**: link repo menu (default: repo ini), dan pilihan update otomatis setiap komputer menyala.
- **⬇️ Update Menu**: mengunduh `menu.json` dan `content/` dari repo, lalu otomatis memasang aplikasi yang dibutuhkan.
- **⬆️ Upgrade**: memperbarui program KidsOS dari repo ini.
- **🔄 Mulai Ulang / ⏻ Matikan**

Update dan upgrade meminta **login akun Linux** (root atau anggota grup `sudo`). Password
diperiksa oleh sistem (`unix_chkpwd`) melalui helper root, jadi anak tidak bisa memasang apa pun
walaupun berhasil membuka terminal.

## 🧩 Menambah menu dan cerita

Edit `menu.json` di repo ini, lalu tekan **Update Menu** di Panel Admin:

```json
{ "items": [
  { "emoji": "📖", "title": "Buku Cerita", "subtitle": "Dongeng bergambar",
    "command": "kidsos:cerita" },
  { "emoji": "🎒", "title": "GCompris", "subtitle": "100+ permainan edukasi",
    "command": "gcompris-qt -f", "packages": ["gcompris-qt"], "color": "#9EE6A0" }
] }
```

| Kolom | Keterangan |
|---|---|
| `command` | Aktivitas bawaan (`kidsos:cerita`, `kidsos:membaca`, `kidsos:berhitung`, `kidsos:hewan`, `kidsos:bentuk`, `kidsos:mewarnai`, `kidsos:puzzle`, `kidsos:musik`, `kidsos:mengetik`, `kidsos:dino`) atau perintah aplikasi Linux |
| `packages` | Paket apt yang otomatis dipasang saat Update Menu |
| `color`, `shade`, `wide` | Warna kartu, warna sisi bawah, dan kartu selebar layar |

Cerita baru ditambahkan di `content/cerita.json`. Setiap halaman berisi `scene` (emoji) dan `text`.

## 🗂️ Struktur repo

```
main.py              launcher: menu, Mode Admin, repository, update
activities.py        Buku Cerita, Membaca, Berhitung, Hewan, Bentuk & Warna, Mengetik
games.py             Mewarnai, Puzzle, Musik, Dinosaurus
sounds.py            semua suara & musik (disintesis, tanpa file audio)
menu.json            daftar menu (sumber "Update Menu")
content/cerita.json  isi Buku Cerita
assets/boot/         tema GRUB, animasi boot, layar sambutan
packaging/           kidsos-setup, kidsos-session, kidsos-pkg, kidsos-bootanim, build_deb.py
Content Foto/        gambar asli untuk menu boot & animasi (sumber make_boot_assets.py)
docs/screenshots/    gambar untuk README ini
```

## 🛠️ Pengembangan

```sh
python3 main.py --dev             # berjendela, tanpa kunci, Esc = keluar
python3 main.py --dev --splash    # sekalian tampilkan layar sambutan
python3 packaging/make_boot_assets.py   # buat ulang aset boot dari "Content Foto" (butuh Pillow)
python3 sounds.py --generate ./sounds   # buat semua suara ke folder ./sounds
```

Kebutuhan: Python 3.9+, PyQt5, `alsa-utils` (aplay), `espeak-ng`, dan `fonts-noto-color-emoji`.
