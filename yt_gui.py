import os
import sys
import subprocess
import json
import threading
import configparser
import shutil
from tkinter import messagebox
from PIL import Image
import customtkinter as ctk
from customtkinter import CTkImage

def resource_path(relative_path):
    """
    Renvoie le chemin absolu vers une ressource embarquée par PyInstaller
    (ou vers un fichier local en mode développement).
    """
    base_path = getattr(sys, '_MEIPASS', os.path.abspath('.'))
    return os.path.join(base_path, relative_path)

# --- Préparation des binaires externes ---
yt_exe     = resource_path('yt-dlp.exe')
ffmpeg_exe = resource_path('ffmpeg.exe')

# Vérifie qu'ils existent dans le bundle
missing = [exe for exe in (yt_exe, ffmpeg_exe) if not os.path.isfile(exe)]
if missing:
    messagebox.showerror(
        "Erreur de dépendances",
        "Binaires manquants :\n" + "\n".join(os.path.basename(m) for m in missing)
    )
    sys.exit(1)

# Prépare un environnement où yt-dlp trouvera ffmpeg
_env = os.environ.copy()
_mei  = getattr(sys, '_MEIPASS', os.path.abspath('.'))
_env['PATH'] = _mei + os.pathsep + _env.get('PATH', '')

# Empêche l'affichage des consoles sur Windows
CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0

# --- Lecture de la config ---
config = configparser.ConfigParser()
if not os.path.exists('config.ini'):
    messagebox.showerror("Erreur", "Fichier config.ini introuvable.")
    sys.exit(1)

config.read('config.ini')
dossier_sortie = config.get('chemins', 'emplacement', fallback='')
if not dossier_sortie:
    messagebox.showerror("Erreur", "Chemin de sortie non spécifié dans config.ini.")
    sys.exit(1)
os.makedirs(dossier_sortie, exist_ok=True)

# --- Apparence CustomTkinter ---
ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('blue')

BG         = '#0d0d0d'
FG         = '#f0f0f0'
ENTRY_BG   = '#2e2e2e'
ENTRY_BR   = '#2e2e2e'
CARD_BG    = '#202020'
CARD_HOVER = '#313155'
CARD_SEL   = '#3d5afe'
BTN_ACTIVE   = '#1a73e8'
BTN_DISABLED = '#333333'

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YouTube Unlinked")
        self.geometry("800x600")
        self.configure(fg_color=BG)
        # icône de la fenêtre
        self.iconbitmap(resource_path('icons/logo.ico'))

        # polices
        self.FONT_TITLE = ctk.CTkFont(family="Segoe UI", size=12, weight="bold")
        self.FONT_INFO  = ctk.CTkFont(family="Segoe UI Emoji", size=10)

        # variables
        self.query          = ctk.StringVar()
        self.selected_urls  = set()
        self.videos         = []
        self.animating      = False
        self.downloading    = False

        # charger les images
        self.icon_search = CTkImage(
            Image.open(resource_path('icons/search.png')),
            size=(18,18)
        )
        logo_img = Image.open(resource_path('icons/full_logo.png'))
        logo_img.thumbnail((120,120))
        self.icon_logo = CTkImage(logo_img, size=logo_img.size)

        self.build_ui()

    def build_ui(self):
        # Barre de recherche
        search_frame = ctk.CTkFrame(self, fg_color='transparent')
        search_frame.pack(pady=20)

        ctk.CTkLabel(search_frame, image=self.icon_logo, text="").pack(side='left', padx=(0,8))
        entry = ctk.CTkEntry(
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
        entry.pack(side='left', padx=(0,10))
        entry.bind("<Return>", lambda e: self.search())
        entry.bind("<Control-BackSpace>", self.delete_prev_word)
        self.entry = entry

        ctk.CTkButton(
            search_frame,
            image=self.icon_search,
            text="",
            width=40, height=40,
            corner_radius=20,
            fg_color=ENTRY_BG,
            hover_color=ENTRY_BR,
            command=self.search
        ).pack(side='left')

        # statut
        self.status = ctk.CTkLabel(self, text="", text_color=FG, font=self.FONT_INFO)
        self.status.pack(pady=(10,0))

        # zone des vignettes
        self.video_frame = ctk.CTkFrame(self, fg_color=BG)
        self.video_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # bouton de téléchargement
        self.download_btn = ctk.CTkButton(
            self,
            text="Télécharger",
            width=200, height=40,
            corner_radius=20,
            fg_color=BTN_DISABLED,
            text_color='white',
            state='disabled',
            font=self.FONT_INFO,
            command=self.download
        )
        self.download_btn.pack(pady=20)

    def delete_prev_word(self, event):
        e = event.widget
        idx = e.index("insert")
        txt = e.get()
        i = idx
        while i>0 and txt[i-1].isspace(): i-=1
        while i>0 and not txt[i-1].isspace(): i-=1
        e.delete(i, idx)
        e.icursor(i)
        return "break"

    def start_search_animation(self):
        self.animating = True
        def loop():
            dots = 0
            while self.animating:
                self.status.configure(text="Rechercher" + "."*dots)
                dots = (dots+1)%4
                threading.Event().wait(0.5)
        threading.Thread(target=loop, daemon=True).start()

    def stop_search_animation(self):
        self.animating = False

    def start_download_animation(self):
        self.downloading = True
        def loop():
            dots = 0
            while self.downloading:
                self.status.configure(text="⬇️ Téléchargement" + "."*dots)
                dots = (dots+1)%4
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
        self.download_btn.configure(state='disabled')
        for w in self.video_frame.winfo_children():
            w.destroy()
        self.selected_urls.clear()
        threading.Thread(target=self._search_videos, args=(q,), daemon=True).start()

    def _search_videos(self, query):
        try:
            out = subprocess.check_output(
                [yt_exe, "--dump-json", f"ytsearch3:{query}"],
                stderr=subprocess.DEVNULL,
                text=True,
                env=_env,
                creationflags=CREATE_NO_WINDOW
            )
            self.videos = [json.loads(line) for line in out.splitlines()]
        except Exception:
            self.stop_search_animation()
            self.status.configure(text="❌ Erreur lors de la recherche.")
            return
        self.after(0, self.display_results)

    def display_results(self):
        self.stop_search_animation()
        self.status.configure(text="✅ Sélectionnez les vidéos")
        for vid in self.videos:
            if 'id' in vid:
                self.add_card(vid)

    def add_card(self, vid):
        video_id = vid['id']
        title    = vid.get('title','Sans titre')
        uploader = vid.get('uploader','Inconnu')
        views    = f"{vid.get('view_count',0):,}".replace(',', ' ')
        dur = vid.get('duration', 0)
        m,s = divmod(dur, 60)
        dur_str = f"{m}m{s:02d}"
        url = vid.get('webpage_url', f"https://www.youtube.com/watch?v={video_id}")

        card = ctk.CTkFrame(self.video_frame, fg_color=CARD_BG, corner_radius=10, height=70)
        card.pack(fill='x', pady=5)
        card.pack_propagate(False)

        def on_enter(_):
            if url not in self.selected_urls:
                card.configure(fg_color=CARD_HOVER)
        def on_leave(_):
            card.configure(fg_color=(CARD_SEL if url in self.selected_urls else CARD_BG))

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        lbl1 = ctk.CTkLabel(card, text=title, anchor='w', text_color=FG, font=self.FONT_TITLE)
        lbl2 = ctk.CTkLabel(
            card,
            text=f"{uploader} | {dur_str} | 👁 {views}",
            anchor='w',
            text_color='#cccccc',
            font=self.FONT_INFO
        )
        lbl1.pack(fill='x', padx=10, pady=(6,0))
        lbl2.pack(fill='x', padx=10, pady=(0,6))

        for w in (lbl1,lbl2):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", lambda e,u=url: self.toggle(card,u))
        card.bind("<Button-1>", lambda e, u=url: self.toggle(card,u))

    def toggle(self, frame, url):
        if url in self.selected_urls:
            self.selected_urls.remove(url)
            frame.configure(fg_color=CARD_BG)
        else:
            self.selected_urls.add(url)
            frame.configure(fg_color=CARD_SEL)
        state = 'normal' if self.selected_urls else 'disabled'
        color = BTN_ACTIVE if self.selected_urls else BTN_DISABLED
        self.download_btn.configure(state=state, fg_color=color)

    def download(self):
        self.status.configure(text="")
        self.start_download_animation()
        urls = list(self.selected_urls)
        threading.Thread(target=self._download_thread, args=(urls,), daemon=True).start()

    def _download_thread(self, urls):
        for u in urls:
            try:
                subprocess.run(
                    [
                        yt_exe,
                        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
                        "--merge-output-format", "mp4",
                        "-o", os.path.join(dossier_sortie, "%(title)s.%(ext)s"),
                        u
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=_env,
                    creationflags=CREATE_NO_WINDOW
                )
            except Exception:
                pass

        self.stop_download_animation()
        self.status.configure(text="✅ Téléchargement terminé")
        def reset():
            threading.Event().wait(5)
            self.status.configure(text="✅ Sélectionnez les vidéos")
        threading.Thread(target=reset, daemon=True).start()

if __name__ == '__main__':
    App().mainloop()
