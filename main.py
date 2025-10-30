from utils.browser import crear_navegador, cerrar_banners
from utils.sso_google import login_con_google
from utils.sage import buscar_en_sage, exportar_ris_paginando
import config

if __name__ == "__main__":
    driver = crear_navegador(config.CHROMEDRIVER_PATH, config.DOWNLOAD_DIR_SAGE)
    try:
        URL_REVISTA = "https://journals-sagepub-com.crai.referencistas.com/"
        DOMINIO_OBJETIVO = "journals-sagepub-com"

        login_con_google(
            driver=driver,
            url_revista=URL_REVISTA,
            correo_institucional=config.USUARIO,
            contrasena=config.CONTRASENA,
            carpeta_descargas=config.DOWNLOAD_DIR_SAGE,
            dominio_objetivo=DOMINIO_OBJETIVO
        )

        cerrar_banners(driver)

        QUERY = "generative artificial intelligence"
        buscar_en_sage(driver, QUERY, config.DOWNLOAD_DIR_SAGE)

        # === Exportar múltiples páginas (ajusta max_paginas a 5–10 según lo que quieras) ===
        exportar_ris_paginando(
            driver,
            carpeta_descargas=config.DOWNLOAD_DIR_SAGE,
            consulta_slug="generative-artificial-intelligence",
            max_paginas=5  # 10 páginas ≈ 100 artículos si pageSize=10
        )

        print("URL actual:", driver.current_url)
        print("Título:", driver.title)

    finally:
        driver.quit()
