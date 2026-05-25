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
import random
from datetime import datetime
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

# Forzar stdout UTF-8 para emojis y acentos en la consola de la GUI
import sys
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

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
NOMBRE     = _s.get("nombre",  "señor Maxi")

# =========================================================
# RESPUESTAS ALEATORIAS Y PLÁTICAS
# =========================================================

_GREETINGS_RESP = [
    "A sus órdenes. ¿En qué le puedo ayudar?",
    "Aquí estoy, siempre listo para servirle. ¿Qué necesita?",
    "Dígame, esperando instrucciones.",
    "¿Qué manda? Listo para trabajar.",
    "Presente. ¿En qué le ayudo hoy?",
    "Buenas, ¿en qué puedo servirle?",
    "A la orden, jefe. ¿Qué necesita?",
]

_IDLE_MSGS = [
    "Solo confirmando que sigo activo y operativo.",
    "Todo tranquilo por aquí. Listo cuando me necesite.",
    "Sistemas en línea. Aquí estaré cuando me llame.",
    "¿Necesita algo? Aquí estoy.",
    "Escaneando el ambiente. Sin novedades.",
]

# (triggers, respuestas) — respuestas=None → handler especial
_QA_PAIRS = [
    (("cómo estás", "como estas", "cómo te va", "como te va", "qué tal", "que tal"),
     ("Funcionando al cien por ciento, gracias por preguntar.",
      "Excelente, todos los sistemas operativos.",
      "Muy bien, gracias. Listo para servirle.")),
    (("qué hora es", "que hora es", "dime la hora", "qué horas son"),
     None),  # handler especial: hora actual
    (("qué día es", "que dia es", "qué fecha", "que fecha", "qué día"),
     None),  # handler especial: fecha actual
    (("quién eres", "quien eres", "qué eres", "que eres"),
     ("Soy JARVIS, su asistente personal de voz. Aquí para servirle.",
      "Soy su asistente de inteligencia artificial. A sus órdenes.")),
    (("gracias", "muchas gracias", "te lo agradezco"),
     ("Para eso estoy. A sus órdenes.",
      "Con gusto. ¿Algo más?",
      "No hay de qué. Siempre a su servicio.")),
    (("muy bien", "excelente trabajo", "bien hecho", "lo hiciste bien"),
     ("Gracias, hago lo mejor que puedo.",
      "Siempre dando el máximo para usted.",
      "Me alegra escuchar eso.")),
    (("hasta luego", "adiós", "adios", "nos vemos", "chao"),
     ("Hasta luego. Aquí estaré cuando me necesite.",
      "Hasta pronto.",
      "Que le vaya bien.")),
    (("cuántos años tienes", "cuantos anos tienes", "qué edad tienes"),
     ("Soy una inteligencia artificial. Técnicamente no tengo edad.",
      "Fui creado hace poco. Aún estoy aprendiendo.")),
    (("eres inteligente", "qué inteligente", "que inteligente", "eres listo"),
     ("Hago lo que puedo con lo que me programaron.",
      "Intento serlo para servirle mejor.")),
    (("qué puedes hacer", "que puedes hacer", "qué sabes", "que sabes hacer"),
     ("Puedo activar el modo café, controlar Spotify, buscar música, "
      "suspender el PC, abrir sitios web, y mucho más.",)),
    (("cuanto es", "cuánto es", "cálcula", "calcula"),
     None),  # handler especial: calculadora básica
]

# Tiempo de inactividad antes de enviar mensaje idle (segundos)
_IDLE_INTERVAL = 12 * 60  # 12 minutos
_last_interaction = 0.0    # se inicializa al arrancar

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
    print(f"[TTS] JARVIS: {texto}")
    _write_state("hablando")
    try:
        engine.say(texto)
        engine.runAndWait()
    except Exception as _e:
        print(f"[ERROR TTS] {_e}")
        # Intentar reiniciar el motor si falla
        try:
            global engine
            engine = pyttsx3.init()
            engine.setProperty('rate',   VOICE_RATE)
            engine.setProperty('volume', VOICE_VOL)
            engine.say(texto)
            engine.runAndWait()
        except Exception as _e2:
            print(f"[ERROR TTS reinicio] {_e2}")
    _write_state("esperando")


# =========================================================
# CONTROL DE SPOTIFY
# =========================================================

def _send_media_key(vk_code):
    """Envía una tecla de medios (keydown + keyup)."""
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)


def pausar_spotify():
    """Pausa o reanuda Spotify con la tecla de medios del sistema."""
    print("[SPOTIFY] Enviando pausa...")
    _send_media_key(0xB3)
    hablar(f"Música pausada, {NOMBRE}.")


def reproducir_back_in_black():
    """Abre Spotify con Back in Black de AC/DC."""
    print("[SPOTIFY] Abriendo Back in Black...")
    subprocess.Popen(["start", config.SPOTIFY_BACK_IN_BLACK], shell=True)
    time.sleep(2.5)
    _send_media_key(0xB3)


def reproducir_musica_favorita():
    """Abre la playlist favorita y fuerza reproducción."""
    print("[SPOTIFY] Abriendo playlist favorita...")
    if "REEMPLAZA" in config.SPOTIFY_PLAYLIST_FAVORITA:
        hablar(f"Aún no configuró el identificador de su playlist. Edite el archivo config punto py, {NOMBRE}.")
        return
    subprocess.Popen(["start", config.SPOTIFY_PLAYLIST_FAVORITA], shell=True)
    hablar(f"Claro, poniendo su música favorita, {NOMBRE}.")
    time.sleep(3.0)   # esperar a que Spotify enfoque y cargue
    _send_media_key(0xB3)   # forzar reproducción


def buscar_musica_spotify(query: str):
    """Busca una canción/artista en Spotify y la reproduce."""
    if not query:
        hablar(f"¿Qué canción o artista quiere que busque, {NOMBRE}?")
        return
    print(f"[SPOTIFY] Buscando: {query}")
    encoded = query.strip().replace(" ", "%20")
    uri = f"spotify:search:{encoded}"
    subprocess.Popen(["start", uri], shell=True)
    hablar(f"Buscando {query} en Spotify.")
    time.sleep(3.0)
    _send_media_key(0xB3)   # reproducir primer resultado


# =========================================================
# MODO CAFÉ
# =========================================================

def activar_modo_cafe():
    """Activa todo: Chrome con sitios configurados + sistema interno + música."""
    hablar(f"Activando modo café. Un momento, {NOMBRE}.")
    # 1. Abrir Chrome (una única ventana nueva con todas las pestañas)
    abrir_chrome_con_sitios()
    time.sleep(2)
    # 2. Sistema interno (si está configurado)
    abrir_sistema_interno()
    time.sleep(1)
    # 3. Música: pausar lo que esté sonando, luego abrir la playlist de trabajo
    _send_media_key(0xB3)   # pausa (por si hay algo sonando)
    time.sleep(0.5)
    reproducir_back_in_black()
    hablar(f"Todo listo {NOMBRE}. Que tenga un excelente día!")


# =========================================================
# CHROME Y SISTEMA INTERNO
# =========================================================

def abrir_chrome_con_sitios():
    """Abre Chrome con los sitios configurados en UNA sola ventana nueva."""
    print("[CHROME] Abriendo sitios...")
    if not config.SITIOS_WEB:
        print("[CHROME] SITIOS_WEB está vacío. Nada que abrir.")
        return
    try:
        if os.path.exists(config.RUTA_CHROME):
            # --new-window + todas las URLs → una ventana con N pestañas
            subprocess.Popen([config.RUTA_CHROME, "--new-window"] + config.SITIOS_WEB)
        else:
            # Fallback: usar 'start' de Windows
            args = ["start", "chrome", "--new-window"] + config.SITIOS_WEB
            subprocess.Popen(args, shell=True)
        print(f"[CHROME] Abierto con {len(config.SITIOS_WEB)} pestaña(s).")
    except Exception as e:
        print(f"[ERROR Chrome] {e}")


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
            hablar(f"Entendido. Hasta la próxima, {NOMBRE}.")
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
        hablar(f"¿De verdad {NOMBRE} quiere ejecutar esa orden?")
        return

    # solo_hablar y cualquier otra acción: solo responde con voz
    if respuesta:
        hablar(respuesta)


# =========================================================
# PROCESADOR DE COMANDOS
# =========================================================

def procesar_comando(cmd):
    """Analiza el texto y ejecuta la acción correspondiente."""
    global _pendiente_suspension, _last_interaction
    _last_interaction = time.time()

    if not cmd:
        if _pendiente_suspension:
            _pendiente_suspension = False
            hablar("No escuché confirmación. Suspensión cancelada.")
        else:
            hablar(f"No escuché ningún comando, {NOMBRE}. ¿Puede repetir?")
        return

    # ── Confirmación pendiente de suspensión ──────────────────────────────────
    if _pendiente_suspension:
        _manejar_suspension(cmd)
        return

    # ── Suspender PC ──────────────────────────────────────────────────────────
    _cmd_norm = cmd.replace("á","a").replace("é","e").replace("í","i")\
                   .replace("ó","o").replace("ú","u")
    if any(x in _cmd_norm for x in
           ("suspende", "suspender", "duerme el pc", "pon a dormir",
            "modo suspension", "modo suspensión")):
        _pendiente_suspension = True
        hablar(f"¿De verdad {NOMBRE} quiere ejecutar esa orden?")
        return

    # ── Búsqueda en Spotify ───────────────────────────────────────────────────
    _busqueda_kw = (
        "busca la música", "busca la musica",
        "busca la canción", "busca la cancion",
        "busca música", "busca musica",
        "busca en spotify", "pon la canción", "pon la cancion",
        "reproduce la canción", "reproduce la cancion",
        "reproduce la música", "reproduce la musica",
    )
    for bkw in _busqueda_kw:
        if bkw in cmd:
            query = cmd.split(bkw, 1)[-1].strip().strip("\"' ")
            buscar_musica_spotify(query)
            return

    # ── Comandos personalizados del JSON (tienen prioridad) ──────────────────
    for custom in _load_commands_json():
        if not custom.get("activo", True):
            continue
        trigger = custom.get("trigger", "").lower()
        if trigger and trigger in cmd:
            _ejecutar_accion(custom)
            return

    # ── Comandos integrados (fallback) ────────────────────────────────────────
    if "modo cafe" in cmd or "modo café" in cmd:
        activar_modo_cafe()
        return

    if (("pausa" in cmd or "para" in cmd) and
            ("musica" in cmd or "música" in cmd or
             "cancion" in cmd or "canción" in cmd)):
        pausar_spotify()
        return

    if ("musica que me gusta" in cmd or "música que me gusta" in cmd or
            "mis favoritas" in cmd or "mi favorita" in cmd):
        reproducir_musica_favorita()
        return

    # ── Q&A y pláticas ────────────────────────────────────────────────────────
    for triggers, respuestas in _QA_PAIRS:
        if any(t in cmd for t in triggers):
            if respuestas is None:
                _now = datetime.now()
                _dias  = ["lunes","martes","miércoles","jueves",
                          "viernes","sábado","domingo"]
                _meses = ["enero","febrero","marzo","abril","mayo",
                          "junio","julio","agosto","septiembre",
                          "octubre","noviembre","diciembre"]
                if any(t in cmd for t in ("hora", "horas")):
                    hablar(f"Son las {_now.strftime('%H')} "
                           f"y {int(_now.strftime('%M'))} minutos.")
                elif any(t in cmd for t in ("día","dia","fecha")):
                    hablar(f"Hoy es {_dias[_now.weekday()]}, {_now.day} "
                           f"de {_meses[_now.month-1]} de {_now.year}.")
                else:
                    hablar("Disculpe, no entendí bien. ¿Puede repetir?")
            else:
                hablar(random.choice(respuestas))
            return

    # ── Saludos sueltos ───────────────────────────────────────────────────────
    _hora_act = datetime.now().hour
    _saludo_hora = (
        "buenas noches" if _hora_act >= 21 or _hora_act < 6
        else "buenas tardes" if _hora_act >= 13
        else "buenos días"
    )
    if any(t in cmd for t in ("hola", "hey", "buenas", "buenos días",
                               "buenas tardes", "buenas noches")):
        opciones = [
            f"¡{_saludo_hora}, {NOMBRE}! ¿En qué le ayudo?",
            f"Hola {NOMBRE}, ¿cómo está su día?",
            f"Aquí estoy, {NOMBRE}. Esperando sus órdenes.",
            f"¿Qué manda, {NOMBRE}?",
        ]
        hablar(random.choice(opciones))
        return

    # ── Fallback ──────────────────────────────────────────────────────────────
    hablar(f"No reconocí ese comando, {NOMBRE}. Puede decir: modo café, "
           f"pausa la música, suspende el PC, o coloca la música que me gusta.")


# =========================================================
# BUCLE PRINCIPAL
# =========================================================

def _idle_thread():
    """Hilo daemon: manda un mensaje idle si hay N minutos sin actividad."""
    global _last_interaction
    while True:
        time.sleep(60)
        try:
            if time.time() - _last_interaction > _IDLE_INTERVAL:
                hablar(random.choice(_IDLE_MSGS))
                _last_interaction = time.time()
        except Exception:
            pass


def main_jarvis_loop():
    global _last_interaction
    print("===========================================")
    print("[JARVIS] Asistente iniciado.")
    print("===========================================\n")

    _calibrar_microfono()
    inicio_automatico()
    _last_interaction = time.time()
    hablar(f"Sistema iniciado. Listo para escuchar, {NOMBRE}.")

    # Iniciar hilo de mensajes idle
    threading.Thread(target=_idle_thread, daemon=True).start()

    _write_state("esperando")

    while True:
        cmd = escuchar_comando(timeout=6)

        if cmd is None:
            if _pendiente_suspension:
                procesar_comando(None)
            continue

        # Confirmación de suspensión pendiente
        if _pendiente_suspension:
            procesar_comando(cmd)
            continue

        # Activación por keyword configurable (normalizar acentos para mejor match)
        _cmd_kn = cmd.replace("á","a").replace("é","e").replace("í","i")\
                     .replace("ó","o").replace("ú","u")
        _kw_kn  = KEYWORD.replace("á","a").replace("é","e").replace("í","i")\
                         .replace("ó","o").replace("ú","u")
        if _kw_kn in _cmd_kn:
            hablar(random.choice(_GREETINGS_RESP))
            followup = escuchar_comando(timeout=10, phrase_limit=15)
            procesar_comando(followup)

        # Comandos directos (contiene "jarvis")
        elif "jarvis" in cmd:
            # Si dijo SOLO "jarvis" sin comando → modo activación (saludo + espera)
            bare = cmd.replace("jarvis", "").strip()
            if bare:
                procesar_comando(cmd)
            else:
                hablar(random.choice(_GREETINGS_RESP))
                followup = escuchar_comando(timeout=10, phrase_limit=15)
                procesar_comando(followup)

        time.sleep(0.1)


if __name__ == "__main__":
    try:
        main_jarvis_loop()
    except KeyboardInterrupt:
        hablar(f"Desconectando. Hasta pronto, {NOMBRE}.")
        print("\n[JARVIS] Desconectado.")
