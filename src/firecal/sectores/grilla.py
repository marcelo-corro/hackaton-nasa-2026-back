"""Grilla de sectores: celdas cuadradas de 1 km (proyección de área igual) recortadas al límite de cada comuna.

Por qué 1 km: la ubicación de un foco VIIRS tiene un error del orden de su píxel (375 m); un sector más chico no
sería confiable. La grilla es global (índices ix, iy en metros / lado), así que una celda partida entre dos comunas
da dos sectores, uno por comuna, con el mismo ix/iy.
"""

from __future__ import annotations

import math

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

CRS_METRICO = "ESRI:102033"  # el mismo del modelo de riesgo (firecal.model.variables)
LADO_M = 1000.0
FRACCION_MINIMA = 0.02  # descarta astillas de borde de menos de 2 % de la celda (2 ha)


def grilla_sectores(comunas: gpd.GeoDataFrame, lado_m: float = LADO_M,
                    fraccion_minima: float = FRACCION_MINIMA) -> gpd.GeoDataFrame:
    """Un sector por (comuna, celda): `sector_id`, `region_id`, `ix`, `iy`, `area_km2`, `lat`, `lon`, geometría (CRS métrico)."""
    g = comunas.to_crs(CRS_METRICO)
    partes = []
    for rid, geom in zip(g["region_id"].astype(str), g.geometry):
        x0, y0, x1, y1 = geom.bounds
        ix, iy = np.meshgrid(np.arange(math.floor(x0 / lado_m), math.ceil(x1 / lado_m)),
                             np.arange(math.floor(y0 / lado_m), math.ceil(y1 / lado_m)))
        ix, iy = ix.ravel(), iy.ravel()
        cajas = shapely.box(ix * lado_m, iy * lado_m, (ix + 1) * lado_m, (iy + 1) * lado_m)
        shapely.prepare(geom)
        toca = shapely.intersects(geom, cajas)
        recorte = shapely.intersection(cajas[toca], geom)
        area = shapely.area(recorte)
        ok = area >= fraccion_minima * lado_m ** 2
        partes.append(gpd.GeoDataFrame(
            {"region_id": rid, "ix": ix[toca][ok], "iy": iy[toca][ok], "area_km2": area[ok] / 1e6},
            geometry=recorte[ok], crs=CRS_METRICO))
    s = pd.concat(partes, ignore_index=True)
    s.insert(0, "sector_id", s["region_id"] + "_" + s["ix"].astype(str) + "_" + s["iy"].astype(str))
    centro = s.geometry.representative_point().to_crs("EPSG:4326")
    s["lat"], s["lon"] = centro.y.round(5), centro.x.round(5)
    return gpd.GeoDataFrame(s, geometry="geometry", crs=CRS_METRICO)
