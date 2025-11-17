"""
req1_automatizacion_descarga.py
----------------------------------------------------
AUTOMATIZACIÓN DE PROCESO DE DESCARGA Y UNIFICACIÓN DE DATOS ACADÉMICOS

Requerimiento 1. Automatización de proceso de descarga de datos.
-----------------------------------------------------------------
Este script implementa la automatización completa del proceso de:
    1. Acceso y autenticación a dos bases de datos académicas (SAGE Journals y ScienceDirect)
       mediante inicio de sesión institucional con Google SSO.
    2. Ejecución de búsquedas automáticas de artículos según una consulta (query).
    3. Descarga masiva de resultados bibliográficos en formato RIS desde cada fuente.
    4. Unificación automática de los resultados descargados, eliminando duplicados por DOI o título.
    5. Generación de dos archivos finales:
         - Archivo unificado (sin duplicados) con toda la información consolidada.
         - Archivo de duplicados eliminados, con trazabilidad de los registros repetidos.

El proceso cubre todo el flujo “búsqueda → descarga → limpieza → unificación”, sin intervención manual.
Está diseñado para ejecutarse en entornos académicos con acceso institucional a través de proxys CRAI.

Autor: [Yan Gomez, Camilo Mejia]
Versión: 1.0
Fecha: 2025-11-09
Lenguaje: Python 3
Dependencias: Selenium, Configuración local (config.py), módulos utils/*
"""

import os
import time
from datetime import datetime

# Módulo de configuración (credenciales, rutas de descarga, paths de ChromeDriver, etc.)
import config

# Utilidades personalizadas (browser automation, login, exportación y manejo RIS)
from utils.browser import crear_navegador, cerrar_banners
from utils.sso_google import login_con_google
import utils.sage as sage
import utils.sciencedirect as sd
from utils.ris_merge import load_ris_from_dirs, merge_records, export_outputs

# Librerías Selenium usadas en los fallbacks locales
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException


# ===============================================================
# SECCIÓN 1. FUNCIONES DE FALLBACK PARA SCIENCEDIRECT
# ---------------------------------------------------------------
# Estas funciones se utilizan solo si el módulo utils.sciencedirect
# no contiene implementaciones equivalentes.
# ===============================================================

def _sd_resultados_listos(driver, timeout=25):
    """
    Verifica que la página de resultados (SRP) de ScienceDirect esté lista.

    Parámetros:
        driver : objeto WebDriver activo.
        timeout : tiempo máximo de espera en segundos.

    Retorna:
        None. (Lanza excepción si los elementos no están disponibles).

    Descripción:
        Esta función comprueba mediante heurísticas que los componentes
        principales (botón "Select All", botón "Export" y la lista de resultados)
        estén cargados antes de continuar la automatización.
    """
    def listo(d):
        try:
            sel_all = bool(d.find_elements(By.CSS_SELECTOR, '#select-all-results'))
            btn_exp = bool(d.find_elements(By.CSS_SELECTOR, 'button[data-aa-button="srp-export-multi-expand"]'))
            items = bool(d.find_elements(By.CSS_SELECTOR, 'a.result-list-title-link, ol.search-results li, div.result-item-content'))
            return (sel_all or btn_exp) and items
        except Exception:
            return False
    WebDriverWait(driver, timeout).until(listo)


def _sd_set_per_page_manual(driver, per_page=100, timeout=20):
    """
    Configura manualmente la cantidad de resultados por página (25, 50 o 100).

    Parámetros:
        driver : objeto WebDriver.
        per_page : número de resultados por página.
        timeout : tiempo máximo de espera.

    Retorna:
        True si se aplicó o ya estaba configurado el valor deseado.
    """
    _sd_resultados_listos(driver, timeout=timeout)

    # Verifica si ya está activo el valor deseado.
    try:
        active = driver.find_element(By.CSS_SELECTOR, 'ol.ResultsPerPage span.active-per-page')
        if (active.text or "").strip() == str(per_page):
            return True
    except Exception:
        pass

    # Busca el enlace correspondiente al número deseado.
    links = driver.find_elements(By.CSS_SELECTOR, 'ol.ResultsPerPage a.anchor')
    target = None
    for a in links:
        if (a.text or "").strip() == str(per_page):
            target = a
            break
    if not target:
        return True  # Si no hay enlace disponible, se asume que ya está aplicado.

    # Desplaza hacia el elemento y hace clic para aplicar el cambio.
    href_before = driver.current_url
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
    except Exception:
        pass
    try:
        target.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", target)

    # Espera a que la página recargue con el nuevo valor.
    def listo(d):
        try:
            a = d.find_element(By.CSS_SELECTOR, 'ol.ResultsPerPage span.active-per-page')
            return (a.text or "").strip() == str(per_page) or d.current_url != href_before
        except Exception:
            return d.current_url != href_before

    WebDriverWait(driver, timeout).until(listo)
    time.sleep(0.4)
    return True


def _sd_marcar_select_all(driver, timeout=12):
    """
    Marca la casilla 'Select all articles' en los resultados de ScienceDirect.

    Parámetros:
        driver : objeto WebDriver.
        timeout : tiempo máximo de espera.

    Retorna:
        None (lanza TimeoutException si no puede marcarse).
    """
    try:
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.2)
    except Exception:
        pass

    inp = None
    for sel in ['#select-all-results', 'input.checkbox-input#select-all-results', 'input.checkbox-input[aria-label*="Select all"]']:
        try:
            inp = driver.find_element(By.CSS_SELECTOR, sel)
            break
        except NoSuchElementException:
            continue

    lbl = None
    for sel in ['label[for="select-all-results"]', 'label.checkbox-label[for="select-all-results"]']:
        try:
            lbl = driver.find_element(By.CSS_SELECTOR, sel)
            break
        except NoSuchElementException:
            continue

    if not inp and not lbl:
        raise TimeoutException("No se encontró el checkbox ni el label de 'Select all articles'.")

    def _checked():
        """Verifica si la casilla ya está marcada."""
        try:
            if inp and inp.is_selected():
                return True
            if inp and (inp.get_attribute("aria-checked") or "").lower() == "true":
                return True
            return False
        except Exception:
            return False

    # Intenta marcar con distintos métodos (click directo, JS, label)
    if not _checked() and inp:
        try:
            inp.click()
            time.sleep(0.25)
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", inp)

    if not _checked() and lbl:
        try:
            lbl.click()
            time.sleep(0.25)
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", lbl)

    if not _checked() and inp:
        driver.execute_script("""
            const el = arguments[0];
            try { el.click(); } catch(e){}
            el.checked = true;
            el.setAttribute('aria-checked','true');
            el.dispatchEvent(new Event('change', {bubbles:true}));
        """, inp)
        time.sleep(0.25)

    if not _checked():
        raise TimeoutException("No fue posible marcar 'Select all articles'.")


def _sd_export_ris_pagina(driver, carpeta_descargas, consulta_slug="generative-artificial-intelligence", etiqueta="p1", timeout=25):
    """
    Exporta los resultados de la página actual en formato RIS.

    Parámetros:
        driver : WebDriver activo.
        carpeta_descargas : directorio donde se almacenará el archivo RIS.
        consulta_slug : nombre simplificado de la consulta (para nombrar archivo).
        etiqueta : identificador de página (ejemplo: p1, p2...).
        timeout : tiempo máximo de espera.

    Retorna:
        Ruta del archivo RIS descargado.
    """
    _sd_resultados_listos(driver, timeout=timeout)
    _sd_marcar_select_all(driver)

    def _export_habilitado(d):
        """Verifica si el botón de exportación está disponible."""
        try:
            b = d.find_element(By.CSS_SELECTOR, 'button[data-aa-button="srp-export-multi-expand"]')
            aria = (b.get_attribute("aria-disabled") or "").lower()
            disabled = b.get_attribute("disabled")
            return (aria == "false") or (aria == "") and (disabled is None)
        except Exception:
            return False

    try:
        WebDriverWait(driver, 10).until(_export_habilitado)
    except TimeoutException:
        pass

    # Inicia el proceso de exportación
    btn = driver.find_element(By.CSS_SELECTOR, 'button[data-aa-button="srp-export-multi-expand"]')
    try:
        btn.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", btn)

    time.sleep(0.3)

    # Selecciona formato RIS
    ris = driver.find_element(By.CSS_SELECTOR, 'button[data-aa-button="srp-export-multi-ris"]')
    try:
        ris.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", ris)

    # Espera la descarga
    from utils.browser import esperar_descarga_por_extension, renombrar_si_es_necesario
    ruta = esperar_descarga_por_extension(carpeta_descargas, extension=".ris", timeout=90)
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    nombre_final = f"sd_{consulta_slug}_{etiqueta}_{fecha}.ris"
    final_path = renombrar_si_es_necesario(ruta, nombre_final)
    print(f"✅ SD {etiqueta}: descargado -> {final_path}")
    return final_path


def _sd_next(driver, timeout=20):
    """
    Avanza a la siguiente página de resultados en ScienceDirect.

    Parámetros:
        driver : objeto WebDriver.
        timeout : tiempo máximo de espera.

    Retorna:
        True si se avanza correctamente, False si no hay más páginas.
    """
    candidatos = [
        (By.CSS_SELECTOR, 'li.pagination-link.next-link a.anchor[data-aa-name="srp-next-page"]'),
        (By.CSS_SELECTOR, 'a.anchor[data-aa-name="srp-next-page"]'),
        (By.XPATH, '//a[contains(@data-aa-name,"srp-next-page") or .//span[contains(., "next")]]')
    ]
    nxt = None
    for how, what in candidatos:
        try:
            nxt = driver.find_element(how, what)
            break
        except NoSuchElementException:
            continue
    if not nxt:
        return False

    url_before = driver.current_url
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", nxt)
    except Exception:
        pass
    try:
        nxt.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", nxt)

    try:
        WebDriverWait(driver, timeout).until(lambda d: d.current_url != url_before)
    except TimeoutException:
        _sd_resultados_listos(driver, timeout=timeout)

    time.sleep(0.4)
    return True


# ===============================================================
# SECCIÓN 2. PIPELINE PRINCIPAL
# ---------------------------------------------------------------
# Orquesta todo el flujo: SAGE → ScienceDirect → Unificación
# ===============================================================

def run_pipeline(
    query="generative artificial intelligence",
    paginas_sage=1,
    paginas_sd=1,
    sd_per_page=100
):
    """
    Ejecuta el pipeline completo de descarga y unificación.

    Parámetros:
        query : término de búsqueda a utilizar en ambas bases.
        paginas_sage : número de páginas a exportar desde SAGE Journals.
        paginas_sd : número de páginas a exportar desde ScienceDirect.
        sd_per_page : número de resultados por página en ScienceDirect.

    Descripción:
        1. Abre navegador y accede a SAGE → descarga resultados.
        2. Abre navegador y accede a ScienceDirect → descarga resultados.
        3. Unifica archivos .RIS y elimina duplicados.
        4. Genera archivo final con registros únicos y otro con duplicados.
    """
    # -------- SAGE --------
    driver = crear_navegador(config.CHROMEDRIVER_PATH, config.DOWNLOAD_DIR_SAGE)
    try:
        URL_SAGE = "https://journals-sagepub-com.crai.referencistas.com/"
        login_con_google(
            driver=driver,
            url_revista=URL_SAGE,
            correo_institucional=config.USUARIO,
            contrasena=config.CONTRASENA,
            carpeta_descargas=config.DOWNLOAD_DIR_SAGE,
            dominio_objetivo="journals-sagepub-com"
        )
        cerrar_banners(driver)
        sage.buscar_en_sage(driver, query, config.DOWNLOAD_DIR_SAGE)

        print(f"→ SAGE: exportando {paginas_sage} página(s)...")
        sage.exportar_ris_paginando(
            driver,
            carpeta_descargas=config.DOWNLOAD_DIR_SAGE,
            consulta_slug=query.replace(" ", "-"),
            max_paginas=paginas_sage
        )
    finally:
        driver.quit()

    # -------- ScienceDirect --------
    driver = crear_navegador(config.CHROMEDRIVER_PATH, config.DOWNLOAD_DIR_SCIENCEDIRECT)
    try:
        URL_SD = getattr(config, "SCIENCEDIRECT_URL", "https://www-sciencedirect-com.crai.referencistas.com/")
        login_con_google(
            driver=driver,
            url_revista=URL_SD,
            correo_institucional=config.USUARIO,
            contrasena=config.CONTRASENA,
            carpeta_descargas=config.DOWNLOAD_DIR_SCIENCEDIRECT,
            dominio_objetivo="www-sciencedirect-com"
        )
        cerrar_banners(driver)

        # Realiza búsqueda y configuración de resultados
        sd.abrir_home_sciencedirect(driver, URL_SD, config.DOWNLOAD_DIR_SCIENCEDIRECT)
        sd.buscar_en_sciencedirect(driver, query, config.DOWNLOAD_DIR_SCIENCEDIRECT)

        # Define número de resultados por página
        if hasattr(sd, "fijar_resultados_por_pagina"):
            sd.fijar_resultados_por_pagina(driver, per_page=sd_per_page, carpeta_descargas=config.DOWNLOAD_DIR_SCIENCEDIRECT)
        else:
            _sd_set_per_page_manual(driver, per_page=sd_per_page)

        # Descarga resultados de varias páginas
        if hasattr(sd, "descargar_varias_paginas_sd"):
            sd.descargar_varias_paginas_sd(
                driver,
                carpeta_descargas=config.DOWNLOAD_DIR_SCIENCEDIRECT,
                consulta_slug=query.replace(" ", "-"),
                paginas=paginas_sd,
                etiqueta_prefijo="p"
            )
        else:
            # Fallback local: exporta página actual y avanza
            for i in range(1, paginas_sd + 1):
                _sd_export_ris_pagina(
                    driver,
                    carpeta_descargas=config.DOWNLOAD_DIR_SCIENCEDIRECT,
                    consulta_slug=query.replace(" ", "-"),
                    etiqueta=f"p{i}"
                )
                if i < paginas_sd:
                    if not _sd_next(driver):
                        print("ℹ SD: no hay más páginas.")
                        break

    finally:
        driver.quit()

    # -------- Unificación --------
    print("\n📥 Leyendo y unificando descargas SAGE + ScienceDirect ...")
    dirs = []
    if os.path.isdir(config.DOWNLOAD_DIR_SAGE):
        dirs.append((config.DOWNLOAD_DIR_SAGE, "SAGE"))
    if os.path.isdir(config.DOWNLOAD_DIR_SCIENCEDIRECT):
        dirs.append((config.DOWNLOAD_DIR_SCIENCEDIRECT, "ScienceDirect"))

    registros = load_ris_from_dirs(dirs, exts=(".ris", ".RIS", ".txt", ".TXT"), verbose=True)
    print(f"\n🧮 Unificando y deduplicando por DOI/Título (total leídos: {len(registros)}) ...")
    unificados, duplicados = merge_records(registros)

    out_dir = getattr(config, "OUTPUT_DIR_BIBLIO", os.path.join(os.path.expanduser("~"), "Desktop", "salidas"))
    os.makedirs(out_dir, exist_ok=True)
    export_outputs(unificados, duplicados, out_dir, base_name="unificado_ai_generativa")

    print("\n✅ Pipeline completo. Archivos en:", out_dir)


# ===============================================================
# SECCIÓN 3. PUNTO DE ENTRADA PRINCIPAL
# ===============================================================
if __name__ == "__main__":
    """
    Punto de entrada principal del programa.
    Permite ajustar parámetros de ejecución del pipeline.
    """
    run_pipeline(
        query='generative artificial intelligence',
        paginas_sage=5,   # Cantidad de páginas a descargar en SAGE
        paginas_sd=5,     # Cantidad de páginas a descargar en ScienceDirect
        sd_per_page=100   # Resultados por página (25/50/100)
    )
