"""Historial de focos por sector (descriptivo: dónde ha habido fuego, no una probabilidad).

Se usa VIIRS Suomi NPP con `uso_base` (2012-2025), el mismo sensor y filtro del objetivo del modelo de riesgo, para
que el historial sea comparable en el tiempo (mezclar MODIS y VIIRS sin armonizar exageraría los años recientes).
Incendio = evento de firecal.events (focos a < 2 km y < 2 días); "grande" = más de 10 focos, como en docs/eventos.md.
"""

from __future__ import annotations

import geopandas as gpd
import numpy as np
import pandas as pd

from firecal.events.agrupar import etiquetar_eventos

SATELITE = "SNPP"
FOCOS_INCENDIO_GRANDE = 10  # "más de 10 focos" (docs/eventos.md)


def focos_con_evento(focos: pd.DataFrame) -> pd.DataFrame:
    """Focos Suomi NPP `uso_base` con el tamaño (n.º de focos) del incendio al que pertenecen.

    El agrupamiento se hace con todos los focos del país, para que un incendio que cruza una comuna no se parta.
    """
    f = focos[(focos["satelite"] == SATELITE) & focos["uso_base"]].copy()
    etiquetas = etiquetar_eventos(f)
    f["evento"] = etiquetas
    f["focos_incendio"] = np.bincount(etiquetas)[etiquetas]
    return f


def asignar_sector(focos: pd.DataFrame, sectores: gpd.GeoDataFrame) -> pd.DataFrame:
    """Agrega `sector_id` a cada foco que cae dentro de algún sector (los demás se descartan)."""
    f = focos[focos["region_id"].astype(str).isin(set(sectores["region_id"]))]
    pts = gpd.GeoDataFrame(f, geometry=gpd.points_from_xy(f["lon"], f["lat"]), crs="EPSG:4326").to_crs(sectores.crs)
    j = gpd.sjoin(pts, sectores[["sector_id", "geometry"]], predicate="within", how="inner")
    j = j[~j.index.duplicated(keep="first")]  # un punto justo en el borde de dos celdas: una sola
    return pd.DataFrame(j.drop(columns=["geometry", "index_right"]))


def fuentes_persistentes(focos_sector: pd.DataFrame, min_dias: int = 10, min_anios: int = 5,
                         min_noche: float = 0.6, max_focos_incendio: int = FOCOS_INCENDIO_GRANDE) -> pd.DataFrame:
    """Sectores con detecciones persistentes que probablemente NO son incendios (industria, antorchas de refinería).

    FIRMS marca algunas fuentes fijas (`tipo` 2) y ya se excluyen en `uso_base`, pero no todas. Regla del proyecto
    (medida en la Región de Valparaíso, ver docs/sectores.md): fuego en >= `min_dias` días de >= `min_anios` años,
    >= `min_noche` de las detecciones de noche (en la región, el 39 % de los focos es nocturno) y nunca parte de un
    incendio de más de `max_focos_incendio` focos. Devuelve sector_id y sus métricas.
    """
    d = focos_sector.assign(dia=focos_sector["fecha_local"].dt.normalize(),
                            noche=focos_sector["dia_noche"].eq("N").fillna(False))
    g = d.groupby("sector_id").agg(dias=("dia", "nunique"), anios=("dia", lambda s: s.dt.year.nunique()),
                                   frac_noche=("noche", "mean"), frp_mediana=("frp", "median"),
                                   mayor_incendio=("focos_incendio", "max"))
    marca = ((g["dias"] >= min_dias) & (g["anios"] >= min_anios) & (g["frac_noche"] >= min_noche)
             & (g["mayor_incendio"] <= max_focos_incendio))
    return g[marca].reset_index()


def historial_por_sector(focos_sector: pd.DataFrame, sectores: gpd.GeoDataFrame) -> pd.DataFrame:
    """Por sector: días con fuego, focos, años con fuego, último día con fuego, incendios grandes y el mayor incendio."""
    d = focos_sector.assign(dia=focos_sector["fecha_local"].dt.normalize())
    g = d.groupby("sector_id")
    grandes = d[d["focos_incendio"] > FOCOS_INCENDIO_GRANDE].groupby("sector_id")["evento"].nunique()
    h = pd.DataFrame({
        "dias_con_fuego": g["dia"].nunique(),
        "focos": g.size(),
        "anios_con_fuego": g["dia"].agg(lambda s: s.dt.year.nunique()),
        "ultimo_fuego": g["dia"].max(),
        "incendios_grandes": grandes,
        "mayor_incendio_focos": g["focos_incendio"].max(),
    })
    h = sectores[["sector_id"]].set_index("sector_id").join(h)
    for c in ["dias_con_fuego", "focos", "anios_con_fuego", "incendios_grandes", "mayor_incendio_focos"]:
        h[c] = h[c].fillna(0).astype(int)
    return h.reset_index()
