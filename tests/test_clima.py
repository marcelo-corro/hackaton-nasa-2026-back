import json

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import requests
from shapely.geometry import Polygon

from firecal.ingest import clima


class _Respuesta:
    def __init__(self, status=200, datos=None):
        self.status_code, self._datos = status, datos

    def json(self):
        return self._datos

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


def _parametros(dias=3, valor=1.0, **sobrescribir):
    """`properties.parameter` de POWER: {parametro: {"YYYYMMDD": valor}}."""
    fechas = pd.date_range("2012-01-01", periods=dias).strftime("%Y%m%d")
    base = {"T2M_MAX": 30.0, "T2MDEW": 10.0, "RH2M": 50.0, "WS10M_MAX": 5.0, "PRECTOTCORR": valor}
    base.update(sobrescribir)
    return {p: {f: base[p] for f in fechas} for p in clima.PARAMETROS_POWER}


def _respuesta(dias=3, **kw):
    return _Respuesta(datos={"properties": {"parameter": _parametros(dias, **kw)}})


def _puntos(n):
    return pd.DataFrame({"region_id": [f"0{i:04d}" for i in range(n)], "lat": -33.0, "lon": -71.0})


def _sin_log(_):
    pass


def _sin_espera(_):
    pass


def test_punto_representativo_cae_dentro_de_una_comuna_en_forma_de_c():
    c = Polygon([(0, 0), (10, 0), (10, 1), (1, 1), (1, 9), (10, 9), (10, 10), (0, 10)])
    assert not c.contains(c.centroid)  # el centroide cae fuera...
    comunas = gpd.GeoDataFrame({"region_id": ["01101"], "geometry": [c]}, crs=4326)
    p = clima.puntos_representativos(comunas).iloc[0]
    assert c.contains(gpd.points_from_xy([p["lon"]], [p["lat"]])[0])  # ...el representativo no


def test_humedad_minima_con_valores_conocidos():
    # 30 °C con rocío de 10 °C: e(10)=12,28 hPa y e(30)=42,43 hPa -> 28,9 %
    hr = clima.humedad_minima_aproximada(pd.Series([30.0]), pd.Series([10.0]))
    assert hr.iloc[0] == pytest.approx(28.9, abs=0.2)
    # rocío igual a la temperatura -> 100 %; rocío mayor se acota a 100
    assert clima.humedad_minima_aproximada(pd.Series([20.0]), pd.Series([20.0])).iloc[0] == pytest.approx(100.0)
    assert clima.humedad_minima_aproximada(pd.Series([20.0]), pd.Series([25.0])).iloc[0] == 100.0


def test_descarga_una_consulta_por_comuna_cachea_y_retoma(tmp_path):
    llamadas = []

    def get(url, params, timeout):
        llamadas.append((params["latitude"], params["longitude"]))
        assert params["parameters"] == ",".join(clima.PARAMETROS_POWER)
        return _respuesta()

    puntos = _puntos(4)
    assert clima.descargar_clima(puntos, tmp_path, get=get, dormir=_sin_espera, log=_sin_log) == 4
    assert len(llamadas) == 4

    llamadas.clear()
    assert clima.descargar_clima(puntos, tmp_path, get=get, dormir=_sin_espera, log=_sin_log) == 0
    assert llamadas == []  # todo estaba en caché


def test_si_se_corta_lo_ya_bajado_queda_en_cache(tmp_path):
    respuestas = iter([_respuesta(), _respuesta(), _Respuesta(404)])
    with pytest.raises(RuntimeError):
        clima.descargar_clima(_puntos(4), tmp_path, get=lambda *a, **k: next(respuestas), dormir=_sin_espera, log=_sin_log)
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_reintenta_con_429_5xx_y_errores_de_red(tmp_path):
    respuestas = iter([_Respuesta(429), requests.Timeout("lento"), _Respuesta(503), _respuesta()])
    esperas = []

    def get(*a, **k):
        r = next(respuestas)
        if isinstance(r, Exception):
            raise r
        return r

    clima.descargar_clima(_puntos(1), tmp_path, get=get, dormir=esperas.append, log=_sin_log, pausa_s=0)
    assert esperas[:3] == [5.0, 10.0, 20.0]  # espera exponencial
    assert (tmp_path / "00000.json").exists()


def test_se_rinde_tras_agotar_los_reintentos(tmp_path):
    with pytest.raises(RuntimeError, match="no respondió"):
        clima.descargar_clima(_puntos(1), tmp_path, reintentos=2, get=lambda *a, **k: _Respuesta(503),
                              dormir=_sin_espera, log=_sin_log)
    assert not list(tmp_path.glob("*.json"))


def test_tabla_diaria_columnas_y_valores_faltantes(tmp_path):
    puntos = _puntos(2)
    for r in puntos["region_id"]:
        guardado = {"lat": -33.0, "lon": -71.0, "parameter": _parametros(3, PRECTOTCORR=-999.0)}
        (tmp_path / f"{r}.json").write_text(json.dumps(guardado), encoding="utf-8")
    tabla = clima.clima_diario(puntos, tmp_path)

    assert list(tabla.columns) == ["region_id", "fecha_local", "tmax", "hrmin", "hr_media", "viento_max", "precip"]
    assert len(tabla) == 6
    assert tabla["tmax"].iloc[0] == 30.0 and tabla["viento_max"].iloc[0] == 5.0
    assert (tabla["hrmin"] <= tabla["hr_media"]).all()
    assert tabla["precip"].isna().all()  # -999 pasa a nulo
    assert "valores nulos" in " ".join(clima.huecos(tabla, n_comunas=2))

    with pytest.raises(FileNotFoundError):
        clima.clima_diario(_puntos(3), tmp_path)


def test_tabla_completa_sin_huecos(tmp_path):
    dias = len(pd.date_range(clima.FECHA_DESDE, clima.FECHA_HASTA))
    assert dias == 5114
    guardado = {"lat": -33.0, "lon": -71.0, "parameter": _parametros(dias)}
    (tmp_path / "00000.json").write_text(json.dumps(guardado), encoding="utf-8")
    tabla = clima.clima_diario(_puntos(1), tmp_path)
    assert clima.huecos(tabla, n_comunas=1) == []
    assert not np.isnan(tabla["hrmin"]).any()
    assert "sin los" in " ".join(clima.huecos(tabla.iloc[:-1], n_comunas=1))
