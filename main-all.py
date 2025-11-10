import argparse
import os
import sys
import time
import subprocess
from pathlib import Path

# ---------- Ajusta si tu estructura difiere ----------
SCRIPTS = {
    "r1": ["main_pipeline.py"],     # Requerimiento 1 (descarga + unificación)
    "r2": ["main_similarity.py"],   # Requerimiento 2 (similitudes)
    "r3": ["main_terminos_es.py"],  # Requerimiento 3 (términos/frecuencias)
    "r4": ["main_cluster.py"],      # Requerimiento 4 (clustering + dendrogramas)
    "r5": ["main_req5.py"],         # Requerimiento 5 (mapa + nube dinámica + timeline + PDF)
}

# Carpeta de salidas (para el log). Mantén la misma que usan tus scripts:
DEFAULT_OUT_DIR = Path(r"C:\Users\USER\Desktop\proyecto-final-algoritmos\salidas")

def run_step(step_key: str, cmd_parts: list[str], logfh, stop_on_error: bool) -> tuple[bool, float, str]:
    """Ejecuta un paso con subprocess, logea stdout/stderr, devuelve (ok, segundos, msg)."""
    start = time.time()
    py = sys.executable  # ejecutable python actual
    cmd = [py] + cmd_parts

    logfh.write(f"\n===== START {step_key} :: {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    logfh.write(f"CMD: {' '.join(cmd)}\n")
    logfh.flush()

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
    except Exception as e:
        secs = time.time() - start
        msg = f"{step_key} ERROR lanzando proceso: {e}"
        logfh.write(msg + "\n")
        logfh.flush()
        return False, secs, msg

    secs = time.time() - start
    # Log detallado
    if proc.stdout:
        logfh.write("--- STDOUT ---\n")
        logfh.write(proc.stdout + "\n")
    if proc.stderr:
        logfh.write("--- STDERR ---\n")
        logfh.write(proc.stderr + "\n")

    ok = (proc.returncode == 0)
    status = "OK" if ok else f"FAIL (rc={proc.returncode})"
    msg = f"{step_key} {status} en {secs:.1f}s"
    logfh.write(msg + "\n")
    logfh.write(f"===== END {step_key} =====\n")
    logfh.flush()

    if (not ok) and stop_on_error:
        return False, secs, msg
    return ok, secs, msg


def parse_args():
    p = argparse.ArgumentParser(
        description="Orquestador de Requerimientos 1→5")
    p.add_argument("--only", type=str, default="",
                   help="Ejecutar solo estos pasos (coma): r1,r2,r3,r4,r5")
    p.add_argument("--skip", type=str, default="",
                   help="Saltar estos pasos (coma): r2,r5")
    p.add_argument("--no-stop-on-error", action="store_true",
                   help="No detener si falla un paso; continuar con los siguientes.")
    p.add_argument("--out-dir", type=str, default=str(DEFAULT_OUT_DIR),
                   help="Carpeta para el log consolidado (por defecto coincide con tus scripts).")
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "main_all.log"

    # Determinar orden de ejecución
    order = ["r1", "r2", "r3", "r4", "r5"]
    if args.only.strip():
        wanted = [k.strip().lower() for k in args.only.split(",") if k.strip()]
        order = [k for k in order if k in wanted]
    if args.skip.strip():
        skips = {k.strip().lower() for k in args.skip.split(",") if k.strip()}
        order = [k for k in order if k not in skips]

    print("\n# MAIN ALL — Orquestador Reqs 1→5")
    print("Pasos a ejecutar:", ", ".join(order) if order else "(ninguno)")
    print(f"Log consolidado: {log_path}\n")

    results = []
    t0 = time.time()
    stop_on_error = not args.no_stop_on_error

    with open(log_path, "a", encoding="utf-8") as logfh:
        logfh.write("\n================ EJECUCIÓN INICIADA ================\n")
        logfh.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        logfh.write(f"Python: {sys.version}\n")
        logfh.write(f"Working dir: {os.getcwd()}\n")

        for k in order:
            script_parts = SCRIPTS.get(k)
            if not script_parts:
                msg = f"{k} SKIP (no definido)"
                print(msg)
                logfh.write(msg + "\n")
                results.append((k, False, 0.0, "no definido"))
                continue

            print(f"→ Ejecutando {k}: {script_parts[0]} ...")
            ok, secs, msg = run_step(k, script_parts, logfh, stop_on_error)
            print("   ", msg)
            results.append((k, ok, secs, msg))
            if not ok and stop_on_error:
                print("\nSe detuvo por error (usar --no-stop-on-error para continuar).")
                break

    total_secs = time.time() - t0

    # Resumen final
    print("\n# RESUMEN")
    for k, ok, secs, msg in results:
        status = "OK" if ok else "FAIL"
        print(f"  {k}: {status}  ({secs:.1f}s)")
    print(f"\nTiempo total: {total_secs:.1f}s")
    print(f"Revisa el log: {log_path}")
    print("\nArtefactos finales esperados (según cada script):")
    print("  - Req1: CSV unificado y JSONL/CSV de duplicados (según tu pipeline).")
    print("  - Req2: similitud_pairs.csv + README explicativo.")
    print("  - Req3: req3_frecuencias_semillas.csv/.png, req3_nuevos_terminos.csv/.png, etc.")
    print("  - Req4: dendrogramas_.png, req4_metricas.csv/json, req4_asignaciones_.csv.")
    print("  - Req5: req5_mapa_paises.png, req5_nube_palabras.png, req5_timeline_revistas.png, req5_report.pdf.")

if __name__ == "__main__":
    main()
