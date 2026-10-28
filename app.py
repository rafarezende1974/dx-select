"""DX Select v0.1 — prototipo Windows de selecao (culling) de fotos.

Uso no Windows (apos o build): abrir o .exe, clicar em "Abrir pasta",
escolher a pasta de JPGs (ex.: D:\\Eventos\\...\\01_Fotos_JPG), revisar
grupo por grupo e exportar as mantidas.

Atalhos:
  Seta direita/esquerda — proxima/anterior foto do grupo
  G — proximo grupo | Shift+G — grupo anterior
  M ou Espaco — Manter | X — Rejeitar | U — Voltar para "a decidir"
  B — Manter so a melhor do grupo (rejeita as outras do grupo)

Nada e apagado ou sobrescrito na origem. A exportacao COPIA as
mantidas. Decisoes sao salvas automaticamente em .dxselect.json na
pasta de origem, entao fechar e reabrir continua de onde parou.
"""

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from culling_core import SESSION_FILE, export_kept, groups_of, save_session, scan_folder

VERSION = "v0.1"
DECISION_LABEL = {"keep": "MANTIDA", "reject": "REJEITADA", "undecided": "A DECIDIR"}
DECISION_COLOR = {"keep": "#1a7a3a", "reject": "#b3261e", "undecided": "#666666"}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"DX Select {VERSION} — Selecao de fotos")
        self.geometry("1180x760")
        self.folder = ""
        self.photos = []
        self.groups = []
        self.group_idx = 0
        self.photo_idx = 0
        self.filter_mode = tk.StringVar(value="all")
        self.scan_queue = queue.Queue()
        self._main_image = None
        self._thumbs = []
        self._build_ui()
        self._bind_keys()
        self.after(200, self._drain_scan_queue)

    # ---------------- interface ----------------
    def _build_ui(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="Abrir pasta…", command=self.open_folder).pack(side="left")
        ttk.Button(top, text="Exportar mantidas…", command=self.export).pack(side="left", padx=6)
        ttk.Button(top, text="Manter só a melhor do grupo (B)",
                   command=self.keep_best_only).pack(side="left")
        ttk.Label(top, text="  Mostrar:").pack(side="left")
        for value, label in (("all", "Todas"), ("undecided", "A decidir"),
                             ("keep", "Mantidas"), ("reject", "Rejeitadas")):
            ttk.Radiobutton(top, text=label, variable=self.filter_mode,
                            value=value, command=self._refresh_counts).pack(side="left")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body, width=210)
        left.pack(side="left", fill="y", padx=(8, 4), pady=4)
        ttk.Label(left, text="Grupos (sequências)").pack(anchor="w")
        self.group_list = tk.Listbox(left, width=28)
        self.group_list.pack(fill="both", expand=True)
        self.group_list.bind("<<ListboxSelect>>", self._on_group_select)

        center = ttk.Frame(body)
        center.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        self.info = ttk.Label(center, text="Abra uma pasta de JPGs para começar.",
                              font=("", 11, "bold"), wraplength=700)
        self.info.pack(anchor="w")
        self.subinfo = ttk.Label(center, text="", foreground="#555555")
        self.subinfo.pack(anchor="w")
        self.canvas = tk.Label(center, background="#1c1c1c")
        self.canvas.pack(fill="both", expand=True, pady=6)
        btns = ttk.Frame(center)
        btns.pack(fill="x")
        ttk.Button(btns, text="◀ Anterior", command=lambda: self._step_photo(-1)).pack(side="left")
        ttk.Button(btns, text="Manter (M)", command=lambda: self._decide("keep")).pack(side="left", padx=4)
        ttk.Button(btns, text="Rejeitar (X)", command=lambda: self._decide("reject")).pack(side="left")
        ttk.Button(btns, text="A decidir (U)", command=lambda: self._decide("undecided")).pack(side="left", padx=4)
        ttk.Button(btns, text="Próxima ▶", command=lambda: self._step_photo(1)).pack(side="left")
        ttk.Button(btns, text="Próximo grupo (G)", command=lambda: self._step_group(1)).pack(side="left", padx=4)

        self.thumb_row = ttk.Frame(center)
        self.thumb_row.pack(fill="x", pady=4)
        self.status = ttk.Label(self, text="Pronto.", relief="sunken", anchor="w")
        self.status.pack(fill="x")
        self.progress = ttk.Progressbar(self, mode="determinate")
        self.progress.pack(fill="x")

    def _bind_keys(self):
        self.bind("<Right>", lambda e: self._step_photo(1))
        self.bind("<Left>", lambda e: self._step_photo(-1))
        self.bind("m", lambda e: self._decide("keep"))
        self.bind("M", lambda e: self._decide("keep"))
        self.bind("<space>", lambda e: self._decide("keep"))
        self.bind("x", lambda e: self._decide("reject"))
        self.bind("X", lambda e: self._decide("reject"))
        self.bind("u", lambda e: self._decide("undecided"))
        self.bind("U", lambda e: self._decide("undecided"))
        self.bind("g", lambda e: self._step_group(1))
        self.bind("G", lambda e: self._step_group(-1))
        self.bind("b", lambda e: self.keep_best_only())
        self.bind("B", lambda e: self.keep_best_only())

    # ---------------- fluxo ----------------
    def open_folder(self):
        folder = filedialog.askdirectory(title="Escolha a pasta de JPGs")
        if not folder:
            return
        self.folder = folder
        self.status.config(text="Analisando fotos… (isso pode levar alguns minutos em pastas grandes)")
        self.progress.config(value=0)
        threading.Thread(target=self._scan_thread, args=(folder,), daemon=True).start()

    def _scan_thread(self, folder):
        def progress(done, total):
            self.scan_queue.put(("progress", done, total))
        try:
            photos = scan_folder(folder, progress=progress)
            self.scan_queue.put(("done", photos))
        except Exception as exc:  # noqa: BLE001 — erro vai para a tela, nao some
            self.scan_queue.put(("error", str(exc)))

    def _drain_scan_queue(self):
        try:
            while True:
                msg = self.scan_queue.get_nowait()
                if msg[0] == "progress":
                    self.progress.config(maximum=msg[2], value=msg[1])
                elif msg[0] == "done":
                    self.photos = msg[1]
                    self.groups = groups_of(self.photos)
                    self.group_idx = 0
                    self.photo_idx = 0
                    self._rebuild_group_list()
                    self._show_current()
                    self._refresh_counts()
                    self.status.config(
                        text=f"{len(self.photos)} fotos em {len(self.groups)} grupos. "
                             f"Sessao salva em {SESSION_FILE} na pasta de origem.")
                elif msg[0] == "error":
                    messagebox.showerror("Erro ao analisar", msg[1])
                    self.status.config(text="Pronto.")
        except queue.Empty:
            pass
        self.after(200, self._drain_scan_queue)

    def _visible_groups(self):
        mode = self.filter_mode.get()
        if mode == "all":
            return list(range(len(self.groups)))
        return [i for i, g in enumerate(self.groups)
                if any(p.decision == mode for p in g)]

    def _rebuild_group_list(self):
        self.group_list.delete(0, "end")
        for i, g in enumerate(self.groups):
            kept = sum(1 for p in g if p.decision == "keep")
            self.group_list.insert("end", f"Grupo {i + 1} — {len(g)} fotos ({kept} mantidas)")
        if self.groups:
            self.group_list.selection_set(self.group_idx)

    def _current(self):
        if not self.groups:
            return None
        group = self.groups[self.group_idx]
        return group[min(self.photo_idx, len(group) - 1)]

    def _show_current(self):
        photo = self._current()
        if photo is None:
            return
        try:
            with Image.open(photo.path) as im:
                im = im.copy()
            im.thumbnail((980, 620))
            self._main_image = ImageTk.PhotoImage(im)
            self.canvas.config(image=self._main_image)
        except Exception:
            self.canvas.config(image="", text="(não foi possível abrir esta foto)")
        label = DECISION_LABEL[photo.decision]
        self.info.config(
            text=f"{photo.rel}  •  Grupo {photo.group}  •  {label}",
            foreground=DECISION_COLOR[photo.decision])
        best = " ★ melhor do grupo (sugerida)" if photo.suggested else ""
        self.subinfo.config(
            text=f"Nota {photo.score}  •  Nitidez {photo.sharpness:.1f}  •  "
                 f"Brilho {photo.brightness:.0f}{best}  •  "
                 f"Foto {self.photo_idx + 1} de {len(self.groups[self.group_idx])} do grupo")
        self._show_thumbs()

    def _show_thumbs(self):
        for w in self.thumb_row.winfo_children():
            w.destroy()
        self._thumbs = []
        group = self.groups[self.group_idx]
        for i, p in enumerate(group):
            try:
                with Image.open(p.path) as im:
                    im = im.copy()
                im.thumbnail((110, 80))
                tk_img = ImageTk.PhotoImage(im)
            except Exception:
                continue
            self._thumbs.append(tk_img)
            border = 3 if i == self.photo_idx else 1
            color = DECISION_COLOR[p.decision] if p.decision != "undecided" else "#999999"
            lbl = tk.Label(self.thumb_row, image=tk_img, background=color,
                           borderwidth=border, relief="solid")
            lbl.pack(side="left", padx=3)
            lbl.bind("<Button-1>", lambda e, idx=i: self._goto_photo(idx))

    def _goto_photo(self, idx):
        self.photo_idx = idx
        self._show_current()

    def _step_photo(self, delta):
        if not self.groups:
            return
        group = self.groups[self.group_idx]
        self.photo_idx = (self.photo_idx + delta) % len(group)
        self._show_current()

    def _step_group(self, delta):
        if not self.groups:
            return
        self.group_idx = (self.group_idx + delta) % len(self.groups)
        self.photo_idx = 0
        self.group_list.selection_clear(0, "end")
        self.group_list.selection_set(self.group_idx)
        self.group_list.see(self.group_idx)
        self._show_current()

    def _on_group_select(self, _event):
        sel = self.group_list.curselection()
        if sel:
            self.group_idx = sel[0]
            self.photo_idx = 0
            self._show_current()

    def _decide(self, decision):
        photo = self._current()
        if photo is None:
            return
        photo.decision = decision
        if self.folder:
            save_session(self.folder, self.photos)
        self._rebuild_group_list()
        self.group_list.selection_set(self.group_idx)
        # Avanca sozinho: o fluxo de triagem e foto apos foto.
        self._step_photo(1)
        self._refresh_counts()

    def keep_best_only(self):
        if not self.groups:
            return
        group = self.groups[self.group_idx]
        best = max(group, key=lambda p: p.score)
        for p in group:
            p.decision = "keep" if p is best else "reject"
        if self.folder:
            save_session(self.folder, self.photos)
        self._rebuild_group_list()
        self.group_list.selection_set(self.group_idx)
        self._show_current()
        self._refresh_counts()

    def _refresh_counts(self):
        if not self.photos:
            return
        kept = sum(1 for p in self.photos if p.decision == "keep")
        rej = sum(1 for p in self.photos if p.decision == "reject")
        und = len(self.photos) - kept - rej
        self.status.config(
            text=f"{len(self.photos)} fotos • {kept} mantidas • {rej} rejeitadas • "
                 f"{und} a decidir • {len(self.groups)} grupos")

    def export(self):
        if not self.photos:
            messagebox.showinfo("Nada para exportar", "Abra uma pasta e revise as fotos primeiro.")
            return
        dest = filedialog.askdirectory(title="Escolha a pasta de destino das mantidas")
        if not dest:
            return
        copied, csv_path = export_kept(self.photos, dest)
        messagebox.showinfo(
            "Exportação concluída",
            f"{copied} fotos copiadas para:\n{dest}\n\nRelatório: {csv_path}\n"
            "Originais não foram movidos nem alterados.")
        self._refresh_counts()


if __name__ == "__main__":
    App().mainloop()
