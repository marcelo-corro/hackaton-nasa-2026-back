import pandas as pd
import pytest

from firecal.contratos import ContratoError, validar_calendario, validar_riesgo, validar_serie_mensual


def _serie() -> pd.DataFrame:
    filas = []
    for region in ("05101", "05109"):
        for anio, mes in [(2011, 12), (2012, 1), (2012, 2)]:
            filas.append(
                {"region_id": region, "anio": anio, "mes": mes, "modis": 3, "viirs": 10 if anio >= 2012 else None,
                 "armonizado": 3.0, "armonizado_p05": 2.5, "armonizado_p95": 3.5, "metodo": "prueba"}
            )
    df = pd.DataFrame(filas)
    df["viirs"] = df["viirs"].astype("Int64")
    return df


def test_serie_valida() -> None:
    validar_serie_mensual(_serie(), n_comunas=2)


def test_serie_con_mes_faltante_falla() -> None:
    df = _serie().iloc[1:]  # a 05101 le falta 2011-12
    with pytest.raises(ContratoError, match="grilla incompleta"):
        validar_serie_mensual(df)


def test_serie_fuera_de_intervalo_y_codigo_malo() -> None:
    df = _serie()
    df.loc[0, "armonizado_p95"] = 1.0
    df.loc[1, "region_id"] = "5101"
    with pytest.raises(ContratoError) as error:
        validar_serie_mensual(df)
    assert "5 dígitos" in str(error.value) and "fuera de [p05, p95]" in str(error.value)


def test_calendario_nivel_invalido() -> None:
    df = _serie().assign(mediana_historica=2.0, percentil=60.0, nivel="normal")
    validar_calendario(df)
    df.loc[0, "nivel"] = "altísima"
    with pytest.raises(ContratoError, match="nivel"):
        validar_calendario(df)


def test_riesgo() -> None:
    df = pd.DataFrame(
        {"region_id": ["05109"], "valido_para": [pd.Timestamp("2026-11-15")], "horizonte_horas": [24],
         "prob_foco": [0.2], "percentil": [80.0], "nivel": ["alto"], "modelo": ["v1"]}
    )
    validar_riesgo(df)
    df.loc[0, "prob_foco"] = 1.5
    with pytest.raises(ContratoError, match="prob_foco"):
        validar_riesgo(df)
