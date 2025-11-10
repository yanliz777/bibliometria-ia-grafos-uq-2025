# req3_frecuencia_terminos.py
# -----------------------------------------------------------------------------------------
# Requerimiento 3 —
# -----------------------------------------------------------------------------------------
# Objetivo general:
#   Analizar la frecuencia y la relevancia semántica de las palabras asociadas
#   a la categoría “Concepts of Generative AI in Education” dentro de los
#   abstracts del dataset unificado.
#
# Fases del requerimiento:
#   1. Leer el CSV unificado con abstracts normalizados.
#   2. Calcular la frecuencia absoluta y relativa de las palabras semilla.
#   3. Descubrir hasta 15 nuevos términos relevantes mediante TF-IDF.
#   4. Evaluar la precisión semántica de esos términos usando embeddings (IA).
#   5. Exportar resultados (CSV y PNG) y mostrar interpretación en consola.
#
# Resultados esperados:
#   • req3_frecuencias_semillas.csv / .png — frecuencia de palabras base.
#   • req3_nuevos_terminos.csv / .png — nuevos términos con TF-IDF y similitud.
#   • Salida en consola explicando interpretación de métricas.
#
# Documentación requerida:
#   - Cada función tiene docstring detallado.
#   - Se incluye descripción de cómo leer resultados.
#   - Compatible con pipelines de análisis reproducible.
# -----------------------------------------------------------------------------------------

import os
import pandas as pd

# -----------------------------------------------------------------------------------------
# Configuración de rutas y parámetros globales
# -----------------------------------------------------------------------------------------

RUTA_CSV_UNIFICADO = "/home/ycmejia/Escritorio/PROYECTO ALGORITMOS/salidas/unificado_ai_generativa.csv"
DIR_SALIDAS = "/home/ycmejia/Escritorio/PROYECTO ALGORITMOS/salidas"
DIR_VISUAL= "/home/ycmejia/Escritorio/Grafos/bibliometria-ia-grafos-uq-2025/utils"

# Parámetros de embeddings (IA opcional)
USAR_IA = True
MODELO_EMB = "all-MiniLM-L6-v2"
UMBRAL_PRECISION = 0.50

from utils.analisis_frecuencias_es import (
    normalizar,
    asegurar_texto,
    semillas_categoria,
    frecuencias_semillas,
    descubrir_nuevos_terminos,
    evaluar_precision_embeddings,
    guardar_barras,
)

# -----------------------------------------------------------------------------------------
# Función: leer_dataset
# -----------------------------------------------------------------------------------------
def leer_dataset(ruta: str) -> pd.DataFrame:
    """
    Lee el archivo CSV unificado y asegura que contenga una columna 'abstract' válida.

    Pasos:
      1. Verifica la existencia del archivo en la ruta especificada.
      2. Intenta ubicar la columna 'abstract' o una variante (mayúsculas, espacios).
      3. Si falta el abstract, utiliza 'title' como respaldo mínimo.
      4. Normaliza los textos (minúsculas, sin tildes ni caracteres especiales).

    Args:
        ruta (str): Ruta absoluta del CSV unificado.

    Returns:
        pd.DataFrame: DataFrame con columna 'abstract' limpia y lista para análisis.

    Raises:
        FileNotFoundError: Si el archivo no existe.
    """
    if not os.path.isfile(ruta):
        raise FileNotFoundError(f"No existe el CSV unificado en: {ruta}")
    df = pd.read_csv(ruta, encoding="utf-8")

    if "abstract" not in df.columns:
        posibles = {c.lower().strip(): c for c in df.columns}
        if "abstract" in posibles:
            df.rename(columns={posibles["abstract"]: "abstract"}, inplace=True)
        else:
            # Si no hay abstract, usa el título como respaldo mínimo
            df["abstract"] = df.get("title", "").fillna("")

    df["abstract"] = asegurar_texto(df["abstract"])
    vacios = df["abstract"].str.len() == 0
    if vacios.any():
        df.loc[vacios, "abstract"] = asegurar_texto(df.loc[vacios, "title"].fillna(""))

    return df


# -----------------------------------------------------------------------------------------
# Función principal: main()
# -----------------------------------------------------------------------------------------
def main():
    """
    Proceso central del Requerimiento 3:
      1. Carga y prepara el dataset.
      2. Calcula la frecuencia de las semillas (palabras base).
      3. Genera nuevos términos mediante TF-IDF.
      4. Evalúa su precisión semántica con embeddings (opcional).
      5. Exporta resultados y presenta interpretación en consola.

    Observaciones:
      - No modifica el CSV original.
      - Las rutas de salida se crean automáticamente si no existen.
      - Si `USAR_IA` es False, los campos de similitud quedan en N/D.
    """
    os.makedirs(DIR_SALIDAS, exist_ok=True)

    # 1️⃣ Lectura del dataset unificado
    df = leer_dataset(RUTA_CSV_UNIFICADO)
    abstracts = df["abstract"].tolist()
    n_docs = len(abstracts)

    # 2️⃣ Frecuencia de semillas base
    semillas = semillas_categoria()
    tabla_semillas = frecuencias_semillas(abstracts, semillas)

    # Guardar CSV y gráfico de frecuencias
    csv_sem = os.path.join(DIR_SALIDAS, "req3_frecuencias_semillas.csv")
    img_sem = os.path.join(DIR_SALIDAS, "req3_frecuencias_semillas.png")
    tabla_semillas.to_csv(csv_sem, index=False, encoding="utf-8-sig")
    guardar_barras(
        tabla_semillas.head(15),
        col_x="termino",
        col_y="total_count",
        titulo="Frecuencia de semillas (Concepts of GenAI in Education)",
        ruta_salida=img_sem,
    )

    # 3️⃣ Descubrimiento de nuevos términos por TF-IDF
    nuevos = descubrir_nuevos_terminos(abstracts, max_terminos=15)

    # 4️⃣ Evaluación de precisión semántica (embeddings)
    if USAR_IA:
        evaluados = evaluar_precision_embeddings(
            nuevos["termino"].tolist(),
            semillas,
            nombre_modelo=MODELO_EMB,
            umbral=UMBRAL_PRECISION,
        )
        nuevos = nuevos.merge(evaluados, on="termino", how="left")
    else:
        nuevos["sim_a_semillas"] = float("nan")
        nuevos["precisa"] = "N/D"

    # Guardar CSV y gráfico de nuevos términos
    csv_new = os.path.join(DIR_SALIDAS, "req3_nuevos_terminos.csv")
    img_new = os.path.join(DIR_SALIDAS, "req3_nuevos_terminos.png")
    nuevos.to_csv(csv_new, index=False, encoding="utf-8-sig")
    guardar_barras(
        nuevos.sort_values("score_tfidf", ascending=False),
        col_x="termino",
        col_y="score_tfidf",
        titulo="Nuevos términos (TF-IDF)",
        ruta_salida=img_new,
    )

    # 5️⃣ Salida explicativa (consola)
    print("\n# Requerimiento 3 — Salida explicativa")
    print("Objetivo: contar la frecuencia de las palabras asociadas (semillas) en los ABSTRACTS,")
    print("descubrir hasta 15 nuevos términos característicos del corpus y evaluar su precisión semántica.\n")

    print(f"Corpus: {n_docs} abstracts analizados.")
    print("\n1) Frecuencia de semillas (Top 10 por total_count):")
    for _, r in tabla_semillas.head(10).iterrows():
        print(f" - {r['termino']}: total={int(r['total_count'])}, docs={int(r['doc_freq'])}, rel/abs={r['rel_freq']:.3f}")

    print("\n2) Nuevos términos (TF-IDF) y precisión:")
    if "sim_a_semillas" in nuevos.columns:
        for _, r in nuevos.iterrows():
            sim = "N/D" if pd.isna(r.get("sim_a_semillas", float("nan"))) else f"{float(r['sim_a_semillas']):.3f}"
            print(f" - {r['termino']}: tfidf={r['score_tfidf']:.3f}, docs={int(r['doc_freq'])}, sim→semillas={sim}, precisa={r.get('precisa','N/D')}")
        if (nuevos["precisa"].isin(["sí", "no"]).any()):
            precision_global = (nuevos["precisa"] == "sí").mean() * 100
            print(f"\nPrecisión global (similitud ≥ {UMBRAL_PRECISION:.2f}): {precision_global:.1f}%")
    else:
        for _, r in nuevos.iterrows():
            print(f" - {r['termino']}: tfidf={r['score_tfidf']:.3f}, docs={int(r['doc_freq'])}")

    print("\nArchivos generados:")
    print(f" • CSV frecuencias semillas: {csv_sem}")
    print(f" • CSV nuevos términos:      {csv_new}")
    print(f" • PNG frecuencias semillas: {img_sem}")
    print(f" • PNG nuevos términos:      {img_new}")
    print("\nCómo leer:")
    print(" - total_count: veces que la semilla aparece en todos los abstracts.")
    print(" - doc_freq: en cuántos abstracts aparece.")
    print(" - score_tfidf: importancia/peso del término en el corpus.")
    print(" - sim→semillas: cercanía semántica del término a la categoría; “precisa” = 'sí' si supera el umbral.")


# -----------------------------------------------------------------------------------------
# Ejecución directa
# -----------------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
