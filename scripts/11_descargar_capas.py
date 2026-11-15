"""Paso 11 (sectores): descarga las capas fijas del territorio para una región (piloto: Valparaíso, 05).

Capas (detalle y citas en docs/fuentes.md):
- ESA WorldCover 2021 v200 (10 m): cobertura del suelo (árboles, matorral, pastizal, cultivo, construido...).
  Bloques de 3° × 3° (el nombre es la esquina suroeste).
- Copernicus DEM GLO-30 (30 m): elevación, para la pendiente. Bloques de 1° × 1° (nombre = esquina suroeste).
- Interfaz urbano-forestal global (WUI) de Schug et al. (2023), 10 m, año 2020. Viene en un zip de 1,7 GB para
  Sudamérica; se leen SOLO los bloques de 100 km que tocan la región, con peticiones HTTP por rango (sin bajar el zip).

Si un archivo ya existe con el tamaño correcto, no se vuelve a bajar. Todo queda en data/raw/sectores/ (no se versiona)
y anotado en data/raw/registro_descargas.csv (URL, tamaño, SHA-256, estado, fecha).

Uso:
    python scripts/11_descargar_capas.py                 # región 05, las tres capas
    python scripts/11_descargar_capas.py --solo wui
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import math
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import requests
from pyproj import CRS, Transformer

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from firecal.sectores.region import comunas_region  # noqa: E402

RAW = RAIZ / "data" / "raw"
DESTINO = RAW / "sectores"
REGISTRO = RAW / "registro_descargas.csv"
CAMPOS_REGISTRO = ["fecha_utc", "fuente", "url", "archivo", "bytes", "sha256", "estado"]

WORLDCOVER_URL = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_{t}_Map.tif"
DEM_URL = "https://copernicus-dem-30m.s3.amazonaws.com/{n}/{n}.tif"
WUI_ZIP_URL = "https://zenodo.org/records/7941460/files/SA.zip"


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def descargar(sesion: requests.Session, url: str, destino: Path) -> str:
    """Baja `url` a `destino` salvo que ya exista con el mismo tamaño. Devuelve el estado."""
    h = sesion.head(url, allow_redirects=True, timeout=60)
    if h.status_code == 404:
        raise FileNotFoundError(url)
    remoto = int(h.headers["Content-Length"]) if h.headers.get("Content-Length", "").isdigit() else None
    if destino.exists() and remoto is not None and destino.stat().st_size == remoto:
        return "ya estaba (tamaño verificado contra el servidor)"
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_suffix(destino.suffix + ".parcial")
    with sesion.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        with temporal.open("wb") as f:
            for bloque in r.iter_content(1 << 20):
                f.write(bloque)
    if remoto is not None and temporal.stat().st_size != remoto:
        temporal.unlink()
        raise IOError(f"Tamaño distinto al del servidor: {url}")
    temporal.replace(destino)
    return "descargado"


class _RangoHTTP(io.RawIOBase):
    """Archivo remoto de solo lectura con búsqueda, vía cabecera Range (lo usa zipfile para leer pocas partes)."""

    def __init__(self, sesion: requests.Session, url: str):
        h = sesion.head(url, allow_redirects=True, timeout=60)
        h.raise_for_status()
        self.sesion, self.url, self.pos = sesion, h.url, 0
        self.size = int(h.headers["Content-Length"])
        self.leidos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, desplazamiento: int, desde: int = 0) -> int:
        base = {0: 0, 1: self.pos, 2: self.size}[desde]
        self.pos = base + desplazamiento
        return self.pos

    def readinto(self, b) -> int:
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        r = self.sesion.get(self.url, headers={"Range": f"bytes={self.pos}-{self.pos + n - 1}"}, timeout=300)
        if r.status_code != 206:
            raise IOError(f"El servidor no respetó el rango (HTTP {r.status_code})")
        b[:n] = r.content
        self.pos += n
        self.leidos += n
        return n


def _bloques_grados(limites: tuple[float, float, float, float], paso: int) -> list[tuple[int, int]]:
    """Esquinas suroeste (lat, lon) de los bloques de `paso` grados que cubren los límites."""
    x0, y0, x1, y1 = limites
    lats = range(math.floor(y0 / paso) * paso, math.ceil(y1 / paso) * paso, paso)
    lons = range(math.floor(x0 / paso) * paso, math.ceil(x1 / paso) * paso, paso)
    return [(la, lo) for la in lats for lo in lons]


def _nombre_lat(la: int, ancho: int) -> str:
    return f"{'S' if la < 0 else 'N'}{abs(la):0{ancho}d}"


def _nombre_lon(lo: int) -> str:
    return f"{'W' if lo < 0 else 'E'}{abs(lo):03d}"


def bajar_worldcover(sesion, limites) -> list[dict]:
    filas = []
    for la, lo in _bloques_grados(limites, 3):
        t = f"{_nombre_lat(la, 2)}{_nombre_lon(lo)}"
        url = WORLDCOVER_URL.format(t=t)
        destino = DESTINO / "worldcover" / Path(url).name
        estado = descargar(sesion, url, destino)
        filas.append({"fuente": "ESA WorldCover 2021 v200", "url": url, "ruta": destino, "estado": estado})
    return filas


def bajar_dem(sesion, limites) -> list[dict]:
    filas = []
    for la, lo in _bloques_grados(limites, 1):
        n = f"Copernicus_DSM_COG_10_{_nombre_lat(la, 2)}_00_{_nombre_lon(lo)}_00_DEM"
        url = DEM_URL.format(n=n)
        destino = DESTINO / "copernicus_dem" / f"{n}.tif"
        try:
            estado = descargar(sesion, url, destino)
        except FileNotFoundError:  # bloque solo de mar: no existe
            print(f"  {n}: no existe (mar)")
            continue
        filas.append({"fuente": "Copernicus DEM GLO-30", "url": url, "ruta": destino, "estado": estado})
    return filas


def bajar_wui(sesion, region: gpd.GeoDataFrame) -> list[dict]:
    """Extrae del zip remoto la definición de la grilla y los bloques de 100 km que tocan la región."""
    destino = DESTINO / "wui"
    remoto = io.BufferedReader(_RangoHTTP(sesion, WUI_ZIP_URL), buffer_size=1 << 20)
    z = zipfile.ZipFile(remoto)
    nombres = set(z.namelist())
    base = destino.resolve()

    def extraer(nombre: str) -> Path:
        ruta = (destino / nombre).resolve()
        if not ruta.is_relative_to(base):
            raise ValueError(f"Ruta sospechosa dentro del zip: {nombre}")
        info = z.getinfo(nombre)
        if ruta.exists() and ruta.stat().st_size == info.file_size:
            return ruta
        ruta.parent.mkdir(parents=True, exist_ok=True)
        with z.open(info) as src, ruta.open("wb") as dst:
            dst.write(src.read())
        return ruta

    # datacube-definition.prj (formato FORCE): WKT, lon/lat del origen, x/y del origen, tamaño del bloque (m)
    definicion = extraer("SA/datacube-definition.prj").read_text(encoding="utf-8").splitlines()
    crs = CRS.from_wkt(definicion[0])
    x0, y0, lado = float(definicion[3]), float(definicion[4]), float(definicion[5])
    xmin, ymin, xmax, ymax = region.to_crs(crs).total_bounds
    filas = []
    for tx in range(int((xmin - x0) // lado), int((xmax - x0) // lado) + 1):
        for ty in range(int((y0 - ymax) // lado), int((y0 - ymin) // lado) + 1):
            nombre = f"SA/X{tx:04d}_Y{ty:04d}/WUI.tif"
            if nombre not in nombres:  # bloque sin datos (mar) no viene en el zip
                continue
            ruta = extraer(nombre)
            filas.append({"fuente": "WUI global (Schug et al. 2023) v1.1", "url": f"{WUI_ZIP_URL} :: {nombre}",
                          "ruta": ruta, "estado": "extraído del zip remoto por rango"})
    print(f"  WUI: {len(filas)} bloques; bytes leídos del zip remoto: {remoto.raw.leidos / 1e6:.1f} MB")
    return filas


def _anotar(filas: list[dict]) -> None:
    nuevo = not REGISTRO.exists()
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRO.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_REGISTRO)
        if nuevo:
            w.writeheader()
        for r in filas:
            w.writerow({"fecha_utc": _ahora(), "fuente": r["fuente"], "url": r["url"], "archivo": r["ruta"].name,
                        "bytes": r["ruta"].stat().st_size, "sha256": _sha256(r["ruta"]), "estado": r["estado"]})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="05", help="código de región (2 dígitos); piloto: 05")
    parser.add_argument("--solo", nargs="+", choices=["worldcover", "dem", "wui"], default=["worldcover", "dem", "wui"])
    args = parser.parse_args()

    region = comunas_region(args.region)
    limites = tuple(region.to_crs("EPSG:4326").total_bounds)
    print(f"Región {args.region}: {len(region)} comunas continentales; límites {tuple(round(v, 3) for v in limites)}")

    sesion = requests.Session()
    sesion.headers["User-Agent"] = "firecal/0.1 (descarga de datos publicos)"
    filas: list[dict] = []
    for capa, funcion in (("worldcover", lambda: bajar_worldcover(sesion, limites)),
                          ("dem", lambda: bajar_dem(sesion, limites)),
                          ("wui", lambda: bajar_wui(sesion, region))):
        if capa not in args.solo:
            continue
        print(f"{capa}...", flush=True)
        nuevas = funcion()
        for r in nuevas:
            print(f"  {r['ruta'].name}: {r['estado']} ({r['ruta'].stat().st_size / 1e6:.1f} MB)", flush=True)
        filas += nuevas
    _anotar(filas)
    print(f"\n{len(filas)} archivos anotados en {REGISTRO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
