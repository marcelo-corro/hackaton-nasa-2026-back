"""Caminos (OpenStreetMap) y cercanía a lo construido, por sector. Variables del modelo B.

Casi todas las igniciones en Chile son humanas: los caminos y el borde de lo construido indican por dónde anda la
gente. Densidad = km de camino por km² de sector, por tipo:
- principal: motorway, trunk, primary, secondary (y sus enlaces);
- secundario: tertiary, unclassified;
- residencial: residential;
- huella: track (caminos de tierra rurales y forestales).
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.spatial import cKDTree

TIPO_CAMINO = {"motorway": "principal", "trunk": "principal", "primary": "principal", "secondary": "principal",
               "tertiary": "secundario", "unclassified": "secundario", "residential": "residencial", "track": "huella"}
TIPOS = ["principal", "secundario", "residencial", "huella"]
UMBRAL_URBANO = 0.30  # un sector con >= 30 % construido cuenta como zona construida
TOPE_KM = 30.0


def leer_caminos(ruta: Path) -> gpd.GeoDataFrame:
    """Respuesta JSON de Overpass (`out geom`) → líneas con su tipo, en EPSG:4326."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    geoms, tipos = [], []
    for e in datos["elements"]:
        if e.get("type") != "way" or len(e.get("geometry", [])) < 2:
            continue
        clase = e.get("tags", {}).get("highway", "").removesuffix("_link")
        if clase not in TIPO_CAMINO:
            continue
        geoms.append(shapely.linestrings([(p["lon"], p["lat"]) for p in e["geometry"]]))
        tipos.append(TIPO_CAMINO[clase])
    return gpd.GeoDataFrame({"tipo": tipos}, geometry=geoms, crs="EPSG:4326")


def variables_caminos(sectores: gpd.GeoDataFrame, caminos: gpd.GeoDataFrame) -> pd.DataFrame:
    """Por sector: densidad de cada tipo (km/km²) y distancia del punto del sector al camino más cercano (km)."""
    s = sectores.reset_index(drop=True)
    c = caminos.to_crs(s.crs).reset_index(drop=True)
    pares = gpd.sjoin(c[["geometry"]], s[["geometry"]], predicate="intersects", how="inner")
    largo = shapely.length(shapely.intersection(c.geometry.values[pares.index.to_numpy()],
                                                s.geometry.values[pares["index_right"].to_numpy()]))
    t = pd.DataFrame({"sector": pares["index_right"].to_numpy(), "tipo": c["tipo"].to_numpy()[pares.index.to_numpy()],
                      "km": largo / 1000})
    dens = t.pivot_table(index="sector", columns="tipo", values="km", aggfunc="sum").reindex(
        index=range(len(s)), columns=TIPOS).fillna(0.0)
    out = pd.DataFrame({"sector_id": s["sector_id"]})
    for tipo in TIPOS:
        out[f"dens_{tipo}"] = dens[tipo].to_numpy() / s["area_km2"].to_numpy()
    punto = s.geometry.representative_point()
    arbol = shapely.STRtree(c.geometry.values)
    _, dist = arbol.query_nearest(punto.values, return_distance=True, all_matches=False)
    out["dist_camino_km"] = np.minimum(dist / 1000, TOPE_KM)
    return out


def distancia_urbano(sectores: gpd.GeoDataFrame) -> pd.Series:
    """Distancia (km) del punto de cada sector al sector más cercano con >= 30 % construido (0 si él mismo lo es)."""
    s = sectores.reset_index(drop=True)
    p = s.geometry.representative_point()
    xy = np.column_stack([p.x, p.y])
    urbano = s["frac_construido"].to_numpy() >= UMBRAL_URBANO
    if not urbano.any():
        return pd.Series(TOPE_KM, index=s.index)
    d, _ = cKDTree(xy[urbano]).query(xy)
    return pd.Series(np.minimum(d / 1000, TOPE_KM), index=s.index)
