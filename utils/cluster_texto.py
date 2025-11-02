# utils/cluster_texto.py
# ======================================================================================
# Núcleo del Requerimiento 4 (agrupamiento jerárquico con dendrogramas sobre abstracts)
# - Limpieza mínima + TF-IDF
# - Similitud coseno y DISTANCIA = 1 - coseno
# - Enlaces jerárquicos: single, complete, average (y Ward opcional)
# - Métricas: silhouette (k=2..8) y correlación cofenética
# - Artefactos: dendrogramas .png, métricas .csv/.json, asignaciones .csv
#
# Comentarios pedagógicos señalan:
#   • DÓNDE ocurre la "multiplicación de vectores" (producto punto) en coseno
#   • CÓMO se construye la matriz de distancias
#   • CÓMO se aplican los distintos "linkage"
# ======================================================================================

from __future__ import annotations

import os
import math
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple

# TF-IDF y similitud coseno
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

# Clustering jerárquico y utilidades
from scipy.cluster.hierarchy import linkage, dendrogram, fcluster, cophenet
from scipy.spatial.distance import squareform

# Visualización
import matplotlib.pyplot as plt


# ---------------------------
# 0) Cargar datos del CSV
# ---------------------------
def cargar_abstracts(ruta_csv: str) -> pd.DataFrame:
    """
    Lee el CSV unificado y retorna un DataFrame con (al menos) columnas:
    - 'title'
    - 'abstract'  (si está vacío, usamos 'title' como respaldo)
    """
    if not os.path.isfile(ruta_csv):
        raise FileNotFoundError(f"No se encontró el CSV: {ruta_csv}")

    df = pd.read_csv(ruta_csv, encoding="utf-8")
    cols = {c.lower().strip(): c for c in df.columns}
    if "abstract" not in cols:
        raise ValueError("El CSV no contiene columna 'abstract'.")

    # Respaldo: si abstract está vacío, usar title
    abs_col = cols["abstract"]
    if "title" in cols:
        title_col = cols["title"]
        df[abs_col] = df[abs_col].fillna("")
        vacios = df[abs_col].astype(str).str.strip().eq("")
        df.loc[vacios, abs_col] = df.loc[vacios, title_col].fillna("")
    else:
        df[abs_col] = df[abs_col].fillna("")

    return df.rename(columns={abs_col: "abstract"})


# ----------------------------------------------
# 1) Preprocesamiento simple + TF-IDF del corpus
# ----------------------------------------------
def vectorizar_tfidf(
    textos: List[str],
    idioma_stopwords: str = "english",
    usar_bigramas: bool = True,
) -> Tuple[np.ndarray, TfidfVectorizer]:
    """
    Transforma lista de abstracts -> MATRIZ TF-IDF (documentos x términos).
    - ngram_range=(1,2) activa bigramas (mejor señal temática)
    - stop_words filtra palabras vacías
    - normalizamos L2 para que el coseno sea un producto punto entre vectores unitarios
    """
    ngram = (1, 2) if usar_bigramas else (1, 1)
    vectorizador = TfidfVectorizer(
        lowercase=True,
        stop_words=idioma_stopwords,
        ngram_range=ngram,
        min_df=1,
        max_df=1.0,
    )
    X = vectorizador.fit_transform(textos)  # matriz dispersa (sparse)
    X = normalize(X, norm="l2", copy=False)  # ||v||=1

    return X, vectorizador


# ----------------------------------------------------------
# 2) Similitud coseno y DISTANCIA (1 - coseno) entre docs
# ----------------------------------------------------------
def matriz_similitud_coseno(X) -> np.ndarray:
    """
    Calcula SIMILITUD(i,j) = coseno(vec_i, vec_j).
    Dónde ocurre la "multiplicación de vectores":
      cos(θ) = (A · B) / (||A|| * ||B||)
    Como X está L2-normalizada: ||A||=||B||=1 ⇒ cos(θ) = A · B = sum_k (a_k * b_k)
    cosine_similarity ejecuta vectorizado:
      SIM = X * X^T   ← AQUÍ pasa la "multiplicación de vectores"
    """
    return cosine_similarity(X, X)


def matriz_distancia_desde_similitud(S: np.ndarray) -> np.ndarray:
    """Convierte SIMILITUD → DISTANCIA para clustering: dist = 1 - similitud."""
    D = 1.0 - S
    np.fill_diagonal(D, 0.0)
    return D


# --------------------------------------------------------------------
# 3) Ejecutar clustering jerárquico para varios "linkage" (criterios)
# --------------------------------------------------------------------
def clustering_jerarquico(
    D: np.ndarray,
    X_euclideo=None,
    linkages: List[str] = ("single", "complete", "average", "ward"),
) -> Dict[str, Dict]:
    """
    - 'single'/'complete'/'average': usan la matriz de distancias por coseno.
      linkage() espera un vector condensado → squareform(D).
    - 'ward': minimiza varianza con distancia EUCLÍDEA; pasamos X (no D).
    Devuelve: {'metodo': {'Z': linkage_matrix, 'tipo': ..., 'usa': 'cosine'/'euclidean'}}
    """
    resultados = {}
    dvec = squareform(D, checks=False)  # vector condensado (triángulo sup.)

    for metodo in linkages:
        m = metodo.lower()
        if m in ("single", "complete", "average"):
            Z = linkage(dvec, method=m)
            resultados[m] = {"Z": Z, "tipo": m, "usa": "cosine"}
        elif m == "ward":
            if X_euclideo is None:
                raise ValueError("Para 'ward' se requiere X en espacio euclídeo.")
            Z = linkage(X_euclideo.toarray() if hasattr(X_euclideo, "toarray") else X_euclideo, method="ward")
            resultados[m] = {"Z": Z, "tipo": m, "usa": "euclidean"}
        else:
            continue

    return resultados


# ---------------------------------------------------------
# 4) Dibujar dendrogramas y guardar como imágenes (PNG)
# ---------------------------------------------------------
def guardar_dendrograma(Z, etiquetas: List[str], ruta_png: str, titulo: str):
    """
    Genera y guarda el dendrograma.
    - Eje Y: "altura" de fusión (distancia)
    - Eje X: documentos (titulares abreviados)
    """
    plt.figure(figsize=(12, 6))
    dendrogram(
        Z,
        labels=etiquetas,
        leaf_rotation=90,
        leaf_font_size=8,
        color_threshold=None,
    )
    plt.title(titulo)
    plt.tight_layout()
    plt.savefig(ruta_png, dpi=150)
    plt.close()


# ---------------------------------------------------------
# 5) Métricas: Silhouette y Correlación Cofenética
# ---------------------------------------------------------
def evaluar_metodo(
    metodo: str,
    Z,
    D_cosine: np.ndarray,
    ks: List[int] = list(range(2, 9)),
) -> Dict:
    """
    Evalúa un 'linkage' con:
      - silhouette para k=2..8 (usando distancias por coseno, precomputed)
      - correlación cofenética (qué tan bien el dendrograma preserva distancias)
    Retorna dict con métricas y el mejor k según silhouette.
    """
    from sklearn.metrics import silhouette_score

    # Vector condensado de la matriz de distancias original (coseno)
    Y = squareform(D_cosine, checks=False)

    # cophenet devuelve (correlación, distancias_cofenéticas) cuando se le pasa Y
    coph_corr, coph_dists = cophenet(Z, Y)

    # Silhouette por k
    silhouette_k = {}
    for k in ks:
        etiquetas = fcluster(Z, t=k, criterion="maxclust")
        try:
            sil = silhouette_score(D_cosine, etiquetas, metric="precomputed")
        except Exception:
            sil = float("nan")
        silhouette_k[str(k)] = float(sil)

    # Mejor k (máx silhouette, ignorando NaN)
    k_mejor, sil_mejor = None, -1.0
    for k_str, val in silhouette_k.items():
        if not math.isnan(val) and val > sil_mejor:
            sil_mejor = val
            k_mejor = int(k_str)

    return {
        "metodo": metodo,
        "cophenetic_correlation": float(coph_corr),
        "silhouette": silhouette_k,
        "k_mejor": k_mejor,
        "silhouette_mejor": float(sil_mejor) if k_mejor is not None else None,
    }


# ---------------------------------------------------------
# 6) Utilidad pedagógica: coseno "a mano" para 2 documentos
# ---------------------------------------------------------
def coseno_manual_para_dos(X, i: int, j: int) -> float:
    """
    Muestra explícitamente la "multiplicación de vectores".
    Suponiendo X normalizada L2:
       cos = A · B = sum_k (a_k * b_k)
    """
    vi = X[i]
    vj = X[j]

    # Convertimos a densos si son dispersos
    if hasattr(vi, "toarray"):
        ai = vi.toarray().ravel()
        bj = vj.toarray().ravel()
    else:
        ai = np.asarray(vi).ravel()
        bj = np.asarray(vj).ravel()

    # PRODUCTO PUNTO → similitud coseno por normalización L2
    return float(np.dot(ai, bj))
