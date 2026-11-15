"""Contratos internos entre etapas del back (detalle en contracts/interno.md).

Cada etapa que produce una tabla compartida la valida con estas funciones antes de guardarla. Así el
trabajo en paralelo no se rompe: si alguien cambia la forma de una tabla, el validador falla en su máquina
y no en la del otro.
"""

from __future__ import annotations

import pandas as pd

SERIE_MENSUAL_COLUMNAS = [
    "region_id", "anio", "mes", "modis", "viirs",
    "armonizado", "armonizado_p05", "armonizado_p95", "metodo",
]
CALENDARIO_COLUMNAS = SERIE_MENSUAL_COLUMNAS + ["mediana_historica", "percentil", "nivel"]
NIVELES_CALENDARIO = {"baja", "normal", "alta", "extrema"}

RIESGO_COLUMNAS = ["region_id", "valido_para", "horizonte_horas", "prob_foco", "percentil", "nivel", "modelo"]
NIVELES_RIESGO = {"bajo", "medio", "alto", "muy_alto"}
HORIZONTES_RIESGO = {24, 48, 168}  # 168 h = la próxima semana


class ContratoError(ValueError):
    """La tabla no cumple el contrato. El mensaje lista todos los problemas encontrados."""


def _fallar_si(problemas: list[str], tabla: str) -> None:
    if problemas:
        raise ContratoError(f"{tabla} no cumple el contrato:\n- " + "\n- ".join(problemas))


def _problemas_comunes(df: pd.DataFrame, columnas: list[str]) -> list[str]:
    faltan = [c for c in columnas if c not in df.columns]
    if faltan:
        return [f"faltan columnas: {faltan}"]
    problemas = []
    if not df["region_id"].astype("string").str.fullmatch(r"\d{5}").fillna(False).all():
        problemas.append("region_id debe ser texto de 5 dígitos (ej. '05109')")
    return problemas


def validar_serie_mensual(df: pd.DataFrame, n_comunas: int | None = None) -> None:
    """Valida data/processed/serie_mensual.parquet (ver contracts/interno.md). Lanza ContratoError."""
    problemas = _problemas_comunes(df, SERIE_MENSUAL_COLUMNAS)
    _fallar_si(problemas[:1] if problemas and problemas[0].startswith("faltan") else [], "serie_mensual")

    if not df["mes"].between(1, 12).all():
        problemas.append("mes debe estar entre 1 y 12")
    if not df["anio"].between(2000, 2035).all():
        problemas.append("anio fuera de rango (2000-2035)")
    if df.duplicated(["region_id", "anio", "mes"]).any():
        problemas.append("hay filas repetidas para la misma (region_id, anio, mes)")
    for col in ("modis", "viirs"):
        if (df[col].dropna() < 0).any():
            problemas.append(f"{col} no puede ser negativo")
    if df["armonizado"].isna().any() or (df["armonizado"] < 0).any():
        problemas.append("armonizado no puede ser nulo ni negativo")
    con_intervalo = df["armonizado_p05"].notna() & df["armonizado_p95"].notna()
    fuera = con_intervalo & ~(
        (df["armonizado_p05"] <= df["armonizado"] + 1e-9) & (df["armonizado"] <= df["armonizado_p95"] + 1e-9)
    )
    if fuera.any():
        problemas.append(f"{int(fuera.sum())} filas con armonizado fuera de [p05, p95]")
    if df["metodo"].isna().any() or df["metodo"].nunique() != 1:
        problemas.append("metodo debe tener un único valor no nulo para toda la tabla")

    if not problemas:
        meses = pd.PeriodIndex.from_fields(year=df["anio"], month=df["mes"], freq="M")
        esperados = len(pd.period_range(meses.min(), meses.max(), freq="M"))
        por_comuna = df.groupby("region_id").size()
        incompletas = por_comuna[por_comuna != esperados]
        if len(incompletas):
            problemas.append(
                f"grilla incompleta: {len(incompletas)} comunas no tienen los {esperados} meses "
                "(un mes sin focos va con 0, no se omite)"
            )
        if n_comunas is not None and por_comuna.size != n_comunas:
            problemas.append(f"se esperaban {n_comunas} comunas y hay {por_comuna.size}")

    _fallar_si(problemas, "serie_mensual")


def validar_calendario(df: pd.DataFrame, n_comunas: int | None = None) -> None:
    """Valida data/processed/calendario.parquet: serie mensual + mediana, percentil y nivel."""
    faltan = [c for c in CALENDARIO_COLUMNAS if c not in df.columns]
    _fallar_si([f"faltan columnas: {faltan}"] if faltan else [], "calendario")
    validar_serie_mensual(df[SERIE_MENSUAL_COLUMNAS], n_comunas=n_comunas)

    problemas = []
    if not df["percentil"].between(0, 100).all():
        problemas.append("percentil debe estar entre 0 y 100")
    if not df["nivel"].isin(NIVELES_CALENDARIO).all():
        problemas.append(f"nivel debe ser uno de {sorted(NIVELES_CALENDARIO)}")
    if (df["mediana_historica"].dropna() < 0).any():
        problemas.append("mediana_historica no puede ser negativa")
    _fallar_si(problemas, "calendario")


def validar_riesgo(df: pd.DataFrame) -> None:
    """Valida data/processed/riesgo.parquet."""
    problemas = _problemas_comunes(df, RIESGO_COLUMNAS)
    _fallar_si(problemas[:1] if problemas and problemas[0].startswith("faltan") else [], "riesgo")
    if not df["prob_foco"].between(0, 1).all():
        problemas.append("prob_foco debe estar entre 0 y 1")
    if not df["nivel"].isin(NIVELES_RIESGO).all():
        problemas.append(f"nivel debe ser uno de {sorted(NIVELES_RIESGO)}")
    if not df["horizonte_horas"].isin(HORIZONTES_RIESGO).all():
        problemas.append(f"horizonte_horas debe ser uno de {sorted(HORIZONTES_RIESGO)}")
    if df.duplicated(["region_id", "valido_para", "horizonte_horas"]).any():
        problemas.append("hay filas repetidas para la misma (region_id, valido_para, horizonte_horas)")
    _fallar_si(problemas, "riesgo")
