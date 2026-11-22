"""Sectores v0.9: atributos fijos guardados con huella, modelo B reutilizable y formato compacto (fijo + diario)."""

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from firecal import config
from firecal.export.sectores import AREA_COMPLETA_KM2, sectores_dia_json, sectores_fijo_json, sectores_geojson
from firecal.sectores.fijo import guardar_fijo, huella_fijo, leer_fijo, traslacion_sad69
from firecal.sectores.grilla import CRS_METRICO, grilla_sectores
from firecal.sectores.modelo_b import ESTATICAS, huella_entrenamiento
from firecal.sectores.recomendaciones import rasgos_sector


def _comunas() -> gpd.GeoDataFrame:
    # Dos comunas cerca de Viña del Mar en ESRI:102033: una de 2,5 × 1,5 km (con bordes) y otra de 2 × 1 km exactos
    return gpd.GeoDataFrame({"region_id": ["05109", "05101"], "nombre": ["Viña", "Valpo"]},
                            geometry=[box(-1033500, -168000, -1031000, -166500), box(-1040000, -175000, -1038000, -174000)],
                            crs=CRS_METRICO).to_crs("EPSG:4326")


def _sectores() -> gpd.GeoDataFrame:
    s = grilla_sectores(_comunas())
    n = len(s)
    rng = np.random.default_rng(0)
    s["frac_wui"] = np.where(np.arange(n) % 3 == 0, 0.6, 0.0)
    s.loc[1, "frac_wui"] = np.nan
    s["frac_pastizal"], s["frac_arboles"], s["frac_matorral"] = 0.45, 0.3, 0.25
    s["frac_cultivo"], s["frac_construido"] = 0.0, 0.1
    s["pendiente_media"] = rng.uniform(0, 30, n).round(2)
    s["dias_con_fuego"] = np.arange(n) % 4
    s["focos"] = s["dias_con_fuego"] * 2
    s["incendios_grandes"], s["mayor_incendio_focos"] = 0, s["focos"]
    s["ultimo_fuego"] = pd.to_datetime(["2024-02-03" if d else None for d in s["dias_con_fuego"]])
    s["fuente_persistente"] = False
    s["prob_condicional"] = rng.uniform(0, 0.02, n)
    s["prob_grande"] = rng.uniform(0, 1, n)
    s["percentil_en_comuna"] = 100 * s.groupby("region_id")["prob_condicional"].rank(pct=True)
    s["rasgos"] = rasgos_sector(s)
    return s


def test_huella_fijo_cambia_solo_si_cambian_las_comunas(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "PROCESSED_DIR", tmp_path)
    c = _comunas()
    h = huella_fijo(c)
    assert h == huella_fijo(c.iloc[::-1])  # no depende del orden de las filas
    otra = c.copy()
    otra.loc[0, "geometry"] = otra.geometry.iloc[0].buffer(0.001)
    assert huella_fijo(otra) != h

    assert leer_fijo("05", h) is None  # aún no se guardó
    guardar_fijo(grilla_sectores(c), "05", h)
    assert len(leer_fijo("05", h)) == len(grilla_sectores(c))
    assert leer_fijo("05", huella_fijo(otra)) is None  # cambió la huella: hay que recalcular


@pytest.mark.parametrize("lon, lat, esperado", [
    (-70.40, -23.65, [-59.0, -11.0, -52.0]),  # Antofagasta: Chile al norte de 32° S
    (-71.55, -33.02, [-64.0, 0.0, -32.0]),  # Viña del Mar: entre 32° y 36° S
    (-72.59, -38.74, [-72.0, 10.0, -32.0]),  # Temuco: entre 36° y 43,5° S
])
def test_traslacion_sad69_por_franja(lon, lat, esperado) -> None:
    assert traslacion_sad69(lon, lat) == esperado


def test_huella_entrenamiento_ignora_lo_posterior_al_periodo() -> None:
    s = pd.DataFrame({"sector_id": ["A_0", "A_1"], "region_id": "A", "ix": [0, 1], "iy": [0, 0]})
    for c in ESTATICAS:
        s[c] = 0.5
    f = pd.DataFrame({"sector_id": ["A_0", "A_1", "A_0"], "region_id": "A",
                      "fecha_local": pd.to_datetime(["2015-01-01", "2020-06-01", "2026-11-20"]),
                      "lat": -33.0, "lon": -71.5, "focos_incendio": [1, 12, 3]})
    hasta = pd.Timestamp("2025-12-31")
    h = huella_entrenamiento(s, f, hasta, "v1")
    nuevo_2026 = pd.concat([f, f.iloc[[2]].assign(fecha_local=pd.Timestamp("2026-11-21"))], ignore_index=True)
    assert huella_entrenamiento(s, nuevo_2026, hasta, "v1") == h  # un foco nuevo de hoy no obliga a reentrenar
    assert huella_entrenamiento(s, f.assign(focos_incendio=[1, 13, 3]), hasta, "v1") != h  # cambió un incendio de 2020
    assert huella_entrenamiento(s.assign(frac_wui=0.1), f, hasta, "v1") != h
    assert huella_entrenamiento(s, f, hasta, "v2") != h


def test_compacto_trae_lo_mismo_que_el_geojson() -> None:
    s = _sectores()
    niveles = {24: "alto", 48: "medio", 168: "bajo"}
    for rid in ["05109", "05101"]:
        sc = s[s["region_id"] == rid]
        fijo = sectores_fijo_json(sc, [-64.0, 0.0, -32.0])
        dia = sectores_dia_json(sc, niveles, "05", fijo["version"], ["calor"], "2026-11-23")
        geo = sectores_geojson(sc, niveles, "05", ["calor"])
        assert fijo["n"] == dia["n"] == len(geo["features"]) == len(sc)
        assert dia["version_fijo"] == fijo["version"]
        bordes = set(fijo["bordes"]["i"])
        assert bordes == set(np.flatnonzero(sc["area_km2"].to_numpy() < AREA_COMPLETA_KM2))
        g = fijo["grilla"]
        for i, feat in enumerate(geo["features"]):
            p = feat["properties"]
            assert p["sector_id"] == f"{rid}_{g['ix0'] + fijo['dx'][i]}_{g['iy0'] + fijo['dy'][i]}"
            for k in ["area_km2", "pct_interfaz", "pct_pastizal", "pct_bosque_matorral", "pendiente_media"]:
                assert fijo[k][i] == p[k]
            for k in ["dias_con_fuego", "focos", "ultimo_fuego", "prob_si_fuego_en_comuna", "percentil_en_comuna"]:
                assert dia[k][i] == p[k]
            combo = dia["combinaciones"][dia["rasgos"][i]]
            assert combo["rasgos"] == p["rasgos"] and combo["recomendaciones"] == p["recomendaciones"]
            if i in bordes:
                j = fijo["bordes"]["i"].index(i)
                assert fijo["bordes"]["geometria"][j] == feat["geometry"]
                assert fijo["bordes"]["punto"][j] == [p["lon"], p["lat"]]
    # la comuna de 2 × 1 km calza con la grilla: sin bordes
    assert sectores_fijo_json(s[s["region_id"] == "05101"], [0, 0, 0])["bordes"]["i"] == []


def test_compacto_sin_modelo_b_y_version_estable() -> None:
    s = _sectores().drop(columns=["prob_condicional", "prob_grande", "percentil_en_comuna"])
    sc = s[s["region_id"] == "05109"]
    fijo = sectores_fijo_json(sc, [-64.0, 0.0, -32.0])
    assert fijo["version"] == sectores_fijo_json(sc.copy(), [-64.0, 0.0, -32.0])["version"]
    assert fijo["pct_interfaz"][1] is None  # sin dato de interfaz
    dia = sectores_dia_json(sc, {24: "bajo"}, "05", fijo["version"])
    assert dia["prob_si_fuego_en_comuna"] == [None] * len(sc) and dia["fecha_prediccion"] is None
