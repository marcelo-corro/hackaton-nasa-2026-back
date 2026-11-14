"""Conteos mensuales de focos por comuna y satélite (grilla completa).

Una fila por comuna × mes (año y mes locales). Columnas por satélite: `terra`, `aqua`, `snpp`, `noaa20`.
Un mes sin focos vale 0; un mes en que el satélite todavía no existía vale nulo (no es lo mismo "no hubo
fuego" que "no había satélite").
"""

from __future__ import annotations

import pandas as pd

SATELITES = {"Terra": "terra", "Aqua": "aqua", "SNPP": "snpp", "NOAA20": "noaa20"}

# Primer mes completo (o casi) de datos de cada satélite en FIRMS para Chile.
INICIO = {
    "terra": "2000-11",
    "aqua": "2002-07",   # Aqua empieza el 4-jul-2002
    "snpp": "2012-02",   # Suomi NPP empieza el 20-ene-2012: enero queda incompleto y se trata como nulo
    "noaa20": "2018-04",
}


def conteos_mensuales(
    focos: pd.DataFrame,
    comunas: pd.DataFrame,
    desde: str = "2000-11",
    hasta: str = "2025-12",
    filtro: str = "uso_base",
) -> pd.DataFrame:
    """Cuenta focos por comuna, mes local y satélite.

    `focos` es data/interim/focos_calidad.parquet; se usan las filas con `filtro` verdadero y comuna asignada.
    `comunas` aporta la lista completa de comunas (`region_id`) y su `cod_region`.
    """
    base = focos[focos[filtro].fillna(False).astype(bool) & focos["region_id"].notna()]
    periodo = base["fecha_local"].dt.to_period("M")
    conteo = (
        base.assign(periodo=periodo, sat=base["satelite"].map(SATELITES))
        .groupby(["region_id", "periodo", "sat"])
        .size()
        .unstack("sat", fill_value=0)
    )

    meses = pd.period_range(desde, hasta, freq="M")
    grilla = pd.MultiIndex.from_product(
        [comunas["region_id"].astype(str).tolist(), meses], names=["region_id", "periodo"]
    )
    tabla = conteo.reindex(grilla, fill_value=0)
    for sat in SATELITES.values():
        if sat not in tabla:
            tabla[sat] = 0
    tabla = tabla[list(SATELITES.values())].astype("Int64").reset_index()

    for sat, inicio in INICIO.items():
        antes = tabla["periodo"] < pd.Period(inicio, freq="M")
        tabla.loc[antes, sat] = pd.NA

    tabla["anio"] = tabla["periodo"].dt.year.astype(int)
    tabla["mes"] = tabla["periodo"].dt.month.astype(int)
    tabla["region_id"] = tabla["region_id"].astype("string")
    regiones = comunas.set_index(comunas["region_id"].astype(str))["cod_region"].astype(int)
    tabla["cod_region"] = tabla["region_id"].astype(str).map(regiones).astype(int)
    return tabla[["region_id", "cod_region", "periodo", "anio", "mes", *SATELITES.values()]]
