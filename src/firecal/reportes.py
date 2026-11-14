"""Utilidades para los reportes en Markdown que generan los scripts (sin depender de `tabulate`)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def formato(valor: object, decimales: int = 2) -> str:
    if valor is None or valor is pd.NA or (isinstance(valor, (float, np.floating)) and np.isnan(valor)):
        return "—"
    if isinstance(valor, (bool, np.bool_)):
        return "sí" if valor else "no"
    if isinstance(valor, (float, np.floating)):
        return f"{valor:,.{decimales}f}".replace(",", " ")
    if isinstance(valor, (int, np.integer)):
        return f"{valor:,}".replace(",", " ")
    if isinstance(valor, pd.Timestamp):
        return valor.strftime("%Y-%m-%d")
    return str(valor)


def tabla_md(df: pd.DataFrame, decimales: int = 2) -> str:
    """DataFrame a tabla Markdown. El índice va como primera columna (años sin separador de miles)."""
    encabezado = [str(df.index.name or "")] + [str(c) for c in df.columns]
    lineas = ["| " + " | ".join(encabezado) + " |", "|" + "---|" * len(encabezado)]
    # itertuples conserva el tipo de cada columna (iterrows convierte las filas mixtas a float).
    for fila in df.itertuples(index=True, name=None):
        indice, valores = fila[0], fila[1:]
        partes = indice if isinstance(indice, tuple) else (indice,)
        etiqueta = " / ".join(p.strftime("%Y-%m-%d") if isinstance(p, pd.Timestamp) else str(p) for p in partes)
        lineas.append("| " + " | ".join([etiqueta] + [formato(v, decimales) for v in valores]) + " |")
    return "\n".join(lineas)
