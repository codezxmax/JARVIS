' Lanzador silencioso de JARVIS
' Ejecuta el script Python sin mostrar ninguna ventana de consola
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "c:\python313\python.exe d:\SoftWare\Jarvis\jarvis.py", 0, False
