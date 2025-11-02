# config.py
# === CONFIGURACIÓN DEL PROYECTO ===

import platform
from pathlib import Path

# === DETECTAR SISTEMA OPERATIVO ===
SO = platform.system()

# === BASE DEL PROYECTO SEGÚN EL USUARIO ===
if SO == "Windows":
    # ⚠️ Ajusta solo esta ruta si cambias de computador
    BASE_DIR = Path(r"C:\Users\USER\Desktop\YAN\Carpeta Universidad\decimo-semestre\Analisis-de-algoritmos\Proyecto-final-algoritmos")
else:
    # ⚠️ Ruta base en Ubuntu o Linux
    BASE_DIR = Path("/home/ycmejia/Escritorio/PROYECTO ALGORITMOS")

# === CHROMEDRIVER ===
if SO == "Windows":
    CHROMEDRIVER_PATH = BASE_DIR / "chromedriver.exe"
else:
    # En Linux normalmente se instala vía apt
    CHROMEDRIVER_PATH = Path("/usr/bin/chromedriver")

# === RUTAS DE DESCARGA ===
DOWNLOAD_DIR_SAGE = BASE_DIR / "bases_de_datos" / "Sage_Journals"
DOWNLOAD_DIR_SCIENCEDIRECT = BASE_DIR / "bases_de_datos" / "science_direct"

# === DIRECTORIO DE SALIDA ===
OUTPUT_DIR_BIBLIO = BASE_DIR / "salidas"

# === URLS IMPORTANTES ===
URL_LOGIN = "https://library.uniquindio.edu.co/databases"
SCIENCEDIRECT_URL = "https://www-sciencedirect-com.crai.referencistas.com/"

# === CREDENCIALES ===
USUARIO = "yarleyc.mejiab@uqvirtual.edu.co"
CONTRASENA = "Familia967vfg15a"

# === CREAR CARPETAS SI NO EXISTEN (opcional, útil para evitar errores) ===
for path in [DOWNLOAD_DIR_SAGE, DOWNLOAD_DIR_SCIENCEDIRECT, OUTPUT_DIR_BIBLIO]:
    path.mkdir(parents=True, exist_ok=True)
