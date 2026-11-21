"""Fuentes fijas que se repiten año tras año y no son incendios de vegetación (industria, minería, volcanes, rellenos).

FIRMS marca algunas fuentes fijas (`tipo` 2) y volcanes (`tipo` 1), pero no todas, y los focos casi en tiempo real no
traen esa marca (el paso 1b la deduce de los focos históricos). Este módulo arma y aplica una máscara de celdas de 1 km
medida con la historia:

- **Fuego repetido:** focos Suomi NPP de vegetación con confianza nominal o alta en >= 10 días de >= 5 años.
- **Fuente persistente:** fuego repetido y además
  - **sin vegetación:** < 10 % de vegetación en ESA WorldCover 2021 (ventana de 1,5 km); ahí no hay qué quemar, o
  - **nocturna y fija:** >= 60 % de las detecciones de noche y nunca parte de un incendio que se propague (más de 10
    focos o más de 2 km). Es la regla medida en los sectores de Valparaíso (firecal.sectores.historial), con la
    extensión como segunda vía: una fuente que detecta casi a diario se encadena en "incendios" largos que no se mueven.
- **Dos grillas:** celdas de 1 km en UTM 19S y otra corrida 500 m, para no perder una fuente en el borde de una celda.

scripts/04b_fuentes_persistentes.py mide la máscara y la guarda en ref/fuentes_persistentes.csv (versionada: el paso
diario no vuelve a leer WorldCover). firecal.calidad marca `fuente_persistente` en cada foco que cae en una celda de la
máscara, de cualquier sensor, y esos focos salen de `uso_base`. Cifras: docs/fuentes_persistentes.md.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

from firecal import config

CRS_METRICO = "EPSG:32719"  # UTM 19S: cubre Chile continental con poca deformación a escala de 1 km
LADO_M = 1000
DESFASES_M = (0, 500)
SATELITE = "SNPP"
MIN_DIAS = 10
MIN_ANIOS = 5
MAX_VEGETACION = 0.10
MIN_NOCHE = 0.6
MAX_FOCOS_INCENDIO = 10
MAX_EXTENSION_KM = 2
RUTA_MASCARA = config.RAIZ / "ref" / "fuentes_persistentes.csv"
COLUMNAS_MASCARA = ["desfase_m", "cx", "cy", "lat", "lon", "region_id", "comuna", "dias", "anios", "frac_noche",
                    "mayor_incendio", "mayor_extension_km", "frac_vegetacion", "motivo"]

_A_METRICO = Transformer.from_crs("EPSG:4326", CRS_METRICO, always_xy=True)


def indices_celda(lon, lat, desfase_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Índices (columna, fila) de la celda de 1 km de cada punto en la grilla corrida `desfase_m` metros."""
    x, y = _A_METRICO.transform(np.asarray(lon, dtype=float), np.asarray(lat, dtype=float))
    return (np.floor((x + desfase_m) / LADO_M).astype(np.int64), np.floor((y + desfase_m) / LADO_M).astype(np.int64))


def metricas_celdas(focos: pd.DataFrame, desfase_m: float) -> pd.DataFrame:
    """Métricas de las celdas con fuego repetido en una grilla.

    `focos`: focos ya filtrados (un sensor, vegetación, confianza, período) con lat, lon, fecha_local, dia_noche,
    region_id y `evento` (etiqueta de firecal.events.agrupar.etiquetar_eventos sobre esos mismos focos).
    Devuelve una fila por celda con >= MIN_DIAS días de >= MIN_ANIOS años: desfase_m, cx, cy, días, años, fracción
    nocturna, el mayor incendio (n.º de focos) y su mayor extensión (km), y la posición mediana de sus focos.
    """
    f = focos[["lat", "lon", "fecha_local", "dia_noche", "region_id", "evento"]].copy()
    f["cx"], f["cy"] = indices_celda(f["lon"], f["lat"], desfase_m)
    f["dia"] = pd.to_datetime(f["fecha_local"]).dt.normalize()
    f["noche"] = f["dia_noche"].eq("N").fillna(False).astype(bool)
    f["focos_incendio"] = f.groupby("evento")["evento"].transform("size")
    ext = f.groupby("evento").agg(x0=("cx", "min"), x1=("cx", "max"), y0=("cy", "min"), y1=("cy", "max"))
    f["extension_km"] = f["evento"].map(np.maximum(ext["x1"] - ext["x0"], ext["y1"] - ext["y0"]) * LADO_M / 1000)
    g = f.groupby(["cx", "cy"]).agg(
        dias=("dia", "nunique"), anios=("dia", lambda s: s.dt.year.nunique()), frac_noche=("noche", "mean"),
        mayor_incendio=("focos_incendio", "max"), mayor_extension_km=("extension_km", "max"),
        lat=("lat", "median"), lon=("lon", "median"),
        region_id=("region_id", lambda s: s.astype(str).mode().iat[0]))
    g = g[(g["dias"] >= MIN_DIAS) & (g["anios"] >= MIN_ANIOS)].reset_index()
    g.insert(0, "desfase_m", int(desfase_m))
    return g


def clasificar(celdas: pd.DataFrame) -> pd.DataFrame:
    """Agrega `sin_vegetacion`, `nocturna_fija`, `persistente` y `motivo` a celdas con `frac_vegetacion`.

    Sin dato de vegetación (NaN) no se marca por esa vía: ante la duda, el foco se sigue contando.
    """
    c = celdas.copy()
    c["sin_vegetacion"] = c["frac_vegetacion"].lt(MAX_VEGETACION).fillna(False).astype(bool)
    c["nocturna_fija"] = (c["frac_noche"] >= MIN_NOCHE) & (
        (c["mayor_incendio"] <= MAX_FOCOS_INCENDIO) | (c["mayor_extension_km"] <= MAX_EXTENSION_KM))
    c["persistente"] = c["sin_vegetacion"] | c["nocturna_fija"]
    c["motivo"] = np.select([c["sin_vegetacion"] & c["nocturna_fija"], c["sin_vegetacion"], c["nocturna_fija"]],
                            ["sin_vegetacion+nocturna_fija", "sin_vegetacion", "nocturna_fija"], default="")
    return c


def en_fuente_persistente(focos: pd.DataFrame, mascara: pd.DataFrame | None) -> pd.Series:
    """True para cada foco que cae en alguna celda de la máscara (en cualquiera de sus grillas)."""
    marca = pd.Series(False, index=focos.index)
    if mascara is None or mascara.empty or focos.empty:
        return marca
    for desfase, celdas in mascara.groupby("desfase_m"):
        cx, cy = indices_celda(focos["lon"], focos["lat"], float(desfase))
        claves = pd.MultiIndex.from_arrays([celdas["cx"].astype(np.int64), celdas["cy"].astype(np.int64)])
        marca |= pd.Series(pd.MultiIndex.from_arrays([cx, cy]).isin(claves), index=focos.index)
    return marca


def leer_mascara(ruta: Path = RUTA_MASCARA) -> pd.DataFrame | None:
    """La máscara versionada, o None si no existe (entonces ningún foco se marca)."""
    if not ruta.exists():
        return None
    return pd.read_csv(ruta, dtype={"region_id": str})
