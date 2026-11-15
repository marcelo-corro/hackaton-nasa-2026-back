import numpy as np
import pandas as pd

from firecal.avance import (
    a_favor_del_viento, error_angular, ficha_avance, incendios_activos, pares_avance, rumbo,
)

PARAMS = {"radios_km": {"p75": 2.53, "p90": 3.63}, "viento_fuerte_desde_ms": 3.18}


def test_rumbos_y_errores() -> None:
    assert rumbo(np.array([0.0, 1.0, 0.0, -1.0]), np.array([1.0, 0.0, -1.0, 0.0])).tolist() == [0, 90, 180, 270]
    assert error_angular(350, 10) == 20 and error_angular(0, 180) == 180
    assert a_favor_del_viento(np.array([270.0]))[0] == 90  # viento del oeste empuja hacia el este


def test_pares_avance_mide_el_frente_nuevo() -> None:
    # día 1 en (0,0); día 2: un foco en el mismo lugar y un frente nuevo ~2,2 km al norte
    f = pd.DataFrame({"evento": 1, "region_id": "05101",
                      "lat": [-33.0, -33.0, -32.98], "lon": [-71.5, -71.5, -71.5],
                      "fecha_local": pd.to_datetime(["2024-02-02", "2024-02-03", "2024-02-03"])})
    p = pares_avance(f)
    assert len(p) == 1
    assert abs(p["rumbo_real"].iat[0] - 0) < 1 and abs(p["km"].iat[0] - 2.21) < 0.05
    assert p["focos_frente"].iat[0] == 1 and np.isnan(p["rumbo_previo"].iat[0])


def test_incendios_activos_y_ficha() -> None:
    f = pd.DataFrame({"evento": [1, 1, 2], "region_id": ["05101", "05101", "05109"],
                      "lat": [-33.0, -33.01, -33.2], "lon": [-71.5, -71.51, -71.6],
                      "fecha_local": pd.to_datetime(["2026-11-10", "2026-11-13", "2026-11-01"])})
    a = incendios_activos(f, pd.Timestamp("2026-11-14"))
    assert list(a["evento"]) == [1]  # el 2 tuvo focos hace más de 3 días
    inc = a.iloc[0]
    assert inc["lat"] == -33.01 and inc["dias_con_focos"] == 2 and inc["focos_incendio"] == 2
    viento = pd.DataFrame({"fecha": pd.to_datetime(["2026-11-11", "2026-11-12"]), "viento_dir": [180.0, 270.0],
                           "viento_vel": [2.0, 4.0]})
    fi = ficha_avance(inc, viento, PARAMS)
    assert fi["viento"]["fecha"] == "2026-11-12" and fi["viento"]["hacia_grados"] == 90
    assert fi["mostrar_flecha"] is True and fi["radio_km_85"] == 3.63
    suave = ficha_avance(inc, viento.assign(viento_vel=1.0), PARAMS)
    assert suave["mostrar_flecha"] is False
    assert ficha_avance(inc, viento.iloc[0:0], PARAMS)["viento"] is None
