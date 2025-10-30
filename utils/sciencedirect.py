# utils/sciencedirect.py
import os, time
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from .browser import esperar_descarga_por_extension, renombrar_si_es_necesario

# ---------------- utilidades pequeñas ----------------

def _scroll_into_view(driver, elem):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", elem)
    except Exception:
        pass

def _click(driver, how, what, timeout=12, use_js_fallback=False):
    el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((how, what)))
    _scroll_into_view(driver, el)
    try:
        el.click()
    except ElementClickInterceptedException:
        if use_js_fallback:
            driver.execute_script("arguments[0].click();", el)
        else:
            raise
    return el

def _type(driver, how, what, text, timeout=12):
    el = WebDriverWait(driver, timeout).until(EC.presence_of_element_located((how, what)))
    _scroll_into_view(driver, el)
    el.clear()
    el.send_keys(text)
    return el

def _guardar(driver, carpeta, nombre):
    try:
        os.makedirs(carpeta, exist_ok=True)
        driver.save_screenshot(os.path.join(carpeta, nombre))
    except Exception:
        pass

# ---------------- helpers específicos SD ----------------

def _esperar_resultados_listos(driver, timeout=20):
    """
    Heurística para saber que la SRP (Search Results Page) está lista:
    - existe el select-all (#select-all-results) o el botón Export
    - y hay al menos un contenedor de resultado
    """
    def listo(d):
        try:
            hay_select_all = bool(d.find_elements(By.CSS_SELECTOR, '#select-all-results'))
            hay_export = bool(d.find_elements(By.CSS_SELECTOR, 'button[data-aa-button="srp-export-multi-expand"]'))
            hay_items = bool(d.find_elements(By.CSS_SELECTOR, 'a.result-list-title-link, ol.search-results li, div.result-item-content'))
            return (hay_select_all or hay_export) and hay_items
        except Exception:
            return False
    WebDriverWait(driver, timeout).until(listo)

def _marcar_select_all_robusto(driver):
    """
    Intenta marcar 'Select all articles':
      1) input#select-all-results
      2) label[for="select-all-results"]
      3) JS click al input si el click normal falla
    Valida con is_selected() o aria-checked=true.
    """
    # asegurarnos de estar arriba (a veces es sticky)
    try:
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.2)
    except Exception:
        pass

    # localizar input
    inp = None
    for sel in ['#select-all-results', 'input.checkbox-input#select-all-results', 'input.checkbox-input[aria-label*="Select all"]']:
        try:
            inp = driver.find_element(By.CSS_SELECTOR, sel)
            break
        except NoSuchElementException:
            continue

    # localizar label
    lbl = None
    for sel in ['label[for="select-all-results"]', 'label.checkbox-label[for="select-all-results"]']:
        try:
            lbl = driver.find_element(By.CSS_SELECTOR, sel)
            break
        except NoSuchElementException:
            continue

    if not inp and not lbl:
        raise TimeoutException("No encontré el checkbox ni su label para 'Select all articles'.")

    # estrategia de clicks
    def _checked():
        try:
            if inp:
                # probar primero property checked
                if getattr(inp, "is_selected", None):
                    if inp.is_selected():
                        return True
                # si no refleja, mirar aria-checked
                aria = (inp.get_attribute("aria-checked") or "").lower()
                return aria == "true"
            return False
        except Exception:
            return False

    if not _checked():
        try:
            if inp:
                _scroll_into_view(driver, inp)
                try:
                    inp.click()
                except ElementClickInterceptedException:
                    driver.execute_script("arguments[0].click();", inp)
                time.sleep(0.25)
        except Exception:
            pass

    if not _checked() and lbl:
        try:
            _scroll_into_view(driver, lbl)
            try:
                lbl.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", lbl)
            time.sleep(0.25)
        except Exception:
            pass

    # último intento: JS directo sobre el input
    if not _checked() and inp:
        try:
            driver.execute_script("""
                const el = arguments[0];
                try { el.click(); } catch(e){}
                el.checked = true;
                el.setAttribute('aria-checked','true');
                el.dispatchEvent(new Event('change', {bubbles:true}));
            """, inp)
            time.sleep(0.25)
        except Exception:
            pass

    if not _checked():
        raise TimeoutException("No pude marcar 'Select all articles' (no quedó seleccionado).")

def _esperar_export_habilitado(driver, timeout=10):
    """
    Espera a que el botón Export NO esté deshabilitado (aria-disabled=false o sin atributo).
    """
    def habilitado(d):
        try:
            b = d.find_element(By.CSS_SELECTOR, 'button[data-aa-button="srp-export-multi-expand"]')
            aria = (b.get_attribute("aria-disabled") or "").lower()
            disabled = b.get_attribute("disabled")
            return (aria == "false") or (aria == "") and (disabled is None)
        except Exception:
            return False
    WebDriverWait(driver, timeout).until(habilitado)

# --------------- paso SD-1: abrir home autenticada ---------------

def abrir_home_sciencedirect(driver, url, carpeta_descargas):
    """
    Abre la home de ScienceDirect (vía CRAI) y verifica que el buscador está visible.
    """
    driver.get(url)

    candidatos = [
        (By.CSS_SELECTOR, 'input#qs[name="qs"]'),
        (By.CSS_SELECTOR, 'input.search-input-field[name="qs"]'),
        (By.CSS_SELECTOR, 'input[aria-label*="Find articles"]'),
    ]

    visible = False
    for how, what in candidatos:
        try:
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((how, what)))
            visible = True
            break
        except Exception:
            continue

    _guardar(driver, carpeta_descargas, "sd_home.png")

    if not visible:
        raise RuntimeError("No se detectó el buscador en ScienceDirect. ¿Sesión CRAI/SSO activa?")
    print("✅ Home de ScienceDirect lista:", driver.current_url)
    return True

# --------------- paso SD-2: buscar cadena ----------------

def buscar_en_sciencedirect(driver, query, carpeta_descargas):
    """
    Escribe la cadena en el input principal y ejecuta la búsqueda.
    Espera a que cargue la página de resultados.
    """
    # 1) Input
    text = f"\"{query}\"" if '"' not in query else query
    _type(driver, By.CSS_SELECTOR, 'input#qs[name="qs"]', text)

    # 2) Botón Search
    _click(driver, By.CSS_SELECTOR, 'button[aria-label="Submit quick search"]', use_js_fallback=True)

    # 3) Esperar resultados listos
    _esperar_resultados_listos(driver, timeout=25)
    time.sleep(0.4)
    _guardar(driver, carpeta_descargas, "sd_resultados.png")
    print("✅ Resultados de ScienceDirect cargados:", driver.current_url)
    return True

# --------------- paso SD-3: exportar RIS de la página actual ---------------

def exportar_ris_pagina_actual_sd(driver, carpeta_descargas, consulta_slug="generative-artificial-intelligence", etiqueta="p1"):
    """
    Página de resultados:
      - Marca 'Select all articles' (#select-all-results) con fallback robusto
      - Espera que Export esté habilitado y lo abre (data-aa-button="srp-export-multi-expand")
      - Click en 'Export citation to RIS' (data-aa-button="srp-export-multi-ris")
      - Espera el .ris y lo renombra
    """
    # asegurar que SRP esté lista
    _esperar_resultados_listos(driver, timeout=25)

    # 1) Marcar select-all (robusto)
    _marcar_select_all_robusto(driver)

    # 2) Esperar que Export esté habilitado (algunas UIs lo habilitan tras seleccionar)
    try:
        _esperar_export_habilitado(driver, timeout=10)
    except TimeoutException:
        # algunas veces ya está habilitado por defecto
        pass

    # 3) Abrir Export
    _click(driver, By.CSS_SELECTOR, 'button[data-aa-button="srp-export-multi-expand"]', use_js_fallback=True)
    time.sleep(0.3)

    # 4) Elegir RIS
    _click(driver, By.CSS_SELECTOR, 'button[data-aa-button="srp-export-multi-ris"]', use_js_fallback=True)

    # 5) Esperar .ris
    ruta = esperar_descarga_por_extension(carpeta_descargas, extension=".ris", timeout=90)
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    nombre_final = f"sd_{consulta_slug}_{etiqueta}_{fecha}.ris"
    final_path = renombrar_si_es_necesario(ruta, nombre_final)

    print(f"✅ SD {etiqueta}: descargado -> {final_path}")
    return final_path
