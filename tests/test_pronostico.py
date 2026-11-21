import numpy as np
import pandas as pd
import pytest

from firecal.ingest import pronostico as pr
from firecal.model.variables import bloque_clima, combinar_con_pronostico, variables_futuro


def _horario(dias: int, horas_ultimo: int = 24) -> pd.DataFrame:
    filas = []
    for d in range(dias):
        n = horas_ultimo if d == dias - 1 else 24
        for h in range(n):
            filas.append({"time": f"2026-11-{10 + d:02d}T{h:02d}:00", "temperature_2m": 10 + h, "relative_humidity_2m":
                          80 - h, "wind_speed_10m": h / 4, "precipitation": 0.5 if h == 6 else 0.0})
    return pd.DataFrame(filas)


def test_horario_a_diario_resume_y_descarta_dias_incompletos() -> None:
    d = pr.horario_a_diario(_horario(2, horas_ultimo=12))
    assert len(d) == 1  # el segundo día tiene 12 horas (< 20)
    fila = d.iloc[0]
    assert fila["tmax"] == 33 and fila["hrmin"] == 57 and fila["viento_max"] == 23 / 4 and fila["precip"] == 0.5


class _Resp:
    def __init__(self, datos, status=200):
        self._d, self.status_code, self.text = datos, status, ""

    def json(self):
        return self._d


class _Sesion:
    def __init__(self, respuestas):
        self.respuestas, self.pedidos = list(respuestas), []

    def get(self, url, params, timeout):
        self.pedidos.append(params)
        return self.respuestas.pop(0)


def test_pedir_pronostico_varias_comunas_por_peticion(monkeypatch) -> None:
    monkeypatch.setattr(pr.time, "sleep", lambda s: None)
    horario = _horario(2).to_dict(orient="list")
    puntos = pd.DataFrame({"region_id": ["05101", "05109"], "lat": [-33.0, -33.02], "lon": [-71.6, -71.55]})
    s = _Sesion([_Resp([{"hourly": horario}, {"hourly": horario}])])
    p = pr.pedir_pronostico(puntos, dias_atras=5, dias_adelante=3, sesion=s)
    assert len(s.pedidos) == 1
    assert s.pedidos[0]["latitude"] == "-33.0000,-33.0200" and s.pedidos[0]["past_days"] == 5
    assert s.pedidos[0]["wind_speed_unit"] == "ms" and s.pedidos[0]["timezone"] == "America/Santiago"
    assert sorted(p["region_id"].unique()) == ["05101", "05109"] and len(p) == 4


def test_pedir_pronostico_falla_con_error_no_reintentable(monkeypatch) -> None:
    monkeypatch.setattr(pr.time, "sleep", lambda s: None)
    puntos = pd.DataFrame({"region_id": ["05101"], "lat": [-33.0], "lon": [-71.6]})
    with pytest.raises(RuntimeError):
        pr.pedir_pronostico(puntos, sesion=_Sesion([_Resp({}, status=400)]))


def _power() -> pd.DataFrame:
    fechas = pd.date_range("2026-11-01", "2026-11-10")
    return pd.DataFrame({"region_id": "05101", "fecha": fechas, "tmax": 20.0, "hrmin": 40.0, "viento_max": 5.0,
                         "precip": [0.0] * 9 + [3.0]})


def _pronostico() -> pd.DataFrame:
    fechas = pd.date_range("2026-11-09", "2026-11-14")  # se superpone con POWER el 9 y el 10
    return pd.DataFrame({"region_id": "05101", "fecha": fechas, "tmax": [99.0, 99.0, 25.0, 26.0, 27.0, 28.0],
                         "hrmin": 30.0, "viento_max": 6.0, "precip": [0.0, 0.0, 1.0, 0.0, 0.0, 2.0]})


def test_combinar_usa_power_y_solo_los_dias_siguientes_del_pronostico() -> None:
    c = combinar_con_pronostico(_power(), _pronostico())
    assert c["fecha"].max() == pd.Timestamp("2026-11-14")
    assert not c.duplicated(["region_id", "fecha"]).any()
    assert (c.loc[c["fecha"] <= "2026-11-10", "tmax"] == 20.0).all()  # NASA POWER manda donde existe
    assert c.loc[c["fecha"] > "2026-11-10", "pronostico"].all()


def test_bloque_clima_con_pronostico(tmp_path) -> None:
    ruta = tmp_path / "clima.parquet"
    _power().rename(columns={"fecha": "fecha_local"}).to_parquet(ruta)
    c = bloque_clima(ruta, _pronostico()).set_index("fecha")
    assert c.loc["2026-11-11", "tmax"] == 25.0
    assert c.loc["2026-11-11", "precip_7d"] == pytest.approx(4.0)  # 3 mm del 10 (POWER) + 1 mm del 11 (pronóstico)
    assert bloque_clima(ruta)["fecha"].max() == pd.Timestamp("2026-11-10")  # sin pronóstico, como antes


def test_variables_futuro() -> None:
    c = combinar_con_pronostico(_power(), _pronostico())
    f = variables_futuro(c).set_index("fecha")
    assert f.loc["2026-11-10", "tmax_f1"] == 25.0  # el día t+1
    assert f.loc["2026-11-10", "tmax_f2"] == 26.0  # máximo de t+1 y t+2
    assert f.loc["2026-11-10", "precip_f2"] == pytest.approx(1.0)
    assert np.isnan(f.loc["2026-11-13", "tmax_f2"])  # no hay t+2 (el 15)


def test_fecha_clima_a_mostrar_prefiere_el_dia_pronosticado() -> None:
    from firecal.export.comunas import fecha_clima_a_mostrar

    c = combinar_con_pronostico(_power(), _pronostico())  # POWER hasta el 10, pronóstico hasta el 14
    assert fecha_clima_a_mostrar(c, pd.Timestamp("2026-11-12")) == (pd.Timestamp("2026-11-13"), True)
    # Sin pronóstico para el día que se predice: el último observado, como antes
    assert fecha_clima_a_mostrar(_power().assign(pronostico=False), pd.Timestamp("2026-11-12")) == (
        pd.Timestamp("2026-11-10"), False)
    assert fecha_clima_a_mostrar(None, pd.Timestamp("2026-11-12")) == (None, False)


def test_condiciones_clima_dice_si_es_pronostico(tmp_path) -> None:
    from firecal.sectores.recomendaciones import condiciones_clima

    ruta = tmp_path / "clima.parquet"
    _power().rename(columns={"fecha": "fecha_local"}).to_parquet(ruta)
    c = bloque_clima(ruta, _pronostico())
    pron = condiciones_clima(c, pd.Timestamp("2026-11-13")).iloc[0]
    obs = condiciones_clima(c, pd.Timestamp("2026-11-08")).iloc[0]
    assert pron["pronostico"] and pron["fuente"] == "Open-Meteo"
    assert not obs["pronostico"] and obs["fuente"] == "NASA POWER"
