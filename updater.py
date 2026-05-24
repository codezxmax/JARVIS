"""
updater.py — Auto-actualización de JARVIS
==========================================
Compara la versión local (version.json) con la versión publicada en la URL
configurada en jarvis_settings.json ("update_url"). Si hay novedad descarga
el instalador y lo ejecuta para que el usuario actualice sin esfuerzo.

Uso desde otro módulo:
    import updater
    updater.check_and_notify(parent_window)   # llama en hilo daemon
"""

import json
import os
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from urllib import error, request

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
LOCAL_VER_FILE = os.path.join(BASE_DIR, "version.json")
SETTINGS_FILE  = os.path.join(BASE_DIR, "jarvis_settings.json")


# ── Helpers internos ──────────────────────────────────────────────────────────

def _ver_tuple(s: str) -> tuple:
    """Convierte '2.1.0' → (2, 1, 0) para comparación numérica."""
    try:
        return tuple(int(x) for x in str(s).strip().split("."))
    except Exception:
        return (0,)


def _load_local_info() -> dict:
    if os.path.exists(LOCAL_VER_FILE):
        try:
            with open(LOCAL_VER_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"version": "0.0", "download_url": "", "changelog": ""}


def _load_update_url() -> str:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                s = json.load(f)
            return s.get("update_url", "").strip()
        except Exception:
            pass
    return ""


# ── API pública ───────────────────────────────────────────────────────────────

def fetch_remote_info(url: str) -> dict | None:
    """
    Descarga el version.json remoto desde `url`.
    Devuelve el dict con los campos, o None si falla.
    """
    try:
        req = request.Request(url, headers={"User-Agent": "JARVIS-Updater/1.0"})
        with request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data
    except Exception:
        return None


def is_update_available(remote: dict) -> bool:
    """True si la versión remota es estrictamente mayor que la local."""
    local   = _load_local_info()
    rv = _ver_tuple(remote.get("version", "0.0"))
    lv = _ver_tuple(local.get("version",  "0.0"))
    return rv > lv


def download_installer(download_url: str, progress_cb=None) -> str | None:
    """
    Descarga el instalador .exe al directorio temporal.
    progress_cb(downloaded_bytes, total_bytes) — callback opcional.
    Devuelve la ruta del archivo descargado, o None si falla.
    """
    dest = os.path.join(tempfile.gettempdir(), "jarvis_update_setup.exe")
    try:
        req = request.Request(
            download_url, headers={"User-Agent": "JARVIS-Updater/1.0"}
        )
        with request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            done  = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        progress_cb(done, total)
        return dest
    except Exception:
        return None


def run_installer(path: str) -> None:
    """Lanza el instalador de forma silenciosa y sale de JARVIS."""
    subprocess.Popen([path, "/SILENT", "/NORESTART"])


# ── Ventana de progreso de descarga ──────────────────────────────────────────

class _DownloadDialog(tk.Toplevel):
    """Ventana modal de progreso mientras se descarga el instalador."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Descargando actualización…")
        self.resizable(False, False)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", lambda: None)  # no cerrable

        bg = "#0d0d1a"
        fg = "#e0e0ff"
        self.configure(bg=bg)

        tk.Label(self, text="Descargando nueva versión de JARVIS…",
                 bg=bg, fg=fg, font=("Segoe UI", 11)).pack(padx=24, pady=(18, 6))

        self._var  = tk.DoubleVar(value=0)
        self._bar  = ttk.Progressbar(self, variable=self._var,
                                     maximum=100, length=340)
        self._bar.pack(padx=24, pady=4)

        self._lbl  = tk.Label(self, text="0 %", bg=bg, fg="#00d4aa",
                              font=("Segoe UI", 9))
        self._lbl.pack(pady=(0, 14))

        self.update_idletasks()
        # Centrar respecto al padre
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        self.geometry(f"380x120+{px - 190}+{py - 60}")

    def set_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = downloaded / total * 100
            self._var.set(pct)
            self._lbl.config(text=f"{pct:.0f} %  ({downloaded // 1024} KB / {total // 1024} KB)")
        else:
            self._lbl.config(text=f"{downloaded // 1024} KB descargados…")
        self.update_idletasks()


# ── Función principal ─────────────────────────────────────────────────────────

def check_and_notify(parent: tk.Misc | None = None) -> None:
    """
    Comprueba actualizaciones y, si las hay, muestra un diálogo al usuario.
    Diseñada para ejecutarse en un hilo daemon desde el GUI de JARVIS.

    Si `parent` es None el messagebox usa la ventana raíz de Tk.
    """
    url = _load_update_url()
    if not url:
        return  # Sin URL configurada → no hay nada que hacer

    remote = fetch_remote_info(url)
    if remote is None or not is_update_available(remote):
        return

    new_ver      = remote.get("version", "?")
    download_url = remote.get("download_url", "").strip()
    changelog    = remote.get("changelog", "").strip()

    msg = (
        f"¡Nueva versión de JARVIS disponible! ({new_ver})\n\n"
        + (f"{changelog}\n\n" if changelog else "")
        + "¿Deseas descargar e instalar la actualización ahora?"
    )

    def _ask():
        resp = messagebox.askyesno(
            "Actualización disponible", msg, parent=parent
        )
        if not resp:
            return
        if not download_url:
            messagebox.showwarning(
                "Sin enlace",
                "No hay URL de descarga configurada para esta versión.\n"
                "Contacta al desarrollador.",
                parent=parent,
            )
            return

        # Mostrar progreso y descargar
        dlg = _DownloadDialog(parent) if parent else None

        def _download():
            def _prog(done, total):
                if dlg:
                    dlg.set_progress(done, total)

            path = download_installer(download_url, progress_cb=_prog)

            if dlg:
                dlg.destroy()

            if path is None:
                messagebox.showerror(
                    "Error de descarga",
                    "No se pudo descargar el instalador.\n"
                    "Comprueba tu conexión e inténtalo más tarde.",
                    parent=parent,
                )
                return

            messagebox.showinfo(
                "Listo",
                "La descarga se completó.\n"
                "Se cerrará JARVIS y se iniciará el instalador.",
                parent=parent,
            )
            run_installer(path)
            # Cerrar la aplicación para que el instalador pueda reemplazar archivos
            if parent:
                parent.after(500, parent.destroy)

        threading.Thread(target=_download, daemon=True).start()

    # El diálogo debe mostrarse en el hilo principal de Tk
    if parent:
        parent.after(0, _ask)
    else:
        _ask()
