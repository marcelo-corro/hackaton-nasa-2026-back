"""Clima diario por comuna desde NASA POWER (MERRA-2). Tarea B5. Fuente citada en docs/fuentes.md.

Un punto por comuna, **dentro** del polígono (`representative_point`, no el centroide, que en comunas irregulares
puede caer afuera). Cada comuna se guarda en caché (`data/raw/clima_power/{region_id}.json`) apenas llega, para
poder retomar si se corta la descarga.

Salida de `clima_diario`:

    region_id    string
    fecha_local  datetime  día (POWER entrega hora solar local, `time-standard=LST`)
    tmax         float     temperatura máxima a 2 m (°C)
    hrmin        float     humedad relativa mínima (%) **aproximada**: POWER no la entrega; se estima con la
                           fórmula de Magnus desde el punto de rocío medio y la temperatura máxima
    hr_media     float     humedad relativa media a 2 m (%), medida por POWER
    viento_max   float     viento máximo a 10 m (m/s)
    precip       float     precipitación (mm/día)
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMETROS_POWER = ["T2M_MAX", "T2MDEW", "RH2M", "WS10M_MAX", "PRECTOTCORR"]
FECHA_DESDE = "2012-01-01"
FECHA_HASTA = "2025-12-31"
VALOR_FALTANTE = -999.0
COLUMNAS = ["region_id", "fecha_local", "tmax", "hrmin", "hr_media", "viento_max", "precip"]
COLUMNAS_NUMERICAS = COLUMNAS[2:]
ESTADOS_REINTENTABLES = {429, 500, 502, 503, 504}


def puntos_representativos(comunas: gpd.GeoDataFrame) -> pd.DataFrame:
    """Un punto (lat, lon) dentro de cada comuna."""
    if comunas.crs is not None and comunas.crs.to_epsg() != 4326:
        comunas = comunas.to_crs(4326)
    puntos = comunas.geometry.representative_point()
    return pd.DataFrame(
        {"region_id": comunas["region_id"].astype(str).to_numpy(), "lat": puntos.y.to_numpy(), "lon": puntos.x.to_numpy()}
    )


def presion_vapor_saturado(temperatura_c: pd.Series | np.ndarray) -> pd.Series | np.ndarray:
    """Presión de vapor de saturación (hPa) por la fórmula de Magnus."""
    return 6.112 * np.exp(17.62 * temperatura_c / (243.12 + temperatura_c))


def humedad_minima_aproximada(tmax_c: pd.Series, punto_rocio_c: pd.Series) -> pd.Series:
    """HR mínima del día ≈ 100 · e(rocío medio) / e(temperatura máxima), acotada a [0, 100].

    Aproximación: la humedad es mínima cuando la temperatura es máxima y se supone que el punto de rocío se
    mantiene en su media diaria. Siempre queda por debajo de la humedad media.
    """
    hr = 100.0 * presion_vapor_saturado(punto_rocio_c) / presion_vapor_saturado(tmax_c)
    return hr.clip(lower=0.0, upper=100.0)


def _consultar(
    lat: float,
    lon: float,
    get: Callable[..., requests.Response],
    reintentos: int,
    espera_s: float,
    dormir: Callable[[float], None],
    desde: str = FECHA_DESDE,
    hasta: str = FECHA_HASTA,
    variables: list[str] | None = None,
) -> dict:
    parametros = {
        "parameters": ",".join(variables or PARAMETROS_POWER),
        "community": "AG",
        "longitude": f"{lon:.4f}",
        "latitude": f"{lat:.4f}",
        "start": desde.replace("-", ""),
        "end": hasta.replace("-", ""),
        "format": "JSON",
    }
    ultimo_error: Exception | None = None
    for intento in range(reintentos + 1):
        try:
            respuesta = get(URL, params=parametros, timeout=120)
        except (requests.ConnectionError, requests.Timeout) as e:
            ultimo_error = e
        else:
            if respuesta.status_code in ESTADOS_REINTENTABLES:
                ultimo_error = RuntimeError(f"HTTP {respuesta.status_code}")
            else:
                respuesta.raise_for_status()
                return respuesta.json()
        dormir(espera_s * 2**intento)
    raise RuntimeError(f"NASA POWER no respondió tras {reintentos} reintentos (lat={lat}, lon={lon}): {ultimo_error}")


def descargar_clima(
    puntos: pd.DataFrame,
    cache_dir: Path,
    reintentos: int = 5,
    espera_s: float = 5.0,
    pausa_s: float = 0.5,
    get: Callable[..., requests.Response] = requests.get,
    dormir: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
    desde: str = FECHA_DESDE,
    hasta: str = FECHA_HASTA,
    variables: list[str] | None = None,
) -> int:
    """Descarga las comunas que faltan en la caché, una consulta por comuna. Devuelve cuántas bajó.
    `desde`/`hasta` (YYYY-MM-DD) permiten bajar otro período a otra caché (por ejemplo el año en curso) y
    `variables`, otras variables de POWER (por defecto las del clima del modelo)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    pendientes = puntos[~puntos["region_id"].map(lambda r: (cache_dir / f"{r}.json").exists())]
    descargadas = 0
    for fila in pendientes.itertuples():
        datos = _consultar(fila.lat, fila.lon, get, reintentos, espera_s, dormir, desde, hasta, variables)
        guardar = {"lat": fila.lat, "lon": fila.lon, "parameter": datos["properties"]["parameter"]}
        (cache_dir / f"{fila.region_id}.json").write_text(json.dumps(guardar, separators=(",", ":")), encoding="utf-8")
        descargadas += 1
        if descargadas % 10 == 0 or descargadas == len(pendientes):
            log(f"  {len(puntos) - len(pendientes) + descargadas}/{len(puntos)} comunas en caché")
        dormir(pausa_s)
    return descargadas


def _tabla_de_una_comuna(region_id: str, parametros: dict) -> pd.DataFrame:
    fechas = sorted(parametros["T2M_MAX"])  # claves "YYYYMMDD"
    crudo = pd.DataFrame({p: pd.Series(parametros[p]).reindex(fechas).astype(float) for p in PARAMETROS_POWER})
    crudo = crudo.replace(VALOR_FALTANTE, np.nan)
    tabla = pd.DataFrame(
        {
            "region_id": region_id,
            "fecha_local": pd.to_datetime(fechas, format="%Y%m%d"),
            "tmax": crudo["T2M_MAX"].to_numpy(),
            "hrmin": humedad_minima_aproximada(crudo["T2M_MAX"], crudo["T2MDEW"]).to_numpy(),
            "hr_media": crudo["RH2M"].to_numpy(),
            "viento_max": crudo["WS10M_MAX"].to_numpy(),
            "precip": crudo["PRECTOTCORR"].to_numpy(),
        }
    )
    tabla[COLUMNAS_NUMERICAS] = tabla[COLUMNAS_NUMERICAS].astype("float32")
    return tabla


def clima_diario(puntos: pd.DataFrame, cache_dir: Path) -> pd.DataFrame:
    """Arma la tabla diaria desde la caché. Falla si falta alguna comuna."""
    faltan = [r for r in puntos["region_id"] if not (cache_dir / f"{r}.json").exists()]
    if faltan:
        raise FileNotFoundError(f"Faltan {len(faltan)} comunas en {cache_dir} (ej. {faltan[:3]}); corre la descarga.")
    partes = [
        _tabla_de_una_comuna(r, json.loads((cache_dir / f"{r}.json").read_text(encoding="utf-8"))["parameter"])
        for r in puntos["region_id"]
    ]
    salida = pd.concat(partes, ignore_index=True)
    salida["region_id"] = salida["region_id"].astype("string")
    return salida[COLUMNAS]


def huecos(clima: pd.DataFrame, n_comunas: int) -> list[str]:
    """Problemas de completitud: comunas, días esperados y valores nulos. Lista vacía = sin huecos."""
    dias = len(pd.date_range(FECHA_DESDE, FECHA_HASTA, freq="D"))
    problemas = []
    if clima["region_id"].nunique() != n_comunas:
        problemas.append(f"se esperaban {n_comunas} comunas y hay {clima['region_id'].nunique()}")
    por_comuna = clima.groupby("region_id").size()
    incompletas = por_comuna[por_comuna != dias]
    if len(incompletas):
        problemas.append(f"{len(incompletas)} comunas sin los {dias} días esperados")
    nulos = clima[COLUMNAS_NUMERICAS].isna().sum()
    nulos = nulos[nulos > 0]
    if len(nulos):
        problemas.append("valores nulos: " + ", ".join(f"{k}={v}" for k, v in nulos.items()))
    return problemas
