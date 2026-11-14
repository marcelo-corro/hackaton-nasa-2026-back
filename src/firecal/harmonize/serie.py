"""Armado de la serie mensual armonizada (contrato `serie_mensual`, ver contracts/interno.md).

Unidad: **focos equivalentes MODIS**, es decir, lo que habrían contado Terra + Aqua con su órbita nominal y
su procesamiento previo a 2018. Regla por período:

| Período            | `armonizado`                                   | Por qué |
|--------------------|------------------------------------------------|---------|
| 2000-11 a 2002-06  | Terra convertido a Terra + Aqua                | Aqua todavía no existía |
| 2002-07 a 2017-12  | MODIS observado (Terra + Aqua)                 | Referencia confiable |
| 2018-01 en adelante| VIIRS Suomi NPP convertido a escala MODIS      | MODIS cambia de procesamiento en 2018 y su órbita se desvía; VIIRS es estable |
"""

from __future__ import annotations

import numpy as np
import pandas as pd

INICIO_AQUA = "2002-07"
CORTE_MODIS = "2018-01"


def construir_serie(
    conteos: pd.DataFrame,
    conv_viirs,
    conv_terra,
    metodo: str,
    corte_modis: str = CORTE_MODIS,
    inicio_aqua: str = INICIO_AQUA,
) -> pd.DataFrame:
    """Arma la serie mensual a partir de `conteos_mensuales` y dos calibradores ya ajustados.

    `conv_viirs` predice MODIS (Terra + Aqua) desde `snpp`; `conv_terra` predice Terra + Aqua desde `terra`.
    En los meses observados el intervalo es el propio valor (no hay conversión); en los convertidos es el
    intervalo de predicción del calibrador.
    """
    d = conteos.reset_index(drop=True)
    periodo = d["periodo"]
    terra = d["terra"].astype("Float64")
    aqua = d["aqua"].astype("Float64")
    modis = terra.where(aqua.isna(), terra + aqua)

    armonizado = modis.astype(float)
    p05 = armonizado.copy()
    p95 = armonizado.copy()

    tramos = [
        (periodo < pd.Period(inicio_aqua, freq="M"), conv_terra),
        (periodo >= pd.Period(corte_modis, freq="M"), conv_viirs),
    ]
    for mascara, conversor in tramos:
        if mascara.any():
            sub = d.loc[mascara]
            armonizado[mascara] = conversor.predecir(sub).to_numpy()
            bajo, alto = conversor.intervalo(sub)
            p05[mascara] = bajo.to_numpy()
            p95[mascara] = alto.to_numpy()

    # Los cuantiles de un conteo son enteros: con medias chicas el p95 puede quedar bajo la media. El intervalo
    # se amplía lo justo para contenerla.
    p05 = np.minimum(p05, armonizado)
    p95 = np.maximum(p95, armonizado)

    return pd.DataFrame(
        {
            "region_id": d["region_id"].astype("string"),
            "anio": d["anio"].astype(int),
            "mes": d["mes"].astype(int),
            "modis": modis.round().astype("Int64"),
            "viirs": d["snpp"].astype("Int64"),
            "armonizado": armonizado.astype(float),
            "armonizado_p05": p05.astype(float),
            "armonizado_p95": p95.astype(float),
            "metodo": pd.Series(metodo, index=d.index, dtype="string"),
        }
    )
