# main_sciencedirect.py
from utils.browser import crear_navegador, cerrar_banners
from utils.sso_google import login_con_google
from utils.sciencedirect import (
    abrir_home_sciencedirect,
    buscar_en_sciencedirect,
    fijar_resultados_por_pagina,
    descargar_varias_paginas_sd,
)
import config

if __name__ == "__main__":
    driver = crear_navegador(config.CHROMEDRIVER_PATH, config.DOWNLOAD_DIR_SCIENCEDIRECT)
    try:
        URL_SD = getattr(config, "SCIENCEDIRECT_URL", "https://www-sciencedirect-com.crai.referencistas.com/")
        DOMINIO_OBJETIVO = "www-sciencedirect-com"

        # 1) Autenticación CRAI con Google
        login_con_google(
            driver=driver,
            url_revista=URL_SD,
            correo_institucional=config.USUARIO,
            contrasena=config.CONTRASENA,
            carpeta_descargas=config.DOWNLOAD_DIR_SCIENCEDIRECT,
            dominio_objetivo=DOMINIO_OBJETIVO
        )

        # 2) Cerrar banners genéricos
        cerrar_banners(driver)

        # 3) Home OK
        abrir_home_sciencedirect(driver, URL_SD, config.DOWNLOAD_DIR_SCIENCEDIRECT)

        # 4) Buscar cadena
        QUERY = "generative artificial intelligence"
        buscar_en_sciencedirect(driver, QUERY, config.DOWNLOAD_DIR_SCIENCEDIRECT)

        # 5) Forzar 100 por página (solo una vez)
        fijar_resultados_por_pagina(
            driver,
            per_page=100,
            carpeta_descargas=config.DOWNLOAD_DIR_SCIENCEDIRECT
        )

        # 6) Descargar varias páginas: actual + “next” x 4 = 5 páginas en total
        descargar_varias_paginas_sd(
            driver,
            carpeta_descargas=config.DOWNLOAD_DIR_SCIENCEDIRECT,
            consulta_slug="generative-artificial-intelligence",
            paginas=5,                 # <-- ajusta aquí cuántas páginas quieres
            etiqueta_prefijo="p"
        )

        print("URL actual:", driver.current_url)
        print("Título:", driver.title)

    finally:
        driver.quit()
