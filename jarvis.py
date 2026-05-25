import speech_recognition as sr
import subprocess
import time
import pyautogui
import ctypes
import ctypes.wintypes
import os
import json
import threading
import tempfile
import pyttsx3
import config
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# =========================================================
# CONFIGURACIÓN DINÁMICA (interfaz gráfica → jarvis_settings.json)
# =========================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_settings():
    sf = os.path.join(BASE_DIR, "jarvis_settings.json")
    if os.path.exists(sf):
        with open(sf, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_commands_json():
    """Carga commands.json en tiempo real (permite actualizar sin reiniciar)."""
    cf = os.path.join(BASE_DIR, "commands.json")
    if os.path.exists(cf):
        with open(cf, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


_s         = _load_settings()
VOICE_RATE = _s.get("rate",    145)
VOICE_VOL  = _s.get("volume",  1.0)
VOICE_NAME = _s.get("voice",   "Auto (español preferido)")
KEYWORD    = _s.get("keyword", "hola jarvis")
LANG       = _s.get("lang",    "es-ES")
SALUDO     = _s.get("saludo",  "Hola señor Maxi, ¿cómo está su día? ¿Qué necesita de mí?")

# Archivo de señal IPC: jarvis.py escribe aquí su estado para que la GUI lo muestre
_STATE_FILE = os.path.join(BASE_DIR, ".jarvis_state")

def _write_state(state: str):
    """Escribe el estado actual en .jarvis_state (GUI lo lee cada 200 ms)."""
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            f.write(state)
    except Exception:
        pass

# =========================================================
# CONTROL DE VOLUMEN DEL SISTEMA (pycaw)
# =========================================================

try:
    _devices  = AudioUtilities.GetSpeakers()
    _interface = _devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    _volume_ctrl = _interface.QueryInterface(IAudioEndpointVolume)
    _HAS_VOLUME = True
except Exception:
    _HAS_VOLUME = False
    _volume_ctrl = None

_LISTEN_DUCK = 0.20   # nivel al que se baja el volumen mientras escucha (0-1)

def _get_master_volume() -> float:
    """Devuelve el nivel de volumen maestro actual (0.0–1.0)."""
    if _HAS_VOLUME and _volume_ctrl:
        try:
            return _volume_ctrl.GetMasterVolumeLevelScalar()
        except Exception:
            pass
    return 1.0

def _set_master_volume(level: float):
    """Fija el volumen maestro al nivel indicado (0.0–1.0)."""
    if _HAS_VOLUME and _volume_ctrl:
        try:
            _volume_ctrl.SetMasterVolumeLevelScalar(
                max(0.0, min(1.0, level)), None)
        except Exception:
            pass

# =========================================================
# MOTOR DE VOZ TTS
# =========================================================

engine = pyttsx3.init()
engine.setProperty('rate',   VOICE_RATE)
engine.setProperty('volume', VOICE_VOL)

# Seleccionar voz según configuración
if VOICE_NAME and VOICE_NAME != "Auto (español preferido)":
    for voice in engine.getProperty('voices'):
        if voice.name == VOICE_NAME:
            engine.setProperty('voice', voice.id)
            break
else:
    for voice in engine.getProperty('voices'):
        nombre = voice.name.lower()
        if 'spanish' in nombre or 'helena' in nombre or 'sabina' in nombre or 'es-' in voice.id.lower():
            engine.setProperty('voice', voice.id)
            break


def hablar(texto):
    """Jarvis responde con voz y muestra el texto en consola."""
    print(f"🔊 JARVIS: {texto}")
    _write_state("hablando")
    engine.say(texto)
    engine.runAndWait()
    _write_state("esperando")


# =========================================================
# CONTROL DE SPOTIFY
# =========================================================

def pausar_spotify():
    """Pausa o reanuda Spotify con la tecla de medios del sistema."""
    print("⏸️  Enviando pausa a Spotify...")
    ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)
    hablar("Música pausada, señor Maxi.")


def reproducir_back_in_black():
    """Abre Spotify con Back in Black de AC/DC."""
    print("🎸 Abriendo Back in Black...")
    subprocess.Popen(["start", config.SPOTIFY_BACK_IN_BLACK], shell=True)


def reproducir_musica_favorita():
    """Abre la playlist favorita 'Tus Me Gusta'."""
    print("🎵 Abriendo playlist favorita...")
    if "REEMPLAZA" in config.SPOTIFY_PLAYLIST_FAVORITA:
        hablar("Señor Maxi, aún no configuró el identificador de su playlist. Edite el archivo config punto py.")
        return
    subprocess.Popen(["start", config.SPOTIFY_PLAYLIST_FAVORITA], shell=True)
    hablar("Claro, poniendo su música favorita.")


# =========================================================
# MODO CAFÉ
# =========================================================

def activar_modo_cafe():
    """Activa todo: Chrome con Gmail/Google + sistema interno + música."""
    hablar("Activando modo café. Un momento, señor Maxi.")
    abrir_chrome_con_sitios()
    time.sleep(2)
    abrir_sistema_interno()
    time.sleep(1)
    reproducir_back_in_black()
    hablar("Todo listo señor Maxi. Que tenga un excelente día!")


# =========================================================
# CHROME Y SISTEMA INTERNO
# =========================================================

def abrir_chrome_con_sitios():
    """Abre Chrome con los sitios configurados en pestañas."""
    print("🌐 Abriendo Chrome...")
    try:
        if os.path.exists(config.RUTA_CHROME):
            subprocess.Popen([config.RUTA_CHROME] + config.SITIOS_WEB)
        else:
            subprocess.Popen(["start", "chrome"] + config.SITIOS_WEB, shell=True)
        print(f"✅ Chrome abierto con {len(config.SITIOS_WEB)} pestañas.")
    except Exception as e:
        print(f"❌ Error al abrir Chrome: {e}")


def abrir_sistema_interno():
    """Abre el sistema interno y escribe las credenciales automáticamente."""
    if not config.RUTA_SISTEMA or "RUTA" in config.RUTA_SISTEMA:
        print("⚠️  Sistema interno no configurado. Edita RUTA_SISTEMA en config.py")
        return
    if not os.path.exists(config.RUTA_SISTEMA):
        print(f"⚠️  No se encontró: {config.RUTA_SISTEMA}")
        return
    print("🖥️  Abriendo sistema interno...")
    subprocess.Popen([config.RUTA_SISTEMA])
    print(f"⏳ Esperando {config.ESPERA_SISTEMA}s para que cargue...")
    time.sleep(config.ESPERA_SISTEMA)
    print("⌨️  Escribiendo credenciales...")
    pyautogui.typewrite(config.USUARIO, interval=0.05)
    pyautogui.press("tab")
    pyautogui.typewrite(config.CONTRASENA, interval=0.05)
    pyautogui.press("enter")
    print("✅ Credenciales enviadas.")


def inicio_automatico():
    """Se ejecuta una sola vez al arrancar Jarvis."""
    print("\n🚀 Ejecutando inicio automático...")
    abrir_chrome_con_sitios()
    time.sleep(2)
    abrir_sistema_interno()
    print("✅ Inicio automático completado.\n")


# =========================================================
# RECONOCIMIENTO DE VOZ
# =========================================================

# Reutilizar el mismo Recognizer y Microphone en cada ciclo para
# evitar la latencia de recrearlos y perder el inicio de la frase.
_recognizer = sr.Recognizer()
_microphone = sr.Microphone()

# ── Parámetros de detección (optimizados) ────────────────────────────────
# pause_threshold: cuánto silencio hace falta para cerrar la frase (1.5 s = natural)
_recognizer.pause_threshold              = 1.5
# non_speaking_duration: cuánto silencio al INICIO es ignorado
_recognizer.non_speaking_duration        = 0.4
# Umbral de energía: 300 = sensible (habla normal); sube si hay mucho ruido
_recognizer.energy_threshold             = 300
# Ajuste dinámico habilitado pero amortiguado (0.10 = muy suave → menos falsos neg.)
_recognizer.dynamic_energy_threshold     = True
_recognizer.dynamic_energy_adjustment_damping = 0.10
# Multiplicador por sobre el nivel de ruido ambiente para detectar habla
_recognizer.dynamic_energy_ratio         = 1.5

def _calibrar_microfono():
    """Calibra el umbral de ruido ambiental una sola vez al arrancar."""
    print("🎙️  Calibrando micrófono (2 s)...")
    with _microphone as source:
        _recognizer.adjust_for_ambient_noise(source, duration=2.0)
    print(f"✅ Umbral de energía calibrado: {int(_recognizer.energy_threshold)}")


def escuchar_comando(timeout=8, phrase_limit=15):
    """Escucha el micrófono, baja el volumen mientras escucha y retorna el texto."""
    vol_previo = _get_master_volume()
    # Solo baja el volumen si hay algo sonando (volumen > duck level)
    if vol_previo > _LISTEN_DUCK:
        _set_master_volume(_LISTEN_DUCK)
    _write_state("escuchando")
    print("🎙️  [ESCUCHANDO]")
    try:
        with _microphone as source:
            # Recalibrar ruido muy rápido (0.3 s) en cada escucha
            _recognizer.adjust_for_ambient_noise(source, duration=0.3)
            audio = _recognizer.listen(source, timeout=timeout,
                                       phrase_time_limit=phrase_limit)
        texto = _recognizer.recognize_google(audio, language=LANG)
        print(f"🎤 Escuché: '{texto}'")
        return texto.lower()
    except sr.WaitTimeoutError:
        return None
    except sr.UnknownValueError:
        print("⚠️  No entendí lo que dijo.")
        return None
    except Exception as e:
        print(f"🚨 Error de audio: {e}")
        return None
    finally:
        # Siempre restaurar el volumen original
        _set_master_volume(vol_previo)
        _write_state("esperando")
        print("🔇  [LISTO]")


# =========================================================
# SUSPENDER / BLOQUEAR PC
# =========================================================

def _suspender_pc():
    """Suspende el equipo (Sleep): lo pone en pantalla de inicio de sesión."""
    print("💤 Suspendiendo el equipo...")
    # Primero bloquea la sesión y luego suspende
    ctypes.windll.user32.LockWorkStation()
    time.sleep(1)
    subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"])


_pendiente_suspension = False   # flag de confirmación


def _manejar_suspension(cmd_confirmacion: str | None):
    """Gestiona el flujo de confirmación para suspender el PC."""
    global _pendiente_suspension
    if _pendiente_suspension:
        # Ya se pidió confirmación: ¿el usuario dice sí?
        _pendiente_suspension = False
        if cmd_confirmacion and any(
            x in cmd_confirmacion for x in
                ("sí", "si", "sí porfa", "si porfa", "dale", "confirmo",
                 "claro", "adelante", "hazlo", "procede")
        ):
            hablar("Entendido. Hasta la próxima, señor Maxi.")
            time.sleep(1.5)
            _suspender_pc()
            return True
        else:
            hablar("Suspensión cancelada. A sus órdenes.")
            return True
    return False


# =========================================================
# EJECUTOR DE ACCIONES (comandos desde commands.json)
# =========================================================

def _ejecutar_accion(cmd_json):
    """Ejecuta la acción definida en un comando del JSON y habla la respuesta."""
    accion   = cmd_json.get("accion", "solo_hablar")
    params   = cmd_json.get("params", {})
    respuesta = cmd_json.get("respuesta", "")

    if accion == "builtin_modo_cafe":
        activar_modo_cafe()   # ya habla internamente
        return

    elif accion == "abrir_url":
        url = params.get("url", "")
        if url:
            try:
                if os.path.exists(config.RUTA_CHROME):
                    subprocess.Popen([config.RUTA_CHROME, url])
                else:
                    subprocess.Popen(["start", url], shell=True)
            except Exception as e:
                print(f"❌ Error abriendo URL: {e}")

    elif accion == "abrir_app":
        exe = params.get("exe", "")
        if exe and os.path.exists(exe):
            subprocess.Popen([exe])
        else:
            print(f"⚠️  No se encontró el ejecutable: {exe}")

    elif accion == "reproducir_spotify":
        uri = params.get("uri", "")
        if uri:
            subprocess.Popen(["start", uri], shell=True)

    elif accion == "media_play_pause":
        ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)

    elif accion == "media_next":
        ctypes.windll.user32.keybd_event(0xB0, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(0xB0, 0, 2, 0)

    elif accion == "media_prev":
        ctypes.windll.user32.keybd_event(0xB1, 0, 0, 0)
        time.sleep(0.05)
        ctypes.windll.user32.keybd_event(0xB1, 0, 2, 0)

    elif accion == "builtin_suspender":
        global _pendiente_suspension
        _pendiente_suspension = True
        hablar("¿De verdad señor Maxi quiere ejecutar esa orden?")
        return

    # solo_hablar y cualquier otra acción: solo responde con voz
    if respuesta:
        hablar(respuesta)


# =========================================================
# PROCESADOR DE COMANDOS
# =========================================================

def procesar_comando(cmd):
    """Analiza el texto y ejecuta la acción correspondiente."""
    global _pendiente_suspension

    if not cmd:
        if _pendiente_suspension:
            # timeout esperando confirmación: cancelar
            _pendiente_suspension = False
            hablar("No escuché confirmación. Suspensión cancelada.")
        else:
            hablar("No escuché ningún comando, señor Maxi. ¿Puede repetir?")
        return

    # ── Si hay confirmación pendiente de suspensión ───────────────────────────
    if _pendiente_suspension:
        _manejar_suspension(cmd)
        return

    # ── Comando builtin: suspender ─────────────────────────────────────────────
    _cmd_norm = cmd.replace("á","a").replace("é","e").replace("í","i")\
                   .replace("ó","o").replace("ú","u")
    if any(x in _cmd_norm for x in
           ("suspende", "suspender", "duerme el pc", "pon a dormir",
            "modo suspension", "modo suspensión")):
        _pendiente_suspension = True
        hablar("¿De verdad señor Maxi quiere ejecutar esa orden?")
        return

    # ── Comandos personalizados del JSON (tienen prioridad) ──────────────────
    for custom in _load_commands_json():
        if not custom.get("activo", True):
            continue
        trigger = custom.get("trigger", "").lower()
        if trigger and trigger in cmd:
            _ejecutar_accion(custom)
            return

    # ── Comandos integrados (fallback si no hay JSON) ─────────────────────────
    if "modo cafe" in cmd or "modo café" in cmd:
        activar_modo_cafe()

    elif ("pausa" in cmd or "para" in cmd) and \
         ("musica" in cmd or "música" in cmd or "cancion" in cmd or "canción" in cmd):
        pausar_spotify()

    elif "musica que me gusta" in cmd or "música que me gusta" in cmd or "mis favoritas" in cmd:
        reproducir_musica_favorita()

    else:
        hablar("No reconocí ese comando, señor Maxi. Puede decir: modo café, pausa la música, suspende el PC, o coloca la música que me gusta.")


# =========================================================
# BUCLE PRINCIPAL
# =========================================================

def main_jarvis_loop():
    print("===========================================")
    print("✨  Asistente JARVIS iniciado.")
    print("===========================================\n")

    _calibrar_microfono()
    inicio_automatico()
    hablar("Sistema iniciado. Listo para escuchar, señor Maxi.")

    _write_state("esperando")

    while True:
        cmd = escuchar_comando(timeout=6)

        if cmd is None:
            # Si había confirmación pendiente y no llegó respuesta → cancelar
            if _pendiente_suspension:
                procesar_comando(None)
            continue

        # ── Si hay confirmación pendiente de suspensión ───────────────────
        if _pendiente_suspension:
            procesar_comando(cmd)
            continue

        # Activación principal: palabra clave configurable
        if KEYWORD in cmd:
            hablar(SALUDO)
            followup = escuchar_comando(timeout=10, phrase_limit=15)
            procesar_comando(followup)

        # Comandos directos (contiene "jarvis")
        elif "jarvis" in cmd:
            procesar_comando(cmd)

        time.sleep(0.1)


if __name__ == "__main__":
    try:
        main_jarvis_loop()
    except KeyboardInterrupt:
        hablar("Desconectando. Hasta pronto, señor Maxi.")
        print("\n\n👋 JARVIS desconectado.")
