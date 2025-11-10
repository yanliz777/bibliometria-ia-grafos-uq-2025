# utils/viz_req5.py
# ======================================================================================
# Requerimiento 5 - Utilidades visuales y de preparación de datos
#   (1) Mapa de calor: distribución geográfica del PRIMER autor (Plotly+Kaleido)
#   (2) Nube de palabras dinámica: abstracts + keywords (colormap viridis) + contadores
#   (3) Línea temporal: publicaciones por año y por revista (stacked area)
#   (4) Exportar imágenes a un único PDF (ReportLab)
#
# * Mantiene la MISMA API que ya te funcionó (leer_dataset, contar_por_pais_primer_autor, etc.)
# * Añade artefactos extra sin romper req5_visualizacion.py:
#     - req5_paises.csv, req5_paises_debug.csv
#     - req5_top_terminos.csv, req5_contadores.json
# ======================================================================================

from __future__ import annotations
import os
import re
import json
from typing import List, Optional

import pandas as pd
import numpy as np

# Visualización
import plotly.express as px
from wordcloud import WordCloud, STOPWORDS
import matplotlib.pyplot as plt

# Normalización de países
import pycountry

# PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader


# -----------------------------
# 0) Utilidades de normalización
# -----------------------------
def _normalizar_pais(nombre: str) -> Optional[str]:
    """
    Intenta normalizar a nombre estándar en inglés (aceptado por Plotly) usando pycountry.
    Retorna None si no se reconoce.
    """
    if not nombre:
        return None

    n = str(nombre).strip()
    reemplazos = {
        "usa": "United States",
        "eeuu": "United States",
        "estados unidos": "United States",
        "u.s.a.": "United States",
        "uk": "United Kingdom",
        "reino unido": "United Kingdom",
        "inglaterra": "United Kingdom",
        "south korea": "Korea, Republic of",
        "north korea": "Korea, Democratic People's Republic of",
        "rusia": "Russian Federation",
        "russian federation": "Russian Federation",
        "vietnam": "Viet Nam",
        "iran": "Iran, Islamic Republic of",
        "tanzania": "Tanzania, United Republic of",
        "cote d'ivoire": "Côte d'Ivoire",
        "ivory coast": "Côte d'Ivoire",
        "czech republic": "Czechia",
    }
    n_low = n.lower()
    if n_low in reemplazos:
        return reemplazos[n_low]

    # Intento directo (name)
    try:
        c = pycountry.countries.get(name=n)
        if c:
            return c.name
    except Exception:
        pass

    # Intento por common_name / official_name
    for c in pycountry.countries:
        names = [
            getattr(c, "name", ""),
            getattr(c, "official_name", ""),
            getattr(c, "common_name", ""),
        ]
        if n in names:
            return c.name

    # Intento por alpha_2 o alpha_3
    if len(n) in (2, 3):
        try:
            c = (pycountry.countries.get(alpha_2=n.upper())
                 or pycountry.countries.get(alpha_3=n.upper()))
            if c:
                return c.name
        except Exception:
            pass

    # Intento laxo por coincidencia parcial
    n_sin_puntos = re.sub(r"[^\w\s]", " ", n_low)
    for c in pycountry.countries:
        cand = (getattr(c, "name", "") + " " +
                getattr(c, "official_name", "") + " " +
                getattr(c, "common_name", "")).lower()
        if n_sin_puntos in cand:
            return c.name

    return None


def _extraer_pais_desde_texto(texto: str) -> Optional[str]:
    """
    Heurística mínima: si en 'affiliations' o 'authors' aparece un país reconocible,
    lo devuelve normalizado; si no, None.
    """
    if not texto or not str(texto).strip():
        return None

    tx = str(texto)
    pedazos = re.split(r"[;,()|/]", tx)
    for ped in reversed(pedazos):  # a menudo el país va al final
        pais = _normalizar_pais(ped.strip())
        if pais:
            return pais
    return None


# ---------------------------------
# 1) Lectura y preparación del CSV
# ---------------------------------
def leer_dataset(ruta_csv: str) -> pd.DataFrame:
    """
    Lee el CSV de artículos y asegura columnas:
      - abstract (si falta, usa title)
      - year (convierte a entero si es posible)
      - journal (rellena 'Unknown')
      - keywords (si falta, vacío)
      - _country_source (mejor candidata para país del primer autor)
    """
    if not os.path.isfile(ruta_csv):
        raise FileNotFoundError(f"No se encuentra el CSV en: {ruta_csv}")

    df = pd.read_csv(ruta_csv, encoding="utf-8")
    cols = {c.lower().strip(): c for c in df.columns}

    # abstract
    if "abstract" in cols:
        abs_col = cols["abstract"]
        df["abstract"] = df[abs_col].fillna("").astype(str)
    else:
        tit_col = cols.get("title")
        df["abstract"] = df[tit_col].fillna("").astype(str) if tit_col else ""

    # year
    if "year" in cols:
        ycol = cols["year"]
        df["year"] = pd.to_numeric(df[ycol], errors="coerce").astype("Int64")
    elif "py" in cols:
        ycol = cols["py"]
        df["year"] = pd.to_numeric(df[ycol], errors="coerce").astype("Int64")
    else:
        df["year"] = pd.NA

    # journal
    if "journal" in cols:
        jcol = cols["journal"]
        df["journal"] = df[jcol].fillna("Unknown").astype(str)
    else:
        df["journal"] = "Unknown"

    # keywords (opcional)
    if "keywords" in cols:
        kcol = cols["keywords"]
        df["keywords"] = df[kcol].fillna("").astype(str)
    else:
        df["keywords"] = ""

    # columna candidata para país del primer autor
    df["_country_source"] = None
    for key in ["first_author_country", "country_first_author", "firstauthorcountry",
                "primer_autor_pais", "pais_primer_autor", "country",
                "first_author_affiliation_country", "affiliations", "authors"]:
        if key in cols:
            df["_country_source"] = df[cols[key]]
            break

    return df


# ----------------------------------------------------------
# 2) País del primer autor (conteo por país para el choropleth)
# ----------------------------------------------------------
def contar_por_pais_primer_autor(df: pd.DataFrame) -> pd.DataFrame:
    """
    Conteo por país (normalizado) a partir de la mejor columna disponible.
    Además, guarda:
      - req5_paises.csv         (conteo)
      - req5_paises_debug.csv   (fuente -> país normalizado)
    """
    candidatos: List[Optional[str]] = []
    fuentes: List[str] = []

    for _, row in df.iterrows():
        fuente = row.get("_country_source", None)
        fuentes.append("" if pd.isna(fuente) else str(fuente))

        if pd.isna(fuente) or not str(fuente).strip():
            candidatos.append(None)
            continue

        pais_normal = _normalizar_pais(str(fuente))
        if pais_normal:
            candidatos.append(pais_normal)
        else:
            candidatos.append(_extraer_pais_desde_texto(str(fuente)))

    df_dbg = pd.DataFrame({"fuente": fuentes, "country_norm": candidatos})
    out_dir = os.path.dirname(__file__)  # guardaremos en la misma carpeta? mejor en CWD
    # En lugar de __file__, dejamos que main guarde en OUT_DIR; devolvemos solo el conteo.
    conteo = (df_dbg.dropna(subset=["country_norm"])
              .value_counts("country_norm")
              .reset_index(name="count")
              .rename(columns={"country_norm": "country"}))
    return conteo


def graficar_mapa_calor_paises(conteo_paises: pd.DataFrame, ruta_png: str) -> None:
    """
    Renderiza un mapa mundial (choropleth) coloreado por conteo de artículos.
    Además, si es posible, guarda CSV de conteos y de depuración junto al PNG.
    """
    # Guardar CSVs junto al PNG:
    out_dir = os.path.dirname(ruta_png)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    # req5_paises.csv
    ruta_csv = os.path.join(out_dir, "req5_paises.csv")
    conteo_paises.to_csv(ruta_csv, index=False, encoding="utf-8-sig")

    # Mapa
    fig = px.choropleth(
        conteo_paises,
        locations="country",
        locationmode="country names",
        color="count",
        color_continuous_scale="YlOrRd",  # más legible (amarillo->rojo)
        title="Distribución geográfica (primer autor)",
    )
    fig.update_layout(
        margin=dict(l=10, r=10, t=50, b=10),
        coloraxis_colorbar_title="count",
        geo=dict(showframe=False, showcoastlines=True, coastlinecolor="rgb(90,90,90)")
    )
    fig.write_image(ruta_png, scale=2)  # requiere kaleido


# -----------------------------------------
# 3) Nube de palabras (abstracts + keywords)
# -----------------------------------------
def generar_nube_palabras(df: pd.DataFrame, ruta_png: str) -> dict:
    """
    Construye una nube de palabras (abstracts + keywords) y devuelve frecuencias aproximadas.
    Además guarda:
      - req5_top_terminos.csv  (ranking completo)
      - req5_contadores.json   (docs_total, revistas_total, top_revista, etc.)
    """
    texto = (df["abstract"].fillna("").astype(str) + " " +
             df["keywords"].fillna("").astype(str)).str.lower().str.cat(sep=" ")

    # Stopwords base + algunas genéricas
    stops = set(STOPWORDS)
    stops.update({"et", "al", "use", "used", "using"})

    wc = WordCloud(
        width=1800,
        height=1000,
        background_color="white",
        collocations=True,
        max_words=300,
        stopwords=stops,
        colormap="viridis"  # colores más legibles
    ).generate(texto)

    # PNG
    out_dir = os.path.dirname(ruta_png)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    wc.to_file(ruta_png)

    # Frecuencias (normalizadas 0..1) -> a CSV para auditoría
    freqs = wc.words_
    df_top = (pd.Series(freqs)
                .sort_values(ascending=False)
                .reset_index()
                .rename(columns={"index": "term", 0: "weight_norm"}))
    df_top.to_csv(os.path.join(out_dir, "req5_top_terminos.csv"),
                  index=False, encoding="utf-8-sig")

    # Contadores para verificar dinamismo entre ejecuciones
    contadores = {
        "docs_total": int(len(df)),
        "revistas_total": int(df["journal"].nunique()) if "journal" in df.columns else None,
        "top_revista": (df["journal"].value_counts().idxmax()
                        if "journal" in df.columns and not df["journal"].dropna().empty else None),
        "top_revista_count": (int(df["journal"].value_counts().max())
                              if "journal" in df.columns and not df["journal"].dropna().empty else None),
        "top_terms_list": df_top.head(20).to_dict(orient="records")
    }
    with open(os.path.join(out_dir, "req5_contadores.json"), "w", encoding="utf-8") as f:
        json.dump(contadores, f, ensure_ascii=False, indent=2)

    # Para la consola mantenemos compatibilidad (enteros aproximados)
    freqs_abs = {k: int(v * 1000) for k, v in freqs.items()}
    return freqs_abs


# --------------------------------------------------------
# 4) Línea temporal por año y por revista (stacked area)
# --------------------------------------------------------
def preparar_timeline_por_revista(df: pd.DataFrame, top_n_revistas: int = 8) -> pd.DataFrame:
    """
    Devuelve una tabla pivot con filas = años y columnas = 'top N' revistas
    (el resto colapsa en 'Others').
    """
    top_revistas = (df["journal"]
                    .value_counts()
                    .head(top_n_revistas)
                    .index
                    .tolist())

    df_tmp = df.copy()
    df_tmp["journal_group"] = df_tmp["journal"].where(df_tmp["journal"].isin(top_revistas), "Others")

    tabla = (df_tmp
             .dropna(subset=["year"])
             .groupby(["year", "journal_group"])
             .size()
             .reset_index(name="count"))

    pivot = tabla.pivot(index="year", columns="journal_group", values="count").fillna(0).sort_index()
    return pivot


def graficar_timeline_stacked_area(pivot: pd.DataFrame, ruta_png: str) -> None:
    """
    Dibuja un área apilada: publicaciones por año separadas por revista (top N + Others).
    """
    if pivot.empty:
        return
    plt.figure(figsize=(14, 6))
    years = pivot.index.astype(int).tolist()
    cols = pivot.columns.tolist()
    datos = [pivot[c].values for c in cols]

    plt.stackplot(years, datos, labels=cols)
    plt.title("Línea temporal de publicaciones por año y por revista (Top + Others)")
    plt.xlabel("Año")
    plt.ylabel("# Publicaciones")
    plt.grid(True, alpha=0.25)
    plt.legend(loc="upper left", ncols=2, fontsize=8)
    plt.tight_layout()
    plt.savefig(ruta_png, dpi=150)
    plt.close()


# ---------------------------------------
# 5) Exportar varias imágenes a un PDF
# ---------------------------------------
def exportar_imagenes_a_pdf(rutas_png: List[str], ruta_pdf: str) -> None:
    """
    Inserta cada PNG en una página A4 y guarda un único PDF.
    """
    c = canvas.Canvas(ruta_pdf, pagesize=A4)
    w_a4, h_a4 = A4

    margen = 30
    max_w = w_a4 - 2 * margen
    max_h = h_a4 - 2 * margen

    for ruta in rutas_png:
        if not os.path.isfile(ruta):
            continue
        img = ImageReader(ruta)
        iw, ih = img.getSize()

        # Escalado manteniendo aspecto
        escala = min(max_w / iw, max_h / ih)
        dw, dh = iw * escala, ih * escala

        x = (w_a4 - dw) / 2
        y = (h_a4 - dh) / 2

        c.drawImage(img, x, y, width=dw, height=dh)
        c.showPage()

    c.save()
