# utils/analisis_frecuencias_es.py
# -------------------------------------------------------------------------------------------------
# Requerimiento 3 (versión en español):
# 1) Contar frecuencia de un conjunto de términos semilla en los abstracts.
# 2) Descubrir hasta 15 nuevos términos (unigramas/bigramas) relevantes con TF-IDF.
# 3) Evaluar la “precisión” de los nuevos términos mediante similitud semántica con embeddings.
#    - Si no hay sentence-transformers, el análisis semántico queda como N/D y el flujo continúa.
# 4) Guardar gráficos de barras simples (matplotlib) para visualización rápida.
# -------------------------------------------------------------------------------------------------

import os
import re
import math
from typing import List, Tuple, Dict

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

# Embeddings opcionales
try:
    from sentence_transformers import SentenceTransformer
    _HAY_ST = True
except Exception:
    _HAY_ST = False

# -----------------------
# Normalización de texto
# -----------------------

_patron_palabra = re.compile(r"[A-Za-z][A-Za-z\-']+")

def normalizar(texto: str) -> str:
    """
    Convierte a minúsculas y conserva letras/apóstrofos/guiones.
    Devuelve una cadena “limpia” apta para conteo y TF-IDF.
    """
    if not isinstance(texto, str):
        texto = "" if texto is None else str(texto)
    tokens = [t.lower() for t in _patron_palabra.findall(texto)]
    return " ".join(tokens)

def asegurar_texto(serie: pd.Series) -> pd.Series:
    """Aplica normalización a una Serie que contiene abstracts."""
    return serie.fillna("").map(normalizar)

# ------------------------------------------
# 1) Frecuencia de términos “semilla”
# ------------------------------------------

def semillas_categoria() -> List[str]:
    """
    Lista de “palabras asociadas” (semillas) para la categoría:
    Concepts of Generative AI in Education.
    """
    semillas = [
        "generative models",
        "prompting",
        "machine learning",
        "multimodality",
        "fine-tuning",
        "training data",
        "algorithmic bias",
        "explainability",
        "transparency",
        "ethics",
        "privacy",
        "personalization",
        "human-ai interaction",
        "ai literacy",
        "co-creation",
    ]
    # las devolvemos ya normalizadas para hacer matching consistente
    return [normalizar(s) for s in semillas]

def frecuencias_semillas(abstracts: List[str], semillas_norm: List[str]) -> pd.DataFrame:
    """
    Calcula cuántas veces aparece cada semilla en el corpus:
      - total_count: ocurrencias totales en todos los abstracts
      - doc_freq: número de abstracts que la contienen al menos una vez
      - rel_freq: ocurrencias por abstract = total_count / N
    Coincidimos tanto unigramas como frases (bigramas) con borde de palabra aproximado.
    """
    abstracts_norm = [normalizar(t) for t in abstracts]
    corpus_unido = "\n".join(abstracts_norm)

    filas = []
    for termino in semillas_norm:
        # Borde aproximado para evitar falsos positivos (inicio/fin o espacio)
        patron = r"(?<![A-Za-z])" + re.escape(termino) + r"(?![A-Za-z])"

        total = len(re.findall(patron, corpus_unido))
        docs = sum(1 for t in abstracts_norm if re.search(patron, t))

        filas.append({
            "termino": termino,
            "total_count": int(total),
            "doc_freq": int(docs),
            "rel_freq": float(total / max(1, len(abstracts_norm))),
        })

    df = (
        pd.DataFrame(filas)
        .sort_values(by=["total_count", "doc_freq"], ascending=False)
        .reset_index(drop=True)
    )
    return df

# ---------------------------------------------------------
# 2) Descubrimiento de nuevos términos (≤ 15) con TF-IDF
# ---------------------------------------------------------

def descubrir_nuevos_terminos(abstracts: List[str], max_terminos: int = 15) -> pd.DataFrame:
    """
    Aplica TF-IDF (unigramas y bigramas, stopwords inglés, min_df=2) sobre todos los abstracts.
    Retorna los “max_terminos” más característicos con:
      - termino
      - score_tfidf (suma TF-IDF en el corpus)
      - doc_freq (en cuántos abstracts aparece)
    """
    vectorizador = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
    )
    X = vectorizador.fit_transform([normalizar(t) for t in abstracts])
    vocab = np.array(vectorizador.get_feature_names_out())

    # Suma global TF-IDF por término y su frecuencia documental
    puntuacion = np.asarray(X.sum(axis=0)).ravel()
    df_docs = np.asarray((X > 0).sum(axis=0)).ravel()

    df = (
        pd.DataFrame({
            "termino": vocab,
            "score_tfidf": puntuacion,
            "doc_freq": df_docs,
        })
        .sort_values(by=["score_tfidf", "doc_freq"], ascending=False)
        .head(max_terminos)
        .reset_index(drop=True)
    )
    return df

# -------------------------------------------------------------------
# 3) Evaluación de precisión de nuevos términos (embeddings/coseno)
# -------------------------------------------------------------------

_modelos_cache = {}

def _modelo(name: str):
    if not _HAY_ST:
        raise RuntimeError("No está instalada la librería 'sentence-transformers'.")
    if name not in _modelos_cache:
        _modelos_cache[name] = SentenceTransformer(name)
    return _modelos_cache[name]

def evaluar_precision_embeddings(
    nuevos_terminos: List[str],
    semillas_norm: List[str],
    nombre_modelo: str = "all-MiniLM-L6-v2",
    umbral: float = 0.50,
) -> pd.DataFrame:
    """
    Calcula la similitud coseno entre cada término nuevo y el centro semántico de las semillas.
    Devuelve:
      - termino
      - sim_a_semillas (similaridad coseno)
      - precisa ("sí"/"no") según umbral
    Si no hay embeddings, devuelve N/D pero el flujo continúa.
    """
    if not _HAY_ST:
        return pd.DataFrame({
            "termino": nuevos_terminos,
            "sim_a_semillas": [float("nan")] * len(nuevos_terminos),
            "precisa": ["N/D"] * len(nuevos_terminos),
        })

    modelo = _modelo(nombre_modelo)
    vec_semillas = modelo.encode(semillas_norm, normalize_embeddings=True)
    centro = np.mean(vec_semillas, axis=0)

    vec_candidatos = modelo.encode(nuevos_terminos, normalize_embeddings=True)
    # Coseno = producto punto porque están normalizados
    similitudes = (vec_candidatos * centro).sum(axis=1)

    return pd.DataFrame({
        "termino": nuevos_terminos,
        "sim_a_semillas": similitudes.astype(float),
        "precisa": ["sí" if s >= umbral else "no" for s in similitudes],
    })

# ---------------------------------------
# 4) Gráficos de barras (matplotlib)
# ---------------------------------------

def guardar_barras(df: pd.DataFrame, col_x: str, col_y: str, titulo: str, ruta_salida: str):
    """
    Dibuja y guarda un gráfico de barras simple (sin estilos ni colores especiales).
    """
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(10, 5))
    ax = plt.gca()
    ax.bar(df[col_x], df[col_y])
    ax.set_title(titulo)
    ax.set_ylabel(col_y)
    ax.set_xticklabels(df[col_x], rotation=45, ha="right")
    fig.tight_layout()
    fig.savefig(ruta_salida, dpi=160)
    plt.close(fig)
