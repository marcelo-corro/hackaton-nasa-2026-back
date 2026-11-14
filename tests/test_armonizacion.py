import numpy as np
import pandas as pd

from firecal.contratos import validar_serie_mensual
from firecal.harmonize.calibracion import FactorPorGrupo
from firecal.harmonize.conteos import conteos_mensuales
from firecal.harmonize.serie import construir_serie

COMUNAS = pd.DataFrame({"region_id": ["05101", "05109"], "cod_region": [5, 5]})


def _focos() -> pd.DataFrame:
    filas = [
        ("05109", "2001-01-10", "Terra", True),
        ("05109", "2001-01-11", "Terra", False),  # no cuenta: no es uso_base
        ("05109", "2013-02-01", "SNPP", True),
        ("05109", "2013-02-02", "SNPP", True),
        ("05109", "2013-02-02", "Aqua", True),
        (None, "2013-02-02", "SNPP", True),  # sin comuna: no cuenta
    ]
    df = pd.DataFrame(filas, columns=["region_id", "fecha_local", "satelite", "uso_base"])
    df["fecha_local"] = pd.to_datetime(df["fecha_local"])
    df["region_id"] = df["region_id"].astype("string")
    return df


def test_conteos_grilla_completa_y_nulos_antes_del_satelite() -> None:
    m = conteos_mensuales(_focos(), COMUNAS, desde="2000-11", hasta="2013-12")

    assert len(m) == 2 * len(pd.period_range("2000-11", "2013-12", freq="M"))
    fila = m[(m.region_id == "05109") & (m.anio == 2013) & (m.mes == 2)].iloc[0]
    assert (fila.snpp, fila.aqua, fila.terra) == (2, 1, 0)
    enero_2001 = m[(m.region_id == "05109") & (m.anio == 2001) & (m.mes == 1)].iloc[0]
    assert enero_2001.terra == 1
    assert pd.isna(enero_2001.aqua) and pd.isna(enero_2001.snpp)  # todavía no existían
    assert pd.isna(m[(m.anio == 2012) & (m.mes == 1)].snpp).all()  # enero 2012 incompleto


def _calibracion(n: int = 400, razon: float = 3.0, semilla: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    modis = rng.poisson(5, n).astype(float)
    return pd.DataFrame(
        {"cod_region": rng.choice([5, 8], n), "mes": rng.integers(1, 13, n), "modis": modis,
         "snpp": rng.poisson(modis * razon).astype(float)}
    )


def test_factor_unico_recupera_la_razon_y_su_intervalo_contiene_la_media() -> None:
    datos = _calibracion()
    f = FactorPorGrupo("snpp", "modis").ajustar(datos)

    assert abs(f.razon_global - 3.0) < 0.15
    pred = f.predecir(datos)
    bajo, alto = f.intervalo(datos)
    assert ((bajo <= pred) | (pred < 1)).all()
    assert ((datos["modis"] >= bajo) & (datos["modis"] <= alto)).mean() > 0.85


def test_factor_por_grupo_usa_la_global_si_hay_pocos_datos() -> None:
    datos = _calibracion()
    datos.loc[datos.cod_region == 8, "modis"] = 0  # región 8 sin datos de referencia
    f = FactorPorGrupo("snpp", "modis", grupo="cod_region").ajustar(datos)

    assert 8 not in f.razones
    fila = pd.DataFrame({"cod_region": [8], "mes": [1], "snpp": [30.0]})
    assert f.predecir(fila).iloc[0] == 30.0 / f.razon_global


def test_serie_aplica_la_regla_por_periodo() -> None:
    m = conteos_mensuales(_focos(), COMUNAS, desde="2000-11", hasta="2019-12")
    m["modis"] = (m["terra"] + m["aqua"]).astype("Int64")
    conv_terra = FactorPorGrupo("terra", "modis")
    conv_terra.razon_global, conv_terra.alpha = 0.25, 0.1  # Terra + Aqua = 4 × Terra
    conv_viirs = FactorPorGrupo("snpp", "modis")
    conv_viirs.razon_global, conv_viirs.alpha = 3.0, 0.1

    s = construir_serie(m, conv_viirs, conv_terra, metodo="prueba")
    validar_serie_mensual(s, n_comunas=2)

    def fila(anio: int, mes: int) -> pd.Series:
        return s[(s.region_id == "05109") & (s.anio == anio) & (s.mes == mes)].iloc[0]

    assert fila(2001, 1).armonizado == 4.0  # solo Terra: convertido
    assert fila(2013, 2).armonizado == 1.0 and fila(2013, 2).armonizado_p05 == fila(2013, 2).armonizado_p95  # observado
    assert np.isclose(fila(2019, 1).armonizado, 0.0)  # desde 2018: VIIRS convertido (0 focos)
    assert (s.armonizado_p05 <= s.armonizado).all() and (s.armonizado <= s.armonizado_p95).all()
