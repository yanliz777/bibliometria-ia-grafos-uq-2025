# main_grafo.py
# ============================================================
# Requerimiento (GRAFOS) — EXACTAMENTE lo pedido:
# 1) Construcción automática de un grafo de citaciones dirigido, con pesos.
#    - Nodos: artículos del CSV unificado (req. 1).
#    - Aristas: A -> B si A "cita" a B. Si no hay cita explícita,
#      se infiere por similitud de TÍTULO, AUTORES o PALABRAS CLAVE.
#    - Peso de arista: 1 - similitud  (más similitud = menor costo).
#
# 2) Cálculo de caminos mínimos entre artículos: Dijkstra.
#
# 3) Identificación de componentes fuertemente conexas (SCC): Kosaraju.
# ============================================================

import os
import re
import unicodedata
import heapq
from collections import defaultdict, deque

import pandas as pd
import config

# ------------------------------------------------------------
# 1) Normalización y tokenización (para similitud)
# ------------------------------------------------------------

def _norm_text(s: str) -> str:
    """Normaliza texto: quita tildes, pasa a minúsculas y compacta espacios."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)  # dejar solo letras/dígitos como tokens
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _tokens(s: str) -> set:
    """Convierte texto ya normalizado a un set de tokens (palabras únicas)."""
    if not s:
        return set()
    return set(s.split())

def jaccard(a: set, b: set) -> float:
    """Jaccard clásico: |A ∩ B| / |A ∪ B|. Si ambos vacíos, 0."""
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0

def _split_authors(s: str) -> list:
    """
    Autores llegan como 'A1; A2; A3'. Los normalizamos y devolvemos lista.
    """
    if not s:
        return []
    parts = [p.strip() for p in re.split(r"[;,]", s) if p.strip()]
    return [_norm_text(p) for p in parts if p]

def _split_keywords(s: str) -> list:
    """Palabras clave separadas por ';' u otras comas."""
    if not s:
        return []
    parts = [p.strip() for p in re.split(r"[;,\|]", s) if p.strip()]
    return [_norm_text(p) for p in parts if p]

def similitud_articulos(a: dict, b: dict) -> float:
    """
    Combina similitud por título, autores y palabras clave.
    - título: Jaccard de tokens              (peso 0.5)
    - autores: Jaccard de autores normalizados (peso 0.3)
    - keywords: Jaccard de palabras clave      (peso 0.2)
    Devuelve valor en [0,1].
    """
    # Títulos
    t_a = _tokens(_norm_text(a.get("title", "")))
    t_b = _tokens(_norm_text(b.get("title", "")))
    sim_title = jaccard(t_a, t_b)

    # Autores
    au_a = set(_split_authors(a.get("authors", "")))
    au_b = set(_split_authors(b.get("authors", "")))
    sim_auth = jaccard(au_a, au_b)

    # Palabras clave
    kw_a = set(_split_keywords(a.get("keywords", "")))
    kw_b = set(_split_keywords(b.get("keywords", "")))
    sim_kw = jaccard(kw_a, kw_b)

    # Mezcla lineal simple (puedes ajustar pesos si hace falta)
    return 0.5 * sim_title + 0.3 * sim_auth + 0.2 * sim_kw


# ------------------------------------------------------------
# 2) Estructura de datos del grafo dirigido y con pesos
# ------------------------------------------------------------
class GrafoDirigido:
    """
    Implementamos un grafo dirigido con lista de adyacencia.
    - 'nodos' es un diccionario id->dict con metadata del artículo.
    - 'adj' es un dict: u -> lista de (v, peso)
    """

    def __init__(self):
        self.nodos = {}                 # id -> datos del artículo
        self.adj = defaultdict(list)    # id_u -> [(id_v, peso), ...]

    def agregar_nodo(self, node_id, data):
        """Crea (o actualiza) un nodo con su información."""
        self.nodos[node_id] = data

    def agregar_arista(self, u, v, peso=1.0):
        """
        Agrega arista dirigida u -> v con un 'peso' (float).
        Nota: el enunciado pide conservar dirección y peso.
        """
        self.adj[u].append((v, peso))

    def vecinos(self, u):
        """Devuelve la lista de (v, peso) desde u."""
        return self.adj.get(u, [])

    def nodos_ids(self):
        return list(self.nodos.keys())


# ------------------------------------------------------------
# 3) Construcción automática del grafo a partir del CSV unificado
# ------------------------------------------------------------
def cargar_articulos_desde_unificado(path_csv: str) -> list:
    """
    Lee el CSV generado en el Requerimiento 1 y lo pasa a una lista de dicts.
    Columnas esperadas (ya las generamos): title, authors, keywords, year, doi, ...
    """
    if not os.path.isfile(path_csv):
        raise FileNotFoundError(f"No encontré el CSV unificado en: {path_csv}")

    df = pd.read_csv(path_csv, dtype=str).fillna("")
    # Estructura simple por fila:
    rows = df.to_dict(orient="records")
    return rows

def construir_grafo(articulos: list,
                    umbral_similitud=0.35,
                    max_salientes_por_nodo=5) -> GrafoDirigido:
    """
    Crea el grafo:
      - Un nodo por artículo (id = índice en la lista).
      - Aristas dirigidas inferidas por similitud:
            si sim(a,b) >= umbral => a -> b con peso = 1 - sim.
      - Para evitar grafo denso, limitamos a 'max_salientes_por_nodo'
        las mejores coincidencias por nodo (opcional, ayuda a rendimiento).
    """
    G = GrafoDirigido()

    # 1) Crear nodos
    for idx, art in enumerate(articulos):
        # Guardamos solo lo necesario (puedes ampliar)
        G.agregar_nodo(idx, {
            "title": art.get("title", ""),
            "authors": art.get("authors", ""),
            "keywords": art.get("keywords", ""),
            "year": art.get("year", ""),
            "doi": art.get("doi", ""),
            "url": art.get("url", "")
        })

    # 2) Crear aristas por similitud (O(n^2) en versión simple)
    #    Para conjuntos medianos (100–500) es razonable. Si sube mucho, optimizamos luego.
    n = len(articulos)
    for i in range(n):
        a = articulos[i]
        # acumulamos candidatos (j, sim) para este i y luego elegimos los mejores
        candidatos = []
        for j in range(n):
            if i == j:
                continue
            b = articulos[j]
            sim = similitud_articulos(a, b)
            if sim >= umbral_similitud:
                candidatos.append((j, sim))

        # Ordenar por similitud desc y tomar top-K
        candidatos.sort(key=lambda x: x[1], reverse=True)
        candidatos = candidatos[:max_salientes_por_nodo]

        # Agregar aristas con peso = 1 - sim
        for j, sim in candidatos:
            peso = 1.0 - sim
            G.agregar_arista(i, j, peso=peso)

    return G


# ------------------------------------------------------------
# 4) Caminos mínimos (Dijkstra)
# ------------------------------------------------------------
def dijkstra(G: GrafoDirigido, origen: int):
    """
    Dijkstra clásico desde 'origen'.
    Devuelve:
      - dist: dict id -> distancia mínima
      - prev: dict id -> predecesor en el camino óptimo
    """
    dist = {u: float("inf") for u in G.nodos_ids()}
    prev = {u: None for u in G.nodos_ids()}
    dist[origen] = 0.0

    pq = [(0.0, origen)]  # (dist, nodo)
    while pq:
        d_u, u = heapq.heappop(pq)
        if d_u > dist[u]:
            continue  # entrada obsoleta

        for v, w in G.vecinos(u):
            alt = d_u + w
            if alt < dist[v]:
                dist[v] = alt
                prev[v] = u
                heapq.heappush(pq, (alt, v))

    return dist, prev

def reconstruir_camino(prev: dict, destino: int):
    """Reconstruye el camino usando el arreglo 'prev'."""
    camino = []
    cur = destino
    while cur is not None:
        camino.append(cur)
        cur = prev[cur]
    camino.reverse()
    return camino


# ------------------------------------------------------------
# 5) Componentes Fuertemente Conexas (SCC) — Kosaraju
# ------------------------------------------------------------
def kosaraju_scc(G: GrafoDirigido):
    """
    Kosaraju:
      1) DFS para ordenar por tiempos de finalización.
      2) Transponer el grafo (invirtiendo aristas).
      3) DFS en el grafo transpuesto siguiendo el orden inverso.
    Devuelve lista de componentes, cada una como lista de nodos.
    """
    # Paso 1: orden de salida
    visit = set()
    orden = []

    def dfs1(u):
        visit.add(u)
        for v, _ in G.vecinos(u):
            if v not in visit:
                dfs1(v)
        orden.append(u)

    for u in G.nodos_ids():
        if u not in visit:
            dfs1(u)

    # Paso 2: transpuesto
    GT = defaultdict(list)  # v -> [u] si en G había u->v
    for u in G.nodos_ids():
        for v, _ in G.vecinos(u):
            GT[v].append(u)

    # Paso 3: DFS en transpuesto siguiendo orden inverso
    visit.clear()
    componentes = []

    def dfs2(u, comp):
        visit.add(u)
        comp.append(u)
        for w in GT[u]:
            if w not in visit:
                dfs2(w, comp)

    for u in reversed(orden):
        if u not in visit:
            comp = []
            dfs2(u, comp)
            componentes.append(comp)

    return componentes


# ------------------------------------------------------------
# 6) Utilidades para buscar por título (para pruebas)
# ------------------------------------------------------------
def buscar_por_titulo(G: GrafoDirigido, fragmento: str, k=5):
    """
    Busca nodos cuyo título contenga el 'fragmento' (case-insensitive).
    Retorna lista de (id, título) máx k resultados.
    """
    frag = _norm_text(fragmento)
    resultados = []
    for i, data in G.nodos.items():
        titulo_norm = _norm_text(data.get("title", ""))
        if frag and frag in titulo_norm:
            resultados.append((i, data.get("title", "")))
            if len(resultados) >= k:
                break
    return resultados


# ------------------------------------------------------------
# 7) MAIN: construir, preguntar cosas y demostrar funciones
# ------------------------------------------------------------
def _ruta_csv_unificado():
    base = getattr(config, "OUTPUT_DIR_BIBLIO", "")
    if not base:
        # fallback inocuo: escritorio/salidas
        base = os.path.join(os.path.expanduser("~"), "Desktop", "salidas")
    return os.path.join(base, "unificado_ai_generativa.csv")

def main():
    # === 1) Cargar artículos del CSV unificado ===
    csv_path = _ruta_csv_unificado()
    print(f"Cargando artículos desde: {csv_path}")
    articulos = cargar_articulos_desde_unificado(csv_path)
    print(f"   → Registros leídos: {len(articulos)}")

    # === 2) Construir grafo dirigido y ponderado ===
    #     umbral_similitud: elevarlo ↓ crea menos aristas (más precisas).
    #     max_salientes_por_nodo: tope de aristas salientes por nodo (control densidad).
    print("Construyendo grafo (dirigido, ponderado)...")
    G = construir_grafo(
        articulos,
        umbral_similitud=0.35,
        max_salientes_por_nodo=5
    )
    print(f"   → Nodos: {len(G.nodos)}")
    total_aristas = sum(len(G.vecinos(u)) for u in G.nodos_ids())
    print(f"   → Aristas: {total_aristas}")

    # === 3) Dijkstra: ejemplo de camino mínimo entre dos artículos ===
    #     Puedes editar LOS TÍTULOS a buscar para elegir origen y destino.
    ejemplo_origen = "artificial intelligence"
    ejemplo_destino = "education"

    encontrados_origen = buscar_por_titulo(G, ejemplo_origen, k=1)
    encontrados_dest  = buscar_por_titulo(G, ejemplo_destino, k=1)

    if encontrados_origen and encontrados_dest:
        s = encontrados_origen[0][0]
        t = encontrados_dest[0][0]
        print(f"\n🚦 Dijkstra: camino más corto entre:")
        print(f"   ORIGEN  [{s}]: {G.nodos[s]['title'][:90]}")
        print(f"   DESTINO [{t}]: {G.nodos[t]['title'][:90]}")

        dist, prev = dijkstra(G, s)
        if dist[t] == float("inf"):
            print("   → No hay camino dirigido (∞).")
        else:
            camino = reconstruir_camino(prev, t)
            print(f"   → Distancia total = {dist[t]:.4f}")
            print("   → Camino (ids):", " -> ".join(map(str, camino)))
            print("   → Camino (títulos):")
            for nid in camino:
                print("      •", G.nodos[nid]["title"][:120])
    else:
        print("\nℹ No se encontraron ejemplos de origen/destino por fragmentos de título "
              "(edita 'ejemplo_origen' y 'ejemplo_destino' en el main).")

    # === 4) SCC: Componentes fuertemente conexas ===
    print("\n Calculando Componentes Fuertemente Conexas (SCC) con Kosaraju...")
    sccs = kosaraju_scc(G)
    print(f"   → SCC encontradas: {len(sccs)}")
    # Mostrar las 3 más grandes (o menos si no hay tantas)
    sccs_ordenadas = sorted(sccs, key=len, reverse=True)[:3]
    for idx, comp in enumerate(sccs_ordenadas, start=1):
        print(f"   • SCC #{idx} (tamaño={len(comp)}):")
        for nid in comp[:5]:  # muestra primeros 5 títulos de cada SCC
            print("      -", G.nodos[nid]["title"][:120])
        if len(comp) > 5:
            print("      ...")

    print("\n Listo: grafo construido, Dijkstra y SCC ejecutados.")


if __name__ == "__main__":
    main()
