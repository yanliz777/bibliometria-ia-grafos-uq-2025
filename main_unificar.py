# main_unificar.py
import os
import config
from utils.ris_merge import load_ris_from_dirs, merge_records, export_outputs

def _exists(p: str) -> bool:
    return bool(p) and os.path.isdir(p)

if __name__ == "__main__":
    # 1) Construimos la lista de raíces a inspeccionar (orden de prioridad)
    roots = [
        getattr(config, "DOWNLOAD_DIR_SAGE", r"C:\Users\USER\Desktop\proyecto-final-algoritmos\Sage_Journals"),
        getattr(config, "DOWNLOAD_DIR_SCIENCEDIRECT", r"C:\Users\USER\Desktop\proyecto-final-algoritmos\science_direct"),
        getattr(config, "DOWNLOAD_DIR", ""),  # por compatibilidad con scripts previos
        os.path.join(os.path.expanduser("~"), "Downloads"),  # Descargas por defecto de Windows
        os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir)),  # raíz del proyecto
    ]

    # Normalizamos: existentes, únicos y en el mismo orden
    uniq = []
    seen = set()
    for r in roots:
        if _exists(r) and r not in seen:
            uniq.append(r); seen.add(r)

    print("📚 Directorios a inspeccionar:")
    for d in uniq:
        print(" -", d)

    # 2) Disparamos la carga/parsing en todas las raíces
    pairs = [(d, os.path.basename(d) or d) for d in uniq]
    print("\n📥 Buscando archivos .ris / .txt ...")
    registros = load_ris_from_dirs(
        pairs,
        exts=(".ris", ".RIS", ".txt", ".TXT"),
        verbose=True
    )

    # 3) Deduplicación y export
    print(f"\n🧮 Unificando y deduplicando por DOI y Título ...")
    print(f"   → Registros leídos (incluye duplicados): {len(registros)}")
    unificados, duplicados = merge_records(registros)
    print(f"   → Registros unificados (sin duplicados): {len(unificados)}")
    print(f"   → Duplicados detectados: {len(duplicados)}")

    out_dir = getattr(config, "OUTPUT_DIR_BIBLIO", r"C:\Users\USER\Desktop\proyecto-final-algoritmos\salidas")
    print("\n💾 Exportando archivos ...")
    os.makedirs(out_dir, exist_ok=True)
    export_outputs(unificados, duplicados, out_dir, base_name="unificado_ai_generativa")

    print("\n✅ Listo. Archivos en:", out_dir)
