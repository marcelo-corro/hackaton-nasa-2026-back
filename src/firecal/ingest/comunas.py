"""Límites comunales de la BCN y asignación de focos a comunas.

Salida de `preparar_comunas` (data/interim/comunas.parquet, GeoParquet en EPSG:4326):

    region_id   string   CUT de 5 dígitos ("05109")
    nombre      string   nombre de la comuna
    provincia   string
    region      string
    cod_region  int
    area_km2    float    superficie (proyección de áreas iguales para Sudamérica)
    geometry             polígono o multipolígono válido
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon
from shapely.geometry.base import BaseGeometry

CRS_GEOGRAFICO = "EPSG:4326"
CRS_AREA = "ESRI:102033"  # South America Albers Equal Area Conic
COLUMNAS = ["region_id", "nombre", "provincia", "region", "cod_region", "area_km2", "geometry"]


def _solo_poligonos(geom: BaseGeometry | None) -> BaseGeometry | None:
    """Deja solo la parte poligonal (make_valid puede devolver colecciones con líneas o puntos)."""
    if geom is None or geom.is_empty:
        return None
    if isinstance(geom, (Polygon, MultiPolygon)):
        return geom
    if isinstance(geom, GeometryCollection):
        poligonos: list[Polygon] = []
        for parte in geom.geoms:
            if isinstance(parte, Polygon):
                poligonos.append(parte)
            elif isinstance(parte, MultiPolygon):
                poligonos.extend(parte.geoms)
        return MultiPolygon(poligonos) if poligonos else None
    return None


def preparar_comunas(bcn: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Deja el shapefile de comunas de la BCN listo para cruzar con focos.

    - Excluye la "Zona sin demarcar" (cod_comuna = 0).
    - region_id = CUT de 5 dígitos como texto (5109 -> "05109").
    - Reproyecta a EPSG:4326, repara geometrías inválidas y deja solo polígonos.
    - Calcula la superficie en km².
    """
    comunas = bcn[bcn["cod_comuna"].astype(int) != 0].to_crs(CRS_GEOGRAFICO)
    geometria = comunas.geometry.make_valid().map(_solo_poligonos)
    if geometria.isna().any():
        malas = comunas.loc[geometria.isna(), "Comuna"].tolist()
        raise ValueError(f"Comunas sin polígono válido tras la reparación: {malas}")

    salida = gpd.GeoDataFrame(
        {
            "region_id": comunas["cod_comuna"].astype(int).astype(str).str.zfill(5).astype("string"),
            "nombre": comunas["Comuna"].astype("string"),
            "provincia": comunas["Provincia"].astype("string"),
            "region": comunas["Region"].astype("string"),
            "cod_region": comunas["codregion"].astype(int),
        },
        geometry=gpd.GeoSeries(geometria, crs=CRS_GEOGRAFICO),
    )
    salida["area_km2"] = salida.geometry.to_crs(CRS_AREA).area / 1e6

    if salida["region_id"].duplicated().any():
        repetidos = salida.loc[salida["region_id"].duplicated(), "region_id"].tolist()
        raise ValueError(f"Códigos de comuna repetidos: {repetidos}")
    if not salida.is_valid.all():
        raise ValueError("Quedaron geometrías inválidas después de la reparación")

    return salida[COLUMNAS].sort_values("region_id").reset_index(drop=True)


def cargar_comunas(ruta_shp: Path) -> gpd.GeoDataFrame:
    """Lee el shapefile de la BCN y lo prepara (ver `preparar_comunas`)."""
    return preparar_comunas(gpd.read_file(ruta_shp))


def asignar_comunas(focos: pd.DataFrame, comunas: gpd.GeoDataFrame, tolerancia_m: float = 1000) -> pd.DataFrame:
    """Agrega a cada foco la comuna que lo contiene.

    Columnas nuevas:
        region_id   string  CUT de la comuna, nulo si el foco no se pudo asignar
        asignacion  string  "dentro" (el punto cae en la comuna), "cercana" (cae fuera, a menos de
                            `tolerancia_m` metros de la comuna más cercana) o nulo

    La tolerancia existe porque el punto de FIRMS es el centro del píxel (375 m en VIIRS, 1 km en MODIS):
    un foco en la costa puede tener su centro en el mar. Con `tolerancia_m=0` solo se usa "dentro".
    Si un foco cae justo en el límite entre dos comunas, se queda con la primera que encuentre.
    """
    comunas = comunas[["region_id", "geometry"]].to_crs(CRS_GEOGRAFICO)
    puntos = gpd.GeoDataFrame(
        index=focos.index,
        geometry=gpd.points_from_xy(focos["lon"], focos["lat"]),
        crs=CRS_GEOGRAFICO,
    )
    cruce = gpd.sjoin(puntos, comunas, how="left", predicate="within")
    cruce = cruce[~cruce.index.duplicated(keep="first")]
    region_id = cruce["region_id"].reindex(focos.index).astype("string")
    asignacion = pd.Series(pd.NA, index=focos.index, dtype="string")
    asignacion[region_id.notna()] = "dentro"

    sin_comuna = region_id.isna()
    if tolerancia_m > 0 and sin_comuna.any():
        cercanos = gpd.sjoin_nearest(
            puntos[sin_comuna].to_crs(CRS_AREA),
            comunas.to_crs(CRS_AREA),
            how="inner",
            max_distance=tolerancia_m,
        )
        cercanos = cercanos[~cercanos.index.duplicated(keep="first")]
        region_id[cercanos.index] = cercanos["region_id"].astype("string")
        asignacion[cercanos.index] = "cercana"

    return focos.assign(region_id=region_id, asignacion=asignacion)
