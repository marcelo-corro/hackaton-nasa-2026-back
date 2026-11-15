"""Paso 1b: focos FIRMS del año en curso (por defecto desde el 1 de enero hasta hoy) por la API, con la MAP_KEY de .env.

- VIIRS Suomi NPP y NOAA-20. Versión estándar (SP) donde existe y casi en tiempo real (NRT) después; las fechas de
  cada una se leen de la API de disponibilidad de FIRMS.
- API de área (rectángulo de Chile continental, -76,-56,-66,-17), de a 5 días por consulta (el máximo que acepta). Los
  focos fuera de Chile los descarta el paso 3 al asignar comunas. Juan Fernández e Isla de Pascua quedan fuera.
- NRT no trae `type` (0 vegetación, 1 volcán, 2 fuente fija, 3 costa afuera). Se infiere: un foco a menos de 0,3 km de
  un foco histórico (2012-2025) con `type` distinto de 0 toma ese tipo; el resto, 0. Probado a ciegas en 2025 (máscara
  2012-2024): detecta el 99,0 % de los focos no vegetales y marca por error el 1,0 % de la vegetación.
- Escribe data/raw/firms/viirs-snpp_<año>_Chile.csv y viirs-jpss1_<año>_Chile.csv con las columnas del archivo anual
  (más `fuente_api` y `type_inferido`, que la ingesta ignora), para que 02-04 los procesen igual que los anuales.
- Anota en data/raw/registro_descargas.csv sin la llave.

Uso:
    python scripts/01b_firms_reciente.py                     # año en curso hasta hoy
    python scripts/01b_firms_reciente.py --desde 2026-01-01 --hasta 2026-11-15
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy.spatial import cKDTree

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from firecal import config  # noqa: E402

API = "https://firms.modaps.eosdis.nasa.gov/api"
BBOX_CHILE = "-76,-56,-66,-17"
DIAS_POR_CONSULTA = 5
UMBRAL_TIPO_KM = 0.3
SATELITES = {"VIIRS_SNPP": "viirs-snpp", "VIIRS_NOAA20": "viirs-jpss1"}  # fuente API → prefijo de archivo (paso 1)
REGISTRO = RAIZ / "data" / "raw" / "registro_descargas.csv"
CAMPOS_REGISTRO = ["fecha_utc", "fuente", "url", "archivo", "bytes", "sha256", "estado"]


def disponibilidad(sesion: requests.Session, llave: str) -> dict[str, tuple[date, date]]:
    r = sesion.get(f"{API}/data_availability/csv/{llave}/ALL", timeout=60)
    r.raise_for_status()
    d = pd.read_csv(io.StringIO(r.text))
    return {f: (pd.Timestamp(a).date(), pd.Timestamp(b).date()) for f, a, b in zip(d["data_id"], d["min_date"],
                                                                                    d["max_date"])}


def tramos(desde: date, hasta: date):
    d = desde
    while d <= hasta:
        n = min(DIAS_POR_CONSULTA, (hasta - d).days + 1)
        yield d, n
        d += timedelta(days=n)


def bajar(sesion: requests.Session, llave: str, fuente: str, desde: date, hasta: date) -> tuple[pd.DataFrame, int]:
    partes, n_consultas = [], 0
    for inicio, n in tramos(desde, hasta):
        url = f"{API}/area/csv/{llave}/{fuente}/{BBOX_CHILE}/{n}/{inicio.isoformat()}"
        for intento in range(3):
            r = sesion.get(url, timeout=180)
            if r.ok and r.text.startswith("latitude"):
                break
            time.sleep(5 * (intento + 1))
        else:
            raise IOError(f"{fuente} {inicio}: HTTP {r.status_code}: {r.text[:120]}")
        n_consultas += 1
        df = pd.read_csv(io.StringIO(r.text))
        fuera = ~df["acq_date"].between(inicio.isoformat(), (inicio + timedelta(days=n - 1)).isoformat())
        if fuera.any():
            raise IOError(f"{fuente} {inicio}: llegaron fechas fuera del tramo pedido")
        partes.append(df.assign(fuente_api=fuente))
    return (pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()), n_consultas


def _km(lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    return np.column_stack([lat * 110.57, lon * 111.32 * np.cos(np.radians(lat))])


def inferir_tipo(df: pd.DataFrame, historicos: pd.DataFrame) -> pd.DataFrame:
    """Completa `type` donde falta, con el tipo del foco histórico no vegetal más cercano (< UMBRAL_TIPO_KM)."""
    df = df.copy()
    if "type" not in df:
        df["type"] = np.nan
    falta = df["type"].isna().to_numpy()
    df["type_inferido"] = falta
    if falta.any():
        dist, idx = cKDTree(_km(historicos["lat"].to_numpy(), historicos["lon"].to_numpy())).query(
            _km(df.loc[falta, "latitude"].to_numpy(), df.loc[falta, "longitude"].to_numpy()),
            distance_upper_bound=UMBRAL_TIPO_KM)
        tipo = np.zeros(falta.sum(), dtype=int)
        cerca = np.isfinite(dist)
        tipo[cerca] = historicos["tipo"].to_numpy()[idx[cerca]]
        df.loc[falta, "type"] = tipo
    df["type"] = df["type"].astype(int)
    return df


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with ruta.open("rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    hoy = datetime.now(timezone.utc).date()
    parser.add_argument("--desde", default=f"{hoy.year}-01-01")
    parser.add_argument("--hasta", default=hoy.isoformat())
    args = parser.parse_args()
    llave = config.FIRMS_MAP_KEY
    if not llave:
        print("Falta FIRMS_MAP_KEY en .env (https://firms.modaps.eosdis.nasa.gov/api/map_key/).")
        return 1
    desde, hasta = date.fromisoformat(args.desde), date.fromisoformat(args.hasta)

    sesion = requests.Session()
    sesion.headers["User-Agent"] = "firecal/0.1 (datos publicos)"
    disp = disponibilidad(sesion, llave)
    hist = pd.read_parquet(config.INTERIM_DIR / "focos.parquet", columns=["lat", "lon", "sensor", "tipo", "fecha"])
    hist = hist[(hist["sensor"] == "VIIRS") & hist["tipo"].notna() & (hist["tipo"] != 0)
                & (pd.to_datetime(hist["fecha"]) < pd.Timestamp(desde))]
    print(f"Máscara de fuentes no vegetales: {len(hist):,} focos históricos VIIRS con type != 0")

    destino = config.FIRMS_RAW_DIR
    destino.mkdir(parents=True, exist_ok=True)
    filas_registro = []
    for sat, prefijo in SATELITES.items():
        sp_min, sp_max = disp.get(f"{sat}_SP", (None, None))
        nrt_min, nrt_max = disp.get(f"{sat}_NRT", (None, None))
        partes, consultas = [], 0
        if sp_max and sp_max >= desde:
            df, n = bajar(sesion, llave, f"{sat}_SP", desde, min(hasta, sp_max))
            partes.append(df)
            consultas += n
        ini_nrt = max(desde, (sp_max + timedelta(days=1)) if sp_max else desde, nrt_min or desde)
        fin_nrt = min(hasta, nrt_max) if nrt_max else None
        if fin_nrt and fin_nrt >= ini_nrt:
            df, n = bajar(sesion, llave, f"{sat}_NRT", ini_nrt, fin_nrt)
            partes.append(df)
            consultas += n
        datos = pd.concat([p for p in partes if len(p)], ignore_index=True)
        datos = datos.drop_duplicates(["latitude", "longitude", "acq_date", "acq_time", "satellite"])
        datos = inferir_tipo(datos, hist)
        ruta = destino / f"{prefijo}_{desde.year}_Chile.csv"
        datos.to_csv(ruta, index=False)
        ultimo = datos["acq_date"].max()
        print(f"{sat}: {len(datos):,} focos ({datos['acq_date'].min()} a {ultimo}), {consultas} consultas; "
              f"type inferido en {int(datos['type_inferido'].sum()):,}; no vegetales {int((datos['type'] != 0).sum()):,}"
              f" -> {ruta.name}")
        filas_registro.append({
            "fecha_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "fuente": f"FIRMS API {sat} (SP+NRT)",
            "url": f"{API}/area/csv/[MAP_KEY]/{sat}_SP|NRT/{BBOX_CHILE}/{DIAS_POR_CONSULTA}/[fecha] ({consultas} consultas)",
            "archivo": ruta.name, "bytes": ruta.stat().st_size, "sha256": _sha256(ruta),
            "estado": f"descargado {desde} a {ultimo}"})
    nuevo = not REGISTRO.exists()
    with REGISTRO.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_REGISTRO)
        if nuevo:
            w.writeheader()
        w.writerows(filas_registro)
    print(f"Disponibilidad usada: " + ", ".join(f"{k} {a}..{b}" for k, (a, b) in disp.items() if k.startswith(tuple(SATELITES))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
