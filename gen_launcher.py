"""
Generado por el instalador de JARVIS.
Escribe launcher.vbs (auto-inicio silencioso) y gui_launcher.vbs (panel de
control) con la ruta de Python de ESTE equipo, y copia launcher.vbs al
directorio Startup de Windows.
"""
import sys
import os
import shutil

app_dir     = os.path.dirname(os.path.abspath(__file__))
startup_dir = os.path.join(os.environ["APPDATA"],
                           r"Microsoft\Windows\Start Menu\Programs\Startup")

# Usar pythonw.exe para no mostrar consola negra
py_exe      = sys.executable
pythonw_exe = os.path.join(os.path.dirname(py_exe), "pythonw.exe")
if not os.path.exists(pythonw_exe):
    pythonw_exe = py_exe   # fallback: python.exe

# ── launcher.vbs — inicia jarvis.py sin ventana (para Startup) ──────────────
vbs_src = os.path.join(app_dir, "launcher.vbs")
vbs_dst = os.path.join(startup_dir, "jarvis.vbs")

content_launcher = (
    "' Lanzador silencioso de JARVIS\n"
    "Set WshShell = CreateObject(\"WScript.Shell\")\n"
    f'WshShell.Run Chr(34) & "{py_exe}" & Chr(34) & " " '
    f'& Chr(34) & "{os.path.join(app_dir, "jarvis.py")}" & Chr(34), 0, False\n'
)

with open(vbs_src, "w", encoding="utf-8") as f:
    f.write(content_launcher)

shutil.copy(vbs_src, vbs_dst)
print(f"[OK] launcher.vbs copiado a: {vbs_dst}")

# ── gui_launcher.vbs — abre el panel de control (interfaz.py) ───────────────
gui_vbs_src = os.path.join(app_dir, "gui_launcher.vbs")

content_gui = (
    "' Lanzador del Panel de Control JARVIS\n"
    "Set WshShell = CreateObject(\"WScript.Shell\")\n"
    f'WshShell.Run Chr(34) & "{pythonw_exe}" & Chr(34) & " " '
    f'& Chr(34) & "{os.path.join(app_dir, "interfaz.py")}" & Chr(34), 1, False\n'
)

with open(gui_vbs_src, "w", encoding="utf-8") as f:
    f.write(content_gui)

print(f"[OK] gui_launcher.vbs creado en: {gui_vbs_src}")
