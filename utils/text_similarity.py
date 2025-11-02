# utils/text_similarity.py
# ----------------------------------------------
# 4 ALGORITMOS CLÁSICOS + 2 CON IA (embeddings)
# Cada función devuelve un float en [0, 1].
# Comentarios explican la matemática/algoritmo paso a paso.
# ----------------------------------------------

import math
import re
from typing import List, Tuple
from functools import lru_cache

# Para Coseno TF-IDF
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Para Embeddings con IA (Sentence Transformers)
# Si no tienes instalada la librería, ver instrucciones en el main.
try:
    from sentence_transformers import SentenceTransformer
    _HAS_ST = True
except Exception:
    _HAS_ST = False

_word_re = re.compile(r"\w+", re.UNICODE)

def _tokenize_words(text: str) -> List[str]:
    """Tokeniza a palabras alfanuméricas en minúscula."""
    return [t.lower() for t in _word_re.findall(text or "")]

def _ngrams(words: List[str], n: int = 2) -> List[Tuple[str, ...]]:
    """Genera n-gramas contiguos de longitud n a partir de una lista de palabras."""
    if n <= 0:
        return []
    return [tuple(words[i:i+n]) for i in range(0, max(0, len(words)-n+1))]

# -----------------------------
# 1) Levenshtein → Similitud
# -----------------------------
def levenshtein_similarity(a: str, b: str) -> float:
    """
    Distancia de edición clásica (Levenshtein) y luego normaliza a similitud.
    - dp[i][j] = costo mínimo de convertir a[:i] -> b[:j]
    - operaciones: inserción, eliminación, sustitución (costo 1)
    similitud = 1 - distancia / max(len(a), len(b))
    """
    a = a or ""
    b = b or ""
    if a == b:
        return 1.0
    if not a or not b:
        # todo contra vacío => distancia = longitud del no vacío
        dist = max(len(a), len(b))
        return 1.0 - (dist / max(1, dist))

    # DP iterativa O(len(a)*len(b))
    la, lb = len(a), len(b)
    dp = [[0]*(lb+1) for _ in range(la+1)]

    for i in range(la+1):
        dp[i][0] = i
    for j in range(lb+1):
        dp[0][j] = j

    for i in range(1, la+1):
        ca = a[i-1]
        for j in range(1, lb+1):
            cb = b[j-1]
            cost_sub = 0 if ca == cb else 1
            dp[i][j] = min(
                dp[i-1][j] + 1,        # borrar
                dp[i][j-1] + 1,        # insertar
                dp[i-1][j-1] + cost_sub  # sustituir (0 si iguales)
            )

    dist = dp[la][lb]
    denom = max(la, lb)
    return 1.0 - (dist / denom)

# -----------------------------
# 2) Jaccard (n-gramas de palabras)
# -----------------------------
def jaccard_similarity(a: str, b: str, n: int = 2) -> float:
    """
    Jaccard sobre conjuntos de n-gramas (por defecto, bigramas).
    J(A,B) = |A ∩ B| / |A ∪ B|
    """
    A = set(_ngrams(_tokenize_words(a), n))
    B = set(_ngrams(_tokenize_words(b), n))
    if not A and not B:
        return 1.0
    inter = len(A & B)
    union = len(A | B)
    return inter / union if union else 0.0

# -----------------------------
# 3) Sørensen–Dice (n-gramas)
# -----------------------------
def dice_similarity(a: str, b: str, n: int = 2) -> float:
    """
    Dice sobre n-gramas:
    Dice = 2|A ∩ B| / (|A| + |B|)
    """
    A = set(_ngrams(_tokenize_words(a), n))
    B = set(_ngrams(_tokenize_words(b), n))
    if not A and not B:
        return 1.0
    num = 2 * len(A & B)
    den = len(A) + len(B)
    return num / den if den else 0.0

# -----------------------------
# 4) Coseno con TF-IDF
# -----------------------------
@lru_cache(maxsize=128)
def _cosine_tfidf_pair(a: str, b: str) -> float:
    """
    Construye un TF-IDF para los dos textos y calcula coseno.
    Se cachea por performance.
    """
    vect = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_df=1.0)  # unigrams+bigramas
    X = vect.fit_transform([a or "", b or ""])
    sim = cosine_similarity(X[0], X[1])[0, 0]
    # Coseno ya está en [0,1] si no hay negativos
    return float(sim)

def cosine_tfidf_similarity(a: str, b: str) -> float:
    return _cosine_tfidf_pair(a or "", b or "")

# -----------------------------
# 5-6) IA con Sentence Transformers
# -----------------------------
# Carga perezosa para no pagar tiempo de arranque si no se usa.
_MODELS = {}

def _get_model(name: str):
    if not _HAS_ST:
        raise RuntimeError(
            "La librería 'sentence-transformers' no está instalada. "
            "Instala con: pip install sentence-transformers"
        )
    if name not in _MODELS:
        _MODELS[name] = SentenceTransformer(name)
    return _MODELS[name]

def embedding_cosine_similarity(a: str, b: str, model_name: str) -> float:
    """
    Genera embeddings con un modelo y calcula coseno.
    Recomendados:
      - 'all-MiniLM-L6-v2' (inglés)
      - 'paraphrase-multilingual-MiniLM-L12-v2' (multilingüe)
    """
    model = _get_model(model_name)
    reps = model.encode([a or "", b or ""], normalize_embeddings=True)
    # Con normalize=True, el coseno = dot product
    v1, v2 = reps[0], reps[1]
    # producto punto
    return float((v1 * v2).sum())
