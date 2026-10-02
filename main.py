import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext

from p2p_node import P2PNode


class App:
    def __init__(self, root):
        self.root = root
        root.title("File Sharing & Communication P2P Network")
        root.geometry("900x560")
        root.minsize(760, 480)

        self.node = None
        #events go through a queue
        self.q = queue.Queue()
        self.peer_ids = []

        #left sidebar (col 0) + right main area (col 1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)

        #LEFT SIDEBAR
        side = tk.Frame(root)
        side.grid(row=0, column=0, sticky="ns", padx=(8, 4), pady=8)
        side.rowconfigure(2, weight=1)

        #My Peer
        f1 = tk.LabelFrame(side, text="My Peer")
        f1.grid(row=0, column=0, sticky="ew", pady=(0, 6))

        tk.Label(f1, text="Name:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self.name_var = tk.StringVar(value="Alice")
        tk.Entry(f1, textvariable=self.name_var, width=18).grid(row=0, column=1, padx=6)

        tk.Label(f1, text="Port:").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        self.port_var = tk.StringVar(value="5000")
        tk.Entry(f1, textvariable=self.port_var, width=18).grid(row=1, column=1, padx=6)

        btns = tk.Frame(f1)
        btns.grid(row=2, column=0, columnspan=2, pady=4)
        self.start_btn = tk.Button(btns, text="Start Peer", width=10, command=self.start_peer)
        self.start_btn.pack(side="left", padx=3)
        self.stop_btn = tk.Button(btns, text="Stop", width=10, command=self.stop_peer, state="disabled")
        self.stop_btn.pack(side="left", padx=3)

        self.info_lbl = tk.Label(f1, text="Not running", wraplength=210, justify="left")
        self.info_lbl.grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4))

        # Connect
        f2 = tk.LabelFrame(side, text="Connect to Another Peer")
        f2.grid(row=1, column=0, sticky="ew", pady=(0, 6))

        tk.Label(f2, text="IP:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        self.ip_var = tk.StringVar(value="127.0.0.1")
        tk.Entry(f2, textvariable=self.ip_var, width=18).grid(row=0, column=1, padx=6)

        tk.Label(f2, text="Port:").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        self.rport_var = tk.StringVar(value="5001")
        tk.Entry(f2, textvariable=self.rport_var, width=18).grid(row=1, column=1, padx=6)

        tk.Button(f2, text="Connect", command=self.connect_peer).grid(
            row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=6
        )

        #Connected peers
        lf = tk.LabelFrame(side, text="Connected Peers")
        lf.grid(row=2, column=0, sticky="nsew")
        self.listbox = tk.Listbox(lf, width=30, exportselection=False)
        self.listbox.pack(fill="both", expand=True, padx=4, pady=4)

        #RIGHT MAIN AREA
        main = tk.Frame(root)
        main.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(0, weight=1)

        #Log
        rf = tk.LabelFrame(main, text="Messages / Events")
        rf.grid(row=0, column=0, sticky="nsew", pady=(0, 6))
        self.log_box = scrolledtext.ScrolledText(rf, width=60, height=18, state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=4, pady=4)

        #Send text
        f4 = tk.LabelFrame(main, text="Send Text")
        f4.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.msg_var = tk.StringVar()
        entry = tk.Entry(f4, textvariable=self.msg_var)
        entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        entry.bind("<Return>", lambda e: self.send_text())
        tk.Button(f4, text="Send", width=8, command=self.send_text).pack(side="right", padx=4)

        #Send file
        f5 = tk.LabelFrame(main, text="Send File")
        f5.grid(row=2, column=0, sticky="ew")
        tk.Button(f5, text="Choose File & Send", command=self.send_file).pack(
            side="left", padx=4, pady=4
        )
        tk.Label(f5, text="Text, image, audio, video, PDF, ZIP, etc.").pack(side="left", padx=6)

        #Status bar
        self.status_var = tk.StringVar(value="Ready")
        tk.Label(root, textvariable=self.status_var, anchor="w", relief="sunken").grid(
            row=1, column=0, columnspan=2, sticky="ew"
        )

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.process_queue)

    # Callbacks to use the queue)
    def log(self, text):
        self.q.put(("log", text))

    def peers_changed(self):
        self.q.put(("peers", None))

    def process_queue(self):
        """Runs on the main thread and applies queued updates to the UI."""
        try:
            while True:
                kind, data = self.q.get_nowait()

                if kind == "log":
                    self.log_box.config(state="normal")
                    self.log_box.insert("end", data + "\n")
                    self.log_box.see("end")
                    self.log_box.config(state="disabled")
                    self.status_var.set(data)

                elif kind == "peers":
                    self.refresh_peers()
        except queue.Empty:
            pass

        self.root.after(100, self.process_queue)

    def refresh_peers(self):
        self.listbox.delete(0, "end")
        self.peer_ids = []

        if self.node:
            for pid, name, addr in self.node.get_peers():
                self.listbox.insert("end", f"{name} [{pid}] {addr}")
                self.peer_ids.append(pid)

    # Actions
    def start_peer(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Error", "Peer name cannot be empty")
            return

        try:
            port = int(self.port_var.get().strip())
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Error", "Invalid port (1-65535)")
            return

        node = P2PNode(name, port, self.log, self.peers_changed)

        try:
            node.start()
        except OSError as e:
            messagebox.showerror("Error", f"Could not start on port {port}:\n{e}")
            return

        self.node = node
        self.info_lbl.config(text=f"{name} | ID: {node.peer_id} | Port: {port}")
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        self.log(f"[SYSTEM] Peer started: {name} [{node.peer_id}] on port {port}")

    def stop_peer(self):
        if self.node:
            self.node.stop()
            self.node = None

        self.info_lbl.config(text="Not running")
        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")
        self.refresh_peers()
        self.log("[SYSTEM] Peer stopped")

    def connect_peer(self):
        if not self.node:
            messagebox.showwarning("Error", "Please start the peer first")
            return

        ip = self.ip_var.get().strip()
        port = self.rport_var.get().strip()

        # To UI does not freeze while connecting
        threading.Thread(
            target=self.node.connect, args=(ip, port), daemon=True
        ).start()

    def selected_peer(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showwarning("Error", "Please select a peer from the list first")
            return None
        return self.peer_ids[sel[0]]

    def send_text(self):
        if not self.node:
            messagebox.showwarning("Error", "Peer is not started")
            return

        text = self.msg_var.get().strip()
        if not text:
            return

        pid = self.selected_peer()
        if pid:
            self.node.send_text(pid, text)
            self.msg_var.set("")

    def send_file(self):
        if not self.node:
            messagebox.showwarning("Error", "Peer is not started")
            return

        pid = self.selected_peer()
        if not pid:
            return

        path = filedialog.askopenfilename()
        if path:
            # Run in a thread so the UI does not freeze while sending large files
            threading.Thread(
                target=self.node.send_file, args=(pid, path), daemon=True
            ).start()

    def on_close(self):
        if self.node:
            self.node.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()