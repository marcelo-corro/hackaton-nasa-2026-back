"""Modelo B: si hay fuego en la comuna un día, ¿en qué sectores cae?

Probabilidad condicional P(fuego en el sector el día d | hay fuego en la comuna el día d), con lo conocido hasta d-1:
- qué hay en el sector (vegetación, interfaz, pendiente, caminos, cercanía a lo construido);
- su historial y el de sus 8 vecinos (días con fuego antes de d, días desde el último);
- el fuego reciente (focos de d-3 a d-1): en la celda, en las vecinas y la distancia al más cercano.

Una fila por sector y por día con fuego en su comuna. La probabilidad de fuego en un sector para un horizonte es
P(comuna) × P(sector | comuna), con P(comuna) del modelo por comuna (firecal.model).
Las celdas se identifican por su índice global (ix, iy): el historial de una celda partida entre dos comunas es uno.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ORIGEN = np.datetime64("2012-01-01", "D")
K_DIA = 100_000
VECINOS = [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)]
DIAS_RECIENTES = 3
TOPE_DIAS = 9999
TOPE_KM = 30.0

ESTATICAS = ["frac_arboles", "frac_matorral", "frac_pastizal", "frac_cultivo", "frac_construido", "frac_desnudo",
             "frac_agua", "frac_wui", "frac_wui_bosque", "frac_wui_pastizal", "pendiente_media", "frac_pend_fuerte",
             "frac_pend_muy_fuerte", "dens_principal", "dens_secundario", "dens_residencial", "dens_huella",
             "dist_camino_km", "dist_urbano_km", "area_km2"]
DINAMICAS = ["hist_dias", "hist_dias_vecinos", "dias_desde_ultimo", "recientes_celda", "recientes_vecinos",
             "dist_foco_reciente_km", "comuna_con_fuego_reciente", "mes"]
VARIABLES_B = ESTATICAS + DINAMICAS


def dia_entero(fechas) -> np.ndarray:
    return (pd.to_datetime(fechas).to_numpy().astype("datetime64[D]") - ORIGEN).astype(np.int64)


def codigo_celda(ix, iy) -> np.ndarray:
    return (np.asarray(ix, np.int64) + 5000) * 10_000 + (np.asarray(iy, np.int64) + 5000)


class Historial:
    """Días con fuego por celda, para contar en ventanas [d0, d1) con búsqueda binaria."""

    def __init__(self, celda: np.ndarray, dia: np.ndarray):
        self.claves = np.unique(np.asarray(celda, np.int64) * K_DIA + np.asarray(dia, np.int64))

    def contar(self, celda: np.ndarray, d0: np.ndarray, d1: np.ndarray) -> np.ndarray:
        base = np.asarray(celda, np.int64) * K_DIA
        return np.searchsorted(self.claves, base + d1) - np.searchsorted(self.claves, base + d0)

    def dias_desde_ultimo(self, celda: np.ndarray, d: np.ndarray) -> np.ndarray:
        base = np.asarray(celda, np.int64) * K_DIA
        i = np.searchsorted(self.claves, base + d) - 1
        previo = self.claves[np.clip(i, 0, None)]
        misma = (i >= 0) & (previo // K_DIA == np.asarray(celda, np.int64))
        return np.where(misma, d - previo % K_DIA, TOPE_DIAS)


def tabla_condicional(sectores: pd.DataFrame, focos: pd.DataFrame, xy_focos: np.ndarray,
                      xy_sectores: np.ndarray, pares: list[tuple[str, int]] | None = None) -> pd.DataFrame:
    """Una fila por (sector, día con fuego en su comuna), con variables hasta d-1 y la etiqueta `y`.

    `sectores` trae sector_id, region_id, ix, iy y las ESTATICAS; `focos`, sector_id, region_id y fecha_local (sin
    fuentes persistentes); `xy_focos` y `xy_sectores`, coordenadas métricas alineadas con `focos` y `sectores`.
    `pares` = [(region_id, día entero)] para predecir otros días (por ejemplo, todas las comunas el día siguiente
    al último dato); por defecto, los días con fuego de cada comuna (entrenamiento y validación).
    """
    s = sectores.reset_index(drop=True)
    pos = pd.Series(np.arange(len(s)), index=s["sector_id"])
    f = focos.reset_index(drop=True).assign(dia=dia_entero(focos["fecha_local"]))
    f = f[f["sector_id"].isin(pos.index)]
    f_pos = pos[f["sector_id"]].to_numpy()
    celda_s = codigo_celda(s["ix"], s["iy"])
    hist = Historial(celda_s[f_pos], f["dia"].to_numpy())
    ardio = set(zip(f_pos, f["dia"].to_numpy()))
    xy_f = xy_focos[f.index.to_numpy()] if len(f) else np.empty((0, 2))
    dias_f = f["dia"].to_numpy()
    comuna_f = f["region_id"].astype(str).to_numpy()

    por_comuna = {rid: np.flatnonzero(s["region_id"].to_numpy() == rid) for rid in s["region_id"].unique()}
    partes = []
    if pares is None:
        pares = list(f[["region_id", "dia"]].drop_duplicates().itertuples(index=False, name=None))
    for (rid, d) in pares:
        idx = por_comuna[str(rid)]
        reciente = (dias_f >= d - DIAS_RECIENTES) & (dias_f < d)
        if reciente.any():
            dist, _ = cKDTree(xy_f[reciente]).query(xy_sectores[idx])
            dist = np.minimum(dist / 1000, TOPE_KM)
        else:
            dist = np.full(len(idx), TOPE_KM)
        partes.append(pd.DataFrame({
            "_pos": idx, "dia": d, "dist_foco_reciente_km": dist,
            "comuna_con_fuego_reciente": float((reciente & (comuna_f == str(rid))).any()),
        }))
    t = pd.concat(partes, ignore_index=True)
    p = t["_pos"].to_numpy()
    d = t["dia"].to_numpy()
    celda = celda_s[p]
    ix, iy = s["ix"].to_numpy()[p], s["iy"].to_numpy()[p]
    t["hist_dias"] = hist.contar(celda, np.zeros_like(d), d)
    t["dias_desde_ultimo"] = hist.dias_desde_ultimo(celda, d)
    t["recientes_celda"] = hist.contar(celda, d - DIAS_RECIENTES, d)
    vec_hist = np.zeros(len(t), np.int64)
    vec_rec = np.zeros(len(t), np.int64)
    for dx, dy in VECINOS:
        cv = codigo_celda(ix + dx, iy + dy)
        vec_hist += hist.contar(cv, np.zeros_like(d), d)
        vec_rec += hist.contar(cv, d - DIAS_RECIENTES, d)
    t["hist_dias_vecinos"] = vec_hist
    t["recientes_vecinos"] = vec_rec
    t["mes"] = (ORIGEN + d.astype("timedelta64[D]")).astype("datetime64[M]").astype(int) % 12 + 1
    t["y"] = [float((a, b) in ardio) for a, b in zip(p, d)]
    estaticas = s[["sector_id", "region_id"] + ESTATICAS].iloc[p].reset_index(drop=True)
    t = pd.concat([estaticas, t.drop(columns="_pos")], axis=1)
    t["fecha"] = ORIGEN + t["dia"].to_numpy().astype("timedelta64[D]")
    return t


def captura_top(t: pd.DataFrame, puntaje: np.ndarray, fraccion: float = 0.10, semilla: int = 0) -> float:
    """% de los sector-día con fuego que caen en el `fraccion` de sectores con mayor puntaje de su comuna ese día.
    Empates al azar (con semilla), para no favorecer el orden del archivo."""
    rng = np.random.default_rng(semilla)
    d = pd.DataFrame({"g": t["region_id"].astype(str) + "_" + t["dia"].astype(str), "p": puntaje,
                      "r": rng.random(len(t)), "y": t["y"].to_numpy()})
    d = d.sort_values(["g", "p", "r"], ascending=[True, False, False])
    d["rango"] = d.groupby("g").cumcount()
    n = d.groupby("g")["y"].transform("size")
    d["top"] = d["rango"] < np.maximum(1, np.round(fraccion * n))
    return float(d.loc[d["y"] == 1, "top"].mean())


def etiqueta_grande(t: pd.DataFrame, focos: pd.DataFrame, umbral: int = 10) -> np.ndarray:
    """Para filas con fuego: ¿el sector ardió ese día como parte de un incendio de más de `umbral` focos?"""
    f = focos.assign(dia=dia_entero(focos["fecha_local"]))
    g = f.groupby(["sector_id", "dia"])["focos_incendio"].max()
    return (g.reindex(list(zip(t["sector_id"], t["dia"]))).to_numpy() > umbral).astype(float)
