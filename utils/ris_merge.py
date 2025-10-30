# utils/ris_merge.py
import os, re, unicodedata, json
from typing import List, Dict, Tuple, Iterable
import pandas as pd

# -------------------- utilidades --------------------

def _norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def _norm_doi(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip().replace("\\", "/").replace(" ", "")
    s = re.sub(r"(?i)^doi:\s*", "", s)
    s = re.sub(r"(?i)^https?://(dx\.)?doi\.org/", "", s)
    return s.strip().lower()

def _canon_title(t: str) -> str:
    if not t:
        return ""
    s = t.strip().lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return _norm_spaces(s)

def _year_from_py(py: str) -> str:
    if not py:
        return ""
    m = re.search(r"\d{4}", py)
    return m.group(0) if m else ""

def _read_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="latin-1") as f:
            return f.read()

def _looks_like_ris(txt: str) -> bool:
    # Heurística simple: debe haber varias líneas con TAG "XX  - "
    lines = txt.splitlines()
    hits = 0
    for ln in lines[:200]:  # revisa primeras 200 líneas
        if re.match(r"^[A-Z0-9]{2}\s*-\s+", ln):
            hits += 1
        if hits >= 3:
            return True
    return False

# -------------------- PARSEADOR RIS --------------------

def parse_ris_text(txt: str, source_db: str, source_file: str) -> List[Dict]:
    lines = txt.splitlines()
    recs = []
    cur = {}
    authors = []
    keywords = []

    def _flush():
        if not cur:
            return
        if authors:
            cur["authors"] = authors.copy()
        if keywords:
            cur["keywords"] = list(dict.fromkeys([_norm_spaces(k) for k in keywords if k.strip()]))
        cur["doi_norm"] = _norm_doi(cur.get("doi", ""))
        title_main = cur.get("title", "") or cur.get("ti", "")
        cur["title_canon"] = _canon_title(title_main)
        cur.setdefault("sources", []).append(source_db)
        cur.setdefault("source_files", []).append(source_file)
        recs.append(cur.copy())

    for raw in lines:
        m = re.match(r"^([A-Z0-9]{2})\s*-\s*(.*)$", raw)
        if not m:
            continue
        tag, val = m.group(1), (m.group(2) or "").rstrip()

        if tag == "TY":
            if cur:
                _flush()
            cur = {"ty": val}
            authors = []
            keywords = []
        elif tag == "ER":
            _flush()
            cur = {}
            authors = []
            keywords = []
        elif tag in ("T1", "TI"):
            cur["title"] = _norm_spaces(val); cur["ti"] = cur["title"]
        elif tag in ("T2", "JF", "JO"):
            cur["journal"] = _norm_spaces(val)
        elif tag == "AU":
            if val.strip(): authors.append(_norm_spaces(val))
        elif tag in ("PY", "Y1"):
            cur["year"] = _year_from_py(val); cur["date"] = val.strip()
        elif tag == "DA":
            cur["date"] = _norm_spaces(val)
        elif tag in ("AB", "N2"):
            cur["abstract"] = max([cur.get("abstract", ""), _norm_spaces(val)], key=len)
        elif tag == "KW":
            if val.strip(): keywords.append(val)
        elif tag == "DO":
            cur["doi"] = _norm_doi(val)
        elif tag == "UR":
            cur["url"] = val.strip()
        elif tag == "SN":
            cur["issn"] = _norm_spaces(val)
        elif tag == "VL":
            cur["volume"] = _norm_spaces(val)
        elif tag == "IS":
            cur["issue"] = _norm_spaces(val)
        elif tag == "SP":
            cur["page_start"] = _norm_spaces(val)
        elif tag == "EP":
            cur["page_end"] = _norm_spaces(val)

    return recs

def parse_ris_file(path: str, source_db: str = "") -> List[Dict]:
    txt = _read_text(path)
    if not _looks_like_ris(txt):
        return []
    return parse_ris_text(txt, source_db=source_db or "unknown", source_file=path)

# -------------------- DISCOVERY --------------------

def _iter_candidate_files(folder: str, exts: Iterable[str]) -> Iterable[str]:
    exts_l = tuple(e.lower() for e in exts)
    for root, _, files in os.walk(folder):
        for fn in files:
            if fn.lower().endswith(exts_l):
                yield os.path.join(root, fn)

def load_ris_from_dirs(dirs: List[Tuple[str, str]], exts: Iterable[str]=(".ris",".RIS",".txt",".TXT"), verbose: bool=True) -> List[Dict]:
    """
    dirs: lista de (ruta_carpeta, etiqueta_source_db)
    """
    out = []
    for folder, source in dirs:
        if not folder or not os.path.isdir(folder):
            if verbose:
                print(f"⚠️ Carpeta no existe o no es válida: {folder}")
            continue

        cand = list(_iter_candidate_files(folder, exts))
        if verbose:
            print(f"📂 {source:<13} -> {folder}")
            print(f"   Archivos candidatos ({', '.join(exts)}): {len(cand)}")
            for p in cand[:5]:
                print(f"   - {p}")

        count_before = len(out)
        for path in cand:
            try:
                recs = parse_ris_file(path, source_db=source)
                out.extend(recs)
            except Exception as e:
                print(f"⚠️ Error parseando {path}: {e}")

        if verbose:
            print(f"   Registros RIS válidos añadidos: {len(out)-count_before}")

    return out

# -------------------- DEDUP & EXPORT --------------------

def _prefer(a: str, b: str) -> str:
    a = (a or "").strip(); b = (b or "").strip()
    if a and not b: return a
    if b and not a: return b
    return a if len(a) >= len(b) else b

def _merge_lists(a: List[str], b: List[str]) -> List[str]:
    merged, seen = [], set()
    for item in (a or []) + (b or []):
        key = item.strip()
        if key and key.lower() not in seen:
            seen.add(key.lower()); merged.append(key)
    return merged

def merge_records(records: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    by_key, dups = {}, []

    def key_for(r):
        if r.get("doi_norm"): return ("doi", r["doi_norm"])
        return ("title", r.get("title_canon", ""))

    def merge_two(dst: Dict, src: Dict):
        for k in ["title","journal","year","date","abstract","doi","url","issn","volume","issue","page_start","page_end"]:
            dst[k] = _prefer(dst.get(k, ""), src.get(k, ""))
        dst["authors"]     = _merge_lists(dst.get("authors", []), src.get("authors", []))
        dst["keywords"]    = _merge_lists(dst.get("keywords", []), src.get("keywords", []))
        dst["sources"]     = _merge_lists(dst.get("sources", []), src.get("sources", []))
        dst["source_files"]= _merge_lists(dst.get("source_files", []), src.get("source_files", []))
        dst["doi_norm"]    = _norm_doi(dst.get("doi", "") or dst.get("doi_norm",""))
        dst["title_canon"] = _canon_title(dst.get("title","")) or dst.get("title_canon","")

    for r in records:
        k = key_for(r)
        if not k[1]:
            by_key[("row", id(r))] = r
            continue
        if k not in by_key:
            by_key[k] = r
        else:
            kept = by_key[k]
            dups.append({
                "dedupe_key_type": k[0],
                "dedupe_key_value": k[1],
                "kept_title": kept.get("title",""),
                "kept_doi": kept.get("doi",""),
                "kept_sources": "; ".join(kept.get("sources", [])),
                "dropped_title": r.get("title",""),
                "dropped_doi": r.get("doi",""),
                "dropped_sources": "; ".join(r.get("sources", [])),
                "dropped_file": "; ".join(r.get("source_files", [])),
            })
            merge_two(kept, r)

    result = list(by_key.values())
    def _year_num(x):
        try: return int((x.get("year") or "0")[:4])
        except: return 0
    result.sort(key=lambda x: (-_year_num(x), x.get("title","").lower()))
    return result, dups

def records_to_dataframe(records: List[Dict]) -> pd.DataFrame:
    rows = []
    for r in records:
        rows.append({
            "title": r.get("title",""),
            "authors": "; ".join(r.get("authors", [])),
            "year": r.get("year",""),
            "date": r.get("date",""),
            "journal": r.get("journal",""),
            "doi": r.get("doi",""),
            "url": r.get("url",""),
            "abstract": r.get("abstract",""),
            "keywords": "; ".join(r.get("keywords", [])),
            "issn": r.get("issn",""),
            "volume": r.get("volume",""),
            "issue": r.get("issue",""),
            "page_start": r.get("page_start",""),
            "page_end": r.get("page_end",""),
            "sources": "; ".join(r.get("sources", [])),
            "source_files": "; ".join(r.get("source_files", [])),
        })
    return pd.DataFrame(rows)

def duplicates_to_dataframe(dups: List[Dict]) -> pd.DataFrame:
    return pd.DataFrame(dups)

def export_outputs(unified: List[Dict], duplicates: List[Dict], out_dir: str, base_name: str="unificado"):
    os.makedirs(out_dir, exist_ok=True)
    df_u = records_to_dataframe(unified)
    df_d = duplicates_to_dataframe(duplicates)

    csv_u = os.path.join(out_dir, f"{base_name}.csv")
    csv_d = os.path.join(out_dir, f"{base_name}_duplicados_eliminados.csv")
    jsonl_u = os.path.join(out_dir, f"{base_name}.jsonl")

    df_u.to_csv(csv_u, index=False, encoding="utf-8-sig")
    df_d.to_csv(csv_d, index=False, encoding="utf-8-sig")
    with open(jsonl_u, "w", encoding="utf-8") as f:
        for r in unified:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"✅ Unificado deduplicado -> {csv_u}")
    print(f"✅ Duplicados eliminados -> {csv_d}")
    print(f"✅ JSONL (para app)     -> {jsonl_u}")
