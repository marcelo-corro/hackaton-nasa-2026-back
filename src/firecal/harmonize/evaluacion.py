"""Métricas para comparar métodos de armonización contra el conteo observado de referencia.

Se mide a tres escalas porque el error de una comuna-mes (con muchos ceros y conteos chicos) no es lo mismo
que el error de un total regional o nacional, que es lo que más se usa para decidir.

- sesgo_total: (suma predicha / suma observada) - 1. Cerca de 0 = no sobre ni subestima en total.
- wape_*: suma de errores absolutos / suma observada (error relativo ponderado) a cada escala.
- corr_nacional_mensual: correlación de Pearson de la serie nacional mensual.
- cobertura_90: fracción de observaciones dentro del intervalo del 90 % (debería rondar 0,90).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _wape(obs: pd.Series, pred: pd.Series) -> float:
    total = obs.sum()
    return float(np.abs(pred - obs).sum() / total) if total > 0 else float("nan")


def metricas(
    df: pd.DataFrame,
    obs: str,
    pred: pd.Series,
    bajo: pd.Series | None = None,
    alto: pd.Series | None = None,
) -> dict[str, float]:
    """`df` debe tener `cod_region`, `anio`, `mes` y la columna observada `obs`."""
    d = df[["cod_region", "anio", "mes"]].copy()
    d["obs"] = df[obs].astype(float)
    d["pred"] = pred.astype(float)
    d = d.dropna(subset=["obs", "pred"])

    region_mes = d.groupby(["cod_region", "anio", "mes"])[["obs", "pred"]].sum()
    nacional = d.groupby(["anio", "mes"])[["obs", "pred"]].sum()

    resultado = {
        "sesgo_total": float(d["pred"].sum() / d["obs"].sum() - 1),
        "wape_comuna_mes": _wape(d["obs"], d["pred"]),
        "wape_region_mes": _wape(region_mes["obs"], region_mes["pred"]),
        "wape_nacional_mes": _wape(nacional["obs"], nacional["pred"]),
        "corr_nacional_mensual": float(nacional["obs"].corr(nacional["pred"])),
        "cobertura_90": float("nan"),
    }
    if bajo is not None and alto is not None:
        b = bajo.loc[d.index].astype(float)
        a = alto.loc[d.index].astype(float)
        resultado["cobertura_90"] = float(((d["obs"] >= b) & (d["obs"] <= a)).mean())
    return resultado
