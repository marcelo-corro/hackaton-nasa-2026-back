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


def test_climatologia_solo_con_entrenamiento() -> None:
    t = tabla_base(_focos(), _comunas(), "2020-01-01", "2020-01-05")
    entrenamiento = t["fecha"] >= "2020-01-03"  # deja fuera el día con fuego (y24 del 01-ene)
    c = agregar_climatologia(t, entrenamiento)

    assert (c.loc[c.region_id == "05101", "clim_comuna_mes"] == 0).all()


def test_captura_top() -> None:
    y = np.array([1, 0, 0, 0, 0, 0, 0, 0, 0, 1])
    p = np.array([0.9, 0.8, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.05])
    captura, lift = captura_top(y, p, fraccion=0.10)

    assert captura == 0.5 and lift == 5.0
