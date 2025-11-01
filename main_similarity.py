# main_similarity.py
# ----------------------------------------------------
# Selecciona "dos o más artículos" del CSV unificado,
# extrae el campo abstract y calcula:
#   4 clásicos: Levenshtein, Jaccard, Dice, Coseno TF-IDF
#   2 IA: MiniLM (inglés) y MiniLM multilingüe
# Guarda una tabla de pares con puntajes + reporte legible.
# ----------------------------------------------------

import os
import itertools
import pandas as pd

# Ajusta la ruta a tu CSV unificado:
RUTA_CSV_UNIFICADO = r"C:\Users\USER\Desktop\proyecto-final-algoritmos\salidas\unificado_ai_generativa.csv"

# Carpeta de resultados
OUT_DIR = r"C:\Users\USER\Desktop\proyecto-final-algoritmos\salidas"

# <- AQUÍ "SELECCIONAS" TUS ARTÍCULOS (por índice de fila en el CSV).
#    Deben ser 2 o más. Ejemplos:
#    INDICES_SELECCIONADOS = [0, 1]
#    INDICES_SELECCIONADOS = [2, 5, 7]
INDICES_SELECCIONADOS = [0, 1, 2]

# Modelos de IA (puedes desactivar si no tienes la librería instalada)
USE_AI = True
AI_MODELS = [
    ("st_en", "all-MiniLM-L6-v2"),                         # inglés
    ("st_multi", "paraphrase-multilingual-MiniLM-L12-v2")  # multilingüe
]

from utils.text_similarity import (
    levenshtein_similarity,
    jaccard_similarity,
    dice_similarity,
    cosine_tfidf_similarity,
    embedding_cosine_similarity
)

def _leer_dataset(ruta: str) -> pd.DataFrame:
    """Lee el CSV y garantiza que exista la columna 'abstract'."""
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"No existe el CSV unificado en: {ruta}")
    df = pd.read_csv(ruta, encoding="utf-8")
    if "abstract" not in df.columns:
        # Intento simple de normalización por si viene con mayúsculas/espacios
        m = {c.lower().strip(): c for c in df.columns}
        if "abstract" in m:
            df.rename(columns={m["abstract"]: "abstract"}, inplace=True)
        else:
            raise ValueError("El CSV no tiene columna 'abstract'.")
    return df

def _tomar_texto(df: pd.DataFrame, idx: int) -> str:
    """Devuelve abstract; si está vacío, usa title como respaldo."""
    row = df.iloc[idx]
    abs_txt = str(row.get("abstract", "") or "")
    if not abs_txt.strip():
        abs_txt = str(row.get("title", "") or "")
    return abs_txt

def _pairwise_indices(indices):
    """Genera todas las combinaciones de pares (i,j) con i<j."""
    return list(itertools.combinations(indices, 2))

def _interpretar(score: float) -> str:
    """Regla simple de interpretación para mostrar al usuario."""
    if score is None:
        return "N/D"
    if score >= 0.70: return "muy alta"
    if score >= 0.40: return "moderada"
    if score >= 0.10: return "baja"
    return "muy baja"

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    # 1) Leer data
    df = _leer_dataset(RUTA_CSV_UNIFICADO)

    # 2) Validar selección (≥2)
    if len(INDICES_SELECCIONADOS) < 2:
        raise ValueError("Debes seleccionar al menos DOS artículos en INDICES_SELECCIONADOS.")

    # 3) Construir pares
    pares = _pairwise_indices(INDICES_SELECCIONADOS)

    # 4) Calcular similitudes por par y por algoritmo
    rows = []
    for (i, j) in pares:
        ta = _tomar_texto(df, i)
        tb = _tomar_texto(df, j)

        # --- 4 clásicos ---
        sim_lev = levenshtein_similarity(ta, tb)
        sim_jac = jaccard_similarity(ta, tb, n=2)   # bigramas
        sim_dic = dice_similarity(ta, tb, n=2)      # bigramas
        sim_tfi = cosine_tfidf_similarity(ta, tb)

        row = {
            "i": i,
            "j": j,
            "title_i": str(df.iloc[i].get("title", ""))[:120],
            "title_j": str(df.iloc[j].get("title", ""))[:120],
            "levenshtein": round(sim_lev, 4),
            "jaccard_bi": round(sim_jac, 4),
            "dice_bi": round(sim_dic, 4),
            "cosine_tfidf": round(sim_tfi, 4),
        }

        # --- 2 con IA (opcional) ---
        if USE_AI:
            st_values = {}
            try:
                for tag, model_name in AI_MODELS:
                    sim_ai = embedding_cosine_similarity(ta, tb, model_name=model_name)
                    st_values[tag] = round(float(sim_ai), 4)
            except RuntimeError as e:
                # Si no está instalada la librería, marcamos como None
                st_values = {"st_en": None, "st_multi": None}
                print(f" IA no disponible: {e}")
            row.update(st_values)

        rows.append(row)

    # 5) DataFrame de resultados
    out = pd.DataFrame(rows)

    # 6) Guardar CSV principal
    out_file = os.path.join(OUT_DIR, "similitud_pairs.csv")
    out.to_csv(out_file, index=False, encoding="utf-8-sig")

    # ====== SALIDA PEDAGÓGICA (en consola + README.md) ======
    print("\n# Resumen legible (cómo leer los números)")
    print("• Escala de 0 a 1 (↑ es más similar). Umbrales: ≥0.70 muy alta, 0.40–0.69 moderada, 0.10–0.39 baja, <0.10 muy baja.")
    print("• Métricas: levenshtein (caracteres), jaccard_bi/dice_bi (bigramas), cosine_tfidf (vocabulario), st_en/st_multi (IA).")

    # Elegir métrica para ordenar: si hay columna st_en la usamos; si no, TF-IDF.
    sort_metric = "st_en" if "st_en" in out.columns else "cosine_tfidf"
    df_view = out.sort_values(by=sort_metric, ascending=False).reset_index(drop=True)

    top_n = min(10, len(df_view))
    titulo_metric = "IA - inglés (st_en)" if sort_metric == "st_en" else "TF-IDF (cosine_tfidf)"
    print(f"\nTop {top_n} pares por similitud ({titulo_metric}):")
    for k in range(top_n):
        row = df_view.iloc[k]
        st_ref = row.get("st_en", None) if sort_metric == "st_en" else row.get("cosine_tfidf", 0.0)
        exp = _interpretar(float(st_ref) if st_ref is not None else None)
        t_i = (str(row['title_i'])[:60] + "…") if len(str(row['title_i'])) > 65 else str(row['title_i'])
        t_j = (str(row['title_j'])[:60] + "…") if len(str(row['title_j'])) > 65 else str(row['title_j'])
        print(f"- ({int(row['i'])}, {int(row['j'])}) {sort_metric}={st_ref if st_ref is not None else 'N/D'} → {exp} | TF-IDF={row['cosine_tfidf']:.3f}")
        print(f"    · {t_i}")
        print(f"    · {t_j}")

    # README en Markdown con explicación + top pares
    md_path = os.path.join(OUT_DIR, "similitud_pairs_README.md")

    def _fila_md(r) -> str:
        def _fmt(x):
            return "N/D" if x is None else f"{x:.3f}"
        return (
            f"| {int(r['i'])} | {int(r['j'])} | "
            f"{_fmt(r['levenshtein'])} | {_fmt(r['jaccard_bi'])} | {_fmt(r['dice_bi'])} | {_fmt(r['cosine_tfidf'])} | "
            f"{_fmt(r.get('st_en', None))} | {_fmt(r.get('st_multi', None))} | "
            f"{_interpretar(r.get('st_en', None) if sort_metric=='st_en' else r['cosine_tfidf'])} |"
        )

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Informe de similitud textual (Requerimiento 2)\n\n")
        f.write("**Objetivo:** Dada una selección de 2+ artículos, se extrae su *abstract* (o *title* si falta) y se mide la similitud por 6 algoritmos:\n")
        f.write("- 4 clásicos: **Levenshtein**, **Jaccard (bigramas)**, **Dice (bigramas)**, **Coseno (TF-IDF)**.\n")
        f.write("- 2 con IA: **Sentence-BERT all-MiniLM-L6-v2** (st_en) y **paraphrase-multilingual-MiniLM-L12-v2** (st_multi).\n\n")
        f.write("**Lectura de valores:** escala 0–1 (↑ es más similar). Umbrales: ≥0.70 muy alta, 0.40–0.69 moderada, 0.10–0.39 baja, <0.10 muy baja.\n\n")

        f.write(f"## Top {top_n} pares por similitud ({titulo_metric})\n\n")
        f.write("| i | j | lev | jac | dice | tfidf | st_en | st_multi | interpretación |\n")
        f.write("|---:|---:|---:|---:|---:|---:|---:|---:|---|\n")
        for k in range(top_n):
            f.write(_fila_md(df_view.iloc[k]) + "\n")

        f.write("\n## Ejemplos explicados\n")
        for k in range(min(3, top_n)):  # explica los 3 primeros
            r = df_view.iloc[k]
            st_ref = r.get("st_en", None) if sort_metric == "st_en" else r.get("cosine_tfidf", 0.0)
            exp = _interpretar(float(st_ref) if st_ref is not None else None)
            f.write(f"- **Par ({int(r['i'])}, {int(r['j'])})** — interpretación *{exp}* por **{titulo_metric}**.\n")
            f.write(f"  - **Título A:** {r['title_i']}\n")
            f.write(f"  - **Título B:** {r['title_j']}\n")
            f.write(f"  - *Apoyo clásico:* TF-IDF={r['cosine_tfidf']:.3f}, Jaccard={r['jaccard_bi']:.3f}, Dice={r['dice_bi']:.3f}, Levenshtein={r['levenshtein']:.3f}.\n")

    # 7) Mostrar resumen final (consola limpia)
    print(f"\n Reporte claro generado: {md_path}")
    print(f" Listo. Pares analizados: {len(pares)}")
    print(f"➡ Resultados guardados en: {out_file}")

    # Vista compacta y legible (sin cortar columnas)
    with pd.option_context("display.max_colwidth", 80, "display.width", 120):
        cols = ["i","j","title_i","title_j","levenshtein","jaccard_bi","dice_bi","cosine_tfidf"]
        if "st_en" in out.columns: cols.append("st_en")
        if "st_multi" in out.columns: cols.append("st_multi")
        print("\nVista rápida de resultados:")
        print(out[cols].to_string(index=False))

if __name__ == "__main__":
    main()
