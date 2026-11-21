"""Calidad de los focos: marca, no borra.

`marcar_calidad` agrega a cada foco:

    fecha_hora_local  datetime  hora local (America/Santiago; Pacific/Easter para Isla de Pascua),
                                con horario de verano incluido
    fecha_local       datetime  día local (sin hora). Usar esta y no `fecha` (UTC) para series diarias
    zona_horaria      string
    es_vegetacion     bool      tipo == 0 (fuera volcanes, fuentes fijas como industria y focos costa afuera)
    confianza_ok      bool      confianza nominal o alta (misma regla para MODIS y VIIRS)
    frp_valido        bool      frp > 0 (sin esto el foco sirve para contar, no para medir intensidad)
    pixel_grande      bool      área del píxel > 2 veces la de nadir (borde del barrido: el mismo incendio
                                puede contarse más de una vez y la detección es menos sensible)
    fuente_persistente bool     cae en una fuente fija que FIRMS no marca (industria, minería, volcán, relleno),
                                según la máscara de firecal.fuentes_persistentes
    uso_base          bool      es_vegetacion & confianza_ok & no fuente_persistente: regla por defecto para contar
                                focos

Los filtros se aplican después, en cada análisis, y se prueba cuánto cambia el resultado con cada uno.
`reporte_calidad` arma un resumen en Markdown con las cifras que justifican estas marcas.
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from firecal.fuentes_persistentes import en_fuente_persistente
from firecal.reportes import tabla_md

AREA_NADIR_KM2 = {"MODIS": 1.0, "VIIRS": 0.375 * 0.375}
FACTOR_PIXEL_GRANDE = 2.0
LON_LIMITE_ISLA_DE_PASCUA = -100.0  # al oeste de esto, zona horaria de Isla de Pascua
ZONA_CONTINENTAL = "America/Santiago"
ZONA_PASCUA = "Pacific/Easter"

MARCAS = ["es_vegetacion", "confianza_ok", "frp_valido", "pixel_grande", "fuente_persistente", "uso_base"]


def _fecha_hora_utc(focos: pd.DataFrame) -> pd.Series:
    minutos = focos["hora_utc"].str[:2].astype(int) * 60 + focos["hora_utc"].str[2:].astype(int)
    return (focos["fecha"] + pd.to_timedelta(minutos, unit="m")).dt.tz_localize("UTC")


def marcar_calidad(focos: pd.DataFrame, fuentes_persistentes: pd.DataFrame | None = None) -> pd.DataFrame:
    """Devuelve una copia de `focos` con las columnas de calidad descritas en el módulo.

    `fuentes_persistentes`: máscara de celdas (firecal.fuentes_persistentes.leer_mascara); sin ella ningún foco se
    marca como fuente persistente.
    """
    utc = _fecha_hora_utc(focos)
    pascua = focos["lon"] < LON_LIMITE_ISLA_DE_PASCUA

    partes = []
    for zona, mascara in ((ZONA_CONTINENTAL, ~pascua), (ZONA_PASCUA, pascua)):
        if mascara.any():
            partes.append(utc[mascara].dt.tz_convert(zona).dt.tz_localize(None))
    local = pd.concat(partes).reindex(focos.index)

    area_nadir = focos["sensor"].map(AREA_NADIR_KM2).astype(float)
    salida = focos.copy()
    salida["fecha_hora_local"] = local
    salida["fecha_local"] = local.dt.normalize()
    salida["zona_horaria"] = pd.Series(np.where(pascua, ZONA_PASCUA, ZONA_CONTINENTAL), index=focos.index, dtype="string")
    salida["es_vegetacion"] = focos["tipo"].eq(0).fillna(False).astype(bool)
    salida["confianza_ok"] = focos["confianza"].isin(["nominal", "alta"]).fillna(False).astype(bool)
    salida["frp_valido"] = focos["frp"].gt(0).fillna(False).astype(bool)
    salida["pixel_grande"] = (focos["area_pixel_km2"] > FACTOR_PIXEL_GRANDE * area_nadir).fillna(False).astype(bool)
    # Solo los que FIRMS marcó como vegetación: los demás ya quedaban fuera por su `tipo`.
    salida["fuente_persistente"] = en_fuente_persistente(focos, fuentes_persistentes).astype(bool) & salida["es_vegetacion"]
    salida["uso_base"] = salida["es_vegetacion"] & salida["confianza_ok"] & ~salida["fuente_persistente"]
    return salida


# --- Reporte -----------------------------------------------------------------------------------------

_tabla = tabla_md


def _razones_anuales(marcados: pd.DataFrame, filtro: pd.Series) -> pd.DataFrame:
    sub = marcados[filtro]
    n = sub.groupby([sub["fecha_local"].dt.year.rename("año"), "satelite"]).size().unstack(fill_value=0)
    for s in ("Terra", "Aqua", "SNPP", "NOAA20"):
        if s not in n:
            n[s] = 0
    n = n.replace(0, np.nan)
    return pd.DataFrame(
        {
            "SNPP/Terra": n["SNPP"] / n["Terra"],
            "SNPP/Aqua": n["SNPP"] / n["Aqua"],
            "SNPP/MODIS": n["SNPP"] / (n["Terra"] + n["Aqua"]),
            "NOAA20/SNPP": n["NOAA20"] / n["SNPP"],
        }
    ).dropna(subset=["SNPP/MODIS"])


def reporte_calidad(marcados: pd.DataFrame) -> str:
    """Resumen de calidad en Markdown, a partir de focos ya marcados con `marcar_calidad`."""
    total = len(marcados)
    clave = ["lat", "lon", "fecha", "hora_utc", "satelite"]
    nulos = marcados.drop(columns=["fecha_hora_local", "fecha_local"]).isna().sum()
    nulos = nulos[nulos > 0].rename("nulos").to_frame()
    fuera_de_rango = int((~marcados["lat"].between(-56.5, -17.0) | ~marcados["lon"].between(-110.0, -66.0)).sum())

    tipos = (marcados.groupby("sensor")["tipo"].value_counts(normalize=True).unstack(fill_value=0) * 100)
    tipos.columns = [f"tipo {c}" for c in tipos.columns]
    marcas = marcados.groupby("satelite")[MARCAS].mean() * 100
    versiones = marcados.groupby(["satelite", "version"]).agg(
        focos=("lat", "size"), desde=("fecha", "min"), hasta=("fecha", "max")
    )

    dia = marcados[marcados["uso_base"] & marcados["dia_noche"].eq("D").fillna(False)]
    hora_dec = dia["hora_utc"].str[:2].astype(int) + dia["hora_utc"].str[2:].astype(int) / 60
    deriva = hora_dec.groupby([dia["fecha"].dt.year.rename("año"), dia["satelite"]]).median().unstack()

    razones_base = _razones_anuales(marcados, marcados["uso_base"])
    razones_veg = _razones_anuales(marcados, marcados["es_vegetacion"])
    sensibilidad = pd.DataFrame(
        {"uso_base": razones_base["SNPP/MODIS"], "solo vegetación (con baja confianza)": razones_veg["SNPP/MODIS"]}
    )
    cambio_de_dia = float((marcados["fecha_local"] != marcados["fecha"]).mean() * 100)

    generado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    partes = [
        "# Reporte de calidad de los focos FIRMS",
        f"_Generado por `scripts/04_marcar_calidad.py` el {generado}. No editar a mano: se regenera._",
        "",
        "## 1. Integridad",
        f"- Focos: **{total:,}**".replace(",", " ")
        + f", del {marcados['fecha'].min():%Y-%m-%d} al {marcados['fecha'].max():%Y-%m-%d}.",
        f"- Duplicados exactos (lat, lon, fecha, hora, satélite): **{int(marcados.duplicated(clave).sum())}**.",
        f"- Coordenadas fuera del rango de Chile (incluye Isla de Pascua): **{fuera_de_rango}**.",
        f"- Focos cuyo día local es distinto al día UTC: **{cambio_de_dia:.1f} %** (usar `fecha_local` en series diarias).",
        "",
        "Valores nulos (la confianza numérica solo existe en MODIS):",
        "",
        _tabla(nulos, 0),
        "",
        "## 2. Tipos de foco por sensor (%)",
        "Tipo 0 = vegetación, 1 = volcán, 2 = otra fuente fija (industria, faenas), 3 = costa afuera.",
        "",
        _tabla(tipos, 2),
        "",
        "## 3. Marcas de calidad por satélite (% de focos)",
        "",
        _tabla(marcas, 1),
        "",
        "## 4. Versiones del producto",
        "La versión indica la colección y el tipo de procesamiento (documentación de FIRMS). Cambios de versión pueden "
        "producir saltos en la serie.",
        "",
        _tabla(versiones, 0),
        "",
        "## 5. Deriva de órbita: hora UTC mediana del paso diurno (focos `uso_base`)",
        "Terra y Aqua (MODIS) se están desviando de su órbita original; Suomi NPP y NOAA-20 (VIIRS) no.",
        "",
        _tabla(deriva, 2),
        "",
        "## 6. Razones anuales entre satélites (focos `uso_base`)",
        "Si la razón cambia con los años, un factor calibrado con todo el período no sirve: hay que calibrar en el "
        "período en que ambos sensores son estables (ver [armonizacion.md](armonizacion.md)).",
        "",
        _tabla(razones_base, 2),
        "",
        "Sensibilidad de la razón SNPP/MODIS al filtro de confianza:",
        "",
        _tabla(sensibilidad, 2),
        "",
    ]
    return "\n".join(partes)
