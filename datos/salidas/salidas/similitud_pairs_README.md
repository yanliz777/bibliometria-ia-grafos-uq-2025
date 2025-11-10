# Informe de similitud textual (Requerimiento 2)

**Objetivo:** Dada una selección de 2+ artículos, se extrae su *abstract* (o *title* si falta) y se mide la similitud por 6 algoritmos:
- 4 clásicos: **Levenshtein**, **Jaccard (bigramas)**, **Dice (bigramas)**, **Coseno (TF-IDF)**.
- 2 con IA: **Sentence-BERT all-MiniLM-L6-v2** (st_en) y **paraphrase-multilingual-MiniLM-L12-v2** (st_multi).

**Lectura de valores:** escala 0–1 (↑ es más similar). Umbrales: ≥0.70 muy alta, 0.40–0.69 moderada, 0.10–0.39 baja, <0.10 muy baja.

## Top 3 pares por similitud (IA - inglés (st_en))

| i | j | lev | jac | dice | tfidf | st_en | st_multi | interpretación |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 0 | 1 | 0.208 | 0.014 | 0.028 | 0.277 | 0.591 | 0.601 | moderada |
| 1 | 2 | 0.005 | 0.000 | 0.000 | 0.000 | 0.101 | 0.049 | baja |
| 0 | 2 | 0.006 | 0.000 | 0.000 | 0.000 | 0.032 | 0.012 | muy baja |

## Ejemplos explicados
- **Par (0, 1)** — interpretación *moderada* por **IA - inglés (st_en)**.
  - **Título A:** A generative artificial intelligence-enhanced multiagent approach to empowering collaborative problem solving across dif
  - **Título B:** A systematic literature review on designing self-regulated learning using generative artificial intelligence and its fut
  - *Apoyo clásico:* TF-IDF=0.277, Jaccard=0.014, Dice=0.028, Levenshtein=0.208.
- **Par (1, 2)** — interpretación *baja* por **IA - inglés (st_en)**.
  - **Título A:** A systematic literature review on designing self-regulated learning using generative artificial intelligence and its fut
  - **Título B:** Authenticity and academic integrity in Generative Artificial Intelligence (GenAI) use among undergraduate nursing studen
  - *Apoyo clásico:* TF-IDF=0.000, Jaccard=0.000, Dice=0.000, Levenshtein=0.005.
- **Par (0, 2)** — interpretación *muy baja* por **IA - inglés (st_en)**.
  - **Título A:** A generative artificial intelligence-enhanced multiagent approach to empowering collaborative problem solving across dif
  - **Título B:** Authenticity and academic integrity in Generative Artificial Intelligence (GenAI) use among undergraduate nursing studen
  - *Apoyo clásico:* TF-IDF=0.000, Jaccard=0.000, Dice=0.000, Levenshtein=0.006.
