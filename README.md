Bibliometría IA + Grafos (UQ 2025)

Automatiza la descarga de artículos (SAGE Journals y ScienceDirect vía CRAI/SSO), unifica y deduplica citas en RIS, y construye una red de citaciones para análisis de caminos mínimos y componentes fuertemente conexas.

Proyecto académico – Universidad del Quindío (Análisis de Algoritmos, 2025-2).

Funcionalidades:

Requerimiento 1

Login SSO Google vía CRAI.

Búsqueda por query ("generative artificial intelligence" por defecto).

Descarga por páginas (SD con 100 resultados/página).

Renombrado y verificación de descargas.

Unificación RIS (SAGE + SD) con deduplicación por DOI → título.

Exporta: unificado_ai_generativa.csv, unificado_ai_generativa_duplicados_eliminados.csv, unificado_ai_generativa.jsonl.

Taller de grafos (basado en Req. 1)

Construcción del grafo dirigido de citaciones (inferidas por similitud de título/autores/keywords cuando no hay citas explícitas).

Caminos mínimos (Dijkstra).

Componentes fuertemente conexas (Kosaraju).

Cómo ejecutar
1) Pipeline completo (descarga + unificación):python main_pipeline.py


Qué hace:

SAGE: login → búsqueda → exporta N páginas a .ris.

ScienceDirect: login → búsqueda → fija 100/página → exporta N páginas a .ris.

Unificación: lee .ris de ambas fuentes → deduplica → genera CSV y JSONL en salidas/.

2) Grafo y análisis (Dijkstra + SCC)

Con el CSV unificado generado en salidas/: python main_grafo.py


Salida esperada (ejemplo):

N nodos = #artículos

M aristas = relaciones de citación inferidas

Dijkstra entre dos índices de artículos (puedes cambiar los índices en el script).

SCC reportadas con títulos de ejemplo.

