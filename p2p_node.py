import ipaddress
import os
import socket
import threading
import uuid
from protocol import send_msg, recv_msg, recv_exact,make_hello, make_hello_ack, make_text, make_file

CHUNK_SIZE = 64 * 1024
DOWNLOAD_DIR = "downloads"


class P2PNode:
     # CREATE PEER
    def __init__(self, name, port, log, on_peers_changed):
        self.name = name
        self.port = port
        self.peer_id = uuid.uuid4().hex[:8]
        self.log = log                         
        self.on_peers_changed = on_peers_changed
        self.peers = {}                       
        self.peers_lock = threading.Lock()
        self.server = None
        self.running = False
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # Server role 
    def start(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("0.0.0.0", self.port))
        self.server.listen()
        self.running = True
        threading.Thread(target=self._accept_loop, daemon=True).start()

    def _accept_loop(self):
        while self.running:
            try:
                conn, addr = self.server.accept()
            except OSError:
                break  # server socket bondho hoyeche
            threading.Thread(target=self._handle_incoming,
                             args=(conn, addr), daemon=True).start()

    def _handle_incoming(self, conn, addr):
        try:
            conn.settimeout(10)
            hello = recv_msg(conn)
            if hello.get("type") != "hello":
                raise ValueError("Expected hello message")
            send_msg(conn, make_hello_ack(self.peer_id, self.name, self.port))
            conn.settimeout(None)
        except Exception as e:
            self.log(f"[ERROR] Incoming handshake failed: {e}")
            conn.close()
            return
        self._register_and_listen(conn, addr, hello)

    # Client role
    def connect(self, ip, port):
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            self.log(f"[ERROR] Invalid IP address: {ip}")
            return
        try:
            port = int(port)
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.log("[ERROR] Invalid port (1-65535)")
            return

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(5)
            sock.connect((ip, port))
            send_msg(sock, make_hello(self.peer_id, self.name, self.port))
            ack = recv_msg(sock)
            if ack.get("type") != "hello_ack":
                raise ValueError("Expected hello_ack message")
            sock.settimeout(None)
        except Exception as e:
            self.log(f"[ERROR] Connection failed: {e}")
            sock.close()
            return

        if ack["peer_id"] == self.peer_id:
            self.log("[ERROR] You cannot connect to yourself")
            sock.close()
            return

        threading.Thread(target=self._register_and_listen,
                         args=(sock, (ip, port), ack), daemon=True).start()

    # peer register + receive loop 
    def _register_and_listen(self, sock, addr, info):
        pid = info["peer_id"]
        with self.peers_lock:
            if pid in self.peers:
                self.log(f"[SYSTEM] Already connected to {info['peer_name']}")
                sock.close()
                return
            self.peers[pid] = {
                "id": pid,
                "name": info["peer_name"],
                "sock": sock,
                "addr": f"{addr[0]}:{addr[1]}",
                "send_lock": threading.Lock(),
            }
        self.log(f"[SYSTEM] Connected to {info['peer_name']} [{pid}]")
        self.on_peers_changed()

        try:
            while True:
                msg = recv_msg(sock)
                kind = msg.get("type")
                if kind == "text":
                    self.log(f"{msg['sender_name']} -> You: {msg['message']}")
                elif kind == "file":
                    self._receive_file(sock, msg)
        except Exception:
            pass  # disconnect / socket error
        finally:
            self._remove_peer(pid)

    def _remove_peer(self, pid):
        with self.peers_lock:
            peer = self.peers.pop(pid, None)
        if peer:
            try:
                peer["sock"].close()
            except OSError:
                pass
            self.log(f"[SYSTEM] {peer['name']} disconnected")
            self.on_peers_changed()

    #Text
    def send_text(self, pid, text):
        peer = self.peers.get(pid)
        if not peer:
            self.log("[ERROR] Peer not connected")
            return
        try:
            with peer["send_lock"]:
                send_msg(peer["sock"], make_text(self.peer_id, self.name, text))
            self.log(f"You -> {peer['name']}: {text}")
        except Exception as e:
            self.log(f"[ERROR] Send failed: {e}")
            self._remove_peer(pid)

    #  File
    def send_file(self, pid, path):
        peer = self.peers.get(pid)
        if not peer:
            self.log("[ERROR] Peer not connected")
            return
        if not os.path.isfile(path):
            self.log(f"[ERROR] File not found: {path}")
            return
        filename = os.path.basename(path)
        filesize = os.path.getsize(path)
        try:
            with peer["send_lock"]:
                sock = peer["sock"]
                send_msg(sock, make_file(self.peer_id, self.name, filename, filesize))
                with open(path, "rb") as f:
                    while True:
                        chunk = f.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        sock.sendall(chunk)
            self.log(f"You -> {peer['name']}: File sent: {filename} ({filesize} bytes)")
        except Exception as e:
            self.log(f"[ERROR] File send failed: {e}")
            self._remove_peer(pid)

    def _receive_file(self, sock, meta):
        filename = os.path.basename(str(meta.get("filename", "file"))) 
        try:
            filesize = int(meta["filesize"])
            if filesize < 0:
                raise ValueError
        except (KeyError, ValueError):
            raise ConnectionError("Invalid file size")  
        path = os.path.join(DOWNLOAD_DIR, filename)
        base, ext = os.path.splitext(filename)
        i = 1
        while os.path.exists(path):          # to do not overwrite
            path = os.path.join(DOWNLOAD_DIR, f"{base}_{i}{ext}")
            i += 1

        remaining = filesize
        with open(path, "wb") as f:
            while remaining > 0:
                chunk = sock.recv(min(CHUNK_SIZE, remaining))
                if not chunk:
                    raise ConnectionError("Disconnected during file transfer")
                f.write(chunk)
                remaining -= len(chunk)
        self.log(f"{meta['sender_name']} -> You: File received: {os.path.basename(path)}")

    # Helpers
    def get_peers(self):
        with self.peers_lock:
            return [(p["id"], p["name"], p["addr"]) for p in self.peers.values()]

    def stop(self):
        self.running = False
        try:
            self.server.close()
        except Exception:
            pass
        for pid in list(self.peers.keys()):
            self._remove_peer(pid)