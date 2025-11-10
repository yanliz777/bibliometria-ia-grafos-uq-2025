# ======================================================================================
# req4_cluster.py
# ======================================================================================
# Requerimiento 4 — Agrupamiento jerárquico de textos (clustering)
#
# Descripción general:
# Este módulo orquesta el proceso de análisis jerárquico sobre el conjunto de abstracts
# unificado. A partir del corpus, genera representaciones TF-IDF, calcula similitudes,
# ejecuta diferentes variantes de enlace jerárquico (single, complete, average y ward),
# y evalúa la coherencia de los resultados mediante métricas cuantitativas.
#
# Flujo general:
#   1) Carga y limpieza del corpus de abstracts
#   2) Vectorización mediante TF-IDF (unigramas + bigramas)
#   3) Cálculo de similitud coseno y matriz de distancia
#   4) Ejecución del clustering jerárquico con distintos métodos
#   5) Generación de dendrogramas (visualización de jerarquías)
#   6) Evaluación de la calidad del agrupamiento (silhouette y cophenetic)
#   7) Selección automática del método más coherente
#   8) Exportación de asignaciones de clusters
#   9) Exportación de clusters de términos (preparación Req. 5)
#
# Salida esperada:
#   • dendrograma_<metodo>.png                → visualización jerárquica
#   • req4_metricas.csv                       → resumen de métricas por método
#   • req4_metricas_<metodo>.json             → detalles de evaluación por método
#   • req4_asignaciones_<metodo>.csv          → asignación de abstracts al cluster más coherente
#   • req4_clusters_terminos.csv              → términos agrupados por cluster (para Req. 5)
#
# Nota:
# La salida en consola explica paso a paso la interpretación de resultados
# y los archivos generados.
# ======================================================================================

import os
import pandas as pd
import numpy as np
import json
from scipy.cluster.hierarchy import fcluster

# --- Importación de funciones utilitarias (módulo utils/cluster_texto) ---
from utils.cluster_texto import (
    cargar_abstracts,
    vectorizar_tfidf,
    matriz_similitud_coseno,
    matriz_distancia_desde_similitud,
    clustering_jerarquico,
    guardar_dendrograma,
    evaluar_metodo,
    coseno_manual_para_dos
)

# --------------------------------------------------------------------------------------
# CONFIGURACIÓN GENERAL
# --------------------------------------------------------------------------------------
RUTA_CSV_UNIFICADO = "/home/ycmejia/Escritorio/PROYECTO ALGORITMOS/salidas/unificado_ai_generativa.csv"
OUT_DIR = "/home/ycmejia/Escritorio/PROYECTO ALGORITMOS/salidas"

# Incluir método Ward (usa distancia euclídea sobre los vectores TF-IDF)
INCLUIR_WARD = True


# --------------------------------------------------------------------------------------
# Función auxiliar: acorta textos largos para los dendrogramas
# --------------------------------------------------------------------------------------
def _abreviar(t: str, n=60) -> str:
    """Trunca un texto a 'n' caracteres, añadiendo puntos suspensivos si excede el límite."""
    t = str(t or "")
    return (t[:n] + "…") if len(t) > n else t


# --------------------------------------------------------------------------------------
# Función principal: orquesta el flujo del Requerimiento 4
# --------------------------------------------------------------------------------------
def main():
    """Ejecución principal del proceso de agrupamiento jerárquico."""
    os.makedirs(OUT_DIR, exist_ok=True)

    print("\n# Requerimiento 4 — Agrupamiento jerárquico con dendrogramas")
    print("Objetivo: representar la SIMILITUD entre abstracts y observar cómo se fusionan en grupos")
    print("mediante un árbol (dendrograma). Se compara la coherencia de tres variantes de enlace.\n")

    # 1️⃣ Carga del corpus
    df = cargar_abstracts(RUTA_CSV_UNIFICADO)
    abstracts = df["abstract"].astype(str).tolist()
    titulos = df["title"].astype(str).tolist() if "title" in df.columns else [f"doc_{i}" for i in range(len(df))]
    print(f"Corpus cargado: {len(abstracts)} abstracts.\n")

    # 2️⃣ Vectorización TF-IDF
    # Incluye unigramas y bigramas, conversión a minúsculas, eliminación de stopwords y normalización L2.
    X, vec = vectorizar_tfidf(abstracts, idioma_stopwords="english", usar_bigramas=True)

    # (Demostración pedagógica)
    # Calcula el coseno manual entre los dos primeros documentos para explicar el concepto de similitud.
    if X.shape[0] >= 2:
        cos_demo = coseno_manual_para_dos(X, 0, 1)
        print("Demostración (producto punto de TF-IDF normalizado = coseno):")
        print(f"• cos(abstract_0, abstract_1) = {cos_demo:.4f}\n")

    # 3️⃣ Cálculo de similitud y distancia
    S = matriz_similitud_coseno(X)
    D = matriz_distancia_desde_similitud(S)

    # 4️⃣ Clustering jerárquico (single, complete, average, ward opcional)
    metodos = ["single", "complete", "average"]
    if INCLUIR_WARD:
        metodos.append("ward")
    resultados = clustering_jerarquico(D, X_euclideo=X, linkages=metodos)

    # 5️⃣ Generación de dendrogramas por método
    etiquetas = [_abreviar(t, 35) for t in titulos]
    for metodo, info in resultados.items():
        ruta_png = os.path.join(OUT_DIR, f"dendrograma_{metodo}.png")
        titulo = f"Dendrograma ({metodo}) — distancia: {info['usa']}"
        guardar_dendrograma(info["Z"], etiquetas, ruta_png, titulo)
        print(f"✓ Dendrograma guardado: {ruta_png}")

    # 6️⃣ Evaluación de la coherencia del agrupamiento
    # Se calculan métricas silhouette y cophenetic para cada método.
    filas_metricas = []
    mejor = {"metodo": None, "silhouette_mejor": -1.0, "k_mejor": None}

    for metodo, info in resultados.items():
        m = evaluar_metodo(metodo, info["Z"], D_cosine=D, ks=list(range(2, 9)))
        filas_metricas.append({
            "metodo": m["metodo"],
            "cophenetic_correlation": m["cophenetic_correlation"],
            "k_mejor": m["k_mejor"],
            "silhouette_mejor": m["silhouette_mejor"]
        })

        sm = m.get("silhouette_mejor")
        if sm is not None and sm > mejor["silhouette_mejor"]:
            mejor.update({"metodo": metodo, "silhouette_mejor": sm, "k_mejor": m["k_mejor"]})

        # Guardar detalle JSON
        ruta_json = os.path.join(OUT_DIR, f"req4_metricas_{metodo}.json")
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)

    # Guardar resumen CSV de métricas
    df_metricas = pd.DataFrame(filas_metricas)
    ruta_metricas_csv = os.path.join(OUT_DIR, "req4_metricas.csv")
    df_metricas.to_csv(ruta_metricas_csv, index=False, encoding="utf-8-sig")

    # 7️⃣ Exportación de asignaciones de clusters (solo para el método más coherente)
    if mejor["metodo"] is not None:
        Z_best = resultados[mejor["metodo"]]["Z"]
        etiquetas_best = fcluster(Z_best, t=mejor["k_mejor"], criterion="maxclust")
        asignaciones = pd.DataFrame({
            "doc_idx": np.arange(len(titulos)),
            "title": titulos,
            "cluster": etiquetas_best
        })
        ruta_asig = os.path.join(OUT_DIR, f"req4_asignaciones_{mejor['metodo']}.csv")
        asignaciones.to_csv(ruta_asig, index=False, encoding="utf-8-sig")
    else:
        ruta_asig = None

    # 8️⃣ Exportar clusters de términos (preparación Req. 5)
    if ruta_asig:
        print("\nAsignando clusters a términos (para grafo de coocurrencia)...")
        df_asig = pd.read_csv(ruta_asig)
        ruta_clusters_terminos = os.path.join(OUT_DIR, "req4_clusters_terminos.csv")
        exportar_clusters_a_terminos(df_asig, RUTA_CSV_UNIFICADO, ruta_clusters_terminos)

    # 9️⃣ Resumen y guía de interpretación en consola
    print("\n# Lectura de resultados (Requerimiento 4)")
    print(df_metricas.to_string(index=False))
    if mejor["metodo"] is not None:
        print(f"\n► Método más coherente (silhouette): {mejor['metodo']}  |  "
              f"silhouette={mejor['silhouette_mejor']:.3f}  |  k={mejor['k_mejor']}")
        if ruta_asig:
            print(f"   • Asignaciones guardadas en: {ruta_asig}")
            print(f"   • Clusters de términos guardados en: {ruta_clusters_terminos}")

    print(f"\nArtefactos generados:")
    for metodo in metodos:
        print(f"  • Dendrograma: {os.path.join(OUT_DIR, f'dendrograma_{metodo}.png')}")
        print(f"  • Métricas JSON: {os.path.join(OUT_DIR, f'req4_metricas_{metodo}.json')}")
    print(f"  • Resumen métricas CSV: {ruta_metricas_csv}")
    print("\n✅ Proceso completado correctamente.")


# --------------------------------------------------------------------------------------
# Función auxiliar: exportar relación término–cluster
# --------------------------------------------------------------------------------------
def exportar_clusters_a_terminos(df_asignaciones, ruta_csv_unificado, ruta_salida):
    """
    Asocia términos del corpus con los clusters obtenidos.
    La asignación se realiza observando en qué documentos aparece cada término
    y asignándolo al cluster más frecuente entre ellos.

    Parámetros:
        df_asignaciones (pd.DataFrame): Asignación de documentos a clusters.
        ruta_csv_unificado (str): Ruta al archivo CSV unificado de abstracts.
        ruta_salida (str): Ruta de salida para guardar el CSV final.

    Salida:
        CSV con columnas: termino, cluster_id
    """
    import re

    df_corpus = pd.read_csv(ruta_csv_unificado)
    if "abstract" not in df_corpus.columns:
        print("⚠ No se encontró columna 'abstract' en el corpus, no se puede mapear términos.")
        return

    abstracts = df_corpus["abstract"].astype(str).tolist()

    # Construye una lista única de unigramas frecuentes (palabras ≥ 4 letras)
    terminos = []
    for txt in abstracts:
        terminos.extend(re.findall(r"\b[a-zA-Z]{4,}\b", txt.lower()))
    terminos = list(set(terminos))

    # Mapea cada término al cluster dominante
    term_cluster = {}
    for term in terminos:
        presentes = df_corpus[df_corpus["abstract"].str.contains(term, case=False, na=False)].index.tolist()
        if presentes:
            clusters = df_asignaciones.loc[df_asignaciones["doc_idx"].isin(presentes), "cluster"].tolist()
            if clusters:
                cluster_mas_comun = max(set(clusters), key=clusters.count)
                term_cluster[term] = cluster_mas_comun

    df_out = pd.DataFrame(list(term_cluster.items()), columns=["termino", "cluster_id"])
    df_out.to_csv(ruta_salida, index=False, encoding="utf-8-sig")
    print(f"✓ Clusters de términos exportados a: {ruta_salida}")


# --------------------------------------------------------------------------------------
# Ejecución del script
# --------------------------------------------------------------------------------------
if __name__ == "__main__":
    main()
