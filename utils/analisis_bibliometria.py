#!/usr/bin/env python3
import os, time
import pandas as pd
import matplotlib.pyplot as plt
from collections import Counter

# ---------- Rutas ----------
INPUT = "/home/ycmejia/Escritorio/PROYECTO ALGORITMOS/salidas/unificado_ai_generativa.csv"
OUTDIR = "salida_bibliometria"
os.makedirs(OUTDIR, exist_ok=True)

# ---------- Carga de datos ----------
df = pd.read_csv(INPUT)
df["year"] = pd.to_numeric(df.get("year", 0), errors="coerce").fillna(0).astype(int)
df["title"] = df.get("title", df.columns[0]).astype(str)

# ---------- Ordenar productos ----------
sorted_df = df.sort_values(["year", "title"], ascending=[True, True])
sorted_df.to_csv(f"{OUTDIR}/sorted_products.csv", index=False)

# ---------- Top-15 autores ----------
if "authors" not in df.columns:
    df["authors"] = df["author"] if "author" in df.columns else ""
counts = Counter()
for cell in df["authors"].astype(str):
    parts = [p.strip() for p in cell.replace("\n",";").replace(",",";").split(";") if p.strip()]
    for p in parts: counts[p] += 1
top_authors = pd.DataFrame(counts.most_common(15), columns=["author","count"])\
                 .sort_values("count", ascending=True)
top_authors.to_csv(f"{OUTDIR}/top15_autores.csv", index=False)

# ---------- Clave entera ----------
def clave(row):
    return int(row["year"]) * 100000 + (hash(row["title"]) & 0xFFFF)
claves = [clave(r) for _, r in df.iterrows()]

# ==============================================================
# =============== ALGORITMOS DE ORDENAMIENTO ===================
# ==============================================================
# ============================
# ORDENAMIENTOS EN ESPAÑOL
# ============================

def timsort(lista):
    """
    TimSort: combina Insertion Sort en bloques pequeños (runs)
    y luego los fusiona con Merge Sort.
    """
    arreglo = list(lista)
    BLOQUE = 32  # tamaño mínimo de cada run

    def insertion_sort(inicio, fin):
        for i in range(inicio + 1, fin + 1):
            clave = arreglo[i]
            j = i - 1
            while j >= inicio and arreglo[j] > clave:
                arreglo[j + 1] = arreglo[j]
                j -= 1
            arreglo[j + 1] = clave

    def merge(inicio, medio, fin):
        izquierda = arreglo[inicio:medio + 1]
        derecha   = arreglo[medio + 1:fin + 1]
        i = j = 0
        k = inicio
        while i < len(izquierda) and j < len(derecha):
            if izquierda[i] <= derecha[j]:
                arreglo[k] = izquierda[i]; i += 1
            else:
                arreglo[k] = derecha[j]; j += 1
            k += 1
        while i < len(izquierda):
            arreglo[k] = izquierda[i]; i += 1; k += 1
        while j < len(derecha):
            arreglo[k] = derecha[j]; j += 1; k += 1

    total = len(arreglo)
    for inicio in range(0, total, BLOQUE):
        fin = min(inicio + BLOQUE - 1, total - 1)
        insertion_sort(inicio, fin)

    tamaño = BLOQUE
    while tamaño < total:
        for inicio in range(0, total, 2 * tamaño):
            medio = min(total - 1, inicio + tamaño - 1)
            fin   = min(inicio + 2 * tamaño - 1, total - 1)
            if medio < fin:
                merge(inicio, medio, fin)
        tamaño *= 2
    return arreglo


def selection(lista):
    """Selection Sort: busca el mínimo y lo coloca al frente."""
    arreglo = list(lista)
    for i in range(len(arreglo)):
        minimo = i
        for j in range(i + 1, len(arreglo)):
            if arreglo[j] < arreglo[minimo]:
                minimo = j
        arreglo[i], arreglo[minimo] = arreglo[minimo], arreglo[i]
    return arreglo


def comb(lista):
    """Comb Sort: mejora de Bubble Sort con 'salto' decreciente."""
    arreglo = list(lista)
    salto = len(arreglo)
    factor_reduccion = 1.3
    intercambio = True
    while salto > 1 or intercambio:
        salto = max(1, int(salto / factor_reduccion))
        intercambio = False
        for i in range(len(arreglo) - salto):
            if arreglo[i] > arreglo[i + salto]:
                arreglo[i], arreglo[i + salto] = arreglo[i + salto], arreglo[i]
                intercambio = True
    return arreglo


def quick(lista):
    """QuickSort: divide en menores, iguales y mayores que el pivote."""
    arreglo = list(lista)
    if len(arreglo) <= 1:
        return arreglo
    pivote = arreglo[len(arreglo) // 2]
    menores = [x for x in arreglo if x < pivote]
    iguales = [x for x in arreglo if x == pivote]
    mayores = [x for x in arreglo if x > pivote]
    return quick(menores) + iguales + quick(mayores)


def heap(lista):
    """HeapSort: usa un montículo (heap) para extraer el mínimo repetidamente."""
    import heapq
    arreglo = list(lista)
    heapq.heapify(arreglo)
    return [heapq.heappop(arreglo) for _ in range(len(arreglo))]


def gnome(lista):
    """Gnome Sort: camina adelante y atrás intercambiando elementos desordenados."""
    arreglo = list(lista)
    indice = 0
    while indice < len(arreglo):
        if indice == 0 or arreglo[indice] >= arreglo[indice - 1]:
            indice += 1
        else:
            arreglo[indice], arreglo[indice - 1] = arreglo[indice - 1], arreglo[indice]
            indice -= 1
    return arreglo


def binary_insertion(lista):
    """Insertion Sort con búsqueda binaria para encontrar la posición."""
    from bisect import insort
    resultado = []
    for elemento in lista:
        insort(resultado, elemento)
    return resultado


def radix(lista):
    """Radix Sort: ordena enteros por dígitos (base 10)."""
    arreglo = list(lista)
    if not arreglo:
        return arreglo
    maximo = max(arreglo)
    exp = 1
    while maximo // exp > 0:
        cubetas = [[] for _ in range(10)]
        for numero in arreglo:
            cubetas[(numero // exp) % 10].append(numero)
        arreglo = [num for cubeta in cubetas for num in cubeta]
        exp *= 10
    return arreglo


def bucket(lista):
    """Bucket Sort: reparte los elementos en cubetas y ordena cada una."""
    arreglo = list(lista)
    if not arreglo:
        return arreglo
    minimo, maximo = min(arreglo), max(arreglo)
    cantidad_cubetas = max(1, int(len(arreglo) ** 0.5))
    tamaño = (maximo - minimo) / cantidad_cubetas + 1e-9
    cubetas = [[] for _ in range(cantidad_cubetas)]
    for numero in arreglo:
        indice = int((numero - minimo) // tamaño)
        cubetas[indice].append(numero)
    resultado = []
    for cubeta in cubetas:
        resultado.extend(sorted(cubeta))
    return resultado


def pigeonhole(lista):
    """Pigeonhole Sort: cuenta cuántas veces aparece cada número (enteros)."""
    arreglo = list(lista)
    if not arreglo:
        return arreglo
    minimo, maximo = min(arreglo), max(arreglo)
    huecos = [0] * (maximo - minimo + 1)
    for numero in arreglo:
        huecos[numero - minimo] += 1
    resultado = []
    for indice, cantidad in enumerate(huecos):
        resultado.extend([indice + minimo] * cantidad)
    return resultado


def tree(lista):
    """Tree Sort: inserta los elementos en un árbol binario y recorre en orden."""

    class Nodo:
        __slots__ = ("valor", "izquierda", "derecha")

        def __init__(self, valor):
            self.valor = valor
            self.izquierda = None
            self.derecha = None

        def insertar(self, x):
            if x < self.valor:
                if self.izquierda:
                    self.izquierda.insertar(x)
                else:
                    self.izquierda = Nodo(x)
            else:
                if self.derecha:
                    self.derecha.insertar(x)
                else:
                    self.derecha = Nodo(x)

        def recorrido(self, resultado):
            if self.izquierda: self.izquierda.recorrido(resultado)
            resultado.append(self.valor)
            if self.derecha: self.derecha.recorrido(resultado)

    arreglo = list(lista)
    if not arreglo:
        return arreglo
    iterador = iter(arreglo)
    raiz = Nodo(next(iterador))
    for x in iterador:
        raiz.insertar(x)
    resultado = []
    raiz.recorrido(resultado)
    return resultado


def bitonic(lista):
    """
    Bitonic Sort: funciona para tamaños potencia de 2.
    Si no lo es, se rellena con el máximo para completar.
    """
    arreglo = list(lista)
    n = 1
    while n < len(arreglo):
        n *= 2
    arreglo += [max(arreglo)] * (n - len(arreglo))

    def comparar_e_intercambiar(i, j, ascendente):
        if (arreglo[i] > arreglo[j]) == ascendente:
            arreglo[i], arreglo[j] = arreglo[j], arreglo[i]

    def fusion_bitonica(inicio, conteo, ascendente):
        if conteo > 1:
            mitad = conteo // 2
            for i in range(inicio, inicio + mitad):
                comparar_e_intercambiar(i, i + mitad, ascendente)
            fusion_bitonica(inicio, mitad, ascendente)
            fusion_bitonica(inicio + mitad, mitad, ascendente)

    def ordenar_bitonico(inicio, conteo, ascendente):
        if conteo > 1:
            mitad = conteo // 2
            ordenar_bitonico(inicio, mitad, True)
            ordenar_bitonico(inicio + mitad, mitad, False)
            fusion_bitonica(inicio, conteo, ascendente)

    ordenar_bitonico(0, n, True)
    return arreglo[:len(lista)]

# ---------- Lista de algoritmos ----------
ALGORITHMS = [
    ("TimSort", timsort),
    ("SelectionSort", selection),
    ("CombSort", comb),
    ("QuickSort", quick),
    ("HeapSort", heap),
    ("GnomeSort", gnome),
    ("BinaryInsertionSort", binary_insertion),
    ("RadixSort", radix),
    ("BucketSort", bucket),
    ("PigeonholeSort", pigeonhole),
    ("TreeSort", tree),
    ("BitonicSort", bitonic),
]

# ---------- Medir tiempos ----------
results = []
for name, fn in ALGORITHMS:
    data = claves[:]          # copia para no alterar la original
    t0 = time.perf_counter()
    fn(data)
    t1 = time.perf_counter()
    results.append({"algoritmo": name, "tamaño": len(claves), "tiempo_s": t1 - t0})

times_df = pd.DataFrame(results).sort_values("tiempo_s")
times_df.to_csv(f"{OUTDIR}/tiempos_ordenamiento.csv", index=False)

# ---------- Gráfico ----------
plt.figure(figsize=(10,6))
plt.barh(times_df["algoritmo"], times_df["tiempo_s"])
plt.xlabel("Tiempo (s)")
plt.ylabel("Algoritmo")
plt.title(f"Tiempos de ordenamiento (Cantidad de Archivos={len(claves)})")
plt.tight_layout()
plt.savefig(f"{OUTDIR}/tiempos_barras.png")
print("Archivos generados en:", os.path.abspath(OUTDIR))