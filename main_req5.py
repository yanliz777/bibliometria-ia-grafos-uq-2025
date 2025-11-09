# main_req5.py
# ======================================================================================
# Orquesta el Requerimiento 5:
#   (1) Mapa de calor por país del primer autor
#   (2) Nube de palabras dinámica (abstracts + keywords)
#   (3) Línea temporal por año y por revista (stacked area)
#   (4) Exporta los tres gráficos a un PDF
#
# Mantiene la salida en consola que ya te funcionaba y añade paths de los
# nuevos artefactos (CSV/JSON de verificación).
# ======================================================================================

import os
import pandas as pd

from utils.viz_req5 import (
    leer_dataset,
    contar_por_pais_primer_autor,
    graficar_mapa_calor_paises,
    generar_nube_palabras,
    preparar_timeline_por_revista,
    graficar_timeline_stacked_area,
    exportar_imagenes_a_pdf,
)

# ==== CONFIGURA AQUÍ ====
RUTA_CSV_UNIFICADO = "/home/ycmejia/Escritorio/PROYECTO ALGORITMOS/salidas/unificado_ai_generativa.csv"
OUT_DIR = "/home/ycmejia/Escritorio/PROYECTO ALGORITMOS/salidas"
N_TOP_REVISTAS = 8
# ========================

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("\n# Requerimiento 5 — Análisis visual de la producción científica")
    print("Objetivo: (1) mapa de calor por país del primer autor, "
          "(2) nube de palabras dinámica (abstracts+keywords), "
          "(3) línea temporal por año y revista; y exportar todo a PDF.\n")

    # 1) Cargar datos
    df = leer_dataset(RUTA_CSV_UNIFICADO)
    print(f"• CSV cargado con {len(df)} registros.")

    # ===== (1) Mapa de calor geográfico =====
    conteo_paises = contar_por_pais_primer_autor(df)
    ruta_mapa = os.path.join(OUT_DIR, "req5_mapa_paises.png")
    graficar_mapa_calor_paises(conteo_paises, ruta_mapa)
    print(f"✓ Mapa de calor por país (primer autor) guardado en: {ruta_mapa}")
    print(f"   (También se guarda req5_paises.csv en la misma carpeta)")

    # ===== (2) Nube de palabras dinámica =====
    ruta_nube = os.path.join(OUT_DIR, "req5_nube_palabras.png")
    freqs = generar_nube_palabras(df, ruta_nube)
    print(f"✓ Nube de palabras (abstracts+keywords) guardada en: {ruta_nube}")
    print("   Artefactos para verificación de dinamismo:")
    print(f"   • req5_top_terminos.csv  • req5_contadores.json")
    top10 = sorted(freqs.items(), key=lambda x: x[1], reverse=True)[:10]
    print("   Top 10 términos (aprox.):")
    for w, c in top10:
        print(f"   - {w}: {c}")

    # ===== (3) Línea temporal por año y revista =====
    ruta_timeline = os.path.join(OUT_DIR, "req5_timeline_revistas.png")
    pivot = preparar_timeline_por_revista(df, top_n_revistas=N_TOP_REVISTAS)
    if pivot.empty:
        print("⚠️ No hay datos suficientes de 'year' para la línea temporal.")
    else:
        graficar_timeline_stacked_area(pivot, ruta_timeline)
        print(f"✓ Línea temporal (stacked area) guardada en: {ruta_timeline}")

    # ===== (4) PDF con los tres gráficos =====
    ruta_pdf = os.path.join(OUT_DIR, "req5_report.pdf")
    exportar_imagenes_a_pdf([ruta_mapa, ruta_nube, ruta_timeline], ruta_pdf)
    print(f"\n📄 PDF consolidado generado en: {ruta_pdf}")

    # ===== Salida explicativa =====
    print("\n# Cómo leer los artefactos")
    print("1) Mapa de calor: países con color más intenso = más publicaciones con PRIMER autor en ese país.")
    print("2) Nube (DINÁMICA): al agregar/eliminar estudios, cambian req5_top_terminos.csv y req5_contadores.json.")
    print("3) Línea temporal: área apilada por AÑO y REVISTA (top + Others) para ver tendencias.")
    print("4) PDF: documento único con las tres figuras para el informe.")

if __name__ == "__main__":
    main()
