# utils/navegador.py
import os, time, glob
from selenium import webdriver
# ❌ Ya no usamos Service(ruta_driver); Selenium Manager resolverá el driver correcto
# from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def crear_navegador(ruta_driver, carpeta_descargas):
    """
    Crea un navegador Chrome usando Selenium Manager (sin Service/driver manual).
    El parámetro ruta_driver se mantiene por compatibilidad, pero NO se usa.
    """
    os.makedirs(carpeta_descargas, exist_ok=True)

    opciones = Options()
    preferencias = {
        "download.default_directory": carpeta_descargas,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True,
    }
    opciones.add_experimental_option("prefs", preferencias)
    opciones.add_argument("--start-maximized")

    # ✨ Flags para reducir prompts de bienvenida/sincronización
    opciones.add_argument("--no-first-run")
    opciones.add_argument("--no-default-browser-check")
    opciones.add_argument("--disable-sync")

    # ✅ Usar Selenium Manager (deja que Selenium encuentre/descargue el driver correcto)
    # Antes: service = Service(ruta_driver); webdriver.Chrome(service=service, options=opciones)
    return webdriver.Chrome(options=opciones)

def cerrar_banners(driver):
    posibles = [
        (By.CSS_SELECTOR, 'button#onetrust-accept-btn-handler'),
        (By.XPATH, '//button[contains(., "Aceptar") or contains(., "Accept")]'),
        (By.XPATH, '//button[contains(., "De acuerdo") or contains(., "Agree")]'),
    ]
    for como, que in posibles:
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((como, que))).click()
            time.sleep(0.5)
        except Exception:
            pass

def esperar_descarga_por_extension(carpeta_descargas, extension=".ris", timeout=60):
    """
    Espera hasta que aparezca un archivo con la extensión dada (p. ej. .ris)
    creado/actualizado durante la ventana de espera. Devuelve la ruta del más reciente o None.
    """
    inicio = time.time()
    fin = inicio + timeout
    ya_existentes = set(glob.glob(os.path.join(carpeta_descargas, f"*{extension}")))
    ultimo = None

    while time.time() < fin:
        candidatos = set(glob.glob(os.path.join(carpeta_descargas, f"*{extension}")))
        nuevos = [p for p in candidatos if p not in ya_existentes and os.path.getmtime(p) >= inicio - 1]
        if nuevos:
            nuevos.sort(key=os.path.getmtime, reverse=True)
            ultimo = nuevos[0]
            break
        # si no hay nuevos, a veces el botón descarga un data:URI muy rápido; revisa cambios de mtime
        if candidatos:
            ordenados = sorted(list(candidatos), key=os.path.getmtime, reverse=True)
            if os.path.getmtime(ordenados[0]) >= inicio:
                ultimo = ordenados[0]
                break
        time.sleep(0.3)
    return ultimo

def renombrar_si_es_necesario(ruta_archivo, nombre_final_sugerido):
    """
    Renombra ruta_archivo a nombre_final_sugerido en la misma carpeta (si son distintos).
    Devuelve la ruta final (original si no pudo renombrar).
    """
    if not ruta_archivo:
        return None
    carpeta = os.path.dirname(ruta_archivo)
    destino = os.path.join(carpeta, nombre_final_sugerido)
    try:
        if os.path.abspath(ruta_archivo) != os.path.abspath(destino):
            os.replace(ruta_archivo, destino)
        return destino
    except Exception:
        return ruta_archivo
