"""Capas fijas del territorio resumidas por sector (fracción de la superficie de cada sector en cada clase).

- Vegetación: ESA WorldCover 2021 v200 (10 m). Clases: 10 árboles, 20 matorral, 30 pastizal, 40 cultivo,
  50 construido, 60 suelo desnudo o escasa vegetación, 70 nieve, 80 agua, 90 humedal herbáceo, 95 manglar, 100 musgo.
  WorldCover no separa bosque nativo de plantación forestal.
- Interfaz con viviendas: WUI global de Schug et al. (2023), 10 m, ~2020. Clases 1-4 son WUI (1-2 dominada por
  bosque/matorral, 3-4 por pastizal; impares "intermix" = casas entre la vegetación, pares "interface" = casas junto
  a una gran área de vegetación); 5-8 no son WUI (5 bosque/matorral, 6 pastizal, 7 urbano, 8 otro).
- Pendiente: Copernicus DEM GLO-30 (30 m), en grados.

Método: se rasteriza el identificador de cada sector sobre la grilla del ráster (centro del píxel dentro del sector)
y se cuentan los píxeles por clase. Con píxeles de 10-30 m y sectores de 1 km el error de borde es despreciable.
"""

from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import Window, from_bounds
from shapely.geometry import box

CLASES_WORLDCOVER = {10: "arboles", 20: "matorral", 30: "pastizal", 40: "cultivo", 50: "construido",
                     60: "desnudo", 70: "agua", 80: "agua", 90: "agua", 95: "agua", 100: "desnudo"}
CLASES_WUI = {0: "wui_sin_dato", 1: "wui_bosque", 2: "wui_bosque", 3: "wui_pastizal", 4: "wui_pastizal",
              5: "no_wui", 6: "no_wui", 7: "no_wui", 8: "no_wui"}  # 0 no está en la leyenda: bordes con mar
MAX_SIN_DATO_WUI = 0.5  # si más de la mitad del sector no tiene dato de WUI, la fracción queda vacía
BORDES_PENDIENTE = [5.0, 15.0, 30.0]  # grados: plano <5, suave 5-15, fuerte 15-30, muy fuerte >30
CLASES_PENDIENTE = {0: "pend_plana", 1: "pend_suave", 2: "pend_fuerte", 3: "pend_muy_fuerte"}
BLOQUE = 4096


def _ids(sec: gpd.GeoDataFrame, forma: tuple[int, int], transform) -> np.ndarray:
    """Ráster con la posición (1..N) del sector en `sec`; 0 fuera de los sectores."""
    if sec.empty:
        return np.zeros(forma, dtype=np.int32)
    return rasterize(zip(sec.geometry, sec["_pos"] + 1), out_shape=forma, transform=transform, fill=0,
                     dtype="int32")


def _ventanas(src, sec: gpd.GeoDataFrame):
    """Ventanas de hasta BLOQUE × BLOQUE que cubren la parte del ráster donde hay sectores."""
    v = from_bounds(*sec.total_bounds, transform=src.transform).round_offsets().round_lengths()
    v = v.intersection(Window(0, 0, src.width, src.height))
    for fila in range(int(v.row_off), int(v.row_off + v.height), BLOQUE):
        for col in range(int(v.col_off), int(v.col_off + v.width), BLOQUE):
            yield Window(col, fila, min(BLOQUE, v.col_off + v.width - col), min(BLOQUE, v.row_off + v.height - fila))


def _contar(conteo: np.ndarray, ids: np.ndarray, codigos: np.ndarray, k: int) -> None:
    m = (ids > 0) & (codigos >= 0)
    clave = (ids[m].astype(np.int64) - 1) * k + codigos[m]
    conteo += np.bincount(clave, minlength=conteo.size).reshape(conteo.shape) if clave.size else 0


def _fracciones(conteo: np.ndarray, nombres: list[str], sectores: gpd.GeoDataFrame, prefijo: str) -> pd.DataFrame:
    total = conteo.sum(axis=1, keepdims=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        frac = np.where(total > 0, conteo / total, np.nan)
    d = pd.DataFrame(frac, columns=[f"{prefijo}{n}" for n in nombres])
    d.insert(0, "sector_id", sectores["sector_id"].to_numpy())
    return d


def resumen_categorico(rutas: list[Path], sectores: gpd.GeoDataFrame, clases: dict[int, str],
                       prefijo: str = "frac_") -> pd.DataFrame:
    """Fracción de cada sector en cada clase (las clases con el mismo nombre se suman)."""
    nombres = sorted(set(clases.values()), key=list(clases.values()).index)
    tabla = np.full(256 if max(clases) < 256 else max(clases) + 1, -1, dtype=np.int64)
    for valor, nombre in clases.items():
        tabla[valor] = nombres.index(nombre)
    s = sectores.reset_index(drop=True).assign(_pos=lambda d: np.arange(len(d)))
    conteo = np.zeros((len(s), len(nombres)), dtype=np.int64)
    for ruta in rutas:
        with rasterio.open(ruta) as src:
            sec = s.to_crs(src.crs)
            sec = sec[sec.intersects(box(*src.bounds))]
            if sec.empty:
                continue
            for w in _ventanas(src, sec):
                bw = box(*rasterio.windows.bounds(w, src.transform))
                sub = sec.iloc[sec.sindex.query(bw, predicate="intersects")]
                if sub.empty:
                    continue
                a = src.read(1, window=w)
                ids = _ids(sub, a.shape, src.window_transform(w))
                codigos = tabla[np.clip(a.astype(np.int64), 0, tabla.size - 1)]
                _contar(conteo, ids, codigos, len(nombres))
    return _fracciones(conteo, nombres, s, prefijo)


def _pendiente_grados(dem: np.ndarray, transform, nodata) -> np.ndarray:
    """Pendiente en grados de un DEM en grados geográficos (tamaño del píxel en metros según la latitud)."""
    z = dem.astype(np.float32)
    if nodata is not None:
        z[dem == nodata] = np.nan
    filas = np.arange(z.shape[0])
    lat = transform.f + (filas + 0.5) * transform.e
    dy = abs(transform.e) * 110_574.0
    dx = (abs(transform.a) * 111_320.0 * np.cos(np.radians(lat)))[:, None]
    gy, gx = np.gradient(z)
    return np.degrees(np.arctan(np.hypot(gx / dx, gy / dy)))


def resumen_pendiente(rutas: list[Path], sectores: gpd.GeoDataFrame) -> pd.DataFrame:
    """Pendiente media (grados) y fracción de cada sector por clase de pendiente."""
    s = sectores.reset_index(drop=True).assign(_pos=lambda d: np.arange(len(d)))
    k = len(CLASES_PENDIENTE)
    conteo = np.zeros((len(s), k), dtype=np.int64)
    suma = np.zeros(len(s))
    n = np.zeros(len(s))
    for ruta in rutas:
        with rasterio.open(ruta) as src:
            sec = s.to_crs(src.crs)
            sec = sec[sec.intersects(box(*src.bounds))]
            if sec.empty:
                continue
            pend = _pendiente_grados(src.read(1), src.transform, src.nodata)
            ids = _ids(sec, pend.shape, src.transform)
            ok = (ids > 0) & np.isfinite(pend)
            codigos = np.where(ok, np.digitize(pend, BORDES_PENDIENTE), -1)
            _contar(conteo, ids, codigos, k)
            suma += np.bincount(ids[ok] - 1, weights=pend[ok], minlength=len(s))
            n += np.bincount(ids[ok] - 1, minlength=len(s))
    d = _fracciones(conteo, list(CLASES_PENDIENTE.values()), s, "frac_")
    with np.errstate(invalid="ignore", divide="ignore"):
        d.insert(1, "pendiente_media", np.where(n > 0, suma / n, np.nan))
    return d
