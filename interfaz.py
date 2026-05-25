"""
interfaz.py  —  Panel de control gráfico de JARVIS
Requiere Python 3.9+ con tkinter (incluido en Python estándar)
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import uuid
import subprocess
import threading
import queue
import sys
import ctypes

# Fijar AppUserModelID → Windows mostrará el ícono de JARVIS en la barra de tareas
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Maxi.JARVIS.AsistenteVoz.2")
except Exception:
    pass

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
COMMANDS_FILE = os.path.join(BASE_DIR, "commands.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "jarvis_settings.json")
PYTHON_EXE    = sys.executable
JARVIS_SCRIPT = os.path.join(BASE_DIR, "jarvis.py")

try:
    import updater as _updater
    _HAS_UPDATER = True
except ImportError:
    _HAS_UPDATER = False

try:
    import pystray
    from PIL import Image as PilImage
    _HAS_TRAY = True
except ImportError:
    _HAS_TRAY = False

# ── Paleta ────────────────────────────────────────────────────────────────────
BG     = "#0d0d1a"
BG2    = "#141428"
BG3    = "#1c1c38"
CARD   = "#1a1a30"
ACCENT = "#00d4aa"
FG     = "#e8e8f0"
FG2    = "#6666aa"
RED    = "#ff4466"
GREEN  = "#00e676"
YELLOW = "#ffca28"

FONT      = ("Segoe UI", 10)
FONT_B    = ("Segoe UI", 10, "bold")
FONT_SM   = ("Segoe UI", 9)
FONT_MONO = ("Consolas", 9)
FONT_H1   = ("Segoe UI", 18, "bold")

# ── Tipos de acción ────────────────────────────────────────────────────────────
ACTION_LABELS = {
    "builtin_modo_cafe":  "⚡ Modo Café (integrado)",
    "abrir_url":          "🌐 Abrir URL en Chrome",
    "abrir_app":          "📂 Abrir aplicación (.exe)",
    "reproducir_spotify": "🎵 Reproducir en Spotify",
    "media_play_pause":   "⏯  Pausar / Reproducir",
    "media_next":         "⏭  Siguiente pista",
    "media_prev":         "⏮  Pista anterior",
    "solo_hablar":        "💬 Solo hablar (sin acción extra)",
}
LABEL_TO_KEY = {v: k for k, v in ACTION_LABELS.items()}

DEFAULT_COMMANDS = [
    {
        "id": str(uuid.uuid4()),
        "nombre": "Modo Café",
        "trigger": "modo cafe",
        "accion": "builtin_modo_cafe",
        "params": {},
        "respuesta": "Activando modo café, señor Maxi.",
        "activo": True,
    },
    {
        "id": str(uuid.uuid4()),
        "nombre": "Pausar música",
        "trigger": "pausa la musica",
        "accion": "media_play_pause",
        "params": {},
        "respuesta": "Música pausada, señor Maxi.",
        "activo": True,
    },
    {
        "id": str(uuid.uuid4()),
        "nombre": "Música favorita",
        "trigger": "musica que me gusta",
        "accion": "reproducir_spotify",
        "params": {"uri": "spotify:playlist:37i9dQZF1F5p3rmiWPIYgZ"},
        "respuesta": "Poniendo tu playlist favorita.",
        "activo": True,
    },
]


def load_commands():
    if os.path.exists(COMMANDS_FILE):
        with open(COMMANDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return [dict(c) for c in DEFAULT_COMMANDS]


def save_commands(cmds):
    with open(COMMANDS_FILE, "w", encoding="utf-8") as f:
        json.dump(cmds, f, ensure_ascii=False, indent=2)


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
#  Diálogo: Agregar / Editar comando
# ══════════════════════════════════════════════════════════════════════════════
class CommandDialog(tk.Toplevel):
    def __init__(self, parent, cmd=None, on_save=None):
        super().__init__(parent)
        self.on_save       = on_save
        self._cmd          = cmd or {}
        self.param_widgets = {}
        self.title("Editar comando" if cmd else "Nuevo comando")
        self.configure(bg=BG2)
        self.resizable(False, False)
        self.grab_set()
        self._build()
        if cmd:
            self._populate(cmd)
        self._center()

    # ── Helpers de widgets ────────────────────────────────────────────────────
    def _entry(self, parent=None, **kw):
        p = parent or self
        return tk.Entry(p, bg=BG3, fg=FG, insertbackground=FG,
                        relief="flat", font=FONT, bd=6, **kw)

    def _lbl(self, text, parent=None, color=FG2):
        return tk.Label(parent or self, text=text, bg=BG2,
                        fg=color, font=FONT_SM)

    def _btn(self, parent, text, cmd, bg=BG3, fg=FG):
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg,
                         activebackground=ACCENT, activeforeground=BG,
                         relief="flat", font=FONT_SM, padx=10, pady=5,
                         cursor="hand2")

    # ── Construcción ──────────────────────────────────────────────────────────
    def _build(self):
        P = {"padx": 16, "pady": (0, 6)}

        self._lbl("Nombre del comando").pack(anchor="w", padx=16, pady=(16, 2))
        self.e_nombre = self._entry()
        self.e_nombre.pack(fill="x", **P)

        self._lbl("Frase de activación  (lo que le dices a JARVIS)").pack(
            anchor="w", padx=16, pady=(6, 2))
        self.e_trigger = self._entry()
        self.e_trigger.pack(fill="x", **P)

        self._lbl("Tipo de acción").pack(anchor="w", padx=16, pady=(6, 2))
        self.var_accion = tk.StringVar(value=ACTION_LABELS["solo_hablar"])
        self.cb_accion = ttk.Combobox(
            self, textvariable=self.var_accion,
            values=list(ACTION_LABELS.values()),
            state="readonly", font=FONT,
        )
        self.cb_accion.pack(fill="x", padx=16, pady=(0, 4))
        self.cb_accion.bind("<<ComboboxSelected>>",
                            lambda _: self._refresh_params())

        # Parámetros dinámicos
        self.frame_params = tk.Frame(self, bg=BG2)
        self.frame_params.pack(fill="x", padx=16, pady=(0, 4))

        self._lbl("Respuesta de voz  (lo que dirá JARVIS)").pack(
            anchor="w", padx=16, pady=(6, 2))
        self.e_respuesta = self._entry()
        self.e_respuesta.pack(fill="x", **P)

        self.var_activo = tk.BooleanVar(value=True)
        tk.Checkbutton(
            self, text="Comando activo",
            variable=self.var_activo,
            bg=BG2, fg=FG, selectcolor=BG3,
            activebackground=BG2, activeforeground=ACCENT,
            font=FONT,
        ).pack(anchor="w", padx=16, pady=4)

        # Botones
        row = tk.Frame(self, bg=BG2)
        row.pack(fill="x", padx=16, pady=(8, 16))
        self._btn(row, "🔊 Probar voz", self._test_voice).pack(side="left")
        self._btn(row, "✕ Cancelar", self.destroy).pack(side="right", padx=(6, 0))
        self._btn(row, "✔ Guardar", self._save, bg=ACCENT, fg=BG).pack(side="right")

        self._refresh_params()

    def _refresh_params(self):
        for w in self.frame_params.winfo_children():
            w.destroy()
        self.param_widgets = {}
        accion = LABEL_TO_KEY.get(self.var_accion.get(), "solo_hablar")

        def lbl(text):
            tk.Label(self.frame_params, text=text, bg=BG2,
                     fg=FG2, font=FONT_SM).pack(anchor="w", pady=(4, 0))

        if accion == "abrir_url":
            lbl("URL a abrir:")
            e = self._entry(self.frame_params)
            e.pack(fill="x", pady=(2, 4))
            self.param_widgets["url"] = e

        elif accion == "abrir_app":
            lbl("Ruta del ejecutable (.exe):")
            row = tk.Frame(self.frame_params, bg=BG2)
            row.pack(fill="x", pady=(2, 4))
            e = self._entry(row)
            e.pack(side="left", fill="x", expand=True)
            tk.Button(row, text="📂", command=lambda: self._browse(e),
                      bg=BG3, fg=FG, relief="flat", font=FONT, padx=6,
                      cursor="hand2").pack(side="right", padx=(4, 0))
            self.param_widgets["exe"] = e

        elif accion == "reproducir_spotify":
            lbl("URI de Spotify  (spotify:track:...  o  spotify:playlist:...):")
            e = self._entry(self.frame_params)
            e.pack(fill="x", pady=(2, 4))
            self.param_widgets["uri"] = e

        else:
            tk.Label(self.frame_params, text="Sin parámetros adicionales.",
                     bg=BG2, fg=FG2, font=FONT_SM).pack(anchor="w", pady=4)

    def _browse(self, entry):
        path = filedialog.askopenfilename(
            filetypes=[("Ejecutable", "*.exe"), ("Todos", "*.*")])
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)

    def _populate(self, cmd):
        self.e_nombre.insert(0,    cmd.get("nombre", ""))
        self.e_trigger.insert(0,   cmd.get("trigger", ""))
        self.e_respuesta.insert(0, cmd.get("respuesta", ""))
        self.var_activo.set(cmd.get("activo", True))
        accion = cmd.get("accion", "solo_hablar")
        self.var_accion.set(ACTION_LABELS.get(accion, ACTION_LABELS["solo_hablar"]))
        self._refresh_params()
        params = cmd.get("params", {})
        for key, widget in self.param_widgets.items():
            if key in params:
                widget.insert(0, params[key])

    def _test_voice(self):
        texto = self.e_respuesta.get().strip()
        if not texto:
            messagebox.showwarning("Sin texto",
                                   "Escribe una respuesta primero.", parent=self)
            return

        def _speak():
            try:
                import pyttsx3
                eng = pyttsx3.init()
                eng.setProperty("rate", 145)
                eng.setProperty("volume", 1.0)
                for v in eng.getProperty("voices"):
                    if any(x in v.id.lower()
                           for x in ("helena", "sabina", "es-", "spanish")):
                        eng.setProperty("voice", v.id)
                        break
                eng.say(texto)
                eng.runAndWait()
            except Exception as ex:
                self.after(0, lambda: messagebox.showerror(
                    "Error TTS", str(ex), parent=self))

        threading.Thread(target=_speak, daemon=True).start()

    def _save(self):
        nombre  = self.e_nombre.get().strip()
        trigger = self.e_trigger.get().strip().lower()
        if not nombre or not trigger:
            messagebox.showwarning("Campos requeridos",
                                   "Nombre y frase de activación son obligatorios.",
                                   parent=self)
            return
        params = {k: w.get().strip() for k, w in self.param_widgets.items()}
        result = {
            "id":        self._cmd.get("id", str(uuid.uuid4())),
            "nombre":    nombre,
            "trigger":   trigger,
            "accion":    LABEL_TO_KEY.get(self.var_accion.get(), "solo_hablar"),
            "params":    params,
            "respuesta": self.e_respuesta.get().strip(),
            "activo":    self.var_activo.get(),
        }
        if self.on_save:
            self.on_save(result)
        self.destroy()

    def _center(self):
        self.update_idletasks()
        w  = 520
        h  = self.winfo_reqheight()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")


# ══════════════════════════════════════════════════════════════════════════════
#  Ventana principal
# ══════════════════════════════════════════════════════════════════════════════
class JarvisGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("JARVIS — Panel de Control")
        self.configure(bg=BG)
        self.geometry("920x650")
        # Icono de la ventana (usa .ico para barra de tareas y título)
        _ico_path = os.path.join(BASE_DIR, "icon.ico")
        _png_path = os.path.join(BASE_DIR, "icon.png")
        try:
            if os.path.exists(_ico_path):
                self.iconbitmap(_ico_path)
            elif os.path.exists(_png_path):
                _img = tk.PhotoImage(file=_png_path)
                self.iconphoto(True, _img)
                self._icon_img = _img
        except Exception:
            pass
        self.minsize(800, 520)
        self.commands    = load_commands()
        self.jarvis_proc = None
        self.log_queue   = queue.Queue()
        self._status_var = tk.StringVar(value="● DETENIDO")
        self._last_heard = tk.StringVar(value="—")
        self._tray       = None
        self._apply_theme()
        self._build_ui()
        self._refresh_table()
        self._poll_log()
        self._setup_tray()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # Comprobar actualizaciones 8 segundos después del inicio (no bloquea UI)
        if _HAS_UPDATER:
            self.after(8000, lambda: threading.Thread(
                target=self._check_update_async, daemon=True).start())

    # ── Tema ──────────────────────────────────────────────────────────────────
    def _apply_theme(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, font=FONT)
        s.configure("TNotebook",     background=BG2, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG3, foreground=FG2,
                    padding=[14, 6], font=FONT)
        s.map("TNotebook.Tab",
              background=[("selected", BG2)],
              foreground=[("selected", ACCENT)])
        s.configure("Treeview", background=CARD, fieldbackground=CARD,
                    foreground=FG, rowheight=28, font=FONT)
        s.configure("Treeview.Heading", background=BG3, foreground=ACCENT,
                    font=FONT_B, relief="flat")
        s.map("Treeview",
              background=[("selected", BG3)],
              foreground=[("selected", ACCENT)])
        s.configure("TScrollbar", background=BG3, troughcolor=BG,
                    arrowcolor=FG2, borderwidth=0)
        s.configure("Horizontal.TScale", background=BG2,
                    troughcolor=BG3, sliderlength=16)
        s.configure("TCombobox", fieldbackground=BG3, background=BG3,
                    foreground=FG, arrowcolor=ACCENT,
                    selectbackground=BG3, selectforeground=FG)
        s.map("TCombobox", fieldbackground=[("readonly", BG3)])
        self.option_add("*TCombobox*Listbox.background", BG3)
        self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", BG)

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=BG2, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text=" JARVIS", font=FONT_H1,
                 bg=BG2, fg=ACCENT).pack(side="left", padx=20)
        tk.Label(hdr, text="Panel de Control",
                 font=FONT, bg=BG2, fg=FG2).pack(side="left")
        self.lbl_status = tk.Label(
            hdr, textvariable=self._status_var,
            font=FONT_B, bg=BG2, fg=RED)
        self.lbl_status.pack(side="right", padx=20)

        # Franja de color
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

        # Banner de actualización (oculto hasta que haya novedad)
        self._update_banner = tk.Frame(self, bg="#4a3a00", pady=4)
        self._update_lbl    = tk.Label(
            self._update_banner, text="", bg="#4a3a00", fg=YELLOW,
            font=FONT_SM)
        self._update_lbl.pack(side="left", padx=(14, 8))
        self._update_btn = tk.Button(
            self._update_banner, text="⬆ Actualizar ahora",
            bg=YELLOW, fg="#0d0d1a", font=FONT_SM, relief="flat",
            padx=8, pady=2, cursor="hand2")
        self._update_btn.pack(side="left")
        # No se hace .pack() del banner hasta que haya una actualización

        # Cuerpo
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True)
        self._build_sidebar(body)
        self.nb = ttk.Notebook(body)
        self.nb.pack(fill="both", expand=True, padx=6, pady=6)
        self._build_tab_commands()
        self._build_tab_settings()
        self._build_tab_console()
        self._build_tab_help()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=BG2, width=180)
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        def sec(text):
            tk.Label(sb, text=text, bg=BG2, fg=FG2,
                     font=("Segoe UI", 8, "bold")).pack(
                anchor="w", padx=14, pady=(18, 4))

        def sbtn(text, cmd, color=FG):
            return tk.Button(sb, text=text, command=cmd,
                             bg=BG3, fg=color,
                             activebackground=BG, activeforeground=color,
                             relief="flat", font=FONT_SM, anchor="w",
                             padx=12, pady=7, cursor="hand2")

        sec("CONTROL")
        self.btn_start = sbtn("▶  Iniciar JARVIS", self._start_jarvis, GREEN)
        self.btn_start.pack(fill="x", padx=10, pady=2)
        self.btn_stop = sbtn("■  Detener JARVIS", self._stop_jarvis, RED)
        self.btn_stop.pack(fill="x", padx=10, pady=2)
        self.btn_stop.configure(state="disabled")

        tk.Frame(sb, bg=BG3, height=1).pack(fill="x", padx=10, pady=10)

        sec("ESTADO")
        self._listening_var = tk.StringVar(value="⬜  En espera")
        self.lbl_listening = tk.Label(
            sb, textvariable=self._listening_var,
            bg=BG2, fg=FG2, font=("Segoe UI", 10, "bold"),
            wraplength=154, justify="center")
        self.lbl_listening.pack(fill="x", padx=10, pady=(2, 8))

        sec("ÚLTIMA ORDEN")
        tk.Label(sb, textvariable=self._last_heard,
                 bg=BG2, fg=ACCENT, font=FONT_SM,
                 wraplength=154, justify="left").pack(anchor="w", padx=14)

        tk.Frame(sb, bg=BG3, height=1).pack(fill="x", padx=10, pady=10)

        sec("ATAJOS")
        sbtn("🔊 Probar voz", self._quick_test_voice).pack(
            fill="x", padx=10, pady=2)
        sbtn("📂 Abrir config.py", self._open_config).pack(
            fill="x", padx=10, pady=2)

    # ── Tab: Comandos ─────────────────────────────────────────────────────────
    def _build_tab_commands(self):
        tab = tk.Frame(self.nb, bg=BG2)
        self.nb.add(tab, text="  Comandos  ")

        tb = tk.Frame(tab, bg=BG2)
        tb.pack(fill="x", padx=8, pady=(10, 4))

        def tbtn(text, cmd, danger=False):
            c = RED if danger else ACCENT
            return tk.Button(tb, text=text, command=cmd,
                             bg=BG3, fg=c,
                             activebackground=BG, activeforeground=c,
                             relief="flat", font=FONT_SM, padx=10, pady=5,
                             cursor="hand2")

        tbtn("+ Agregar",             self._add_cmd).pack(side="left", padx=2)
        tbtn("✎ Editar",              self._edit_cmd).pack(side="left", padx=2)
        tbtn("✕ Eliminar",            self._del_cmd, True).pack(side="left", padx=2)
        tbtn("⏻ Activar/Desactivar",  self._toggle_cmd).pack(side="left", padx=2)

        tk.Label(tb, text="Doble clic para editar",
                 bg=BG2, fg=FG2, font=FONT_SM).pack(side="right", padx=8)

        cols = ("nombre", "trigger", "accion", "activo")
        self.tree = ttk.Treeview(tab, columns=cols, show="headings",
                                 selectmode="browse")
        for col, hdr, w, anc in [
            ("nombre",  "Nombre",             165, "w"),
            ("trigger", "Frase de activación", 215, "w"),
            ("accion",  "Acción",              210, "w"),
            ("activo",  "Estado",               90, "center"),
        ]:
            self.tree.heading(col, text=hdr)
            self.tree.column(col, width=w, minwidth=70, anchor=anc)

        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True,
                       padx=(8, 0), pady=(0, 8))
        vsb.pack(side="right", fill="y", pady=(0, 8), padx=(0, 8))

        self.tree.tag_configure("inactive", foreground=FG2)
        self.tree.bind("<Double-Button-1>", lambda _: self._edit_cmd())

    # ── Tab: Configuración ────────────────────────────────────────────────────
    def _build_tab_settings(self):
        tab = tk.Frame(self.nb, bg=BG2)
        self.nb.add(tab, text="  Configuración  ")

        # Canvas con scroll vertical para que quepan todas las secciones
        canvas = tk.Canvas(tab, bg=BG2, highlightthickness=0)
        vsb    = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        inner  = tk.Frame(canvas, bg=BG2)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        vsb.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)

        def sec(text):
            tk.Label(inner, text=text, bg=BG2, fg=ACCENT,
                     font=FONT_B).pack(anchor="w", padx=20, pady=(18, 4))
            tk.Frame(inner, bg=BG3, height=1).pack(fill="x", padx=20,
                                                    pady=(0, 8))

        def row(label_text):
            f = tk.Frame(inner, bg=BG2)
            f.pack(fill="x", padx=20, pady=4)
            tk.Label(f, text=label_text, bg=BG2, fg=FG2, font=FONT_SM,
                     width=26, anchor="w").pack(side="left")
            return f

        # ── Voz
        sec("🔊  Voz  (TTS)")
        f = row("Velocidad de habla")
        self.var_rate = tk.IntVar(value=145)
        ttk.Scale(f, from_=60, to=250, variable=self.var_rate,
                  orient="horizontal", length=200).pack(side="left", padx=4)
        lbl_rate = tk.Label(f, textvariable=self.var_rate,
                            bg=BG2, fg=FG, font=FONT_SM, width=4)
        lbl_rate.pack(side="left")

        f = row("Volumen  (0.0 – 1.0)")
        self.var_vol = tk.DoubleVar(value=1.0)
        ttk.Scale(f, from_=0.0, to=1.0, variable=self.var_vol,
                  orient="horizontal", length=200).pack(side="left", padx=4)
        self.lbl_vol = tk.Label(f, text="1.00", bg=BG2, fg=FG,
                                font=FONT_SM, width=5)
        self.lbl_vol.pack(side="left")
        self.var_vol.trace_add(
            "write",
            lambda *_: self.lbl_vol.configure(
                text=f"{self.var_vol.get():.2f}"))

        f = row("Voz del sistema")
        self.var_voice = tk.StringVar(value="Auto (español preferido)")
        voices = ["Auto (español preferido)"] + self._get_voice_names()
        ttk.Combobox(f, textvariable=self.var_voice, values=voices,
                     state="readonly", width=36,
                     font=FONT).pack(side="left", padx=4)

        # ── Reconocimiento de voz
        sec("🎙  Reconocimiento de voz")
        f = row("Palabra clave de activación")
        self.var_keyword = tk.StringVar(value="hola jarvis")
        tk.Entry(f, textvariable=self.var_keyword, bg=BG3, fg=FG,
                 insertbackground=FG, relief="flat", font=FONT,
                 bd=6, width=26).pack(side="left", padx=4)

        f = row("Idioma de escucha")
        self.var_lang = tk.StringVar(value="es-ES")
        ttk.Combobox(f, textvariable=self.var_lang,
                     values=["es-ES", "es-AR", "es-MX", "es-CL", "en-US"],
                     state="readonly", width=12,
                     font=FONT).pack(side="left", padx=4)

        # ── Saludo
        sec("💬  Saludo de bienvenida")
        f = row("Texto que dirá JARVIS al activarse")
        self.var_saludo = tk.StringVar(
            value="Hola señor Maxi, ¿cómo está su día? ¿Qué necesita de mí?")
        tk.Entry(f, textvariable=self.var_saludo, bg=BG3, fg=FG,
                 insertbackground=FG, relief="flat", font=FONT,
                 bd=6, width=44).pack(side="left", padx=4)

        # ── Nombre del usuario
        sec("👤  Nombre del usuario")
        f = row("Cómo te llama JARVIS (ej. señor García)")
        self.var_nombre = tk.StringVar(value="señor Maxi")
        tk.Entry(f, textvariable=self.var_nombre, bg=BG3, fg=FG,
                 insertbackground=FG, relief="flat", font=FONT,
                 bd=6, width=26).pack(side="left", padx=4)

        # ── Auto-actualización
        sec("🔄  Auto-actualización")
        f = row("URL del version.json remoto")
        _DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/codezxmax/JARVIS/master/version.json"
        self.var_update_url = tk.StringVar(value=_DEFAULT_UPDATE_URL)
        tk.Entry(f, textvariable=self.var_update_url, bg=BG3, fg=FG,
                 insertbackground=FG, relief="flat", font=FONT,
                 bd=6, width=44).pack(side="left", padx=4)
        tk.Label(inner, text=(
            "URL donde JARVIS buscará actualizaciones automáticamente.\n"
            "Deja vacío para deshabilitar la comprobación de actualizaciones."),
                 bg=BG2, fg=FG2, font=FONT_SM, justify="left").pack(
            anchor="w", padx=26, pady=(0, 6))
        tk.Button(inner, text="🔍 Comprobar ahora", command=self._check_update_manual,
                  bg=BG3, fg=ACCENT, activebackground=BG, activeforeground=ACCENT,
                  relief="flat", font=FONT_SM, padx=10, pady=4,
                  cursor="hand2").pack(anchor="w", padx=20, pady=(0, 4))

        # ── Botones
        tk.Frame(inner, bg=BG3, height=1).pack(fill="x", padx=20, pady=14)
        brow = tk.Frame(inner, bg=BG2)
        brow.pack(fill="x", padx=20, pady=(0, 20))

        def cbtn(text, cmd):
            return tk.Button(brow, text=text, command=cmd,
                             bg=BG3, fg=ACCENT,
                             activebackground=BG, activeforeground=ACCENT,
                             relief="flat", font=FONT_SM, padx=10, pady=6,
                             cursor="hand2")

        cbtn("🔊 Probar voz ahora",      self._test_voice_settings).pack(side="left", padx=2)
        cbtn("💾 Guardar configuración", self._save_settings).pack(side="left", padx=2)

        self._load_settings_ui()

    # ── Tab: Consola ──────────────────────────────────────────────────────────
    def _build_tab_console(self):
        tab = tk.Frame(self.nb, bg=BG)
        self.nb.add(tab, text="  Consola  ")

        tb = tk.Frame(tab, bg=BG)
        tb.pack(fill="x", padx=8, pady=(8, 4))
        tk.Button(tb, text="🗑 Limpiar", command=self._clear_log,
                  bg=BG3, fg=ACCENT, activebackground=BG,
                  activeforeground=ACCENT, relief="flat", font=FONT_SM,
                  padx=10, pady=5, cursor="hand2").pack(side="left", padx=2)
        tk.Label(tb, text="Salida en tiempo real de JARVIS",
                 bg=BG, fg=FG2, font=FONT_SM).pack(side="left", padx=10)

        self.console = tk.Text(
            tab, bg=BG2, fg=FG, font=FONT_MONO,
            insertbackground=FG, relief="flat",
            state="disabled", wrap="word", padx=8, pady=4)
        vsb = ttk.Scrollbar(tab, orient="vertical", command=self.console.yview)
        self.console.configure(yscrollcommand=vsb.set)
        self.console.pack(side="left", fill="both", expand=True,
                          padx=(8, 0), pady=(0, 8))
        vsb.pack(side="right", fill="y", pady=(0, 8), padx=(0, 8))

        self.console.tag_configure("heard", foreground=ACCENT)
        self.console.tag_configure("spoke", foreground="#6699ff")
        self.console.tag_configure("ok",    foreground=GREEN)
        self.console.tag_configure("warn",  foreground=YELLOW)
        self.console.tag_configure("error", foreground=RED)
        self.console.tag_configure("info",  foreground=FG2)

    # ── Tab: Ayuda ────────────────────────────────────────────────────────────
    def _build_tab_help(self):
        tab = tk.Frame(self.nb, bg=BG2)
        self.nb.add(tab, text="  ❓ Ayuda  ")

        vsb = ttk.Scrollbar(tab, orient="vertical")
        vsb.pack(side="right", fill="y", pady=8, padx=(0, 8))

        txt = tk.Text(tab, bg=BG2, fg=FG, font=FONT_MONO,
                      wrap="word", relief="flat",
                      yscrollcommand=vsb.set,
                      padx=18, pady=14, cursor="arrow",
                      state="normal")
        txt.pack(side="left", fill="both", expand=True,
                 padx=(8, 0), pady=8)
        vsb.config(command=txt.yview)

        txt.tag_configure("h1",   font=("Segoe UI", 15, "bold"), foreground=ACCENT)
        txt.tag_configure("h2",   font=("Segoe UI", 10, "bold"), foreground=YELLOW)
        txt.tag_configure("code", font=FONT_MONO,                foreground=GREEN,
                          background=BG3)
        txt.tag_configure("body", font=("Segoe UI", 10),         foreground=FG)
        txt.tag_configure("dim",  font=("Segoe UI", 9),          foreground=FG2)

        content = [
            ("h1",   "🤖  Guía de uso de JARVIS\n\n"),

            ("h2",   "▸  Activación\n"),
            ("body", '  Diga "hola jarvis" o simplemente "jarvis" para activar el asistente.\n'
                     '  JARVIS responderá con un saludo y esperará su orden.\n'
                     '  También puede decir "jarvis [comando]" directamente sin esperar.\n\n'),

            ("h2",   "▸  Comandos de voz incorporados\n"),
            ("code", '  "jarvis suspende"                  '),
            ("body", "→  Suspende el PC (pide confirmación)\n"),
            ("code", '  "jarvis modo café"                 '),
            ("body", "→  Abre Chrome con sus sitios + sistema + música\n"),
            ("code", '  "jarvis pausa la música"           '),
            ("body", "→  Pausa / reanuda Spotify\n"),
            ("code", '  "jarvis música que me gusta"       '),
            ("body", "→  Reproduce su playlist favorita\n"),
            ("code", '  "busca la canción [nombre]"        '),
            ("body", "→  Busca y reproduce en Spotify\n"),
            ("code", '  "busca en spotify [artista]"       '),
            ("body", "→  Busca artista/álbum en Spotify\n\n"),

            ("h2",   "▸  Pláticas y preguntas\n"),
            ("body", '  JARVIS entiende frases naturales; no hace falta decir "jarvis" antes:\n\n'),
            ("code", '  "cómo estás"       '),
            ("body", "→  JARVIS responde cómo se encuentra\n"),
            ("code", '  "qué hora es"      '),
            ("body", "→  Dice la hora actual\n"),
            ("code", '  "qué día es"       '),
            ("body", "→  Dice la fecha de hoy\n"),
            ("code", '  "quién eres"       '),
            ("body", "→  Se presenta\n"),
            ("code", '  "qué puedes hacer" '),
            ("body", "→  Lista sus capacidades\n"),
            ("code", '  "gracias"          '),
            ("body", "→  Responde cortésmente\n"),
            ("code", '  "hasta luego"      '),
            ("body", "→  Se despide\n\n"),

            ("h2",   "▸  Confirmación de suspensión\n"),
            ("body", '  Cuando JARVIS pregunte "¿de verdad quiere ejecutar esa orden?"\n'
                     '  responda con: sí, sí porfa, dale, claro, confirmo, adelante...\n'
                     '  Cualquier otra respuesta cancela la operación.\n\n'),

            ("h2",   "▸  Comandos personalizados\n"),
            ("body", '  Agréguelos desde la pestaña Comandos → botón Agregar.\n'
                     '  Cada entrada tiene: nombre, frase activadora y acción.\n'
                     '  Acciones disponibles: abrir URL, abrir aplicación, Spotify URI,\n'
                     '  controles de medios (play/pausa, siguiente, anterior),\n'
                     '  modo café, suspender PC, o solo responder con voz.\n'
                     '  Puede activar/desactivar comandos sin eliminarlos.\n\n'),

            ("h2",   "▸  Nombre y configuración\n"),
            ("body", '  En la pestaña Configuración puede personalizar:\n'
                     '  • Nombre con el que JARVIS lo llama (por defecto: señor Maxi)\n'
                     '  • Frase de activación (keyword)\n'
                     '  • Velocidad y volumen de la voz\n'
                     '  • Saludo inicial al arrancar\n'
                     '  • Idioma de reconocimiento de voz\n\n'),

            ("h2",   "▸  Ícono en la bandeja del sistema\n"),
            ("body", '  Al minimizar la ventana, JARVIS se oculta en la bandeja.\n'
                     '  Haga clic derecho sobre el ícono para:\n'
                     '  • Mostrar panel  →  abre la ventana principal\n'
                     '  • Detener JARVIS →  detiene el asistente sin cerrar el panel\n'
                     '  • Salir          →  cierra completamente JARVIS\n\n'),

            ("h2",   "▸  Mensajes automáticos\n"),
            ("body", '  Si no hay actividad por 12 minutos, JARVIS envía un mensaje\n'
                     '  para confirmar que sigue activo y operativo.\n\n'),

            ("h2",   "▸  Actualización automática\n"),
            ("body", '  JARVIS comprueba actualizaciones al arrancar (8 segundos de espera).\n'
                     '  Si hay una versión nueva, aparece un banner de notificación.\n'
                     '  Configure la URL del archivo version.json en la pestaña Configuración.\n'),
            ("dim",  '  URL por defecto:\n'
                     '  https://raw.githubusercontent.com/codezxmax/JARVIS/master/version.json\n\n'),

            ("h2",   "▸  Indicadores de estado\n"),
            ("body", '  🔴 ESCUCHANDO  →  micrófono activo, puede hablar\n'
                     '  🔊 HABLANDO    →  JARVIS está respondiendo\n'
                     '  ⬜ En espera   →  esperando activación\n\n'),

            ("h2",   "▸  Consejos para mejor reconocimiento\n"),
            ("body", '  • Hable a velocidad normal y con voz clara.\n'
                     '  • Espere a que el indicador muestre 🔴 ESCUCHANDO antes de hablar.\n'
                     '  • El volumen del sistema baja automáticamente al escuchar\n'
                     '    y se restaura al terminar.\n'
                     '  • El micrófono se calibra 2 segundos al arrancar: haga silencio.\n'
                     '  • Si hay errores de audio continuos, detenga y reinicie JARVIS.\n'
                     '  • Puede ver errores y texto reconocido en la pestaña Consola.\n'),
        ]
        for tag, text in content:
            txt.insert("end", text, tag)
        txt.configure(state="disabled")

    # ── CRUD de comandos ──────────────────────────────────────────────────────
    def _refresh_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for cmd in self.commands:
            label  = ACTION_LABELS.get(cmd["accion"], cmd["accion"])
            activo = cmd.get("activo", True)
            estado = "✔ Activo" if activo else "✗ Inactivo"
            tag    = "" if activo else "inactive"
            self.tree.insert("", "end", iid=cmd["id"],
                             values=(cmd["nombre"], cmd["trigger"],
                                     label, estado),
                             tags=(tag,))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            return None, None
        iid = sel[0]
        for i, c in enumerate(self.commands):
            if c["id"] == iid:
                return i, c
        return None, None

    def _add_cmd(self):
        CommandDialog(self, on_save=self._on_saved)

    def _edit_cmd(self):
        _, cmd = self._selected()
        if cmd is None:
            messagebox.showinfo("Sin selección",
                                "Selecciona un comando de la lista.", parent=self)
            return
        CommandDialog(self, cmd=cmd, on_save=self._on_saved)

    def _on_saved(self, new_cmd):
        for i, c in enumerate(self.commands):
            if c["id"] == new_cmd["id"]:
                self.commands[i] = new_cmd
                break
        else:
            self.commands.append(new_cmd)
        save_commands(self.commands)
        self._refresh_table()

    def _del_cmd(self):
        idx, cmd = self._selected()
        if cmd is None:
            messagebox.showinfo("Sin selección",
                                "Selecciona un comando primero.", parent=self)
            return
        if messagebox.askyesno("Eliminar",
                               f"¿Eliminar «{cmd['nombre']}»?", parent=self):
            self.commands.pop(idx)
            save_commands(self.commands)
            self._refresh_table()

    def _toggle_cmd(self):
        idx, _ = self._selected()
        if idx is None:
            return
        self.commands[idx]["activo"] = not self.commands[idx].get("activo", True)
        save_commands(self.commands)
        self._refresh_table()

    # ── Control JARVIS (subprocess) ───────────────────────────────────────────
    def _start_jarvis(self):
        if self.jarvis_proc and self.jarvis_proc.poll() is None:
            return
        self._log("▶ Iniciando JARVIS...\n", "info")
        try:
            self.jarvis_proc = subprocess.Popen(
                [PYTHON_EXE, "-u", JARVIS_SCRIPT],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as ex:
            self._log(f"Error al iniciar: {ex}\n", "error")
            return
        self._status_var.set("● ACTIVO")
        self.lbl_status.configure(fg=GREEN)
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self._update_tray_title(True)
        threading.Thread(target=self._read_output, daemon=True).start()

    def _stop_jarvis(self):
        if self.jarvis_proc:
            self.jarvis_proc.terminate()
            self.jarvis_proc = None
        self._set_stopped()
        self._log("■ JARVIS detenido.\n", "info")

    def _set_stopped(self):
        self._status_var.set("● DETENIDO")
        self.lbl_status.configure(fg=RED)
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self._set_listening_ui("esperando")
        self._update_tray_title(False)

    def _set_listening_ui(self, state: str):
        """Actualiza el indicador de estado del sidebar. state: escuchando|hablando|esperando"""
        if state == "escuchando":
            self._listening_var.set("🔴  ESCUCHANDO...")
            self.lbl_listening.configure(fg="#ff4466")
        elif state == "hablando":
            self._listening_var.set("🔊  HABLANDO...")
            self.lbl_listening.configure(fg=ACCENT)
        else:
            self._listening_var.set("⬜  En espera")
            self.lbl_listening.configure(fg=FG2)

    def _read_output(self):
        for line in self.jarvis_proc.stdout:
            stripped = line.strip()
            # ── Estado de escucha ─────────────────────────────────────────
            if "[ESCUCHANDO]" in stripped:
                self.after(0, self._set_listening_ui, "escuchando")
                tag = "info"
            elif "[LISTO]" in stripped:
                self.after(0, self._set_listening_ui, "esperando")
                tag = "info"
            elif "JARVIS:" in stripped:
                self.after(0, self._set_listening_ui, "hablando")
                tag = "spoke"
            # ── Otros mensajes ────────────────────────────────────────────
            elif "Escuché:" in stripped:
                tag = "heard"
                heard = stripped.split("Escuché:")[-1].strip().strip("'\"")
                self.after(0, lambda v=heard: self._last_heard.set(v))
                self.after(0, self._set_listening_ui, "esperando")
            elif "✅" in stripped:
                tag = "ok"
            elif "⚠" in stripped:
                tag = "warn"
            elif "❌" in stripped or "Error" in stripped:
                tag = "error"
                self.after(0, self._set_listening_ui, "esperando")
            else:
                tag = "info"
            self.log_queue.put((line, tag))
        self.log_queue.put(("─── JARVIS finalizado ───\n", "info"))
        self.after(0, self._set_listening_ui, "esperando")
        self.after(0, self._set_stopped)

    def _poll_log(self):
        while not self.log_queue.empty():
            line, tag = self.log_queue.get_nowait()
            self._log(line, tag)
        self.after(100, self._poll_log)

    def _log(self, text, tag="info"):
        self.console.configure(state="normal")
        self.console.insert("end", text, tag)
        self.console.see("end")
        self.console.configure(state="disabled")

    def _clear_log(self):
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")

    # ── Configuración ─────────────────────────────────────────────────────────
    def _get_voice_names(self):
        try:
            import pyttsx3
            eng   = pyttsx3.init()
            names = [v.name for v in eng.getProperty("voices")]
            eng.stop()
            return names
        except Exception:
            return []

    def _load_settings_ui(self):
        s = load_settings()
        if not s:
            return
        self.var_rate.set(s.get("rate", 145))
        vol = s.get("volume", 1.0)
        self.var_vol.set(vol)
        self.lbl_vol.configure(text=f"{vol:.2f}")
        self.var_voice.set(s.get("voice", "Auto (español preferido)"))
        self.var_keyword.set(s.get("keyword", "hola jarvis"))
        self.var_lang.set(s.get("lang", "es-ES"))
        self.var_saludo.set(
            s.get("saludo",
                  "Hola señor Maxi, ¿cómo está su día? ¿Qué necesita de mí?"))
        self.var_nombre.set(s.get("nombre", "señor Maxi"))
        _DEF = "https://raw.githubusercontent.com/codezxmax/JARVIS/master/version.json"
        self.var_update_url.set(s.get("update_url", "") or _DEF)

    def _save_settings(self):
        data = {
            "rate":       self.var_rate.get(),
            "volume":     round(self.var_vol.get(), 2),
            "voice":      self.var_voice.get(),
            "keyword":    self.var_keyword.get().lower().strip(),
            "lang":       self.var_lang.get(),
            "saludo":     self.var_saludo.get().strip(),
            "nombre":     self.var_nombre.get().strip() or "señor Maxi",
            "update_url": self.var_update_url.get().strip(),
        }
        save_settings(data)
        messagebox.showinfo(
            "Guardado",
            "Configuración guardada.\nReinicia JARVIS para aplicar los cambios.",
            parent=self)

    def _test_voice_settings(self):
        texto = self.var_saludo.get().strip() or "Probando la voz de JARVIS."
        rate  = self.var_rate.get()
        vol   = self.var_vol.get()
        vname = self.var_voice.get()

        def _speak():
            try:
                import pyttsx3
                eng = pyttsx3.init()
                eng.setProperty("rate", rate)
                eng.setProperty("volume", vol)
                if vname != "Auto (español preferido)":
                    for v in eng.getProperty("voices"):
                        if v.name == vname:
                            eng.setProperty("voice", v.id)
                            break
                else:
                    for v in eng.getProperty("voices"):
                        if any(x in v.id.lower()
                               for x in ("helena", "sabina", "es-", "spanish")):
                            eng.setProperty("voice", v.id)
                            break
                eng.say(texto)
                eng.runAndWait()
            except Exception as ex:
                self.after(0, lambda: messagebox.showerror(
                    "Error TTS", str(ex), parent=self))

        threading.Thread(target=_speak, daemon=True).start()

    def _quick_test_voice(self):
        """Prueba rápida de voz desde el sidebar."""
        def _speak():
            try:
                import pyttsx3
                eng = pyttsx3.init()
                eng.setProperty("rate", 145)
                eng.setProperty("volume", 1.0)
                for v in eng.getProperty("voices"):
                    if any(x in v.id.lower()
                           for x in ("helena", "sabina", "es-", "spanish")):
                        eng.setProperty("voice", v.id)
                        break
                eng.say("JARVIS operativo, señor Maxi.")
                eng.runAndWait()
            except Exception:
                pass
        threading.Thread(target=_speak, daemon=True).start()

    def _open_config(self):
        path = os.path.join(BASE_DIR, "config.py")
        if os.path.exists(path):
            os.startfile(path)
        else:
            messagebox.showwarning("No encontrado",
                                   f"No se encontró {path}", parent=self)

    # ── Bandeja del sistema (pystray) ─────────────────────────────────────────
    def _setup_tray(self):
        if not _HAS_TRAY:
            return
        icon_path = os.path.join(BASE_DIR, "icon.png")
        try:
            img = PilImage.open(icon_path).resize((64, 64), PilImage.LANCZOS)
        except Exception:
            img = PilImage.new("RGB", (64, 64), color=(0, 212, 170))
        menu = pystray.Menu(
            pystray.MenuItem("Mostrar panel", self._show_window, default=True),
            pystray.MenuItem("Detener JARVIS", self._stop_jarvis_from_tray),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._quit_from_tray),
        )
        self._tray = pystray.Icon("JARVIS", img, "JARVIS — Panel de Control", menu)
        self._tray.run_detached()

    def _update_tray_title(self, activo: bool):
        if _HAS_TRAY and self._tray is not None:
            try:
                self._tray.title = "JARVIS — ACTIVO" if activo else "JARVIS — Panel de Control"
            except Exception:
                pass

    def _show_window(self, icon=None, item=None):
        self.after(0, self._do_show_window)

    def _do_show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def _stop_jarvis_from_tray(self, icon=None, item=None):
        self.after(0, self._stop_jarvis)

    def _quit_from_tray(self, icon=None, item=None):
        self.after(0, self.on_close)

    def _on_close(self):
        """WM_DELETE_WINDOW: minimiza a bandeja si está disponible."""
        if _HAS_TRAY and self._tray is not None:
            self.withdraw()
        else:
            self.on_close()

    def on_close(self):
        if _HAS_TRAY and self._tray is not None:
            try:
                self._tray.stop()
            except Exception:
                pass
        self._stop_jarvis()
        self.destroy()

    # ── Auto-actualización ────────────────────────────────────────────────────
    def _check_update_async(self):
        """Corre en hilo daemon. Muestra banner si hay actualización."""
        try:
            _updater.check_and_notify(parent=self)
        except Exception:
            pass

    def _show_update_banner(self, info: dict):
        """Muestra la barra amarilla de actualización disponible."""
        ver = info.get("version", "?")
        self._update_lbl.configure(
            text=f"Nueva versión {ver} disponible.")
        self._update_btn.configure(
            command=lambda: threading.Thread(
                target=lambda: _updater.check_and_notify(parent=self),
                daemon=True).start())
        self._update_banner.pack(fill="x", after=self._update_banner.master.children.get(
            list(self._update_banner.master.children)[-2], None))

    def _check_update_manual(self):
        """Botón 'Comprobar ahora' en la pestaña Configuración."""
        url = self.var_update_url.get().strip()
        if not url:
            messagebox.showinfo(
                "Sin URL",
                "Introduce la URL del version.json remoto en el campo de arriba "
                "y guarda la configuración primero.",
                parent=self)
            return
        # Guardar la URL antes de comprobar
        self._save_settings()
        if not _HAS_UPDATER:
            messagebox.showerror("updater.py no encontrado",
                                 "El módulo updater.py no está disponible.",
                                 parent=self)
            return
        threading.Thread(
            target=lambda: _updater.check_and_notify(parent=self),
            daemon=True).start()


# ── Punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = JarvisGUI()
    app.mainloop()
