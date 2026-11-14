"""Paso 1 del pipeline: descarga (o verifica) los datos públicos en data/raw/ y deja un registro.

Fuentes (detalle y citas en docs/fuentes.md):
- NASA FIRMS, archivos anuales por país: MODIS (2000-2025), VIIRS Suomi NPP (2012-2025) y
  VIIRS NOAA-20 (2018-2025; en FIRMS la carpeta se llama `viirs-jpss1`).
- Biblioteca del Congreso Nacional (BCN): límites comunales de Chile (shapefile).

Si un archivo ya existe y su tamaño coincide con el del servidor, no se vuelve a bajar.
Cada archivo queda anotado en data/raw/registro_descargas.csv (URL, tamaño, SHA-256, estado, fecha).

Uso:
    python scripts/01_descargar_datos.py                          # todo
    python scripts/01_descargar_datos.py --solo viirs-jpss1 comunas
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parents[1]
RAW = RAIZ / "data" / "raw"
FIRMS_DIR = RAW / "firms"
COMUNAS_DIR = RAW / "comunas"
REGISTRO = RAW / "registro_descargas.csv"

PAIS = "Chile"
FIRMS_BASE = "https://firms.modaps.eosdis.nasa.gov/data/country"
FIRMS_ANIOS = {
    "modis": range(2000, 2026),
    "viirs-snpp": range(2012, 2026),
    "viirs-jpss1": range(2018, 2026),  # NOAA-20
}
COMUNAS_URL = "https://www.bcn.cl/obtienearchivo?id=repositorio/10221/10396/5/comunas_final.zip"

CAMPOS_REGISTRO = ["fecha_utc", "fuente", "url", "archivo", "bytes", "sha256", "estado"]


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _tamano_remoto(sesion: requests.Session, url: str) -> int | None:
    """Tamaño según el servidor; None si no lo informa. Lanza FileNotFoundError si da 404."""
    try:
        r = sesion.head(url, allow_redirects=True, timeout=60)
    except requests.RequestException:
        return None
    if r.status_code == 404:
        raise FileNotFoundError(url)
    if r.ok and r.headers.get("Content-Length", "").isdigit():
        return int(r.headers["Content-Length"])
    return None


def descargar(sesion: requests.Session, url: str, destino: Path) -> str:
    """Baja `url` a `destino` salvo que ya exista con el mismo tamaño. Devuelve el estado."""
    remoto = _tamano_remoto(sesion, url)
    if destino.exists() and remoto is not None and destino.stat().st_size == remoto:
        return "ya estaba (tamaño verificado contra el servidor)"

    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".parcial")
    with sesion.get(url, stream=True, timeout=300) as r:
        if r.status_code == 404:
            raise FileNotFoundError(url)
        r.raise_for_status()
        with temporal.open("wb") as f:
            for bloque in r.iter_content(1 << 20):
                f.write(bloque)
    if remoto is not None and temporal.stat().st_size != remoto:
        temporal.unlink()
        raise IOError(f"Tamaño distinto al del servidor: {url}")
    temporal.replace(destino)
    return "descargado"


def _validar_csv_firms(ruta: Path) -> None:
    with ruta.open("r", encoding="utf-8", errors="replace") as f:
        if not f.readline().startswith("latitude,"):
            ruta.unlink()
            raise ValueError(f"No es un CSV de FIRMS (se borró): {ruta.name}")


def _extraer_zip(zip_ruta: Path, destino: Path) -> list[str]:
    """Extrae el zip sin permitir rutas fuera de `destino`."""
    if not zipfile.is_zipfile(zip_ruta):
        raise ValueError(f"No es un zip válido: {zip_ruta}")
    destino.mkdir(parents=True, exist_ok=True)
    base = destino.resolve()
    with zipfile.ZipFile(zip_ruta) as z:
        for nombre in z.namelist():
            if not (base / nombre).resolve().is_relative_to(base):
                raise ValueError(f"Ruta sospechosa dentro del zip: {nombre}")
        z.extractall(destino)
        return z.namelist()


def _anotar(filas: list[dict]) -> None:
    nuevo = not REGISTRO.exists()
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRO.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_REGISTRO)
        if nuevo:
            w.writeheader()
        w.writerows(filas)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    opciones = [*FIRMS_ANIOS, "comunas"]
    parser.add_argument("--solo", nargs="+", choices=opciones, default=opciones, help="qué fuentes procesar")
    args = parser.parse_args()

    sesion = requests.Session()
    sesion.headers["User-Agent"] = "firecal/0.1 (descarga de datos publicos)"
    ahora = lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    filas: list[dict] = []
    errores = 0

    for carpeta, anios in FIRMS_ANIOS.items():
        if carpeta not in args.solo:
            continue
        for anio in anios:
            nombre = f"{carpeta}_{anio}_{PAIS}.csv"
            url = f"{FIRMS_BASE}/{carpeta}/{anio}/{nombre}"
            destino = FIRMS_DIR / nombre
            try:
                estado = descargar(sesion, url, destino)
                _validar_csv_firms(destino)
            except FileNotFoundError:
                print(f"  {nombre}: no existe en FIRMS (404)")
                continue
            except (requests.RequestException, IOError, ValueError) as e:
                print(f"  {nombre}: ERROR {e}")
                errores += 1
                continue
            filas.append({"fecha_utc": ahora(), "fuente": f"FIRMS {carpeta}", "url": url, "archivo": nombre,
                          "bytes": destino.stat().st_size, "sha256": _sha256(destino), "estado": estado})
            print(f"  {nombre}: {estado}")

    if "comunas" in args.solo:
        destino = COMUNAS_DIR / "comunas_final.zip"
        try:
            estado = descargar(sesion, COMUNAS_URL, destino)
            archivos = _extraer_zip(destino, COMUNAS_DIR)
            filas.append({"fecha_utc": ahora(), "fuente": "BCN comunas", "url": COMUNAS_URL,
                          "archivo": destino.name, "bytes": destino.stat().st_size,
                          "sha256": _sha256(destino), "estado": estado})
            print(f"  comunas_final.zip: {estado}; {len(archivos)} archivos extraídos en {COMUNAS_DIR}")
        except (requests.RequestException, IOError, ValueError) as e:
            print(f"  comunas_final.zip: ERROR {e}")
            errores += 1

    _anotar(filas)
    print(f"\n{len(filas)} archivos anotados en {REGISTRO}; errores: {errores}")
    return 1 if errores else 0


if __name__ == "__main__":
    raise SystemExit(main())
