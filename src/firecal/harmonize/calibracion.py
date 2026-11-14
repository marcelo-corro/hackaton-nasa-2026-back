"""Métodos de calibración entre satélites.

Cada método aprende a predecir el conteo mensual de un satélite de referencia (`y`, por ejemplo MODIS
Terra + Aqua) a partir del conteo de otro (`x`, por ejemplo VIIRS Suomi NPP) en la misma comuna y mes.
Todos tienen la misma interfaz (`ajustar`, `predecir`, `intervalo`) para compararlos en igualdad de
condiciones.

- `FactorPorGrupo`: y = x / razón. Con `grupo=None` es el factor único (una razón para todo Chile); con un
  grupo (región, zona, mes, temporada) estima una razón por grupo, con la global si el grupo tiene pocos datos.
- `ProporcionalPoisson`: log E[y] = log(x + 0,5) + efectos (regresión de Poisson con offset): una razón
  multiplicativa que combina varios grupos a la vez.
- `ModeloNB`: binomial negativa log E[y] = a + b·log(1 + x) + región + mes, que además permite una relación no
  proporcional (b ≠ 1).

Intervalo de predicción (90 % por defecto): cuantiles de una binomial negativa con media = predicción y
sobredispersión `alpha` estimada por momentos en los datos de calibración. Es el rango plausible de lo que habría
contado el satélite de referencia ese mes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

ZONAS = {
    15: "norte", 1: "norte", 2: "norte", 3: "norte", 4: "norte",
    5: "centro", 13: "centro", 6: "centro",
    7: "centro-sur", 16: "centro-sur", 8: "centro-sur", 9: "centro-sur",
    14: "sur", 10: "sur", 11: "sur", 12: "sur",
}
TEMPORADAS = {12: "verano", 1: "verano", 2: "verano", 3: "verano", 4: "otoño", 5: "otoño",
              6: "invierno", 7: "invierno", 8: "invierno", 9: "invierno", 10: "primavera", 11: "primavera"}


def agregar_grupos(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega `zona` (por región administrativa) y `temporada` (por mes) si no están."""
    d = df.copy()
    if "zona" not in d:
        d["zona"] = d["cod_region"].map(ZONAS)
    if "temporada" not in d:
        d["temporada"] = d["mes"].map(TEMPORADAS)
    return d


def _sin_nulos(df: pd.DataFrame, columnas: list[str]) -> pd.DataFrame:
    d = agregar_grupos(df.dropna(subset=columnas))
    for c in columnas:
        d[c] = d[c].astype(float)
    return d


def alpha_momentos(y: pd.Series, mu: pd.Series) -> float:
    """Sobredispersión de una binomial negativa (Var = mu + alpha·mu²) por el método de momentos."""
    y, mu = y.astype(float), mu.astype(float)
    return max(float(((y - mu) ** 2 - mu).sum() / (mu**2).sum()), 1e-6)


def intervalo_nb(mu: pd.Series, alpha: float, nivel: float = 0.90) -> tuple[pd.Series, pd.Series]:
    n = 1.0 / alpha
    p = n / (n + mu.astype(float))
    cola = (1 - nivel) / 2
    return (
        pd.Series(stats.nbinom.ppf(cola, n, p), index=mu.index),
        pd.Series(stats.nbinom.ppf(1 - cola, n, p), index=mu.index),
    )


@dataclass
class FactorPorGrupo:
    x: str
    y: str
    grupo: str | None = None
    minimo_y: int = 30  # con menos focos de referencia en el grupo, se usa la razón global
    nombre: str = ""
    razones: dict = field(default_factory=dict)
    razon_global: float = float("nan")
    alpha: float = float("nan")

    def __post_init__(self) -> None:
        if not self.nombre:
            self.nombre = "Factor único" if self.grupo is None else f"Factor por {self.grupo}"

    def ajustar(self, df: pd.DataFrame) -> "FactorPorGrupo":
        d = _sin_nulos(df, [self.x, self.y])
        self.razon_global = float(d[self.x].sum() / d[self.y].sum())
        if self.grupo is not None:
            g = d.groupby(self.grupo)[[self.x, self.y]].sum()
            g = g[(g[self.y] >= self.minimo_y) & (g[self.x] > 0)]
            self.razones = (g[self.x] / g[self.y]).astype(float).to_dict()
        self.alpha = alpha_momentos(d[self.y], self.predecir(d))
        return self

    def predecir(self, df: pd.DataFrame) -> pd.Series:
        x = df[self.x].astype(float)
        if self.grupo is None:
            return x / self.razon_global
        razon = agregar_grupos(df)[self.grupo].map(self.razones).astype(float).fillna(self.razon_global)
        return x / razon

    def intervalo(self, df: pd.DataFrame, nivel: float = 0.90) -> tuple[pd.Series, pd.Series]:
        return intervalo_nb(self.predecir(df), self.alpha, nivel)


@dataclass
class ProporcionalPoisson:
    x: str
    y: str
    terminos: str = "C(cod_region) + C(mes)"
    nombre: str = ""
    resultado: object = None
    alpha: float = float("nan")

    def __post_init__(self) -> None:
        if not self.nombre:
            self.nombre = f"Proporcional Poisson ({self.terminos})"

    def ajustar(self, df: pd.DataFrame) -> "ProporcionalPoisson":
        d = _sin_nulos(df, [self.x, self.y])
        self.resultado = smf.glm(
            f"{self.y} ~ {self.terminos}", data=d, offset=np.log(d[self.x] + 0.5), family=sm.families.Poisson()
        ).fit()
        self.alpha = alpha_momentos(d[self.y], self.predecir(d))
        return self

    def predecir(self, df: pd.DataFrame) -> pd.Series:
        pred = pd.Series(np.nan, index=df.index, dtype=float)
        validos = df[self.x].notna()
        if validos.any():
            d = agregar_grupos(df.loc[validos])
            x = d[self.x].astype(float)
            pred[validos] = np.asarray(self.resultado.predict(d, offset=np.log(x + 0.5)), dtype=float)
        return pred

    def intervalo(self, df: pd.DataFrame, nivel: float = 0.90) -> tuple[pd.Series, pd.Series]:
        return intervalo_nb(self.predecir(df), self.alpha, nivel)


@dataclass
class ModeloNB:
    x: str
    y: str
    terminos: str = "C(cod_region) + C(mes)"
    nombre: str = "Binomial negativa con pendiente (región + mes)"
    resultado: object = None
    alpha: float = float("nan")

    def ajustar(self, df: pd.DataFrame) -> "ModeloNB":
        d = _sin_nulos(df, [self.x, self.y])
        formula = f"{self.y} ~ np.log1p({self.x}) + {self.terminos}"
        self.resultado = smf.negativebinomial(formula, data=d).fit(disp=0, maxiter=500)
        self.alpha = float(self.resultado.params["alpha"])
        return self

    @property
    def pendiente(self) -> float:
        """Exponente b de log(1 + x): 1 = proporcional; > 1 = exagera los meses grandes."""
        return float(self.resultado.params[f"np.log1p({self.x})"])

    def predecir(self, df: pd.DataFrame) -> pd.Series:
        pred = pd.Series(np.nan, index=df.index, dtype=float)
        validos = df[self.x].notna()
        if validos.any():
            d = agregar_grupos(df.loc[validos])
            d[self.x] = d[self.x].astype(float)
            pred[validos] = np.asarray(self.resultado.predict(d), dtype=float)
        return pred

    def intervalo(self, df: pd.DataFrame, nivel: float = 0.90) -> tuple[pd.Series, pd.Series]:
        return intervalo_nb(self.predecir(df), self.alpha, nivel)


def metodos_candidatos(x: str, y: str) -> list:
    """Todos los métodos que se comparan en la validación, del más simple al más complejo."""
    return [
        FactorPorGrupo(x, y),
        FactorPorGrupo(x, y, grupo="temporada"),
        FactorPorGrupo(x, y, grupo="mes"),
        FactorPorGrupo(x, y, grupo="zona"),
        FactorPorGrupo(x, y, grupo="cod_region", nombre="Factor por región"),
        ProporcionalPoisson(x, y, terminos="C(zona) + C(temporada)"),
        ProporcionalPoisson(x, y, terminos="C(cod_region) + C(mes)"),
        ModeloNB(x, y),
    ]
