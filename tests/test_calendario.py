import numpy as np
import pandas as pd
import pytest

from firecal.anomalies.calendario import anomalia_contra_otros, calcular_calendario, clasificar_nivel
from firecal.contratos import validar_calendario


def _serie(valores_por_anio: dict[int, float], mes: int = 2, region_id: str = "05109") -> pd.DataFrame:
    """Serie mínima de una comuna: un valor `armonizado` por año, para un solo mes del año."""
    return pd.DataFrame(
        [
            {"region_id": region_id, "anio": a, "mes": mes, "modis": 0, "viirs": 0, "armonizado": v,
             "armonizado_p05": v, "armonizado_p95": v, "metodo": "x"}
            for a, v in valores_por_anio.items()
        ]
    )


def test_cero_contra_otros_ceros_es_percentil_50_y_normal():
    cal = calcular_calendario(_serie({2000 + i: 0.0 for i in range(10)}))
    assert (cal["percentil"] == 50).all()
    assert (cal["nivel"] == "normal").all()
    assert (cal["mediana_historica"] == 0).all()


def test_el_maximo_es_extremo_y_el_minimo_es_bajo():
    cal = calcular_calendario(_serie({2000 + i: float(i) for i in range(20)})).set_index("anio")
    assert cal.loc[2019, "percentil"] == 100 and cal.loc[2019, "nivel"] == "extrema"
    assert cal.loc[2000, "percentil"] == 0 and cal.loc[2000, "nivel"] == "baja"


def test_mediana_y_percentil_excluyen_el_propio_anio():
    # otros años de 2003: 1, 2, 4  -> mediana 2; menores que 3 = 2 de 3 -> percentil 66,67
    fila = calcular_calendario(_serie({2000: 1.0, 2001: 2.0, 2002: 4.0, 2003: 3.0})).set_index("anio").loc[2003]
    assert fila["mediana_historica"] == 2.0
    assert fila["percentil"] == pytest.approx(100 * 2 / 3)
    assert fila["nivel"] == "normal"


def test_empates_usan_rango_medio():
    # otros años de 2002: 0, 0, 5; el valor es 0 -> (0 menores + 0,5 x 2 iguales) / 3 = 33,3
    cal = calcular_calendario(_serie({2000: 0.0, 2001: 0.0, 2002: 0.0, 2003: 5.0})).set_index("anio")
    assert cal.loc[2002, "percentil"] == pytest.approx(100 / 3)


def test_ruido_numerico_no_rompe_los_empates():
    valores = np.array([1 / 3, 2 / 6, 0.1 + 0.2 - 0.3 + 1 / 3, 5.0])  # los tres primeros son iguales
    _, percentiles = anomalia_contra_otros(valores)
    assert percentiles[0] == pytest.approx(100 * (0 + 0.5 * 2) / 3)


def test_meses_y_comunas_no_se_mezclan():
    enero = _serie({2000 + i: 100.0 for i in range(5)}, mes=1)
    febrero = _serie({2000 + i: float(i) for i in range(5)}, mes=2)
    otra = _serie({2000 + i: 999.0 for i in range(5)}, mes=2, region_id="13101")
    cal = calcular_calendario(pd.concat([enero, febrero, otra], ignore_index=True))
    fila = cal[(cal["region_id"] == "05109") & (cal["mes"] == 2) & (cal["anio"] == 2004)].iloc[0]
    assert fila["percentil"] == 100
    assert fila["mediana_historica"] == 1.5  # mediana de 0, 1, 2, 3


def test_un_solo_anio_queda_normal_sin_mediana():
    fila = calcular_calendario(_serie({2020: 7.0})).iloc[0]
    assert pd.isna(fila["mediana_historica"])
    assert fila["percentil"] == 50 and fila["nivel"] == "normal"


def test_conserva_el_orden_y_las_columnas_de_entrada():
    serie = _serie({2002: 1.0, 2000: 5.0, 2001: 3.0})
    cal = calcular_calendario(serie)
    assert list(cal["anio"]) == [2002, 2000, 2001]
    assert list(cal.columns[: len(serie.columns)]) == list(serie.columns)


@pytest.mark.parametrize(
    "percentil, esperado",
    [(0, "baja"), (24.99, "baja"), (25, "normal"), (74.99, "normal"), (75, "alta"), (94.99, "alta"), (95, "extrema"), (100, "extrema")],
)
def test_umbrales_de_nivel(percentil, esperado):
    assert clasificar_nivel(pd.Series([float(percentil)])).iloc[0] == esperado


def test_calendario_completo_pasa_el_validador_y_marca_el_pico():
    # 2 comunas, 302 meses: una con un pico claro en febrero de 2024
    meses = pd.period_range("2000-11", "2025-12", freq="M")
    filas = []
    for region_id in ("05109", "13101"):
        for m in meses:
            valor = 32.0 if (region_id == "05109" and m == pd.Period("2024-02")) else float(m.month % 3)
            filas.append({"region_id": region_id, "anio": m.year, "mes": m.month, "modis": 0, "viirs": 0,
                          "armonizado": valor, "armonizado_p05": valor, "armonizado_p95": valor, "metodo": "x"})
    cal = calcular_calendario(pd.DataFrame(filas))
    validar_calendario(cal, n_comunas=2)
    pico = cal[(cal["region_id"] == "05109") & (cal["anio"] == 2024) & (cal["mes"] == 2)].iloc[0]
    assert pico["nivel"] == "extrema"
