# utils/sso_google.py
# Automatiza el login institucional del CRAI usando "Iniciar sesión con Google"
# Cubre dos escenarios:
#   A) Tu cuenta aparece para seleccionarla
#   B) No aparece y hay que escribir correo y contraseña
#
# Si aparece 2FA/CAPTCHA, el script espera que lo completes manualmente.
# Además maneja el modal de Chrome "¿Quieres acceder a Chrome?" haciendo clic en
# "Usar Chrome sin una cuenta" si aparece.

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, os

# ------------------------ utilidades básicas ------------------------

def _click(driver, how, what, timeout=10):
    """Hace clic cuando un elemento es clicable."""
    WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((how, what))).click()

def _type(driver, how, what, text, timeout=10):
    """Escribe texto en un input cuando está presente."""
    elem = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((how, what)))
    elem.clear()
    elem.send_keys(text)

def _guardar_captura(driver, carpeta, nombre):
    """Guarda una captura PNG con el nombre indicado dentro de la carpeta dada."""
    try:
        os.makedirs(carpeta, exist_ok=True)
        driver.save_screenshot(os.path.join(carpeta, f"{nombre}.png"))
    except Exception:
        pass

# ------------------------ manejo del modal de Chrome ------------------------

def _intentar_cerrar_modal_perfil_chrome(driver):
    """
    Detecta la pantalla '¿Quieres acceder a Chrome?' y pulsa 'Usar Chrome sin una cuenta'.
    Es una página web (no un diálogo nativo), así que la localizamos por texto.
    Devuelve True si lo cerró, False si no apareció o no pudo.
    """
    try:
        boton_sin_cuenta = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    # Botón que contiene el texto "Usar Chrome sin una cuenta"
                    '//button[.//span[contains(., "Usar Chrome sin una cuenta")] '
                    ' or contains(normalize-space(.), "Usar Chrome sin una cuenta")]'
                )
            )
        )
        boton_sin_cuenta.click()
        time.sleep(1)
        return True
    except Exception:
        return False

# ------------------------ flujo principal de login ------------------------

def login_con_google(driver, url_revista, correo_institucional, contrasena, carpeta_descargas, dominio_objetivo=None):
    """
    Flujo:
      1) Abrir URL de la revista (SAGE/ScienceDirect vía CRAI)
      2) Click en "Iniciar sesión con Google" (id=btn-google)
      3) Si aparece tu cuenta -> clic (chip con data-identifier=tu_correo)
         Si NO, escribir correo (id=identifierId) y botón Siguiente (id=identifierNext)
      4) Escribir contraseña (name=Passwd) y botón Siguiente (id=passwordNext)
      5) Cerrar modal de Chrome si aparece ("Usar Chrome sin una cuenta")
      6) Esperar redirección de vuelta al proxy/base (o esperar a que termines 2FA si aplica)
    """
    # 1) Abrir la revista
    driver.get(url_revista)
    _guardar_captura(driver, carpeta_descargas, "01_pantalla_revista")

    # 2) Botón "Iniciar sesión con Google"
    _click(driver, By.ID, "btn-google")
    _guardar_captura(driver, carpeta_descargas, "02_google_iniciado")

    # 3) ¿Aparece tu cuenta para seleccionarla?
    try:
        cuenta_chip = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, f'div[data-identifier="{correo_institucional}"]'))
        )
        cuenta_chip.click()
        _guardar_captura(driver, carpeta_descargas, "03_cuenta_seleccionada")
    except Exception:
        # Si no, escribimos el correo manualmente
        _type(driver, By.ID, "identifierId", correo_institucional, timeout=15)
        _click(driver, By.ID, "identifierNext")
        time.sleep(2)
        _guardar_captura(driver, carpeta_descargas, "03_correo_enviado")

    # 4) Contraseña
    try:
        _type(driver, By.NAME, "Passwd", contrasena, timeout=20)
    except Exception:
        # Puede tardar en renderizar; esperamos un poco y reintentamos
        time.sleep(3)
        _type(driver, By.NAME, "Passwd", contrasena, timeout=20)

    _click(driver, By.ID, "passwordNext")
    _guardar_captura(driver, carpeta_descargas, "04_password_enviado")

    # 5) Cerrar el modal de “¿Quieres acceder a Chrome?” si aparece
    _intentar_cerrar_modal_perfil_chrome(driver)

    # 5.1) Otras pantallas intermedias (confirmaciones genéricas)
    for posible in [
        (By.ID, "confirm"),
        (By.XPATH, '//button[contains(.,"Aceptar") or contains(.,"Acepto") or contains(.,"Continuar")]'),
    ]:
        try:
            _click(driver, *posible, timeout=5)
            time.sleep(1)
        except Exception:
            pass

    # 6) Esperar a volver a la revista/proxy (o a que salgas de accounts.google.com)
    try:
        if dominio_objetivo:
            WebDriverWait(driver, 40).until(EC.url_contains(dominio_objetivo))
        else:
            WebDriverWait(driver, 40).until_not(EC.url_contains("accounts.google.com"))
    except Exception:
        # Si hay 2FA/CAPTCHA, aquí se queda esperando a que lo completes manualmente.
        pass

    _guardar_captura(driver, carpeta_descargas, "05_redirigido_ok")
    print("✅ Autenticación con Google finalizada (o en espera de verificación manual si aplica).")
