"""Agrupación de focos en eventos (incendios) y coincidencia entre sensores.

Dos focos del mismo grupo de satélites pertenecen al mismo evento si están a menos de `d_km` en cada eje
(vecindario cuadrado) y a menos de `t_dias` días locales; un evento es una componente conexa de esa relación
(si A toca a B y B toca a C, A, B y C son un evento). Es una aproximación simple y transparente a "un incendio".
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

KM_POR_GRADO_LAT = 110.57
KM_POR_GRADO_LON_ECUADOR = 111.32


def _coordenadas(lat: np.ndarray, lon: np.ndarray, dia: np.ndarray, d_km: float, t_dias: float) -> np.ndarray:
    """Coordenadas escaladas: una unidad = d_km en el espacio y t_dias en el tiempo."""
    y = lat * KM_POR_GRADO_LAT
    x = lon * KM_POR_GRADO_LON_ECUADOR * np.cos(np.radians(lat))
    return np.column_stack([x / d_km, y / d_km, dia / t_dias])


def _dias(fechas: pd.Series) -> np.ndarray:
    return fechas.to_numpy().astype("datetime64[D]").astype(np.int64).astype(float)


def etiquetar_eventos(focos: pd.DataFrame, d_km: float = 2.0, t_dias: float = 2.0) -> np.ndarray:
    """Etiqueta de evento (0..k-1) para cada fila de `focos` (columnas `lat`, `lon`, `fecha_local`)."""
    n = len(focos)
    if n == 0:
        return np.array([], dtype=int)
    puntos = _coordenadas(focos["lat"].to_numpy(float), focos["lon"].to_numpy(float), _dias(focos["fecha_local"]),
                          d_km, t_dias)
    pares = cKDTree(puntos).query_pairs(r=1.0, p=np.inf, output_type="ndarray")
    grafo = coo_matrix((np.ones(len(pares), dtype=np.int8), (pares[:, 0], pares[:, 1])), shape=(n, n))
    _, etiquetas = connected_components(grafo, directed=False)
    return etiquetas


def resumir_eventos(focos: pd.DataFrame, etiquetas: np.ndarray) -> pd.DataFrame:
    """Una fila por evento: inicio, fin, duración, número de focos, FRP total, centroide y comuna más frecuente."""
    d = focos.assign(evento=etiquetas)
    g = d.groupby("evento")
    resumen = pd.DataFrame(
        {
            "inicio": g["fecha_local"].min(),
            "fin": g["fecha_local"].max(),
            "n_focos": g.size(),
            "frp_total": g["frp"].sum() if "frp" in d else np.nan,
            "lat": g["lat"].mean(),
            "lon": g["lon"].mean(),
        }
    )
    if "region_id" in d:
        resumen["region_id"] = g["region_id"].agg(lambda s: s.mode().iat[0] if s.notna().any() else pd.NA)
    resumen["dias"] = (resumen["fin"] - resumen["inicio"]).dt.days + 1
    return resumen.reset_index()


def evento_detectado_por(
    focos_a: pd.DataFrame, etiquetas_a: np.ndarray, focos_b: pd.DataFrame, d_km: float = 2.0, t_dias: float = 1.0
) -> pd.Series:
    """Para cada evento de A: ¿algún foco de B cae a menos de `d_km` y `t_dias` de algún foco del evento?

    Devuelve una serie booleana indexada por etiqueta de evento de A.
    """
    if len(focos_b) == 0:
        return pd.Series(False, index=np.unique(etiquetas_a))
    pa = _coordenadas(focos_a["lat"].to_numpy(float), focos_a["lon"].to_numpy(float), _dias(focos_a["fecha_local"]),
                      d_km, t_dias)
    pb = _coordenadas(focos_b["lat"].to_numpy(float), focos_b["lon"].to_numpy(float), _dias(focos_b["fecha_local"]),
                      d_km, t_dias)
    distancia, _ = cKDTree(pb).query(pa, k=1, p=np.inf, distance_upper_bound=1.0 + 1e-9)
    tiene_vecino = np.isfinite(distancia)
    return pd.Series(tiene_vecino).groupby(etiquetas_a).any()
