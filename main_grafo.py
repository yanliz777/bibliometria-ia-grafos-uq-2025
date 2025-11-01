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
from collections import defaultdict

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
    """Autores llegan como 'A1; A2; A3'. Los normalizamos y devolvemos lista."""
    if not s:
        return []
    parts = [p.strip() for p in re.split(r"[;,]", s) if p.strip()]
    return [_norm_text(p) for p in parts if p]

def _split_keywords(s: str) -> list:
    """Palabras clave separadas por ';', ',' o '|'."""
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

    # Mezcla lineal
    return 0.5 * sim_title + 0.3 * sim_auth + 0.2 * sim_kw


# ------------------------------------------------------------
# 2) Estructura de datos del grafo dirigido y con pesos
# ------------------------------------------------------------
class GrafoDirigido:
    """
    Grafo dirigido con lista de adyacencia.
    - 'nodos': dict id->dict con metadata del artículo.
    - 'adj'  : dict id_u -> list[(id_v, peso)]
    """

    def __init__(self):
        self.nodos = {}                 # id -> datos del artículo
        self.adj = defaultdict(list)    # id_u -> [(id_v, peso), ...]

    def agregar_nodo(self, node_id, data):
        """Crea (o actualiza) un nodo con su información."""
        self.nodos[node_id] = data

    def agregar_arista(self, u, v, peso=1.0):
        """Agrega arista dirigida u -> v con un 'peso' (float)."""
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
    Columnas esperadas: title, authors, keywords, year, doi, url, ...
    """
    if not os.path.isfile(path_csv):
        raise FileNotFoundError(f"No encontré el CSV unificado en: {path_csv}")

    df = pd.read_csv(path_csv, dtype=str).fillna("")
    return df.to_dict(orient="records")

def construir_grafo(articulos: list,
                    umbral_similitud=0.35,
                    max_salientes_por_nodo=5) -> GrafoDirigido:
    """
    Crea el grafo:
      - Un nodo por artículo (id = índice en la lista).
      - Aristas dirigidas inferidas por similitud:
            si sim(a,b) >= umbral => a -> b con peso = 1 - sim.
      - Se limita a 'max_salientes_por_nodo' mejores coincidencias por nodo
        para controlar densidad.
    """
    G = GrafoDirigido()

    # 1) Nodos
    for idx, art in enumerate(articulos):
        G.agregar_nodo(idx, {
            "title": art.get("title", ""),
            "authors": art.get("authors", ""),
            "keywords": art.get("keywords", ""),
            "year": art.get("year", ""),
            "doi": art.get("doi", ""),
            "url": art.get("url", "")
        })

    # 2) Aristas por similitud (O(n^2) simple)
    n = len(articulos)
    for i in range(n):
        a = articulos[i]
        candidatos = []
        for j in range(n):
            if i == j:
                continue
            b = articulos[j]
            sim = similitud_articulos(a, b)
            if sim >= umbral_similitud:
                candidatos.append((j, sim))

        # Mejores K
        candidatos.sort(key=lambda x: x[1], reverse=True)
        candidatos = candidatos[:max_salientes_por_nodo]

        # Peso = 1 - similitud
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
# 6) Búsqueda por título (para elegir nodos de ejemplo)
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
# 6.1) IMPRESIONES EN CONSOLA (vistas del grafo)
# ------------------------------------------------------------
def imprimir_lista_adyacencia(titulos, adj, max_nodos=10, max_vecinos=10):
    """
    Muestra la lista de adyacencia:
      [u] Título_u
         └─→ [v] Título_v  (peso=w)
    """
    n = len(titulos)
    tope = min(max_nodos, n)
    print("\n Lista de adyacencia (recorte):")
    for u in range(tope):
        vecinos = adj.get(u, [])
        print(f"[{u:>3}] {titulos[u][:90]}")
        if not vecinos:
            print("     (sin salientes)")
            continue
        for v, w in vecinos[:max_vecinos]:
            print(f"     └─→ [{v:>3}] {titulos[v][:70]}  (peso={w:.3f})")
        if len(vecinos) > max_vecinos:
            print(f"     … {len(vecinos) - max_vecinos} aristas más desde este nodo")

def imprimir_aristas(titulos, adj, max_aristas=60):
    """
    Lista aristas como: [u] → [v] w=...
    Limitado a max_aristas para no inundar la consola.
    """
    total = sum(len(vs) for vs in adj.values())
    print("\n Aristas (recorte):")
    count = 0
    for u, vecinos in adj.items():
        for v, w in vecinos:
            print(f"[{u:>3}] → [{v:>3}]  w={w:.3f}  |  {titulos[u][:42]} → {titulos[v][:42]}")
            count += 1
            if count >= max_aristas:
                if total > max_aristas:
                    print(f"… ({total - max_aristas} aristas más)")
                return

def imprimir_subgrafo_en_torno(titulos, adj, nodo_centro, max_vecinos=12):
    """
    Muestra el “ego-graph” de un nodo: sus salientes y quiénes lo apuntan.
    Útil para inspección puntual.
    """
    print(f"\n Subgrafo en torno a [{nodo_centro}] {titulos[nodo_centro]}")
    salientes = adj.get(nodo_centro, [])
    entrantes = []
    for u, vecinos in adj.items():
        for v, w in vecinos:
            if v == nodo_centro:
                entrantes.append((u, w))
    print("  → Salientes:")
    if salientes:
        for v, w in salientes[:max_vecinos]:
            print(f"     [{nodo_centro}] → [{v}] (w={w:.3f})  {titulos[v][:70]}")
        if len(salientes) > max_vecinos:
            print(f"     … {len(salientes) - max_vecinos} más")
    else:
        print("     (ninguno)")

    print("  ← Entrantes:")
    if entrantes:
        for u, w in entrantes[:max_vecinos]:
            print(f"     [{u}] → [{nodo_centro}] (w={w:.3f})  {titulos[u][:70]}")
        if len(entrantes) > max_vecinos:
            print(f"     … {len(entrantes) - max_vecinos} más")
    else:
        print("     (ninguno)")


# ------------------------------------------------------------
# 7) MAIN: construir, mostrar vistas y ejecutar Dijkstra + SCC
# ------------------------------------------------------------
def _ruta_csv_unificado():
    base = getattr(config, "OUTPUT_DIR_BIBLIO", "")
    if not base:
        # fallback: Escritorio/salidas
        base = os.path.join(os.path.expanduser("~"), "Desktop", "salidas")
    return os.path.join(base, "unificado_ai_generativa.csv")

def main():
    # === 1) Cargar artículos del CSV unificado ===
    csv_path = _ruta_csv_unificado()
    print(f"Cargando artículos desde: {csv_path}")
    articulos = cargar_articulos_desde_unificado(csv_path)
    print(f"   → Registros leídos: {len(articulos)}")

    # === 2) Construir grafo dirigido y ponderado ===
    print("Construyendo grafo (dirigido, ponderado)...")
    G = construir_grafo(
        articulos,
        umbral_similitud=0.35,     # ajusta si quieres más/menos aristas
        max_salientes_por_nodo=5   # controla la densidad
    )
    print(f"   → Nodos: {len(G.nodos)}")
    total_aristas = sum(len(G.vecinos(u)) for u in G.nodos_ids())
    print(f"   → Aristas: {total_aristas}")

    # === 2.1) Vistas en consola del grafo ===
    titulos = [G.nodos[i]["title"] for i in sorted(G.nodos.keys())]
    adj = G.adj
    imprimir_lista_adyacencia(titulos, adj, max_nodos=15, max_vecinos=8)
    imprimir_aristas(titulos, adj, max_aristas=80)
    # (Opcional) inspeccionar el nodo 0:
    if len(titulos) > 0:
        imprimir_subgrafo_en_torno(titulos, adj, nodo_centro=0, max_vecinos=12)

    # === 3) Dijkstra: camino mínimo entre dos artículos (ejemplo básico) ===
    ejemplo_origen = "artificial intelligence"
    ejemplo_destino = "education"
    encontrados_origen = buscar_por_titulo(G, ejemplo_origen, k=1)
    encontrados_dest  = buscar_por_titulo(G, ejemplo_destino, k=1)

    print("\n Dijkstra: camino más corto entre:")
    if encontrados_origen and encontrados_dest:
        s = encontrados_origen[0][0]
        t = encontrados_dest[0][0]
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
        print("   → No se encontraron nodos para los fragmentos elegidos "
              "(edita 'ejemplo_origen' y 'ejemplo_destino').")

    # === 4) SCC: Componentes fuertemente conexas ===
    print("\n Calculando Componentes Fuertemente Conexas (SCC) con Kosaraju...")
    sccs = kosaraju_scc(G)
    print(f"   → SCC encontradas: {len(sccs)}")
    sccs_ordenadas = sorted(sccs, key=len, reverse=True)[:3]
    for idx, comp in enumerate(sccs_ordenadas, start=1):
        print(f"   • SCC #{idx} (tamaño={len(comp)}):")
        for nid in comp[:5]:
            print("      -", G.nodos[nid]["title"][:120])
        if len(comp) > 5:
            print("      ...")

    print("\n Listo: grafo construido, Dijkstra y SCC ejecutados.")


if __name__ == "__main__":
    main()
