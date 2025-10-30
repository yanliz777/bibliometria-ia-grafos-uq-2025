# utils/sage.py
# Automatiza búsqueda y exportación por páginas en SAGE Journals (robusto contra modal/backdrop).

import os, time
from datetime import datetime
from urllib.parse import urljoin
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, NoSuchElementException, ElementClickInterceptedException
)
from .browser import esperar_descarga_por_extension, renombrar_si_es_necesario

# ---------------- utilidades ----------------

def _guardar(driver, carpeta, nombre_png):
    try:
        os.makedirs(carpeta, exist_ok=True)
        driver.save_screenshot(os.path.join(carpeta, nombre_png))
    except Exception:
        pass

def _cerrar_banners_sage(driver):
    """Intenta cerrar el banner de cookies de SAGE (OneTrust u otros)."""
    candidatos = [
        (By.CSS_SELECTOR, "#onetrust-accept-btn-handler"),
        (By.XPATH, '//button[contains(., "Accept") or contains(., "Aceptar")]'),
        (By.XPATH, '//button[contains(., "Agree") or contains(., "De acuerdo")]'),
    ]
    for how, what in candidatos:
        try:
            WebDriverWait(driver, 3).until(EC.element_to_be_clickable((how, what))).click()
            time.sleep(0.5)
            break
        except Exception:
            pass

def _scroll_center(driver, el):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
    except Exception:
        pass

def _ensure_no_modal(driver):
    """
    Cierra/oculta el modal de export y elimina cualquier 'modal-backdrop' residual
    que pueda bloquear la interacción con la paginación.
    """
    # intentar cerrar con el botón Close si está visible
    try:
        _cerrar_modal_export(driver, timeout=2)
    except Exception:
        pass

    # limpieza agresiva con JS
    try:
        driver.execute_script("""
            const modal = document.querySelector('#exportCitation');
            if (modal) {
                modal.style.display = 'none';
                modal.classList.remove('show');
            }
            document.querySelectorAll('.modal-backdrop').forEach(b => b.remove());
            document.body.classList.remove('modal-open');
            document.body.style.overflow = '';
        """)
    except Exception:
        pass
    time.sleep(0.2)

def _lista_resultados_cargada(d):
    """Heurística simple: hay resultados listados (sin depender de selectores frágiles)."""
    try:
        items = d.find_elements(By.CSS_SELECTOR, 'a[href*="/doi/"], a.issue-item__title, div.search__item')
        return len(items) > 0
    except Exception:
        return False

# ---------------- búsqueda ----------------

def buscar_en_sage(driver, query, carpeta_descargas):
    """
    Desde la home de SAGE:
      - cierra banners
      - escribe la cadena (entre comillas) en el input
      - envía el formulario
      - espera a que cargue la página de resultados
    """
    _cerrar_banners_sage(driver)

    # 1) Contenedor de búsqueda presente
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="search"][aria-label*="Search Sage Journals"]'))
    )

    # 2) Input (selectores estables)
    input_selectores = [
        (By.NAME, "AllField"),
        (By.CSS_SELECTOR, 'input.quick-search__input'),
        (By.CSS_SELECTOR, 'form.quick-search__form input[type="search"]'),
    ]

    textbox = None
    for how, what in input_selectores:
        try:
            textbox = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((how, what)))
            break
        except Exception:
            continue

    if textbox is None:
        raise RuntimeError("No se encontró el input de búsqueda en SAGE.")

    # 3) Escribir la cadena (forzamos comillas)
    cadena = f"\"{query}\"" if not (query.startswith('"') and query.endswith('"')) else query
    textbox.clear()
    textbox.send_keys(cadena)

    # 4) Enviar búsqueda
    try:
        boton_buscar = driver.find_element(By.CSS_SELECTOR, 'button.quick-search__button')
        boton_buscar.click()
    except Exception:
        textbox.submit()

    # 5) Esperar resultados (/action/doSearch o /search)
    WebDriverWait(driver, 20).until(
        lambda d: ("/action/doSearch" in d.current_url) or ("/search" in d.current_url)
    )

    time.sleep(1)
    _guardar(driver, carpeta_descargas, "06_sage_resultados.png")
    print("✅ Búsqueda enviada en SAGE. URL resultados:", driver.current_url)
    return True

# ---------------- export modal helpers ----------------

def _export_habilitado(d):
    """Devuelve True cuando el enlace 'Export selected citations' está habilitado."""
    try:
        a = d.find_element(By.CSS_SELECTOR, 'a[data-id="srp-export-citations"]')
        cls = a.get_attribute("class") or ""
        aria = (a.get_attribute("aria-disabled") or "").lower()
        disabled = a.get_attribute("disabled")
        return ("disabled" not in cls) and (aria != "true") and (disabled is None)
    except Exception:
        return False

def _cerrar_modal_export(driver, timeout=10):
    """Cierra el modal #exportCitation con el botón 'Close'."""
    try:
        modal = WebDriverWait(driver, timeout).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, '#exportCitation'))
        )
    except TimeoutException:
        return False

    candidatos = [
        (By.CSS_SELECTOR, '#exportCitation button.close[data-dismiss="modal"]'),
        (By.CSS_SELECTOR, '#exportCitation button.close'),
        (By.XPATH, '//*[@id="exportCitation"]//button[@data-dismiss="modal" and contains(@class,"close")]')
    ]
    for how, what in candidatos:
        try:
            WebDriverWait(driver, 5).until(EC.element_to_be_clickable((how, what))).click()
            WebDriverWait(driver, timeout).until(
                EC.invisibility_of_element_located((By.CSS_SELECTOR, '#exportCitation'))
            )
            return True
        except Exception:
            continue
    return False

# ---------------- paginación robusta ----------------

def _ir_a_siguiente_pagina(driver):
    """
    Click robusto en 'Siguiente':
      - limpia/oculta modal y backdrop
      - intenta click normal / JS
      - fallback: navegar a href (absoluto)
    """
    _ensure_no_modal(driver)

    next_anchor = None
    candidatos = [
        (By.CSS_SELECTOR, 'a.next.hvr-forward.pagination__link'),
        (By.CSS_SELECTOR, 'a.pagination__link.next'),
        (By.CSS_SELECTOR, 'li.pagination-link.next-link > a.anchor'),
        (By.XPATH, '//a[contains(@class,"pagination__link") and contains(@class,"next")]'),
        (By.XPATH, '//a[contains(@data-aa-name,"next") or .//span[contains(., "next")]]'),
    ]
    for how, what in candidatos:
        try:
            next_anchor = driver.find_element(how, what)
            break
        except NoSuchElementException:
            continue

    if not next_anchor:
        return False

    # ¿deshabilitado?
    try:
        aria = (next_anchor.get_attribute("aria-disabled") or "").lower()
        cls = (next_anchor.get_attribute("class") or "")
        if 'disabled' in cls or aria == 'true':
            return False
    except Exception:
        pass

    href_before = driver.current_url
    href = next_anchor.get_attribute("href")

    _scroll_center(driver, next_anchor)
    try:
        WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, '.')))
        next_anchor.click()
    except Exception:
        try:
            driver.execute_script("arguments[0].click();", next_anchor)
        except Exception:
            if href:
                driver.get(urljoin(href_before, href))
            else:
                return False

    # esperar cambio
    try:
        WebDriverWait(driver, 15).until(
            lambda d: (d.current_url != href_before) or _lista_resultados_cargada(d)
        )
        time.sleep(0.6)
        _ensure_no_modal(driver)
        return True
    except TimeoutException:
        return False

# ---------------- exportar página actual ----------------

def exportar_ris_pagina_actual(driver, carpeta_descargas, consulta_slug="generative-artificial-intelligence", etiqueta="p1"):
    """
    Selecciona todos los resultados visibles, abre Export, descarga RIS y CIERRA el modal.
      - Select all: #action-bar-select-all
      - Export: a[data-id="srp-export-citations"]
      - Modal: #exportCitation
      - Descargar: a.download__btn
    """
    _cerrar_banners_sage(driver)
    _ensure_no_modal(driver)  # por si quedó algo de una operación previa

    # Select all
    chk_all = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, '#action-bar-select-all'))
    )
    _scroll_center(driver, chk_all)
    if not chk_all.is_selected():
        chk_all.click()
        time.sleep(0.3)

    # Habilitar export
    WebDriverWait(driver, 10).until(_export_habilitado)
    export_link = driver.find_element(By.CSS_SELECTOR, 'a[data-id="srp-export-citations"]')
    try:
        export_link.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", export_link)

    # Modal visible
    modal = WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, '#exportCitation'))
    )
    time.sleep(0.2)

    # (si hubiera un select de formato, forzamos RIS)
    try:
        sel = modal.find_element(By.CSS_SELECTOR, 'select')
        for opt in sel.find_elements(By.TAG_NAME, 'option'):
            if "RIS" in (opt.text or ""):
                opt.click()
                time.sleep(0.2)
                break
    except Exception:
        pass

    # Descargar
    btn_download = WebDriverWait(modal, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, 'a.download__btn'))
    )
    try:
        btn_download.click()
    except ElementClickInterceptedException:
        driver.execute_script("arguments[0].click();", btn_download)

    # Esperar archivo .ris
    ruta = esperar_descarga_por_extension(carpeta_descargas, extension=".ris", timeout=120)
    fecha = datetime.now().strftime("%Y%m%d_%H%M")
    nombre_final = f"sage_{consulta_slug}_{etiqueta}_{fecha}.ris"
    final_path = renombrar_si_es_necesario(ruta, nombre_final)
    print(f"✅ Página {etiqueta}: descargado -> {final_path}")

    # Cerrar/limpiar modal y backdrop
    _ensure_no_modal(driver)
    return final_path

# ---------------- loop de paginación ----------------

def exportar_ris_paginando(driver, carpeta_descargas, consulta_slug="generative-artificial-intelligence", max_paginas=5):
    """
    Exporta RIS de varias páginas: página actual + 'Siguiente' hasta max_paginas o fin.
    Retorna lista de rutas de archivos descargados.
    """
    rutas = []
    for i in range(1, max_paginas + 1):
        etiqueta = f"p{i}"
        print(f"--- Procesando {etiqueta} ---")
        try:
            ruta = exportar_ris_pagina_actual(driver, carpeta_descargas, consulta_slug, etiqueta)
            rutas.append(ruta)
        except Exception as e:
            print(f"⚠️  Falló exportación en {etiqueta}: {e}")
            break

        # Intentar ir a siguiente
        pudo = _ir_a_siguiente_pagina(driver)
        if not pudo:
            print("ℹ️  No hay más páginas (o no se encontró 'Siguiente').")
            break
        time.sleep(0.6)

    print(f"✅ Descargas completadas: {len(rutas)} archivo(s).")
    return rutas
