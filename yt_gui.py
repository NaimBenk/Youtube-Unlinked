import customtkinter as ctk
from PIL import Image
from customtkinter import CTkImage
import subprocess, json, threading, os, configparser, shutil, sys
from tkinter import messagebox

# 🔇 Pour empêcher les fenêtres CMD (Windows uniquement)
if os.name == "nt":
    CREATE_NO_WINDOW = 0x08000000
else:
    CREATE_NO_WINDOW = 0

# --- Config & dépendances ---
try:
    config = configparser.ConfigParser()
    if not os.path.exists("config.ini"):
        messagebox.showerror("Erreur", "Fichier config.ini introuvable.")
        sys.exit(1)
    config.read("config.ini")
    dossier_sortie = config["chemins"].get("emplacement", "")
    if not os.path.exists(dossier_sortie):
        os.makedirs(dossier_sortie)
    missing = [p for p in ("yt-dlp", "ffmpeg") if not shutil.which(p)]
    if missing:
        messagebox.showerror("Erreur de dépendances", "Installez :\n- " + "\n- ".join(missing))
        sys.exit(1)
except:
    sys.exit(1)

# --- Apparence ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
BG = "#0d0d0d"
FG = "#f0f0f0"
ENTRY_BG = "#2e2e2e"
ENTRY_BR = "#2e2e2e"
CARD_BG = "#202020"
CARD_HOVER = "#313155"
CARD_SEL = "#3d5afe"
BTN_ACTIVE = "#1a73e8"
BTN_DISABLED = "#333333"

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Unlinked")
        self.geometry("800x600")
        self.configure(fg_color=BG)
        self.iconbitmap("icons/logo.ico")

        self.FONT_TITLE = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        self.FONT_INFO = ctk.CTkFont(family="Segoe UI Emoji", size=10)

        self.query = ctk.StringVar()
        self.selected_urls = set()
        self.videos = []
        self.animating = False
        self.downloading = False

        self.icon_search = CTkImage(Image.open("icons/search.png"), size=(18, 18))
        self.icon_dl = CTkImage(Image.open("icons/download.png"), size=(20, 20))

        logo_img = Image.open("icons/full_logo.png")
        logo_img.thumbnail((120, 120))
        self.icon_logo = CTkImage(logo_img, size=logo_img.size)

        self.build_ui()

    def build_ui(self):
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(pady=20)

        logo_label = ctk.CTkLabel(search_frame, image=self.icon_logo, text="")
        logo_label.pack(side="left", padx=(0, 8))

        self.entry = ctk.CTkEntry(
            search_frame,
            width=400, height=40,
            corner_radius=20,
            fg_color=ENTRY_BG,
            border_width=2,
            border_color=ENTRY_BR,
            placeholder_text="Rechercher…",
            text_color=FG,
            font=ctk.CTkFont(family="Segoe UI", size=14),
            textvariable=self.query
        )
        self.entry.pack(side="left", padx=(0, 10))
        self.entry.bind("<Return>", lambda e: self.search())
        self.entry.bind("<Control-BackSpace>", self.delete_prev_word)

        search_btn = ctk.CTkButton(
            search_frame,
            image=self.icon_search,
            text="",
            width=40, height=40,
            corner_radius=20,
            fg_color=ENTRY_BG,
            hover_color=ENTRY_BR,
            command=self.search
        )
        search_btn.pack(side="left")

        self.status = ctk.CTkLabel(self, text="", text_color=FG, font=self.FONT_INFO)
        self.status.pack(pady=(10, 0))

        self.video_frame = ctk.CTkFrame(self, fg_color=BG)
        self.video_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self.download_btn = ctk.CTkButton(
            self,
            text="Télécharger",
            width=200, height=40,
            corner_radius=20,
            fg_color=BTN_DISABLED,
            text_color="white",
            state="disabled",
            font=self.FONT_INFO
        )
        self.download_btn.pack(pady=20)
        self.download_btn.configure(command=self.download)

    def delete_prev_word(self, event):
        e = event.widget
        idx = e.index("insert")
        txt = e.get()
        i = idx
        while i > 0 and txt[i-1].isspace():
            i -= 1
        while i > 0 and not txt[i-1].isspace():
            i -= 1
        e.delete(i, idx)
        e.icursor(i)
        return "break"

    def start_search_animation(self):
        self.animating = True
        def loop():
            dots = 0
            while self.animating:
                self.status.configure(text="Rechercher" + "." * dots)
                dots = (dots + 1) % 4
                threading.Event().wait(0.5)
        threading.Thread(target=loop, daemon=True).start()

    def stop_search_animation(self):
        self.animating = False

    def start_download_animation(self):
        self.downloading = True
        def loop():
            dots = 0
            while self.downloading:
                self.status.configure(text="⬇️ Téléchargement" + "." * dots)
                dots = (dots + 1) % 4
                threading.Event().wait(0.5)
        threading.Thread(target=loop, daemon=True).start()

    def stop_download_animation(self):
        self.downloading = False

    def search(self):
        q = self.query.get().strip()
        if not q:
            self.status.configure(text="❗ Entrez une requête.")
            return
        self.status.configure(text="")
        self.start_search_animation()
        self.set_download_button_state(False)
        for w in self.video_frame.winfo_children():
            w.destroy()
        self.selected_urls.clear()
        threading.Thread(target=self._search_videos, args=(q,), daemon=True).start()

    def _search_videos(self, query):
        try:
            out = subprocess.check_output(
                ["yt-dlp", "--dump-json", f"ytsearch3:{query}"],
                stderr=subprocess.DEVNULL, text=True,
                creationflags=CREATE_NO_WINDOW
            )
            self.videos = [json.loads(line) for line in out.splitlines()]
        except:
            self.stop_search_animation()
            self.status.configure(text="❌ Erreur lors de la recherche.")
            return
        self.after(0, self.display_results)

    def display_results(self):
        self.stop_search_animation()
        self.status.configure(text="✅ Sélectionnez les vidéos")
        for vid in self.videos:
            if "id" not in vid:
                continue
            self.add_card(vid)

    def add_card(self, vid):
        video_id = vid.get("id")
        title = vid.get("title", "Sans titre")
        uploader = vid.get("uploader", "Inconnu")
        views = f"{vid.get('view_count', 0):,}".replace(",", " ")
        url = vid.get("webpage_url") or f"https://www.youtube.com/watch?v={video_id}"
        dur = vid.get("duration", 0)
        m, s = divmod(dur, 60)
        dur_str = f"{m}m{s:02d}"

        card = ctk.CTkFrame(self.video_frame, fg_color=CARD_BG, corner_radius=10, height=70)
        card.pack(fill="x", pady=5)
        card.pack_propagate(False)

        def on_enter(_): 
            if url not in self.selected_urls: card.configure(fg_color=CARD_HOVER)
        def on_leave(_): 
            card.configure(fg_color=(CARD_SEL if url in self.selected_urls else CARD_BG))

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        lbl1 = ctk.CTkLabel(card, text=title, anchor="w", text_color=FG, font=self.FONT_TITLE)
        lbl2 = ctk.CTkLabel(card, text=f"{uploader} | {dur_str} | 👁 {views}", anchor="w",
                            text_color="#cccccc", font=self.FONT_INFO)
        lbl1.pack(fill="x", padx=10, pady=(6, 0))
        lbl2.pack(fill="x", padx=10, pady=(0, 6))

        for w in (lbl1, lbl2):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", lambda e: self.toggle(card, url))
        card.bind("<Button-1>", lambda e: self.toggle(card, url))

    def toggle(self, frame, url):
        if url in self.selected_urls:
            self.selected_urls.remove(url)
            frame.configure(fg_color=CARD_BG)
        else:
            self.selected_urls.add(url)
            frame.configure(fg_color=CARD_SEL)
        self.set_download_button_state(bool(self.selected_urls))

    def set_download_button_state(self, active):
        self.download_btn.configure(
            state="normal" if active else "disabled",
            fg_color=BTN_ACTIVE if active else BTN_DISABLED,
            cursor="hand2" if active else "arrow"
        )

    def download(self):
        self.status.configure(text="")
        self.start_download_animation()
        urls = list(self.selected_urls)
        threading.Thread(target=self._download_thread, args=(urls,), daemon=True).start()

    def _download_thread(self, urls):
        for u in urls:
            try:
                subprocess.run([
                    "yt-dlp", "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
                    "--merge-output-format", "mp4",
                    "-o", os.path.join(dossier_sortie, "%(title)s.%(ext)s"),
                    u
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            except:
                pass
        self.stop_download_animation()
        self.status.configure(text="✅ Téléchargement terminé")
        def reset_status():
            threading.Event().wait(5)
            self.status.configure(text="✅ Sélectionnez les vidéos")
        threading.Thread(target=reset_status, daemon=True).start()

if __name__ == "__main__":
    App().mainloop()
