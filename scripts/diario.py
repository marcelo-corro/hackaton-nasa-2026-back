"""Actualización diaria: corre el pipeline en orden y, al final, los controles antes de publicar.

Pensado para GitHub Actions (repo de datos, .github/workflows/actualizar.yml), pero corre igual en local. No publica:
eso lo hace después scripts/10_publicar.py, solo si este script termina sin errores.

- Cada día: FIRMS del año (1b) → ingesta (2) → comunas (3) → calidad (4) → clima (5c) y viento (5d) → riesgo (8) →
  sectores (12), modelo B (12c) y alertas (12d) de Valparaíso → exportar (9, 13, 15, 16).
- Primera vez o caché vacía (carga completa): antes baja lo que falte y arma lo que no cambia a diario: archivo FIRMS
  2000-2025 y comunas (1), serie armonizada (5) y calendario (7), clima 2012-2025 (5b), capas de sectores (11) y
  parámetros de la zona de avance (14). Se detecta solo por los archivos que faltan; --carga-completa la fuerza.
- Se detiene en el primer paso que falle. Los controles (firecal.export.controles) revisan fecha del riesgo, 345
  comunas, contrato, archivos y que la MAP_KEY no aparezca; con algún error termina con código 1.

Uso:
    python scripts/diario.py                     # lo de cada día (y la carga completa si falta algo)
    python scripts/diario.py --carga-completa    # rehace también lo que no cambia a diario
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from firecal import config  # noqa: E402
from firecal.export.contrato import VERSION_CONTRATO  # noqa: E402
from firecal.export.controles import controles_publicacion  # noqa: E402

REGION = "05"
EN_ACTIONS = os.getenv("GITHUB_ACTIONS") == "true"


def falta_archivo_firms() -> bool:
    nombres = ("modis_2025_Chile.csv", "viirs-snpp_2025_Chile.csv", "viirs-jpss1_2025_Chile.csv")
    return not config.COMUNAS_SHP.exists() or not all((config.FIRMS_RAW_DIR / n).exists() for n in nombres)


def falta_serie_y_calendario() -> bool:
    pr = config.PROCESSED_DIR
    return not all((pr / n).exists() for n in ("serie_mensual.parquet", "calibracion.json", "calendario.parquet"))


def falta_clima_historico() -> bool:
    ruta = config.INTERIM_DIR / "clima_diario.parquet"
    if not ruta.exists():
        return True
    import pandas as pd  # solo si hace falta mirar el archivo
    fechas = pd.read_parquet(ruta, columns=None)
    col = next(c for c in fechas.columns if "fecha" in c)
    return pd.Timestamp(fechas[col].min()) > pd.Timestamp("2012-01-31")


def faltan_capas() -> bool:
    capas = config.DATA_DIR / "raw" / "sectores"
    return not all((capas / d).is_dir() and any((capas / d).iterdir()) for d in ("worldcover", "copernicus_dem", "wui", "osm"))


def falta_avance() -> bool:
    return not (config.PROCESSED_DIR / "avance_params.json").exists()


def pasos(completa: bool) -> list[list[str]]:
    """Lista de pasos (script y argumentos) en orden. La carga completa suma lo que falte."""
    cargar = {
        "firms": completa or falta_archivo_firms(),
        "serie": completa or falta_serie_y_calendario(),
        "clima": completa or falta_clima_historico(),
        "capas": completa or faltan_capas(),
        "avance": completa or falta_avance(),
    }
    print("Carga completa de:", ", ".join(k for k, v in cargar.items() if v) or "nada (solo lo de cada día)")
    p: list[list[str]] = []
    if cargar["firms"]:
        p.append(["01_descargar_datos"])
    p += [["01b_firms_reciente"], ["02_ingestar_firms"], ["03_asignar_comunas"], ["04_marcar_calidad"]]
    if cargar["serie"]:
        p += [["05_armonizar"], ["07_calendario"]]
    if cargar["clima"]:
        p.append(["05b_clima_diario"])
    p += [["05c_clima_reciente"], ["05d_viento_power"], ["08_riesgo"]]
    if cargar["capas"]:
        p.append(["11_descargar_capas", "--region", REGION])
    p += [["12_sectores", "--region", REGION], ["12c_modelo_sectores", "--region", REGION, "--prueba"],
          ["12d_validar_alertas", "--region", REGION]]
    if cargar["avance"]:
        p.append(["14_validar_avance"])
    p += [["09_exportar"], ["13_exportar_sectores", "--region", REGION], ["15_exportar_avance"], ["16_exportar_comunas"]]
    return p


def correr(paso: list[str]) -> tuple[int, float]:
    script = RAIZ / "scripts" / f"{paso[0]}.py"
    if EN_ACTIONS:
        print(f"::group::{' '.join(paso)}", flush=True)
    else:
        print(f"\n=== {' '.join(paso)}", flush=True)
    t0 = time.time()
    codigo = subprocess.run([sys.executable, str(script), *paso[1:]], cwd=RAIZ).returncode
    dt = time.time() - t0
    if EN_ACTIONS:
        print("::endgroup::", flush=True)
    print(f"{paso[0]}: {'OK' if codigo == 0 else f'FALLÓ (código {codigo})'} en {dt:.0f} s", flush=True)
    return codigo, dt


def resumen(hoy, tiempos: list[tuple[str, float]], errores: list[str], avisos: list[str]) -> str:
    """Texto para el resumen de la corrida en GitHub (o la consola)."""
    lineas = [f"## Actualización diaria · {hoy}", ""]
    try:
        pub = config.PUBLIC_DIR
        r = json.loads((pub / "riesgo" / "ultimo.json").read_text(encoding="utf-8"))
        a = json.loads((pub / "avance" / "activos.json").read_text(encoding="utf-8"))
        m = json.loads((pub / "manifest.json").read_text(encoding="utf-8"))
        altas = sum(i["nivel"] in ("alto", "muy_alto") for i in r["items"])
        lineas += [f"- Riesgo para el **{r['valido_para']}** (focos hasta {m.get('datos', {}).get('ultimo_dato_focos')}, "
                   f"clima hasta {m.get('datos', {}).get('clima_hasta')})",
                   f"- Comunas en nivel alto o muy alto (24 h): **{altas}** · incendios activos: **{len(a.get('incendios', []))}**",
                   f"- Contrato {m.get('contrato')}", ""]
    except Exception as e:  # el resumen nunca debe tapar el error real
        lineas += [f"- (sin resumen de datos: {e})", ""]
    lineas += ["| Paso | Segundos |", "|---|---|"] + [f"| {n} | {s:.0f} |" for n, s in tiempos] + [""]
    lineas += [f"- ❌ {e}" for e in errores] + [f"- ⚠️ {a}" for a in avisos]
    lineas.append("**Listo para publicar.**" if not errores else "**No se publica:** revisa los errores.")
    return "\n".join(lineas)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--carga-completa", action="store_true", help="rehace también lo que no cambia a diario")
    args = parser.parse_args()
    if not config.FIRMS_MAP_KEY:
        print("Falta FIRMS_MAP_KEY (en .env o como secreto del repo).")
        return 1
    hoy = datetime.now(ZoneInfo("America/Santiago")).date()
    tiempos: list[tuple[str, float]] = []
    errores: list[str] = []
    for paso in pasos(args.carga_completa):
        codigo, dt = correr(paso)
        tiempos.append((paso[0], dt))
        if codigo != 0:
            errores.append(f"falló {paso[0]} (código {codigo}); no se siguió con los demás pasos")
            break
    avisos: list[str] = []
    if not errores:
        errores, avisos = controles_publicacion(config.PUBLIC_DIR, hoy, VERSION_CONTRATO, config.FIRMS_MAP_KEY)
    texto = resumen(hoy, tiempos, errores, avisos)
    print("\n" + texto)
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(texto + "\n")
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
