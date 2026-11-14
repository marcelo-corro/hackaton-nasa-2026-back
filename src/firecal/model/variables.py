"""Tabla comuna × día para el modelo de riesgo, con bloques de variables que se pueden sumar.

Cada fila es una comuna en un día local `fecha` (día t). Las variables usan solo lo conocido al cierre de t;
los objetivos miran el futuro:

    y24  ¿hay al menos un foco Suomi NPP (`uso_base`) en la comuna el día t+1?
    y48  ¿y en t+1 o t+2?

Bloques:
- FIRMS (`tabla_base`): focos y FRP de hoy, ventanas de 3/7/30 días, días desde el último foco, focos en comunas
  vecinas, calendario y datos fijos de la comuna.
- Climatología (`agregar_climatologia`): frecuencia histórica de días con fuego por comuna y mes, calculada SOLO
  con las filas de entrenamiento para no filtrar información del período de prueba.
- Clima (`bloque_clima`): opcional; se suma si existe data/interim/clima_diario.parquet (tarea B5).
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import sparse

SATELITE_OBJETIVO = "SNPP"
CRS_METRICO = "ESRI:102033"

VARIABLES_FIRMS = [
    "n_hoy", "frp_hoy", "n_3d", "n_7d", "n_30d", "dias_desde_ultimo",
    "vecinos_hoy", "vecinos_3d", "mes", "doy_sin", "doy_cos", "dia_semana", "lat", "lon", "area_km2",
]
VARIABLES_CLIMATOLOGIA = ["clim_comuna_mes", "clim_comuna"]
VARIABLES_CLIMA = ["tmax", "hrmin", "viento_max", "precip", "precip_7d", "dias_sin_lluvia"]


def matrices_diarias(
    focos: pd.DataFrame, region_ids: list[str], dias: pd.DatetimeIndex, satelite: str = SATELITE_OBJETIVO
) -> tuple[np.ndarray, np.ndarray]:
    """Conteo de focos y FRP total por comuna (filas) y día (columnas)."""
    f = focos[(focos["satelite"] == satelite) & focos["uso_base"] & focos["region_id"].notna()]
    f = f[(f["fecha_local"] >= dias[0]) & (f["fecha_local"] <= dias[-1])]
    fila = pd.Index(region_ids).get_indexer(f["region_id"].astype(str))
    col = ((f["fecha_local"] - dias[0]).dt.days).to_numpy()
    ok = fila >= 0
    forma = (len(region_ids), len(dias))
    conteo = sparse.coo_matrix((np.ones(ok.sum()), (fila[ok], col[ok])), shape=forma).toarray()
    frp = sparse.coo_matrix((f["frp"].to_numpy(float)[ok], (fila[ok], col[ok])), shape=forma).toarray()
    return conteo, frp


def suma_movil(m: np.ndarray, k: int) -> np.ndarray:
    """Suma de los últimos k días incluyendo el actual (por fila)."""
    c = np.cumsum(m, axis=1)
    out = c.copy()
    out[:, k:] = c[:, k:] - c[:, :-k]
    return out


def dias_desde_ultimo(m: np.ndarray, tope: int = 365) -> np.ndarray:
    """Días desde el último día con foco (0 si hubo foco hoy), con tope."""
    out = np.empty_like(m, dtype=float)
    ultimo = np.full(m.shape[0], -tope, dtype=float)
    for j in range(m.shape[1]):
        ultimo = np.where(m[:, j] > 0, j, ultimo)
        out[:, j] = np.minimum(j - ultimo, tope)
    return out


def matriz_vecinos(comunas: gpd.GeoDataFrame, distancia_m: float = 500.0) -> sparse.csr_matrix:
    """Adyacencia entre comunas (se tocan o están a menos de `distancia_m`), sin la diagonal."""
    g = comunas[["region_id", "geometry"]].to_crs(CRS_METRICO).reset_index(drop=True)
    g["geometry"] = g.geometry.simplify(200).buffer(distancia_m / 2)
    pares = gpd.sjoin(g, g, predicate="intersects")
    pares = pares[pares.index != pares["index_right"]]
    n = len(g)
    return sparse.csr_matrix((np.ones(len(pares)), (pares.index.to_numpy(), pares["index_right"].to_numpy())), shape=(n, n))


def tabla_base(focos: pd.DataFrame, comunas: gpd.GeoDataFrame, inicio: str, fin: str) -> pd.DataFrame:
    """Tabla larga comuna × día con objetivos y variables FIRMS."""
    comunas = comunas.sort_values("region_id").reset_index(drop=True)
    ids = comunas["region_id"].astype(str).tolist()
    dias = pd.date_range(inicio, fin, freq="D")
    n_c, n_d = len(ids), len(dias)

    conteo, frp = matrices_diarias(focos, ids, dias)
    vecinos = matriz_vecinos(comunas)
    hay = (conteo > 0).astype(float)
    y24 = np.full((n_c, n_d), np.nan)
    y24[:, :-1] = hay[:, 1:]
    y48 = np.full((n_c, n_d), np.nan)
    y48[:, :-2] = np.maximum(hay[:, 1:-1], hay[:, 2:])

    destino = dias + pd.Timedelta(days=1)  # el calendario se refiere al día que se predice
    doy = destino.day_of_year.to_numpy()
    centro = comunas.to_crs(CRS_METRICO).geometry.representative_point().to_crs("EPSG:4326")

    columnas = {
        "region_id": np.repeat(ids, n_d),
        "fecha": np.tile(dias.to_numpy(), n_c),
        "y24": y24.ravel(),
        "y48": y48.ravel(),
        "n_hoy": conteo.ravel(),
        "frp_hoy": frp.ravel(),
        "n_3d": suma_movil(conteo, 3).ravel(),
        "n_7d": suma_movil(conteo, 7).ravel(),
        "n_30d": suma_movil(conteo, 30).ravel(),
        "dias_desde_ultimo": dias_desde_ultimo(conteo).ravel(),
        "vecinos_hoy": (vecinos @ conteo).ravel(),
        "vecinos_3d": (vecinos @ suma_movil(conteo, 3)).ravel(),
        "mes": np.tile(destino.month.to_numpy(), n_c),
        "doy_sin": np.tile(np.sin(2 * np.pi * doy / 365.25), n_c),
        "doy_cos": np.tile(np.cos(2 * np.pi * doy / 365.25), n_c),
        "dia_semana": np.tile(destino.day_of_week.to_numpy(), n_c),
        "lat": np.repeat(centro.y.to_numpy(), n_d),
        "lon": np.repeat(centro.x.to_numpy(), n_d),
        "area_km2": np.repeat(comunas["area_km2"].to_numpy(float), n_d),
    }
    tabla = pd.DataFrame(columnas)
    tabla["region_id"] = tabla["region_id"].astype("string")
    for c in VARIABLES_FIRMS:
        tabla[c] = tabla[c].astype("float32")
    return tabla


def agregar_climatologia(tabla: pd.DataFrame, filas_entrenamiento: pd.Series) -> pd.DataFrame:
    """Frecuencia histórica de días con fuego (y24) por comuna y mes, usando SOLO filas de entrenamiento."""
    ent = tabla.loc[filas_entrenamiento & tabla["y24"].notna()]
    por_mes = ent.groupby(["region_id", "mes"])["y24"].mean().rename("clim_comuna_mes")
    por_comuna = ent.groupby("region_id")["y24"].mean().rename("clim_comuna")
    out = tabla.join(por_mes, on=["region_id", "mes"]).join(por_comuna, on="region_id")
    out[VARIABLES_CLIMATOLOGIA] = out[VARIABLES_CLIMATOLOGIA].fillna(0).astype("float32")
    return out


def bloque_clima(ruta: Path) -> pd.DataFrame | None:
    """Clima diario por comuna (tarea B5). None si todavía no existe.

    Espera `region_id, fecha_local, tmax, hrmin, viento_max, precip` y deriva lluvia de 7 días y días sin llover.
    """
    if not Path(ruta).exists():
        return None
    c = pd.read_parquet(ruta).rename(columns={"fecha_local": "fecha"}).sort_values(["region_id", "fecha"])
    c["region_id"] = c["region_id"].astype("string")
    g = c.groupby("region_id")["precip"]
    c["precip_7d"] = g.transform(lambda s: s.rolling(7, min_periods=1).sum())
    llueve = (c["precip"] >= 1.0).astype(int)
    racha = llueve.groupby(c["region_id"]).transform(lambda s: s.eq(0).groupby(s.ne(0).cumsum()).cumsum())
    c["dias_sin_lluvia"] = racha.clip(upper=120)
    return c[["region_id", "fecha", *VARIABLES_CLIMA]].astype({v: "float32" for v in VARIABLES_CLIMA})
