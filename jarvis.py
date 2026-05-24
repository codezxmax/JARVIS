import speech_recognition as sr
import subprocess
import time
import pyautogui
import ctypes
import os
import json
import pyttsx3
import config

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
    engine.say(texto)
    engine.runAndWait()


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

# pause_threshold: cuánto silencio (seg) hace falta para dar la frase por terminada.
# El defecto (0.8 s) corta demasiado rápido; con 1.5 s el usuario puede hablar
# con pausas naturales sin que JARVIS lo interrumpa.
_recognizer.pause_threshold       = 1.5
_recognizer.non_speaking_duration = 0.5
_recognizer.dynamic_energy_threshold = True

def _calibrar_microfono():
    """Calibra el umbral de ruido ambiental una sola vez al arrancar."""
    print("🎙️  Calibrando micrófono...")
    with _microphone as source:
        _recognizer.adjust_for_ambient_noise(source, duration=1.0)
    print(f"✅ Umbral de energía: {int(_recognizer.energy_threshold)}")


def escuchar_comando(timeout=8, phrase_limit=12):
    """Escucha el micrófono y retorna el texto reconocido en minúsculas."""
    try:
        with _microphone as source:
            audio = _recognizer.listen(source, timeout=timeout,
                                       phrase_time_limit=phrase_limit)
        texto = _recognizer.recognize_google(audio, language=LANG)
        print(f"🎤 Escuché: '{texto}'")
        return texto.lower()
    except Exception as e:
        print(f"🚨 Error de audio: {e}")
        return None


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

    # solo_hablar y cualquier otra acción: solo responde con voz
    if respuesta:
        hablar(respuesta)


# =========================================================
# PROCESADOR DE COMANDOS
# =========================================================

def procesar_comando(cmd):
    """Analiza el texto y ejecuta la acción correspondiente."""
    if not cmd:
        hablar("No escuché ningún comando, señor Maxi. ¿Puede repetir?")
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
        hablar("No reconocí ese comando, señor Maxi. Puede decir: modo café, pausa la música, o coloca la música que me gusta.")


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

    while True:
        print("🎙️  Escuchando...")
        cmd = escuchar_comando(timeout=5)

        if cmd is None:
            continue

        # Activación principal: palabra clave configurable
        if KEYWORD in cmd:
            hablar(SALUDO)
            print("🎙️  Esperando su orden...")
            followup = escuchar_comando(timeout=8, phrase_limit=8)
            procesar_comando(followup)

        # Comandos directos (contiene "jarvis" sin el saludo completo)
        elif "jarvis" in cmd:
            procesar_comando(cmd)

        time.sleep(0.3)


if __name__ == "__main__":
    try:
        main_jarvis_loop()
    except KeyboardInterrupt:
        hablar("Desconectando. Hasta pronto, señor Maxi.")
        print("\n\n👋 JARVIS desconectado.")
