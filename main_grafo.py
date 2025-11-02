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

# —— Importaciones de librerías estándar ——
import os              # Operaciones con archivos/rutas (os.path.join, isfile, etc.)
import re              # Expresiones regulares para limpiar/partir texto
import unicodedata     # Normalización Unicode (quitar tildes)
import heapq           # Cola de prioridad (min-heap) para Dijkstra
from collections import defaultdict  # Diccionario con valor por defecto (listas para la adyacencia)

# —— Dependencias de terceros ——
import pandas as pd    # Lectura del CSV (DataFrame → lista de diccionarios)

# —— Tu archivo de configuración (rutas) ——
import config

# ------------------------------------------------------------
# 1) Normalización y tokenización (para similitud)
# ------------------------------------------------------------

def _norm_text(s: str) -> str:
    """
    Normaliza texto:
      - Quita tildes (normalización NFKD + filtrado de marcas diacríticas)
      - Convierte a minúsculas
      - Sustituye cualquier cosa que no sea [a-z0-9] por espacios
      - Colapsa múltiples espacios en uno
    Parámetros:
      s: str  → cadena original (puede ser None/NaN, por eso se controla)
    Retorna:
      str normalizada
    """
    if not s:
        return ""
    # NFKD descompone caracteres con tilde en "base" + "marca"
    s = unicodedata.normalize("NFKD", s)
    # Quitamos las marcas diacríticas (combining marks)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    # Reemplazamos todo lo que no sea alfanumérico por espacio
    s = re.sub(r"[^a-z0-9]+", " ", s)
    # Compactamos espacios
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _tokens(s: str) -> set:
    """
    Toma un texto YA normalizado y lo convierte en un conjunto (set) de palabras únicas.
    - En Python, set() es una estructura sin elementos repetidos y con operaciones de teoría de conjuntos.
    """
    if not s:
        return set()
    # "a b c a" → {"a", "b", "c"}
    return set(s.split())

def jaccard(a: set, b: set) -> float:
    """
    Similitud de Jaccard clásica: |A ∩ B| / |A ∪ B|
    - a y b son conjuntos (sets) de tokens/palabras.
    - Si ambos están vacíos, retornamos 0.0 para evitar división por cero.
    """
    if not a and not b:
        return 0.0
    inter = len(a & b)   # Intersección: elementos comunes
    union = len(a | b)   # Unión: todos los elementos distintos
    return inter / union if union else 0.0

def _split_authors(s: str) -> list:
    """
    Parte la cadena de autores (formato típico "A1; A2; A3") en una lista,
    normalizando cada autor (quita tildes, minúsculas, etc.).
    - Usamos re.split para separar por ';' o ',' indistintamente.
    """
    if not s:
        return []
    parts = [p.strip() for p in re.split(r"[;,]", s) if p.strip()]
    return [_norm_text(p) for p in parts if p]

def _split_keywords(s: str) -> list:
    """
    Parte la cadena de keywords por ';', ',' o '|' y normaliza cada término.
    """
    if not s:
        return []
    parts = [p.strip() for p in re.split(r"[;,\|]", s) if p.strip()]
    return [_norm_text(p) for p in parts if p]

def similitud_articulos(a: dict, b: dict) -> float:
    """
    Puntaje de similitud combinado (0..1) entre dos artículos.
    - Título (50%): Jaccard sobre tokens del título normalizado.
    - Autores (30%): Jaccard sobre conjuntos de autores normalizados.
    - Keywords (20%): Jaccard sobre conjuntos de palabras clave normalizadas.
    Retorna:
      float en [0,1], donde 1 = idénticos según este esquema simple.
    """
    # —— Títulos ——
    t_a = _tokens(_norm_text(a.get("title", "")))
    t_b = _tokens(_norm_text(b.get("title", "")))
    sim_title = jaccard(t_a, t_b)

    # —— Autores ——
    au_a = set(_split_authors(a.get("authors", "")))
    au_b = set(_split_authors(b.get("authors", "")))
    sim_auth = jaccard(au_a, au_b)

    # —— Palabras clave ——
    kw_a = set(_split_keywords(a.get("keywords", "")))
    kw_b = set(_split_keywords(b.get("keywords", "")))
    sim_kw = jaccard(kw_a, kw_b)

    # —— Mezcla lineal (pesos configurados) ——
    return 0.5 * sim_title + 0.3 * sim_auth + 0.2 * sim_kw


# ------------------------------------------------------------
# 2) Estructura de datos del grafo dirigido y con pesos
# ------------------------------------------------------------
class GrafoDirigido:
    """
    Implementación simple de un grafo dirigido con lista de adyacencia.
    - self.nodos: dict[int -> dict]   Mapa de id de nodo ⇒ metadatos (title, authors, etc.)
    - self.adj  : dict[int -> list[(int, float)]]
                  Para cada u, una lista de tuplas (v, peso) representando aristas u → v.
    """

    def __init__(self):
        # Diccionario normal para meta de nodos
        self.nodos = {}                 # id -> datos del artículo (dict)
        # defaultdict(list) crea automáticamente una lista vacía al acceder a una clave nueva
        self.adj = defaultdict(list)    # id_u -> [(id_v, peso), ...]

    def agregar_nodo(self, node_id, data):
        """
        Inserta o actualiza un nodo con su 'data'.
        - node_id: int (usamos el índice del artículo en la lista)
        - data: dict con metadatos (title, authors, year, doi, url, ...)
        """
        self.nodos[node_id] = data

    def agregar_arista(self, u, v, peso=1.0):
        """
        Agrega arista dirigida u -> v con un 'peso' (float).
        - Nota: el enunciado exige conservar dirección y peso.
        """
        self.adj[u].append((v, peso))

    def vecinos(self, u):
        """Devuelve lista de tuplas (v, peso) que salen de u. Si u no tiene, retorna []."""
        return self.adj.get(u, [])

    def nodos_ids(self):
        """Devuelve la lista de ids de nodos (claves del dict self.nodos)."""
        return list(self.nodos.keys())


# ------------------------------------------------------------
# 3) Construcción automática del grafo a partir del CSV unificado
# ------------------------------------------------------------
def cargar_articulos_desde_unificado(path_csv: str) -> list:
    """
    Lee el CSV generado en el Requerimiento 1 y lo convierte en lista de dicts (uno por fila).
    - path_csv: ruta absoluta al CSV.
    - Espera columnas: title, authors, keywords, year, doi, url, ...
    - pandas.read_csv(..., dtype=str).fillna("") asegura strings y sin NaN.
    Retorna:
      list[dict], donde cada dict es un artículo con sus campos.
    """
    if not os.path.isfile(path_csv):
        raise FileNotFoundError(f"No encontré el CSV unificado en: {path_csv}")

    df = pd.read_csv(path_csv, dtype=str).fillna("")
    # DataFrame → lista de registros (cada registro es un dict columna→valor)
    return df.to_dict(orient="records")

def construir_grafo(articulos: list,
                    umbral_similitud=0.35,
                    max_salientes_por_nodo=5) -> GrafoDirigido:
    """
    Crea el grafo dirigido y ponderado a partir de la lista de artículos.
    Pasos:
      1) Crear un nodo por artículo (id = índice en la lista).
      2) Inferir aristas por similitud:
         - Para cada par (i, j), i != j, calculamos similitud_articulos(i, j).
         - Si la similitud >= umbral_similitud, proponemos arista i → j.
      3) Para limitar densidad, nos quedamos con las K mejores (mayor similitud)
         por cada nodo i: 'max_salientes_por_nodo'.
      4) Definimos el peso de la arista como 1 - similitud (más similares ⇒ menor costo).
    Complejidad:
      - La versión simple es O(n^2). Para ~100–500 artículos es razonable.
    """
    G = GrafoDirigido()

    # (1) Crear nodos con metadatos mínimos
    for idx, art in enumerate(articulos):
        G.agregar_nodo(idx, {
            "title": art.get("title", ""),        # título
            "authors": art.get("authors", ""),    # cadena de autores
            "keywords": art.get("keywords", ""),  # cadena de keywords
            "year": art.get("year", ""),          # año
            "doi": art.get("doi", ""),            # doi
            "url": art.get("url", "")             # url
        })

    # (2) Crear aristas por similitud
    n = len(articulos)
    for i in range(n):
        a = articulos[i]
        candidatos = []  # acumulamos (j, similitud) para i
        for j in range(n):
            if i == j:
                continue
            b = articulos[j]
            sim = similitud_articulos(a, b)
            if sim >= umbral_similitud:
                candidatos.append((j, sim))

        # (3) Ordenamos por similitud descendente y tomamos top-K
        candidatos.sort(key=lambda x: x[1], reverse=True)
        candidatos = candidatos[:max_salientes_por_nodo]

        # (4) Agregamos aristas con peso = 1 - similitud
        for j, sim in candidatos:
            peso = 1.0 - sim
            G.agregar_arista(i, j, peso=peso)

    return G


# ------------------------------------------------------------
# 4) Caminos mínimos (Dijkstra)
# ------------------------------------------------------------
def dijkstra(G: GrafoDirigido, origen: int):
    """
    Dijkstra clásico con cola de prioridad (heapq) para encontrar
    distancias mínimas desde 'origen' al resto.
    Estructuras:
      - dist: dict nodo → distancia min encontrada (inicial ∞, excepto origen=0)
      - prev: dict nodo → predecesor en el camino óptimo (para reconstruir ruta)
      - pq  : lista de tuplas (distancia_actual, nodo) usada como min-heap
    Retorna:
      (dist, prev)
    """
    # Inicializamos distancias a infinito y sin predecesor
    dist = {u: float("inf") for u in G.nodos_ids()}
    prev = {u: None for u in G.nodos_ids()}
    dist[origen] = 0.0

    # Cola de prioridad con (distancia, nodo). heapq siempre saca el menor.
    pq = [(0.0, origen)]
    while pq:
        d_u, u = heapq.heappop(pq)
        # Si el par sacado tiene una distancia peor que la guardada, se ignora (entrada obsoleta).
        if d_u > dist[u]:
            continue

        # Relajación de aristas salientes u → v con peso w
        for v, w in G.vecinos(u):
            alt = d_u + w
            if alt < dist[v]:
                dist[v] = alt
                prev[v] = u
                heapq.heappush(pq, (alt, v))

    return dist, prev

def reconstruir_camino(prev: dict, destino: int):
    """
    Reconstruye el camino desde el origen hasta 'destino' usando el mapa 'prev'.
    - Se recorre hacia atrás: destino → ... → origen, y luego se invierte la lista.
    """
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
    Algoritmo de Kosaraju para SCC:
      1) DFS en G para obtener orden por tiempos de finalización (pila/orden).
      2) Construir el grafo transpuesto GT (invertir dirección u→v a v→u).
      3) DFS en GT siguiendo el orden inverso del paso 1. Cada DFS produce una SCC.
    Retorna:
      list[list[int]]  → lista de componentes; cada componente es una lista de ids de nodos.
    """
    # —— Paso 1: DFS para obtener orden de salida ——
    visit = set()
    orden = []

    def dfs1(u):
        visit.add(u)
        for v, _ in G.vecinos(u):
            if v not in visit:
                dfs1(v)
        orden.append(u)  # al finalizar u, lo apilamos

    for u in G.nodos_ids():
        if u not in visit:
            dfs1(u)

    # —— Paso 2: Grafo transpuesto GT (diccionario de listas) ——
    GT = defaultdict(list)  # v -> [u] si en G había u -> v
    for u in G.nodos_ids():
        for v, _ in G.vecinos(u):
            GT[v].append(u)

    # —— Paso 3: DFS en GT en orden inverso ——
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
    Busca nodos cuyo título contiene 'fragmento' (ignorando mayúsculas/acentos).
    - Devuelve hasta k resultados como lista de tuplas (id, título).
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
    Muestra la lista de adyacencia “recortada”:
      [u] Título_u
         └─→ [v] Título_v  (peso=w)
    Parámetros:
      - titulos: list[str] con los títulos en orden por id
      - adj    : dict[int -> list[(int, float)]] (lista de adyacencia)
      - max_nodos / max_vecinos: límites para no inundar la consola
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
    Lista aristas como líneas:
      [u] → [v]  w=...
      Título_u → Título_v
    Se limita a 'max_aristas' para mantener legible la salida.
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
    Muestra el “ego-graph” de un nodo:
      - Sus aristas salientes
      - Quiénes lo apuntan (entrantes)
    Útil para inspección puntual de conexiones alrededor de un artículo.
    """
    print(f"\n Subgrafo en torno a [{nodo_centro}] {titulos[nodo_centro]}")
    salientes = adj.get(nodo_centro, [])
    entrantes = []
    # Recorremos toda la adyacencia para recolectar quién apunta a nodo_centro
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
    """
    Construye la ruta al CSV unificado:
      - Preferimos config.OUTPUT_DIR_BIBLIO si existe.
      - Si no, usamos Escritorio/salidas como fallback.
    """
    base = getattr(config, "OUTPUT_DIR_BIBLIO", "")
    if not base:
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
        umbral_similitud=0.35,     # ↓ sube para menos aristas (más estrictas), ↑ baja para más conexiones
        max_salientes_por_nodo=5   # controla cuántas salientes puede tener cada nodo (densidad)
    )
    print(f"   → Nodos: {len(G.nodos)}")
    total_aristas = sum(len(G.vecinos(u)) for u in G.nodos_ids())
    print(f"   → Aristas: {total_aristas}")

    # === 2.1) Vistas en consola del grafo ===
    # 'titulos' es una lista indexada por id de nodo para imprimir más fácil
    titulos = [G.nodos[i]["title"] for i in sorted(G.nodos.keys())]
    adj = G.adj
    imprimir_lista_adyacencia(titulos, adj, max_nodos=15, max_vecinos=8)
    imprimir_aristas(titulos, adj, max_aristas=80)
    # (Opcional) inspeccionar el nodo 0 si existe
    if len(titulos) > 0:
        imprimir_subgrafo_en_torno(titulos, adj, nodo_centro=0, max_vecinos=12)

    # === 3) Dijkstra: camino mínimo entre dos artículos (ejemplo) ===
    # Elegimos dos títulos por fragmentos para no depender de índices exactos.
    ejemplo_origen = "artificial intelligence"
    ejemplo_destino = "education"
    encontrados_origen = buscar_por_titulo(G, ejemplo_origen, k=1)
    encontrados_dest  = buscar_por_titulo(G, ejemplo_destino, k=1)

    print("\n Dijkstra: camino más corto entre:")
    if encontrados_origen and encontrados_dest:
        s = encontrados_origen[0][0]  # id del nodo origen
        t = encontrados_dest[0][0]    # id del nodo destino
        print(f"   ORIGEN  [{s}]: {G.nodos[s]['title'][:90]}")
        print(f"   DESTINO [{t}]: {G.nodos[t]['title'][:90]}")

        # Ejecutamos Dijkstra desde s
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
    # Mostramos las 3 SCC más grandes (o menos si hay pocas)
    sccs_ordenadas = sorted(sccs, key=len, reverse=True)[:3]
    for idx, comp in enumerate(sccs_ordenadas, start=1):
        print(f"   • SCC #{idx} (tamaño={len(comp)}):")
        for nid in comp[:5]:  # vemos los primeros 5 títulos para no saturar consola
            print("      -", G.nodos[nid]["title"][:120])
        if len(comp) > 5:
            print("      ...")

    print("\n Listo: grafo construido, Dijkstra y SCC ejecutados.")


# —— Entry point (punto de entrada) ——
if __name__ == "__main__":
    # Este bloque se ejecuta solo si corres:  python main_grafo.py
    # Si importas este archivo desde otro módulo, no se ejecuta main().
    main()
