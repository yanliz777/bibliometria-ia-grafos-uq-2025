# req5_visualizacion.py
# ======================================================================================
# Orquesta el Requerimiento 5:
#   (1) Mapa de calor por país del primer autor
#   (2) Nube de palabras dinámica (abstracts + keywords)
#   (3) Línea temporal por año y por revista (stacked area)
#   (4) Exporta los tres gráficos a un PDF consolidado
#
# Este script integra los módulos de visualización del proyecto, generando
# artefactos gráficos y métricos que permiten interpretar patrones de producción
# científica en el dataset unificado.
#
# Artefactos generados:
#   • req5_mapa_paises.png           → mapa de calor de publicaciones por país
#   • req5_nube_palabras.png         → nube de términos más frecuentes
#   • req5_timeline_revistas.png     → línea temporal de revistas por año
#   • req5_report.pdf                → reporte final con los tres gráficos
#   • req5_paises.csv, req5_top_terminos.csv, req5_contadores.json → datos de verificación
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

# ==== CONFIGURACIÓN DE ENTRADA Y SALIDA ====
# RUTA_CSV_UNIFICADO : CSV generado en el requerimiento 3 o 4, con abstracts unificados
# OUT_DIR            : Carpeta donde se almacenan los artefactos de salida
# N_TOP_REVISTAS     : Número máximo de revistas que se mostrarán en la gráfica temporal
# ============================================================
RUTA_CSV_UNIFICADO = "/home/ycmejia/Escritorio/PROYECTO ALGORITMOS/salidas/unificado_ai_generativa.csv"
OUT_DIR = "/home/ycmejia/Escritorio/PROYECTO ALGORITMOS/salidas"
N_TOP_REVISTAS = 8
# ============================================================


def main():
    """
    Función principal que orquesta la ejecución completa del Requerimiento 5.
    Realiza las siguientes etapas:
      1. Carga el dataset unificado.
      2. Genera un mapa de calor de publicaciones por país (primer autor).
      3. Construye una nube de palabras basada en abstracts y keywords.
      4. Produce una línea temporal por año y revista (área apilada).
      5. Consolida todos los gráficos en un único reporte PDF.

    Cada etapa produce artefactos gráficos y CSV/JSON de apoyo para verificación.
    """
    # Crear directorio de salida si no existe
    os.makedirs(OUT_DIR, exist_ok=True)

    # --- Introducción descriptiva del proceso ---
    print("\n# Requerimiento 5 — Análisis visual de la producción científica")
    print("Objetivo: (1) mapa de calor por país del primer autor, "
          "(2) nube de palabras dinámica (abstracts+keywords), "
          "(3) línea temporal por año y revista; y exportar todo a PDF.\n")

    # ============================================================
    # (1) Cargar datos desde el CSV unificado
    # ============================================================
    df = leer_dataset(RUTA_CSV_UNIFICADO)
    print(f"• CSV cargado con {len(df)} registros.")

    # ============================================================
    # (2) Generar mapa de calor geográfico
    # ============================================================
    conteo_paises = contar_por_pais_primer_autor(df)
    ruta_mapa = os.path.join(OUT_DIR, "req5_mapa_paises.png")

    # Renderización y guardado del mapa
    graficar_mapa_calor_paises(conteo_paises, ruta_mapa)
    print(f"✓ Mapa de calor por país (primer autor) guardado en: {ruta_mapa}")
    print(f"   (También se guarda req5_paises.csv en la misma carpeta)")

    # ============================================================
    # (3) Generar nube de palabras (abstracts + keywords)
    # ============================================================
    ruta_nube = os.path.join(OUT_DIR, "req5_nube_palabras.png")
    freqs = generar_nube_palabras(df, ruta_nube)

    print(f"✓ Nube de palabras (abstracts+keywords) guardada en: {ruta_nube}")
    print("   Artefactos para verificación de dinamismo:")
    print(f"   • req5_top_terminos.csv  • req5_contadores.json")

    # Mostrar top 10 términos más frecuentes
    top10 = sorted(freqs.items(), key=lambda x: x[1], reverse=True)[:10]
    print("   Top 10 términos (aprox.):")
    for w, c in top10:
        print(f"   - {w}: {c}")

    # ============================================================
    # (4) Línea temporal por año y revista (área apilada)
    # ============================================================
    ruta_timeline = os.path.join(OUT_DIR, "req5_timeline_revistas.png")

    # Preparar los datos agregados (año vs revista)
    pivot = preparar_timeline_por_revista(df, top_n_revistas=N_TOP_REVISTAS)

    if pivot.empty:
        print("⚠️ No hay datos suficientes de 'year' para la línea temporal.")
    else:
        # Generar gráfico de tendencia temporal
        graficar_timeline_stacked_area(pivot, ruta_timeline)
        print(f"✓ Línea temporal (stacked area) guardada en: {ruta_timeline}")

    # ============================================================
    # (5) Exportar todos los gráficos a un PDF consolidado
    # ============================================================
    ruta_pdf = os.path.join(OUT_DIR, "req5_report.pdf")
    exportar_imagenes_a_pdf([ruta_mapa, ruta_nube, ruta_timeline], ruta_pdf)
    print(f"\n📄 PDF consolidado generado en: {ruta_pdf}")

    # ============================================================
    # (6) Instrucciones de lectura e interpretación de resultados
    # ============================================================
    print("\n# Cómo leer los artefactos")
    print("1) Mapa de calor: países con color más intenso = mayor número de publicaciones "
          "con PRIMER autor afiliado a ese país.")
    print("2) Nube (DINÁMICA): al agregar o eliminar estudios, se actualizan "
          "req5_top_terminos.csv y req5_contadores.json con nuevos términos y frecuencias.")
    print("3) Línea temporal: visualiza la evolución de publicaciones por AÑO y REVISTA "
          "(las más relevantes + categoría 'Others').")
    print("4) PDF: documento único con las tres figuras para incluir en el informe final.")


# Punto de entrada estándar del script
if __name__ == "__main__":
    main()
