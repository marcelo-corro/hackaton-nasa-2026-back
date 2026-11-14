"""Calendario y anomalías (tarea B2): cada comuna-mes contra el mismo mes de los demás años de esa comuna.

Reglas en contracts/interno.md. Funciones puras: no leen ni escriben archivos.

    mediana_historica  mediana de `armonizado` del mismo mes en los demás años
    percentil          100 × (n_menores + 0,5 × n_iguales) / n_otros_años   (rango medio para empates)
    nivel              baja < 25 <= normal < 75 <= alta < 95 <= extrema

El rango medio importa: en comunas con pocos incendios hay muchos meses en 0, y sin él un 0 contra otros
ceros saldría como "baja" en vez de "normal".
"""

from __future__ import annotations

import numpy as np
import pandas as pd

UMBRALES_NIVEL = (25.0, 75.0, 95.0)
NIVELES = ("baja", "normal", "alta", "extrema")
TOLERANCIA = 1e-9  # `armonizado` es decimal: evita que ruido numérico rompa los empates


def clasificar_nivel(percentil: pd.Series) -> pd.Series:
    """`baja` si percentil < 25; `normal` < 75; `alta` < 95; `extrema` >= 95."""
    indices = np.searchsorted(UMBRALES_NIVEL, percentil.to_numpy(dtype=float), side="right")
    return pd.Series(np.array(NIVELES, dtype=object)[indices], index=percentil.index, dtype="string")


def anomalia_contra_otros(valores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Mediana y percentil de cada valor contra todos los **demás** del arreglo.

    Devuelve dos arreglos del mismo largo. Con un solo valor no hay con qué comparar: mediana NaN y percentil 50.
    """
    valores = np.asarray(valores, dtype=float)
    n = len(valores)
    if n < 2:
        return np.full(n, np.nan), np.full(n, 50.0)

    diferencia = valores[None, :] - valores[:, None]  # [i, j] = valores[j] - valores[i]
    fuera_diagonal = ~np.eye(n, dtype=bool)
    menores = ((diferencia < -TOLERANCIA) & fuera_diagonal).sum(axis=1)  # otros j con valor menor que el de i
    iguales = ((np.abs(diferencia) <= TOLERANCIA) & fuera_diagonal).sum(axis=1)
    percentiles = 100.0 * (menores + 0.5 * iguales) / (n - 1)

    medianas = np.array([np.median(np.delete(valores, i)) for i in range(n)])
    return medianas, percentiles


def calcular_calendario(serie: pd.DataFrame) -> pd.DataFrame:
    """Agrega `mediana_historica`, `percentil` y `nivel` a una serie mensual (contrato `serie_mensual`).

    Un mes sin otros años con los cuales compararse queda con `mediana_historica` nula, percentil 50 y `normal`.
    """
    salida = serie.reset_index(drop=True).copy()
    valores = salida["armonizado"].to_numpy(dtype=float)
    medianas = np.full(len(salida), np.nan)
    percentiles = np.full(len(salida), 50.0)

    for posiciones in salida.groupby(["region_id", "mes"], sort=False).indices.values():
        medianas[posiciones], percentiles[posiciones] = anomalia_contra_otros(valores[posiciones])

    salida["mediana_historica"] = medianas
    salida["percentil"] = percentiles
    salida["nivel"] = clasificar_nivel(salida["percentil"])
    return salida
