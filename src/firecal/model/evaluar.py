"""Métricas del modelo de riesgo.

- auc: capacidad de ordenar (0,5 = azar, 1 = perfecto).
- precision_media (AP): resume precisión vs. captura; su referencia es la tasa base (~4 %), no 0,5.
- captura_top10: de todos los días-comuna con fuego, qué fracción cae en el 10 % de mayor riesgo.
- lift_top10: cuántas veces más fuego hay en ese 10 % que en promedio.
- brier: error cuadrático de la probabilidad (solo tiene sentido si la salida es una probabilidad calibrada).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def captura_top(y: np.ndarray, p: np.ndarray, fraccion: float = 0.10) -> tuple[float, float]:
    """Captura y lift en la fracción de mayor puntaje (empates rotos por orden estable)."""
    y = np.asarray(y, float)
    orden = np.argsort(-np.asarray(p, float), kind="stable")
    k = max(1, int(round(len(y) * fraccion)))
    captura = y[orden[:k]].sum() / y.sum() if y.sum() > 0 else float("nan")
    lift = (y[orden[:k]].mean() / y.mean()) if y.mean() > 0 else float("nan")
    return float(captura), float(lift)


def metricas(y, p, probabilidad: bool = True) -> dict[str, float]:
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    cap, lift = captura_top(y, p)
    return {
        "auc": float(roc_auc_score(y, p)) if 0 < y.mean() < 1 else float("nan"),
        "precision_media": float(average_precision_score(y, p)) if y.sum() > 0 else float("nan"),
        "captura_top10": cap,
        "lift_top10": lift,
        "brier": float(brier_score_loss(y, np.clip(p, 0, 1))) if probabilidad else float("nan"),
        "tasa_base": float(y.mean()),
    }


def por_segmento(y, p, segmento: pd.Series, probabilidad: bool = True) -> pd.DataFrame:
    filas = {}
    for nombre in sorted(pd.unique(segmento)):
        m = (segmento == nombre).to_numpy()
        filas[nombre] = metricas(np.asarray(y)[m], np.asarray(p)[m], probabilidad)
    return pd.DataFrame(filas).T


def confiabilidad(y, p, bins: int = 10) -> pd.DataFrame:
    """Probabilidad media predicha vs. frecuencia observada por decil de predicción."""
    d = pd.DataFrame({"y": np.asarray(y, float), "p": np.asarray(p, float)})
    d["grupo"] = pd.qcut(d["p"].rank(method="first"), bins, labels=False)
    t = d.groupby("grupo").agg(predicho=("p", "mean"), observado=("y", "mean"), n=("y", "size"))
    t.index = [f"decil {i + 1}" for i in t.index]
    return t


def curva_captura(y, p, puntos: int = 50) -> pd.DataFrame:
    """Fracción de días con fuego capturados según la fracción de días-comuna marcados (de mayor a menor riesgo)."""
    y = np.asarray(y, float)
    orden = np.argsort(-np.asarray(p, float), kind="stable")
    acumulado = np.cumsum(y[orden]) / y.sum()
    fr = np.linspace(0, 1, puntos + 1)[1:]
    idx = np.clip((fr * len(y)).astype(int) - 1, 0, len(y) - 1)
    return pd.DataFrame({"marcado": fr, "capturado": acumulado[idx]})
