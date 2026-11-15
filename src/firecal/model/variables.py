"""Tabla comuna × día para el modelo de riesgo, con bloques de variables que se pueden sumar.

Cada fila es una comuna en un día local `fecha` (día t). Las variables usan solo lo conocido al cierre de t;
los objetivos miran el futuro:

    y24  ¿hay al menos un foco Suomi NPP (`uso_base`) en la comuna el día t+1?
    y48  ¿y en t+1 o t+2?
    y7d  ¿y entre t+1 y t+7 (la próxima semana)?

Bloques:
- FIRMS (`tabla_base`): focos y FRP de hoy, ventanas de 3/7/30 días, días desde el último foco, focos en comunas
  vecinas, calendario y datos fijos de la comuna.
- Climatología (`agregar_climatologia`): frecuencia histórica de días con fuego por comuna y mes, calculada SOLO
  con las filas de entrenamiento (sin información del período de prueba) y, para cada año de entrenamiento, con los
  otros años (sin fuga de objetivo dentro del entrenamiento).
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

# Variables que usa el modelo: 14 de las 23 columnas (selección del 14-11-2026, ver docs/decisiones.md). En
# calibración 2020-2021, sacar n_hoy, n_3d, vecinos_hoy, vecinos_3d, doy_sin, doy_cos, dia_semana, area_km2 y
# dias_sin_lluvia subió la precisión media a 24 h (+0,0043, 3 de 3 semillas), empató a 48 h y costó −0,0014 a 7 días.
# Las otras columnas se siguen calculando: las usan las líneas base, la regresión logística y el backtest.
VARIABLES_MODELO_FIRMS = ["frp_hoy", "n_7d", "n_30d", "dias_desde_ultimo", "mes", "lat", "lon"]
VARIABLES_MODELO_CLIMA = ["tmax", "hrmin", "viento_max", "precip", "precip_7d"]


def completar_con_noaa20(focos: pd.DataFrame) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Si Suomi NPP dejó de entregar datos antes que NOAA-20, usa NOAA-20 para los días siguientes (como si fuera SNPP).

    Pasó en noviembre de 2026: FIRMS tiene Suomi NPP solo hasta el 1-nov y NOAA-20 hasta el día anterior. Medido en
    2022-2025 con el modelo v3: con variables de NOAA-20 rinde igual (AUC 0,845 vs 0,846, precisión media 0,282 en
    ambos); los conteos de 7 días de los dos satélites tienen correlación 0,986 y NOAA-20 ve ~5 % menos.
    Devuelve los focos (con las filas sustitutas agregadas, `sustituto_noaa20` = True) y el último día de Suomi NPP.
    """
    snpp = focos["satelite"] == SATELITE_OBJETIVO
    ultimo = pd.Timestamp(focos.loc[snpp, "fecha_local"].max()).normalize()
    extra = focos[(focos["satelite"] == "NOAA20") & (focos["fecha_local"].dt.normalize() > ultimo)].copy()
    salida = focos.assign(sustituto_noaa20=False)
    if extra.empty:
        return salida, ultimo
    extra["satelite"] = SATELITE_OBJETIVO
    extra["sustituto_noaa20"] = True
    return pd.concat([salida, extra], ignore_index=True), ultimo


def extender_clima(clima: pd.DataFrame, hasta: pd.Timestamp) -> tuple[pd.DataFrame, int]:
    """Repite el último clima disponible de cada comuna hasta `hasta` (NASA POWER publica con ~4 días de retraso).

    Solo afecta a los últimos días (los de la predicción publicada); entrenamiento y pruebas usan clima real. Medido en
    2022-2025: con 3 días de rezago el modelo baja de AUC 0,846 a 0,824 y de precisión media 0,282 a 0,251 (la
    climatología sola: 0,789 y 0,150). Devuelve el clima extendido y cuántos días se rellenaron.
    """
    ultimo = pd.Timestamp(clima["fecha"].max())
    hasta = pd.Timestamp(hasta)
    if hasta <= ultimo:
        return clima, 0
    base = clima[clima["fecha"] == ultimo]
    dias = pd.date_range(ultimo + pd.Timedelta(days=1), hasta, freq="D")
    extra = pd.concat([base.assign(fecha=d) for d in dias], ignore_index=True)
    return pd.concat([clima, extra], ignore_index=True), len(dias)


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
    acum = np.concatenate([np.zeros((n_c, 1)), np.cumsum(hay, axis=1)], axis=1)  # acum[:, k] = días con fuego < k
    y7d = np.full((n_c, n_d), np.nan)
    y7d[:, :-7] = (acum[:, 8:] - acum[:, 1:-7]) > 0  # algún foco entre t+1 y t+7

    destino = dias + pd.Timedelta(days=1)  # el calendario se refiere al día que se predice
    doy = destino.day_of_year.to_numpy()
    centro = comunas.to_crs(CRS_METRICO).geometry.representative_point().to_crs("EPSG:4326")

    columnas = {
        "region_id": np.repeat(ids, n_d),
        "fecha": np.tile(dias.to_numpy(), n_c),
        "y24": y24.ravel(),
        "y48": y48.ravel(),
        "y7d": y7d.ravel(),
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
    """Frecuencia histórica de días con fuego (y24) por comuna y mes (`clim_comuna_mes`) y por comuna (`clim_comuna`).

    Solo usa filas de entrenamiento, y sin fuga de objetivo:
    - filas de entrenamiento: se calcula con los OTROS años de entrenamiento (se deja fuera el año de la fila). Si
      se incluyera el propio año, cada fila "vería" en parte su propia respuesta y el modelo aprendería a confiar
      demasiado en esta variable (pasaba: permutarla pesaba mucho, pero quitarla mejoraba la calibración);
    - demás filas (calibración, prueba, predicción): con todos los años de entrenamiento.
    Sin datos (por ejemplo, un solo año de entrenamiento) queda en 0.
    """
    anio = (tabla["fecha"] + pd.Timedelta(days=1)).dt.year  # año del día que se predice, igual que `mes`
    ent = filas_entrenamiento & tabla["y24"].notna()
    d = pd.DataFrame({"region_id": tabla["region_id"], "mes": tabla["mes"], "anio": anio,
                      "y": tabla["y24"].where(ent)})

    out = tabla.copy()
    for nombre, llave in (("clim_comuna_mes", ["region_id", "mes"]), ("clim_comuna", ["region_id"])):
        por_anio = d[ent].groupby(llave + ["anio"])["y"].agg(["sum", "count"])
        total = por_anio.groupby(level=llave).sum()
        # Todas las filas: con todos los años de entrenamiento
        tot = d[llave].join(total, on=llave)
        valor = tot["sum"] / tot["count"]
        # Filas de entrenamiento: restando su propio año
        propio = d.loc[ent, llave + ["anio"]].join(por_anio, on=llave + ["anio"])
        resto_sum = tot.loc[ent, "sum"] - propio["sum"]
        resto_n = tot.loc[ent, "count"] - propio["count"]
        valor.loc[ent] = (resto_sum / resto_n.where(resto_n > 0)).to_numpy()
        out[nombre] = valor.fillna(0).astype("float32").to_numpy()
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
