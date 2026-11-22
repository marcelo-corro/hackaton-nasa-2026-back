"""Atributos fijos de los sectores: grilla y resumen de las capas del territorio (vegetación, interfaz, pendiente,
caminos y distancia a lo construido).

No cambian de un día a otro: se calculan una vez por región (con las capas de `11_descargar_capas.py`) y se guardan en
data/processed/sectores_<región>_fijo.parquet junto con una huella de lo que los determina (versión de este cálculo y
límites de las comunas). Cada día `12_sectores.py` los lee y solo rehace el historial de focos.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from pyproj.transformer import TransformerGroup

from firecal import config
from firecal.sectores.capas import (
    CLASES_WORLDCOVER, CLASES_WUI, MAX_SIN_DATO_WUI, resumen_categorico, resumen_pendiente,
)
from firecal.sectores.caminos import distancia_urbano, leer_caminos, variables_caminos
from firecal.sectores.grilla import CRS_METRICO, LADO_M, grilla_sectores

# Subir si cambia cómo se calculan los atributos fijos (umbrales, capas, grilla): obliga a rehacerlos.
VERSION_FIJO = 1
COLUMNAS_GRILLA = ["sector_id", "region_id", "ix", "iy", "area_km2", "geometry", "lat", "lon"]  # como grilla_sectores


def huella_fijo(comunas: gpd.GeoDataFrame) -> str:
    """Huella (sha256) de lo que determina los atributos fijos: versión del cálculo, grilla y límites de las comunas."""
    h = hashlib.sha256(f"fijo-v{VERSION_FIJO}|{CRS_METRICO}|{LADO_M}".encode())
    for rid, geom in sorted(zip(comunas["region_id"].astype(str), comunas.geometry)):
        h.update(rid.encode())
        h.update(shapely.to_wkb(geom))
    return h.hexdigest()


def rutas_fijo(region: str) -> tuple[Path, Path]:
    base = config.PROCESSED_DIR / f"sectores_{region}_fijo"
    return base.with_suffix(".parquet"), base.with_suffix(".json")


def leer_fijo(region: str, huella: str) -> gpd.GeoDataFrame | None:
    """Atributos fijos guardados, si existen y su huella calza; si no, None (hay que calcularlos)."""
    ruta, meta = rutas_fijo(region)
    if not (ruta.exists() and meta.exists()):
        return None
    if json.loads(meta.read_text(encoding="utf-8")).get("huella") != huella:
        return None
    return gpd.read_parquet(ruta)


def guardar_fijo(tabla: gpd.GeoDataFrame, region: str, huella: str) -> None:
    ruta, meta = rutas_fijo(region)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tabla.to_parquet(ruta)
    meta.write_text(json.dumps({"huella": huella, "version": VERSION_FIJO, "sectores": len(tabla)}, indent=2),
                    encoding="utf-8")


def calcular_fijo(comunas: gpd.GeoDataFrame, capas: Path, region: str, avisar=print) -> gpd.GeoDataFrame:
    """Grilla de la región con el resumen de cada capa (lo que antes hacía `12_sectores.py` cada día)."""
    faltan = [d for d in ("worldcover", "copernicus_dem", "wui") if not any((capas / d).rglob("*.tif"))]
    if faltan:
        raise FileNotFoundError(f"Faltan capas en {capas} ({', '.join(faltan)}): corre "
                                f"`python scripts/11_descargar_capas.py --region {region}`.")
    sectores = grilla_sectores(comunas)
    avisar("Vegetación (WorldCover)...")
    veg = resumen_categorico(sorted((capas / "worldcover").glob("*.tif")), sectores, CLASES_WORLDCOVER)
    avisar("Interfaz con viviendas (WUI)...")
    wui = resumen_categorico(sorted((capas / "wui").rglob("WUI.tif")), sectores, CLASES_WUI)
    avisar("Pendiente (Copernicus DEM)...")
    pend = resumen_pendiente(sorted((capas / "copernicus_dem").glob("*.tif")), sectores)

    tabla = sectores.merge(veg, on="sector_id").merge(wui, on="sector_id").merge(pend, on="sector_id")
    tabla["frac_combustible"] = tabla[["frac_arboles", "frac_matorral", "frac_pastizal"]].sum(axis=1)
    tabla["dist_urbano_km"] = distancia_urbano(tabla).to_numpy()
    ruta_caminos = capas / "osm" / f"caminos_{region}.json"
    if ruta_caminos.exists():  # opcional: lo baja `11_descargar_capas.py --solo caminos` (modelo B)
        avisar("Caminos (OpenStreetMap)...")
        tabla = tabla.merge(variables_caminos(tabla, leer_caminos(ruta_caminos)), on="sector_id")
    # WUI: fracciones sobre la parte del sector con dato; vacías si falta más de la mitad
    con_dato = 1 - tabla["frac_wui_sin_dato"]
    for c in ["frac_wui_bosque", "frac_wui_pastizal", "frac_no_wui"]:
        tabla[c] = (tabla[c] / con_dato).where(tabla["frac_wui_sin_dato"] <= MAX_SIN_DATO_WUI)
    tabla["frac_wui"] = tabla["frac_wui_bosque"] + tabla["frac_wui_pastizal"]
    return gpd.GeoDataFrame(tabla, geometry="geometry", crs=sectores.crs)


def traslacion_sad69(lon: float, lat: float) -> list[float]:
    """Traslación (m) SAD69 → WGS84 que PROJ usa en ese punto para ESRI:102033 → EPSG:4326.

    PROJ elige la transformación según la zona (en Chile, una por franja de latitud). El front la necesita para pasar
    las esquinas de la grilla a longitud/latitud igual que geopandas (`app/lib/grilla.ts` del front).
    """
    directo = Transformer.from_crs("EPSG:4326", CRS_METRICO, always_xy=True)
    x, y = directo.transform(lon, lat)
    inverso = Transformer.from_crs(CRS_METRICO, "EPSG:4326", always_xy=True)
    esperado = np.array(inverso.transform(x, y))
    for t in TransformerGroup(CRS_METRICO, "EPSG:4326", always_xy=True).transformers:
        if "helmert" not in t.definition:
            continue
        if np.abs(np.array(t.transform(x, y)) - esperado).max() < 1e-9:
            partes = dict(p.split("=") for p in t.definition.split() if p[:2] in ("x=", "y=", "z="))
            return [float(partes["x"]), float(partes["y"]), float(partes["z"])]
    raise ValueError(f"No se encontró la transformación SAD69 → WGS84 de PROJ en ({lon}, {lat})")
