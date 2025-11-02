# main_cluster.py
# ======================================================================================
# Orquesta el Requerimiento 4 sobre tu CSV unificado:
#  1) Carga abstracts
#  2) TF-IDF (unigramas+bigramas, stopwords en inglés por defecto)
#  3) Similitud coseno y DISTANCIA (1 - coseno)
#  4) Agrupamiento jerárquico: single, complete, average  (Ward opcional)
#  5) Dendrogramas PNG + métricas (silhouette y cophenetic)
#  6) Selecciona el método "más coherente" (mejor silhouette) y exporta asignaciones
#
# Salida en consola: explicación clara del objetivo y lectura de resultados.
# Artefactos:
#   • salidas/dendrograma_<metodo>.png
#   • salidas/req4_metricas.csv  +  salidas/req4_metricas_<metodo>.json
#   • salidas/req4_asignaciones_<metodo>.csv   (para el mejor método)
# ======================================================================================

import os
import pandas as pd
import numpy as np
import json
from scipy.cluster.hierarchy import fcluster

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

# ---------- CONFIGURA RUTAS AQUÍ ----------
RUTA_CSV_UNIFICADO = r"C:\Users\USER\Desktop\proyecto-final-algoritmos\salidas\unificado_ai_generativa.csv"
OUT_DIR = r"C:\Users\USER\Desktop\proyecto-final-algoritmos\salidas"

# ¿Incluir Ward? (usa distancia euclídea sobre TF-IDF)
INCLUIR_WARD = True

def _abreviar(t: str, n=60) -> str:
    t = str(t or "")
    return (t[:n] + "…") if len(t) > n else t

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("\n# Requerimiento 4 — Agrupamiento jerárquico con dendrogramas")
    print("Objetivo: representar la SIMILITUD entre abstracts y observar cómo se fusionan en grupos")
    print("mediante un árbol (dendrograma). Se compara la coherencia de tres variantes de enlace.\n")

    # 1) Cargar
    df = cargar_abstracts(RUTA_CSV_UNIFICADO)
    abstracts = df["abstract"].astype(str).tolist()
    titulos = df["title"].astype(str).tolist() if "title" in df.columns else [f"doc_{i}" for i in range(len(df))]

    print(f"Corpus cargado: {len(abstracts)} abstracts.\n")

    # 2) TF-IDF (minúsculas, stopwords, unigrams+bigramas + L2-normalizado)
    X, vec = vectorizar_tfidf(abstracts, idioma_stopwords="english", usar_bigramas=True)

    # (Pedagógico) Mostrar el coseno "a mano" entre los dos primeros documentos
    if X.shape[0] >= 2:
        cos_demo = coseno_manual_para_dos(X, 0, 1)
        print("Demostración (producto punto de TF-IDF normalizado = coseno):")
        print(f"• cos(abstract_0, abstract_1) = {cos_demo:.4f}\n")

    # 3) Similitud coseno y DISTANCIA
    S = matriz_similitud_coseno(X)              # SIMILITUD = X * X^T (multiplicación matricial)
    D = matriz_distancia_desde_similitud(S)     # DISTANCIA = 1 - S

    # 4) Clustering (3 variantes mínimas). Ward opcional.
    metodos = ["single", "complete", "average"]
    if INCLUIR_WARD:
        metodos.append("ward")

    resultados = clustering_jerarquico(D, X_euclideo=X, linkages=metodos)

    # 5) Dendrogramas por método
    etiquetas = [_abreviar(t, 35) for t in titulos]
    for metodo, info in resultados.items():
        ruta_png = os.path.join(OUT_DIR, f"dendrograma_{metodo}.png")
        titulo = f"Dendrograma ({metodo}) — distancia: {info['usa']}"
        guardar_dendrograma(info["Z"], etiquetas, ruta_png, titulo)
        print(f"✓ Dendrograma guardado: {ruta_png}")

    # 6) Métricas de coherencia (silhouette y cophenetic)
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

        # Seleccionar mejor por silhouette
        sm = m.get("silhouette_mejor")
        if sm is not None and sm > mejor["silhouette_mejor"]:
            mejor.update({"metodo": metodo, "silhouette_mejor": sm, "k_mejor": m["k_mejor"]})

        # Guardar JSON detallado por método (trazabilidad)
        ruta_json = os.path.join(OUT_DIR, f"req4_metricas_{metodo}.json")
        with open(ruta_json, "w", encoding="utf-8") as f:
            json.dump(m, f, ensure_ascii=False, indent=2)

    # Guardar CSV resumen de métricas
    df_metricas = pd.DataFrame(filas_metricas)
    ruta_metricas_csv = os.path.join(OUT_DIR, "req4_metricas.csv")
    df_metricas.to_csv(ruta_metricas_csv, index=False, encoding="utf-8-sig")

    # 7) Asignaciones de cluster usando el “mejor” método
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

    # 8) Salida explicativa en consola
    print("\n# Lectura de resultados (Requerimiento 4)")
    print("• Cada dendrograma muestra cómo los abstracts se van uniendo desde los más similares")
    print("  (distancia baja) hasta formar un solo grupo (altura mayor).")
    print("• Comparamos variantes de enlace: single (encadena), complete (grupos compactos),")
    print("  average (promedio; término medio estable) y Ward (minimiza varianza con euclídea).")
    print("\n# Métricas (coherencia)")
    print(df_metricas.to_string(index=False))
    if mejor["metodo"] is not None:
        print(f"\n► Método más coherente (silhouette): {mejor['metodo']}  |  "
              f"silhouette={mejor['silhouette_mejor']:.3f}  |  k={mejor['k_mejor']}")
        if ruta_asig:
            print(f"   • Asignaciones guardadas en: {ruta_asig}")
    print(f"\nArtefactos generados:")
    for metodo in metodos:
        print(f"  • Dendrograma: {os.path.join(OUT_DIR, f'dendrograma_{metodo}.png')}")
        print(f"  • Métricas JSON: {os.path.join(OUT_DIR, f'req4_metricas_{metodo}.json')}")
    print(f"  • Resumen métricas CSV: {ruta_metricas_csv}")

    print("\nCómo usar el dendrograma:")
    print("  - Si 'cortas' horizontalmente a una altura, obtienes k clusters.")
    print("  - A alturas bajas: muchos grupos MUY similares.")
    print("  - A alturas altas: pocos grupos más diversos.")
    print("\nInterpretación rápida:")
    print("  - Revisa si los títulos dentro de un mismo cluster comparten tema (p. ej., ética/privacidad,")
    print("    prompting en educación, evaluación de aprendizajes con GenAI). Ese juicio cualitativo +")
    print("    las métricas (silhouette/cofenética) sustenta qué método agrupa más coherentemente.\n")

if __name__ == "__main__":
    main()
