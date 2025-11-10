from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess, shlex, uuid, os
from pathlib import Path
from datetime import datetime

app = FastAPI(title="Mini Job Runner")

# Carpeta donde se guardan resultados y logs
BASE_DIR = Path(os.environ.get("OUT_BASE", "/data"))
BASE_DIR.mkdir(parents=True, exist_ok=True)

class RunReq(BaseModel):
    script: str
    args: list[str] | None = None

@app.post("/run")
def run(req: RunReq, bg: BackgroundTasks):
    scripts = {
        "similarity": "main_similarity.py",
        "terminos": "main_terminos_es.py",
        "cluster": "main_cluster.py",
        "req5": "main_req5.py",
    }
    if req.script not in scripts:
        raise HTTPException(400, f"Script no permitido: {req.script}")

    task_id = str(uuid.uuid4())[:8]
    out_dir = BASE_DIR / task_id
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "run.log"

    cmd = f"python3 scripts/{scripts[req.script]} " + " ".join(shlex.quote(a) for a in (req.args or []))

    def run_bg():
        with open(log_path, "w") as lf:
            lf.write(f"Inicio: {datetime.utcnow().isoformat()}\nComando: {cmd}\n\n")
            lf.flush()
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in proc.stdout:
                lf.write(line)
                lf.flush()
            proc.wait()
            lf.write(f"\nFinalizado con código {proc.returncode}\n")

    bg.add_task(run_bg)
    return {"task_id": task_id, "log_url": f"/logs/{task_id}", "files_url": f"/files/{task_id}"}

@app.get("/logs/{task_id}")
def get_log(task_id: str):
    path = BASE_DIR / task_id / "run.log"
    if not path.exists():
        raise HTTPException(404, "Log no encontrado (aún corriendo o ID incorrecto)")
    return FileResponse(path)

@app.get("/files/{task_id}")
def list_files(task_id: str):
    task_dir = BASE_DIR / task_id
    if not task_dir.exists():
        raise HTTPException(404, "Tarea no encontrada")
    files = [str(p.relative_to(BASE_DIR / task_id)) for p in task_dir.rglob("*") if p.is_file()]
    return {"task_id": task_id, "files": files}

@app.get("/files/{task_id}/{file_path:path}")
def get_file(task_id: str, file_path: str):
    path = BASE_DIR / task_id / file_path
    if not path.exists():
        raise HTTPException(404, "Archivo no encontrado")
    return FileResponse(path)
