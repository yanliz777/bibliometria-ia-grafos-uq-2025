# utils/login.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, os

def login_revista(driver, url_revista, usuario, contrasena, carpeta_descargas):
    """Abre la URL de una revista y hace login con usuario/contraseña CRAI"""
    driver.get(url_revista)

    try:
        # Esperar que aparezca el campo de usuario
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "lp-usuario"))
        )

        # Llenar usuario y contraseña
        input_usuario = driver.find_element(By.ID, "lp-usuario")
        input_contrasena = driver.find_element(By.ID, "lp-contrasena")

        input_usuario.clear()
        input_usuario.send_keys(usuario)
        input_contrasena.clear()
        input_contrasena.send_keys(contrasena)

        # Clic en botón
        boton = driver.find_element(By.CLASS_NAME, "boton_iniciar")
        boton.click()

        print("✅ Login en revista realizado, esperando redirección...")
        time.sleep(8)

        # Captura de pantalla después del login
        driver.save_screenshot(os.path.join(carpeta_descargas, "revista_post_login.png"))
    except Exception as e:
        print("❌ Error en login de revista:", e)
