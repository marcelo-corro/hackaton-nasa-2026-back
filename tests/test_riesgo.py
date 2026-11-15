import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import box

from firecal.model.evaluar import captura_top
from firecal.model.variables import agregar_climatologia, dias_desde_ultimo, suma_movil, tabla_base


def test_suma_movil_y_dias_desde_ultimo() -> None:
    m = np.array([[0, 2, 0, 0, 1]], dtype=float)

    assert suma_movil(m, 3).tolist() == [[0, 2, 2, 2, 1]]
    assert dias_desde_ultimo(m, tope=10).tolist() == [[10, 0, 1, 2, 0]]


def _comunas() -> gpd.GeoDataFrame:
    # A y B se tocan; C está lejos.
    return gpd.GeoDataFrame(
        {"region_id": ["05101", "05109", "13101"], "area_km2": [10.0, 10.0, 10.0]},
        geometry=[box(-71.70, -33.10, -71.60, -33.00), box(-71.60, -33.10, -71.50, -33.00),
                  box(-70.70, -33.50, -70.60, -33.40)],
        crs="EPSG:4326",
    )


def _focos() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region_id": pd.Series(["05101", "05101", "05101"], dtype="string"),
            "fecha_local": pd.to_datetime(["2020-01-02", "2020-01-02", "2020-01-04"]),
            "satelite": ["SNPP", "SNPP", "Terra"],  # Terra no cuenta: el objetivo es Suomi NPP
            "uso_base": [True, True, True],
            "frp": [5.0, 7.0, 3.0],
        }
    )


def test_tabla_base_objetivo_y_vecinos() -> None:
    t = tabla_base(_focos(), _comunas(), "2020-01-01", "2020-01-05").set_index(["region_id", "fecha"])

    assert t.loc[("05101", pd.Timestamp("2020-01-01")), "y24"] == 1.0   # mañana (02-ene) hay fuego
    assert t.loc[("05101", pd.Timestamp("2020-01-02")), "n_hoy"] == 2.0
    assert t.loc[("05101", pd.Timestamp("2020-01-02")), "frp_hoy"] == 12.0
    assert t.loc[("05101", pd.Timestamp("2020-01-03")), "y24"] == 0.0   # el foco del 04-ene es Terra
    assert t.loc[("05109", pd.Timestamp("2020-01-02")), "vecinos_hoy"] == 2.0  # vecina de 05101
    assert t.loc[("13101", pd.Timestamp("2020-01-02")), "vecinos_hoy"] == 0.0  # lejos
    assert np.isnan(t.loc[("05101", pd.Timestamp("2020-01-05")), "y24"])  # último día: sin futuro


def test_objetivo_7_dias() -> None:
    focos = pd.DataFrame({"region_id": pd.Series(["05101"], dtype="string"),
                          "fecha_local": pd.to_datetime(["2020-01-09"]), "satelite": ["SNPP"], "uso_base": [True],
                          "frp": [5.0]})
    t = tabla_base(focos, _comunas(), "2020-01-01", "2020-01-20").set_index(["region_id", "fecha"])["y7d"]

    assert t[("05101", pd.Timestamp("2020-01-01"))] == 0.0  # 02-ene..08-ene: sin fuego
    assert t[("05101", pd.Timestamp("2020-01-02"))] == 1.0  # 03-ene..09-ene: incluye el 09
    assert t[("05101", pd.Timestamp("2020-01-08"))] == 1.0
    assert t[("05101", pd.Timestamp("2020-01-09"))] == 0.0  # el fuego de hoy no cuenta: solo el futuro
    assert t[("05101", pd.Timestamp("2020-01-13"))] == 0.0  # 14-ene..20-ene: última semana completa
    assert np.isnan(t[("05101", pd.Timestamp("2020-01-14"))])  # semana incompleta: sin objetivo
    assert t[("13101", pd.Timestamp("2020-01-02"))] == 0.0


def test_validar_riesgo_acepta_varios_horizontes() -> None:
    import pytest

    from firecal.contratos import ContratoError, validar_riesgo

    base = {"region_id": ["05109", "05109"], "valido_para": [pd.Timestamp("2026-01-01")] * 2,
            "horizonte_horas": [24, 168], "prob_foco": [0.1, 0.4], "percentil": [50.0, 60.0],
            "nivel": ["medio", "alto"], "modelo": ["hgb_firms_clima_v3"] * 2}
    validar_riesgo(pd.DataFrame(base))  # mismo día, distinto horizonte: válido
    with pytest.raises(ContratoError, match="horizonte_horas"):
        validar_riesgo(pd.DataFrame(base | {"horizonte_horas": [24, 72]}))
    with pytest.raises(ContratoError, match="repetidas"):
        validar_riesgo(pd.DataFrame(base | {"horizonte_horas": [24, 24]}))


def test_climatologia_solo_con_entrenamiento() -> None:
    t = tabla_base(_focos(), _comunas(), "2020-01-01", "2020-01-05")
    entrenamiento = t["fecha"] >= "2020-01-03"  # deja fuera el día con fuego (y24 del 01-ene)
    c = agregar_climatologia(t, entrenamiento)

    assert (c.loc[c.region_id == "05101", "clim_comuna_mes"] == 0).all()


def test_climatologia_sin_fuga_del_propio_anio() -> None:
    # Fuego solo el 10-ene-2019 en 05101. Todo es entrenamiento.
    focos = pd.DataFrame(
        {
            "region_id": pd.Series(["05101"], dtype="string"),
            "fecha_local": pd.to_datetime(["2019-01-10"]),
            "satelite": ["SNPP"],
            "uso_base": [True],
            "frp": [5.0],
        }
    )
    t = tabla_base(focos, _comunas(), "2019-01-01", "2020-12-30")
    c = agregar_climatologia(t, pd.Series(True, index=t.index))
    enero = c[(c.region_id == "05101") & (c.mes == 1)]
    anio = (enero["fecha"] + pd.Timedelta(days=1)).dt.year

    # Enero de 2019 solo puede "ver" enero de 2020 (sin fuego): 0. Si viera su propio año, sería > 0.
    assert (enero.loc[anio == 2019, "clim_comuna_mes"] == 0).all()
    # Enero de 2020 ve enero de 2019: 1 día con fuego de 30 días predichos (la tabla parte el 1-ene, así que el
    # primer día que se predice es el 2-ene).
    assert np.allclose(enero.loc[anio == 2020, "clim_comuna_mes"], 1 / 30)


def test_climatologia_fuera_de_entrenamiento_usa_todos_los_anios() -> None:
    focos = pd.DataFrame(
        {
            "region_id": pd.Series(["05101"], dtype="string"),
            "fecha_local": pd.to_datetime(["2019-01-10"]),
            "satelite": ["SNPP"],
            "uso_base": [True],
            "frp": [5.0],
        }
    )
    t = tabla_base(focos, _comunas(), "2019-01-01", "2020-12-30")
    entrenamiento = (t["fecha"] + pd.Timedelta(days=1)).dt.year == 2019
    c = agregar_climatologia(t, entrenamiento)
    enero_2020 = c[(c.region_id == "05101") & (c.mes == 1) & ~entrenamiento]

    assert np.allclose(enero_2020["clim_comuna_mes"], 1 / 30)  # usa todo el entrenamiento (enero 2019: 30 días)


def test_captura_top() -> None:
    y = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    p = np.array([0.9, 0.8, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.05])
    captura, lift = captura_top(y, p, fraccion=0.10)

    assert captura == 0.5 and lift == 5.0
