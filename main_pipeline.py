# main_pipeline.py
# Orquestra todo: SAGE -> ScienceDirect -> Unificación en un solo run.

import os
import time
from datetime import datetime

import config

from utils.browser import crear_navegador, cerrar_banners
from utils.sso_google import login_con_google
import utils.sage as sage
import utils.sciencedirect as sd
from utils.ris_merge import load_ris_from_dirs, merge_records, export_outputs

# Selenium helpers para los fallbacks locales (por si tus utils no traen ciertas funciones)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException


# ---------------- Fallbacks locales SOLO si no existen en utils.sciencedirect ----------------

def _sd_resultados_listos(driver, timeout=25):
    """Heurística: hay select-all o botón export + hay resultados en la SRP."""
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
    """Clic en el link del paginador 'ResultsPerPage' (25/50/100) si existe."""
    _sd_resultados_listos(driver, timeout=timeout)
    # ¿ya activo?
    try:
        active = driver.find_element(By.CSS_SELECTOR, 'ol.ResultsPerPage span.active-per-page')
        if (active.text or "").strip() == str(per_page):
            return True
    except Exception:
        pass

    # buscar enlace con el número
    links = driver.find_elements(By.CSS_SELECTOR, 'ol.ResultsPerPage a.anchor')
    target = None
    for a in links:
        if (a.text or "").strip() == str(per_page):
            target = a
            break
    if not target:
        return True  # si no hay link, asumimos que ya está aplicado

    href_before = driver.current_url
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", target)
    except Exception:
        pass
    try:
        target.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", target)

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
    """Marca 'Select all articles' con distintos intentos (input, label, JS)."""
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
        raise TimeoutException("No encontré el checkbox ni su label para 'Select all articles'.")

    def _checked():
        try:
            if inp and inp.is_selected():
                return True
            if inp and (inp.get_attribute("aria-checked") or "").lower() == "true":
                return True
            return False
        except Exception:
            return False

    if not _checked() and inp:
        try:
            inp.click()
            time.sleep(0.25)
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", inp)
            time.sleep(0.25)

    if not _checked() and lbl:
        try:
            lbl.click()
            time.sleep(0.25)
        except ElementClickInterceptedException:
            driver.execute_script("arguments[0].click();", lbl)
            time.sleep(0.25)

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
        raise TimeoutException("No pude marcar 'Select all articles'.")

def _sd_export_ris_pagina(driver, carpeta_descargas, consulta_slug="generative-artificial-intelligence", etiqueta="p1", timeout=25):
    """Exporta RIS de la página actual (fallback si no usamos sd.exportar_ris_pagina_actual_sd)."""
    _sd_resultados_listos(driver, timeout=timeout)
    _sd_marcar_select_all(driver)

    # habilitado export
    def _export_habilitado(d):
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

    # abrir export
    btn = driver.find_element(By.CSS_SELECTOR, 'button[data-aa-button="srp-export-multi-expand"]')
    try:
        btn.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", btn)
    time.sleep(0.3)

    # RIS
    ris = driver.find_element(By.CSS_SELECTOR, 'button[data-aa-button="srp-export-multi-ris"]')
    try:
        ris.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", ris)

    # esperar .ris usando el helper de utils.browser (ya lo usa utils.sciencedirect)
    from utils.browser import esperar_descarga_por_extension, renombrar_si_es_necesario
    ruta = esperar_descarga_por_extension(carpeta_descargas, extension=".ris", timeout=90)
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    nombre_final = f"sd_{consulta_slug}_{etiqueta}_{fecha}.ris"
    final_path = renombrar_si_es_necesario(ruta, nombre_final)
    print(f"✅ SD {etiqueta}: descargado -> {final_path}")
    return final_path

def _sd_next(driver, timeout=20):
    """Clic en 'next' en SRP (fallback)."""
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


# ---------------- Pipeline ----------------

def run_pipeline(
    query="generative artificial intelligence",
    paginas_sage=5,
    paginas_sd=5,
    sd_per_page=100
):
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

        # abrir home + buscar
        sd.abrir_home_sciencedirect(driver, URL_SD, config.DOWNLOAD_DIR_SCIENCEDIRECT)
        sd.buscar_en_sciencedirect(driver, query, config.DOWNLOAD_DIR_SCIENCEDIRECT)

        # forzar 100 por página: si el módulo lo trae, úsalo; si no, fallback local
        if hasattr(sd, "fijar_resultados_por_pagina"):
            sd.fijar_resultados_por_pagina(driver, per_page=sd_per_page, carpeta_descargas=config.DOWNLOAD_DIR_SCIENCEDIRECT)
        else:
            _sd_set_per_page_manual(driver, per_page=sd_per_page)

        # paginar y descargar
        if hasattr(sd, "descargar_varias_paginas_sd"):
            sd.descargar_varias_paginas_sd(
                driver,
                carpeta_descargas=config.DOWNLOAD_DIR_SCIENCEDIRECT,
                consulta_slug=query.replace(" ", "-"),
                paginas=paginas_sd,
                etiqueta_prefijo="p"
            )
        else:
            # Fallback: descargar página actual + next x (paginas_sd-1)
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


if __name__ == "__main__":
    # Ajusta aquí cuántas páginas quieres de cada fuente:
    run_pipeline(
        query='generative artificial intelligence',
        paginas_sage=5,   # SAGE: páginas
        paginas_sd=5,     # ScienceDirect: páginas
        sd_per_page=100   # SD: resultados por página (25/50/100)
    )
