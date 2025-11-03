"""


Requerimiento 2: Construcción y análisis del grafo de coocurrencia entre términos.
Lee automáticamente los términos de las salidas del Req. 3 y 4, y construye un grafo
no dirigido a partir de los abstracts del corpus.

Cumple:
 1️⃣ Construcción automática del grafo desde textos procesados.
 2️⃣ Cálculo de grado de cada nodo.
 3️⃣ Detección de grupos temáticos (componentes conexas).

Dependencias:
    pip install networkx pandas matplotlib numpy pyvis
"""

import os
import re
from collections import Counter, defaultdict
from typing import List, Optional, Dict, Tuple, Set
import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from pyvis.network import Network


# ============================================================
# CLASE PRINCIPAL
# ============================================================
class CooccurrenceGraph:
    def __init__(self, terms: Optional[List[str]] = None, min_cooccurrence: int = 1, normalizar: bool = True):
        self.terms = [t.strip() for t in terms] if terms else []
        self.min_cooccurrence = max(1, int(min_cooccurrence))
        self.normalizar = normalizar
        self._doc_term_matrix: List[Set[str]] = []
        self.cooccurrence_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        self._term_doc_freq: Counter = Counter()
        self.G: Optional[nx.Graph] = None

    # ---------------- Normalización ----------------
    @staticmethod
    def _normalize_text(text: str) -> str:
        if not isinstance(text, str):
            text = str(text or "")
        t = text.lower()
        t = re.sub(r"[\r\n\t]+", " ", t)
        t = re.sub(r"[^\w\s\-]", " ", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _term_present_in_text(self, term: str, text: str) -> bool:
        if self.normalizar:
            term = self._normalize_text(term)
            text = self._normalize_text(text)
        pattern = r"\b" + re.escape(term) + r"\b"
        return re.search(pattern, text) is not None

    # ---------------- Construcción ----------------
    def build_from_abstracts(self, abstracts: List[str], terms: Optional[List[str]] = None):
        if terms is not None:
            self.terms = [t.strip() for t in terms]
        if not self.terms:
            raise ValueError("Debe proporcionar una lista de términos.")

        self._doc_term_matrix = []
        self.cooccurrence_counts = defaultdict(int)
        self._term_doc_freq = Counter()

        for txt in abstracts:
            presentes = set()
            for term in self.terms:
                try:
                    if self._term_present_in_text(term, txt):
                        presentes.add(term)
                except re.error:
                    if term.lower() in txt.lower():
                        presentes.add(term)

            self._doc_term_matrix.append(presentes)
            for t in presentes:
                self._term_doc_freq[t] += 1

            # Pares de coocurrencia
            for i, a in enumerate(sorted(presentes)):
                for b in list(sorted(presentes))[i + 1:]:
                    self.cooccurrence_counts[(a, b)] += 1

        self._build_graph_from_counts()

    def _build_graph_from_counts(self):
        G = nx.Graph()
        for term in self.terms:
            G.add_node(term, doc_freq=int(self._term_doc_freq.get(term, 0)))

        for (a, b), count in self.cooccurrence_counts.items():
            if count >= self.min_cooccurrence:
                G.add_edge(a, b, weight=int(count))
        self.G = G

    def filtrar_aristas_principales(self, top_k: int = 30):
        """Conserva solo las top_k aristas con mayor peso."""
        if self.G is None:
            raise RuntimeError("El grafo no está construido.")
        # Ordenar aristas por peso
        edges_sorted = sorted(self.G.edges(data=True), key=lambda x: x[2].get("weight", 1), reverse=True)
        top_edges = edges_sorted[:top_k]
        # Crear subgrafo
        G_filtrado = nx.Graph()
        for u, v, data in top_edges:
            G_filtrado.add_edge(u, v, **data)
        for n in G_filtrado.nodes():
            G_filtrado.nodes[n]["doc_freq"] = self.G.nodes[n].get("doc_freq", 0)
        self.G = G_filtrado

    # ---------------- Métricas ----------------
    def get_node_degrees(self) -> pd.DataFrame:
        if self.G is None:
            raise RuntimeError("El grafo no está construido.")
        rows = [{'term': n,
                 'degree': self.G.degree(n),
                 'doc_freq': self.G.nodes[n].get('doc_freq', 0)} for n in self.G.nodes]
        return pd.DataFrame(rows).sort_values('degree', ascending=False).reset_index(drop=True)

    def connected_components(self, min_size: int = 1):
        if self.G is None:
            raise RuntimeError("El grafo no está construido.")
        comps = [set(c) for c in nx.connected_components(self.G) if len(c) >= min_size]
        comps.sort(key=lambda s: -len(s))
        return comps

    # ---------------- Exportar / Visualizar ----------------
    def save_graph_png(self, path: str, layout: str = 'kamada_kawai', show_weights=False):
        if self.G is None:
            raise RuntimeError("El grafo no está construido.")
        plt.figure(figsize=(12, 9))
        pos = nx.kamada_kawai_layout(self.G)
        doc_freqs = np.array([self.G.nodes[n].get('doc_freq', 0) for n in self.G.nodes()], dtype=float)
        nsizes = (doc_freqs + 1.0) * 250
        nx.draw_networkx_nodes(self.G, pos, node_size=nsizes, node_color="#8cbdd9", edgecolors="black")
        nx.draw_networkx_labels(self.G, pos, font_size=9)
        edge_weights = [self.G[u][v].get('weight', 1) for u, v in self.G.edges()]
        widths = [1.0 + 2.0 * (w / max(edge_weights)) for w in edge_weights]
        nx.draw_networkx_edges(self.G, pos, width=widths, alpha=0.4)
        if show_weights:
            edge_labels = {(u, v): self.G[u][v].get('weight', 1) for u, v in self.G.edges()}
            nx.draw_networkx_edge_labels(self.G, pos, edge_labels=edge_labels, font_size=8)
        plt.axis('off')
        plt.tight_layout()
        plt.savefig(path, dpi=300)
        plt.close()

    def save_graph_html(self, path_html: str):
        if self.G is None:
            raise RuntimeError("El grafo no está construido.")
        net = Network(height="800px", width="100%", bgcolor="#ffffff", font_color="black")
        net.from_nx(self.G)
        net.toggle_physics(True)
        net.write_html(path_html)


# ============================================================
# PROCESO AUTOMÁTICO (LEE SALIDAS DEL REQ. 3 Y 4)
# ============================================================
if __name__ == "__main__":
    print("=== Requerimiento 2"
          ": Grafo de Coocurrencia ===")

    # --- Ruta de archivos ---
    DIR = "/home/ycmejia/Escritorio/PROYECTO ALGORITMOS/salidas"
    CORPUS = os.path.join(DIR, "unificado_ai_generativa.csv")
    SEMILLAS = os.path.join(DIR, "req3_frecuencias_semillas.csv")
    NUEVOS = os.path.join(DIR, "req3_nuevos_terminos.csv")


    # --- Leer términos de Req 3 y 4 ---
    def leer_terminos():
        terminos = []
        for ruta in [SEMILLAS, NUEVOS]:
            if os.path.exists(ruta):
                df = pd.read_csv(ruta)
                col = [c for c in df.columns if "term" in c.lower() or "palabra" in c.lower()]
                if col:
                    terminos.extend(df[col[0]].dropna().astype(str).tolist())
        return sorted(set(terminos))

    # --- Leer abstracts del corpus ---
    df_corpus = pd.read_csv(CORPUS)
    col_abs = [c for c in df_corpus.columns if "abstract" in c.lower()][0]
    abstracts = df_corpus[col_abs].dropna().astype(str).tolist()

    # --- Construcción del grafo ---
    terms = leer_terminos()
    print(f"Términos leídos: {len(terms)} | Abstracts: {len(abstracts)}")

    cg = CooccurrenceGraph(terms=terms, min_cooccurrence=1)
    cg.build_from_abstracts(abstracts)

    # --- Resultados ---
    print(f"Nodos: {len(cg.G.nodes)} | Aristas: {len(cg.G.edges)}")
    print("\nTop grados de nodos:")
    print(cg.get_node_degrees().head(10))

    comps = cg.connected_components()
    print(f"\nComponentes conexas encontradas: {len(comps)}")
    for i, comp in enumerate(comps[:5], 1):
        print(f"  • Componente #{i} ({len(comp)} términos): {', '.join(list(comp)[:10])}...")

    # --- Filtrar solo las principales aristas ---
    cg.filtrar_aristas_principales(top_k=40)  # ajusta a 20, 30, 50 según quieras más o menos densidad

    # --- Guardar visualizaciones ---
    output_dir = "/home/ycmejia/Escritorio/Grafos/bibliometria-ia-grafos-uq-2025/seguimiento2/requerimiento2"
    os.makedirs(output_dir, exist_ok=True)  # Crea la carpeta si no existe

    png_path = os.path.join(output_dir, "grafo_coocurrencia_top.png")
    html_path = os.path.join(output_dir, "grafo_coocurrencia_top.html")

    cg.save_graph_png(png_path, show_weights=True)
    cg.save_graph_html(html_path)

    print(f"\n✅ Grafo reducido a las {len(cg.G.edges())} aristas principales")
    print(f"✅ Imagen PNG guardada en: {png_path}")
    print(f"✅ Grafo interactivo HTML guardado en: {html_path}")

