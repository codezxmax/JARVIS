@echo off
chcp 65001 >nul
title Instalador de JARVIS
color 0A

:: ============================================================
::  JARVIS - Instalador automático
::  Doble clic para instalar en cualquier PC con Python
:: ============================================================

echo.
echo  ============================================================
echo    ___  _   ____  _   _ ___ ____
echo   ^|_ _^|^| ^| ^|  _ \^| ^| ^| ^|_ _^/ ___^|
echo    ^| ^| ^| ^| ^| ^|_) ^| ^|_^| ^|^| ^|\___ \
echo    ^| ^| ^|_^| ^|  _ ^<^|  _  ^|^| ^| ___) ^|
echo   ^|___^|\___/^|_^| \_\_^| ^|_^|___^|____/
echo.
echo    Asistente de Voz Personal - Instalador
echo  ============================================================
echo.

set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%
set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
set PASO=0
set ERRORES=0

:: ────────────────────────────────────────────────────────────
:: PASO 1 — Verificar Python
:: ────────────────────────────────────────────────────────────
set /a PASO+=1
echo  [%PASO%/4]  Buscando Python...

set PYTHON_PATH=
for /f "tokens=*" %%p in ('where python 2^>nul') do (
    if not defined PYTHON_PATH set PYTHON_PATH=%%p
)

:: Fallback: buscar en rutas comunes si 'where' no lo encontró
if not defined PYTHON_PATH (
    for %%d in (
        "C:\Python313\python.exe"
        "C:\Python312\python.exe"
        "C:\Python311\python.exe"
        "C:\Python310\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    ) do (
        if not defined PYTHON_PATH (
            if exist %%d set PYTHON_PATH=%%~d
        )
    )
)

if not defined PYTHON_PATH (
    echo.
    echo  [ERROR] No se encontro Python en este equipo.
    echo.
    echo    Descargalo desde: https://www.python.org/downloads/
    echo    IMPORTANTE: Al instalar, marcar "Add Python to PATH"
    echo.
    set /a ERRORES+=1
    goto :RESUMEN
)

for /f "tokens=*" %%v in ('"%PYTHON_PATH%" --version 2^>^&1') do set PYVER=%%v
echo         Encontrado: %PYVER%
echo         Ruta: %PYTHON_PATH%
echo.

:: ────────────────────────────────────────────────────────────
:: PASO 2 — Instalar librerías
:: ────────────────────────────────────────────────────────────
set /a PASO+=1
echo  [%PASO%/4]  Instalando librerias de Python...
echo         (puede tardar 1-2 minutos la primera vez)
echo.

"%PYTHON_PATH%" -m pip install --upgrade pip --quiet 2>nul

set LIBS=SpeechRecognition PyAudio pyttsx3 pyautogui
for %%L in (%LIBS%) do (
    echo         Instalando %%L...
    "%PYTHON_PATH%" -m pip install %%L --quiet
    if errorlevel 1 (
        echo         [!] Advertencia: %%L pudo no instalarse correctamente.
        set /a ERRORES+=1
    )
)

echo.
if %ERRORES% EQU 0 (
    echo         Todas las librerias instaladas correctamente.
) else (
    echo         Se instalaron con advertencias ^(ver arriba^).
)
echo.

:: ────────────────────────────────────────────────────────────
:: PASO 3 — Verificar micrófono
:: ────────────────────────────────────────────────────────────
set /a PASO+=1
echo  [%PASO%/4]  Verificando microfono del sistema...

"%PYTHON_PATH%" -c "import speech_recognition as sr; sr.Microphone(); print('OK')" 2>nul | find "OK" >nul
if errorlevel 1 (
    echo         [!] No se detecto microfono. JARVIS necesita uno para funcionar.
    echo             Conecta un microfono y vuelve a ejecutar este instalador.
    set /a ERRORES+=1
) else (
    echo         Microfono detectado correctamente.
)
echo.

:: ────────────────────────────────────────────────────────────
:: PASO 4 — Configurar inicio automático con Windows
:: ────────────────────────────────────────────────────────────
set /a PASO+=1
echo  [%PASO%/4]  Configurando inicio automatico con Windows...

(
echo ' ── Lanzador silencioso de JARVIS ─────────────────────────
echo ' Generado por instalar.bat el %DATE%
echo Set WshShell = CreateObject^("WScript.Shell"^)
echo WshShell.Run """%PYTHON_PATH%"" ""%SCRIPT_DIR%\jarvis.py""", 0, False
) > "%SCRIPT_DIR%\launcher.vbs"

copy /y "%SCRIPT_DIR%\launcher.vbs" "%STARTUP%\jarvis.vbs" >nul
if errorlevel 1 (
    echo         [!] No se pudo copiar al inicio de Windows.
    set /a ERRORES+=1
) else (
    echo         JARVIS iniciara automaticamente con Windows.
)
echo.

:: ────────────────────────────────────────────────────────────
:: RESUMEN FINAL
:: ────────────────────────────────────────────────────────────
:RESUMEN
echo  ============================================================
if %ERRORES% EQU 0 (
    echo    INSTALACION COMPLETADA SIN ERRORES
) else (
    echo    INSTALACION COMPLETADA CON %ERRORES% ADVERTENCIA(S)
)
echo  ============================================================
echo.
echo    Ubicacion de JARVIS:  %SCRIPT_DIR%\jarvis.py
echo    Inicio automatico:    %STARTUP%\jarvis.vbs
echo.
echo    PROXIMOS PASOS:
echo    1. Edita config.py con tus datos (usuario, contrasena, rutas)
echo    2. Para probar ahora, cierra esta ventana y ejecuta:
echo.
echo       "%PYTHON_PATH%" "%SCRIPT_DIR%\jarvis.py"
echo.
echo    Di "Hola Jarvis" para activarlo.
echo.
echo  ============================================================
echo.
pause
