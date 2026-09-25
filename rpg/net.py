# -*- coding: utf-8 -*-
"""
Jaringan LAN untuk main bersama (co-op), tanpa pustaka tambahan.

  * Tuan rumah (host) mengumumkan lobinya lewat UDP broadcast (port 47777)
    setiap detik; pemain lain mendengarkan dan melihat daftar lobi.
  * Permainan memakai TCP (port 47778): pesan JSON, satu per baris.

Semua soket non-blocking dan dibaca lewat poll() dari timer permainan,
jadi tidak ada thread.
"""

import json
import socket
import time

UDP_PORT = 47777
TCP_PORT = 47778
MAGIC = "KIDSOS-RPG"
PROTOCOL = 1
MAX_LINE = 512 * 1024


def local_ips():
    ips = set()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))           # tidak benar-benar mengirim
        ips.add(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.add(info[4][0])
    except OSError:
        pass
    ips.discard("127.0.0.1")
    return sorted(ips) or ["127.0.0.1"]


def _broadcast_targets():
    targets = {"255.255.255.255", "127.0.0.1"}
    for ip in local_ips():
        parts = ip.split(".")
        if len(parts) == 4:
            targets.add(".".join(parts[:3] + ["255"]))     # umumnya /24 di rumah
    return targets


class Conn:
    """Satu koneksi TCP berisi pesan JSON per baris."""

    def __init__(self, sock, addr=None):
        self.sock = sock
        self.addr = addr
        self.sock.setblocking(False)
        try:
            self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        self.rbuf = b""
        self.wbuf = b""
        self.closed = False

    def send(self, msg):
        if self.closed:
            return
        self.wbuf += json.dumps(msg, separators=(",", ":")).encode("utf-8") + b"\n"
        self.flush()

    def flush(self):
        while self.wbuf and not self.closed:
            try:
                n = self.sock.send(self.wbuf)
            except (BlockingIOError, InterruptedError):
                return
            except OSError:
                self.close()
                return
            self.wbuf = self.wbuf[n:]

    def poll(self):
        """Pesan yang sudah lengkap (list)."""
        out = []
        if self.closed:
            return out
        self.flush()
        while True:
            try:
                chunk = self.sock.recv(65536)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                self.close()
                break
            if not chunk:
                self.close()
                break
            self.rbuf += chunk
            if len(self.rbuf) > MAX_LINE * 4:
                self.close()
                break
        while b"\n" in self.rbuf:
            line, self.rbuf = self.rbuf.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                msg = json.loads(line.decode("utf-8"))
            except ValueError:
                continue
            if isinstance(msg, dict):
                out.append(msg)
        return out

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                self.sock.close()
            except OSError:
                pass


class Server:
    """Tuan rumah: menerima pemain & mengumumkan lobi."""

    def __init__(self, lobby_name, port=TCP_PORT):
        self.lobby_name = lobby_name
        self.port = port
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("0.0.0.0", port))
        self.listener.listen(8)
        self.listener.setblocking(False)
        self.clients = {}           # pid -> Conn
        self.next_pid = 1
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.udp.setblocking(False)
        self._last_beacon = 0.0
        self.players = 1
        self.max_players = 4
        self.open = True
        self.targets = _broadcast_targets()

    def beacon(self, force=False):
        now = time.monotonic()
        if not self.open or (not force and now - self._last_beacon < 1.0):
            return
        self._last_beacon = now
        msg = json.dumps({"magic": MAGIC, "v": PROTOCOL, "name": self.lobby_name,
                          "port": self.port, "players": self.players,
                          "max": self.max_players}).encode("utf-8")
        for t in self.targets:
            try:
                self.udp.sendto(msg, (t, UDP_PORT))
            except OSError:
                pass

    def poll(self):
        """-> [(pid, pesan)] ; pesan khusus: {"t":"_join"} / {"t":"_leave"}."""
        self.beacon()
        out = []
        while True:
            try:
                sock, addr = self.listener.accept()
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                break
            if len(self.clients) + 1 >= self.max_players:
                try:
                    sock.sendall(b'{"t":"full"}\n')
                    sock.close()
                except OSError:
                    pass
                continue
            pid = self.next_pid
            self.next_pid += 1
            self.clients[pid] = Conn(sock, addr)
            out.append((pid, {"t": "_join", "addr": addr[0]}))
        for pid, conn in list(self.clients.items()):
            for msg in conn.poll():
                out.append((pid, msg))
            if conn.closed:
                del self.clients[pid]
                out.append((pid, {"t": "_leave"}))
        return out

    def send(self, pid, msg):
        conn = self.clients.get(pid)
        if conn:
            conn.send(msg)

    def broadcast(self, msg, exclude=None):
        data = json.dumps(msg, separators=(",", ":")).encode("utf-8") + b"\n"
        for pid, conn in self.clients.items():
            if pid != exclude and not conn.closed:
                conn.wbuf += data
                conn.flush()

    def kick(self, pid):
        conn = self.clients.pop(pid, None)
        if conn:
            conn.close()

    def close(self):
        for conn in self.clients.values():
            conn.close()
        self.clients.clear()
        for s in (self.listener, self.udp):
            try:
                s.close()
            except OSError:
                pass


class Finder:
    """Mendengarkan pengumuman lobi di jaringan lokal."""

    def __init__(self):
        self.lobbies = {}           # (ip, port) -> info
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        self.ok = True
        try:
            self.sock.bind(("", UDP_PORT))
        except OSError:
            self.ok = False
        self.sock.setblocking(False)

    def poll(self):
        while self.ok:
            try:
                raw, addr = self.sock.recvfrom(4096)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                break
            try:
                info = json.loads(raw.decode("utf-8"))
            except ValueError:
                continue
            if not isinstance(info, dict) or info.get("magic") != MAGIC:
                continue
            if info.get("v") != PROTOCOL:
                continue
            key = (addr[0], int(info.get("port", TCP_PORT)))
            info["ip"], info["seen"] = addr[0], time.monotonic()
            # host yang sama bisa terdengar lewat 127.0.0.1 & IP LAN: satukan
            if addr[0] == "127.0.0.1" or addr[0] in local_ips():
                for k in list(self.lobbies):
                    if k[1] == key[1] and k[0] in ("127.0.0.1", *local_ips()) and k != key:
                        del self.lobbies[k]
            self.lobbies[key] = info
        now = time.monotonic()
        for k in [k for k, v in self.lobbies.items() if now - v["seen"] > 3.5]:
            del self.lobbies[k]
        return sorted(self.lobbies.values(), key=lambda v: v["name"])

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class Client:
    """Pemain tamu: tersambung ke tuan rumah."""

    def __init__(self, host, port=TCP_PORT, timeout=5.0):
        self.host, self.port = host, port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setblocking(False)
        self.conn = None
        self.failed = None
        self.started = time.monotonic()
        self.timeout = timeout
        try:
            self.sock.connect((host, port))
        except (BlockingIOError, InterruptedError):
            pass
        except OSError as e:
            self.failed = str(e)

    @property
    def connected(self):
        return self.conn is not None and not self.conn.closed

    def poll(self):
        if self.failed:
            return []
        if self.conn is None:
            err = self.sock.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            if err and err not in (115, 10035, 10036, 36, 114, 37):   # sedang menyambung
                self.failed = f"kode {err}"
                return []
            try:
                self.sock.getpeername()
            except OSError:
                if time.monotonic() - self.started > self.timeout:
                    self.failed = "waktu habis"
                return []
            self.conn = Conn(self.sock)
        msgs = self.conn.poll()
        if self.conn.closed and not msgs:
            self.failed = self.failed or "terputus"
        return msgs

    def send(self, msg):
        if self.conn:
            self.conn.send(msg)

    def close(self):
        if self.conn:
            self.conn.close()
        else:
            try:
                self.sock.close()
            except OSError:
                pass
