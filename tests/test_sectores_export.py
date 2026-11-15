import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from firecal.export.sectores import niveles_por_comuna, riesgo_horizonte, sectores_geojson
from firecal.sectores.recomendaciones import (
    CONDICIONES, RECOMENDACIONES, condiciones_clima, prioridad_alertas, rasgos_sector, recomendaciones_clima,
    recomendaciones_completas, recomendaciones_sector,
)


def _sectores() -> gpd.GeoDataFrame:
    base = {"frac_wui": [0.6, 0.0, 0.0, None], "frac_pastizal": [0.1, 0.5, 0.0, 0.0],
            "frac_arboles": [0.5, 0.1, 0.0, 0.0], "frac_matorral": [0.1, 0.1, 0.0, 0.0],
            "frac_cultivo": [0.0, 0.2, 0.9, 0.0], "frac_construido": [0.2, 0.0, 0.0, 1.0],
            "pendiente_media": [20.0, 5.0, 2.0, 1.0], "dias_con_fuego": [3, 0, 1, 40],
            "focos": [5, 0, 1, 50], "incendios_grandes": [0, 0, 0, 0], "mayor_incendio_focos": [4, 0, 1, 3],
            "ultimo_fuego": pd.to_datetime(["2024-02-03", None, "2019-01-01", "2025-12-01"]),
            "fuente_persistente": [False, False, False, True]}
    s = gpd.GeoDataFrame({"sector_id": ["05109_0_0", "05109_1_0", "05101_0_0", "05101_1_0"],
                          "region_id": ["05109", "05109", "05101", "05101"], "comuna": ["Viña", "Viña", "Valpo", "Valpo"],
                          "area_km2": [1.0] * 4, "lat": [-33.0] * 4, "lon": [-71.5] * 4, **base},
                         geometry=[box(-71.5, -33.0, -71.49, -32.99), box(-71.49, -33.0, -71.48, -32.99),
                                   box(-71.6, -33.0, -71.59, -32.99), box(-71.59, -33.0, -71.58, -32.99)],
                         crs="EPSG:4326")
    s["rasgos"] = rasgos_sector(s)
    return s


def test_rasgos() -> None:
    r = _sectores().set_index("sector_id")["rasgos"]
    assert r["05109_0_0"] == ["interfaz", "bosque_matorral", "pendiente", "historial"]
    assert r["05109_1_0"] == ["pastizal"]
    assert r["05101_0_0"] == []  # cultivo, plano, 1 solo día con fuego
    assert "fuente_persistente" in r["05101_1_0"]


def test_recomendaciones_segun_rasgos_y_nivel() -> None:
    interfaz_alto = recomendaciones_sector(["interfaz", "historial"], "alto", "05")
    assert interfaz_alto[0] == "avisar_130"
    assert {"entorno_vivienda", "sin_quemas_05", "plan_barrio"} <= set(interfaz_alto)
    assert recomendaciones_sector(["pastizal"], "bajo", "13") == ["calendario_quemas", "sin_colillas"]
    assert recomendaciones_sector([], "bajo", "05") == []
    # poda (MINVU) solo para casas junto a árboles: interfaz + bosque/matorral
    assert "poda" in recomendaciones_sector(["interfaz", "bosque_matorral"], "bajo", "05")
    assert "poda" not in recomendaciones_sector(["interfaz", "pastizal"], "bajo", "05")
    assert "poda" not in recomendaciones_sector(["bosque_matorral"], "bajo", "05")


def test_prioridad_ordena_comuna_luego_historial_y_excluye_persistentes() -> None:
    riesgo = pd.DataFrame({"region_id": ["05109", "05101"], "prob_foco": [0.2, 0.5], "nivel": ["alto", "alto"]})
    p = prioridad_alertas(_sectores(), riesgo)
    assert list(p["sector_id"]) == ["05101_0_0", "05109_0_0", "05109_1_0"]  # Valpo primero (más prob.)
    assert "05101_1_0" not in set(p["sector_id"])  # fuente persistente


def test_geojson_y_recomendaciones_por_horizonte() -> None:
    s = _sectores()
    g = sectores_geojson(s[s["region_id"] == "05109"].to_crs("ESRI:102033"), {24: "alto", 168: "bajo"}, "05")
    p = g["features"][0]["properties"]
    assert g["type"] == "FeatureCollection" and len(g["features"]) == 2
    assert p["pct_interfaz"] == 60.0 and p["exposicion"] == 4
    assert p["recomendaciones"]["24"][0] == "avisar_130"
    assert "avisar_130" not in p["recomendaciones"]["168"]


def test_riesgo_horizonte_y_niveles() -> None:
    r = pd.DataFrame({"region_id": ["05109", "05109", "05101"], "valido_para": pd.to_datetime(["2026-01-01"] * 3),
                      "horizonte_horas": [24, 168, 168], "prob_foco": [0.1, 0.6, 0.2], "percentil": [50.0, 80.0, 10.0],
                      "nivel": ["medio", "alto", "bajo"], "modelo": ["m"] * 3})
    info = {"modelo": "m", "periodo_prueba": "2022-2025", "horizontes": {"168": {
        "valido_desde": "2026-01-01", "valido_hasta": "2026-01-07", "umbrales": {"alto": 0.52},
        "prueba_modelo": {"auc": 0.8}, "prueba_climatologia": {"precision_media": 0.44},
        "ventaja_sobre_climatologia": 1.1}}}
    j = riesgo_horizonte(r, 168, info, "2026-11-15T00:00:00Z")
    assert j["horizonte_horas"] == 168 and j["valido_hasta"] == "2026-01-07" and j["orientativo"] is True
    assert [i["region_id"] for i in j["items"]] == ["05101", "05109"]
    assert niveles_por_comuna(r)["05109"] == {24: "medio", 168: "alto"}


def test_condiciones_clima_percentil_del_mismo_mes() -> None:
    fechas = pd.to_datetime([f"{a}-12-31" for a in range(2015, 2026)])
    c = pd.DataFrame({"region_id": "05109", "fecha": fechas, "tmax": list(range(20, 30)) + [35],
                      "hrmin": 50.0, "viento_max": 5.0, "precip": 0.0, "precip_7d": 0.0, "dias_sin_lluvia": 60})
    d = condiciones_clima(c, pd.Timestamp("2025-12-31")).iloc[0]
    assert d["tmax_percentil"] >= 90 and "calor" in d["condiciones"]
    assert "sin_lluvia" not in d["condiciones"]  # 60 días sin lluvia es lo normal en ese mes
    assert "temp_sobre_30" in d["condiciones"]  # 35 °C
    assert "condicion_30_30_30" not in d["condiciones"]  # humedad 50 % y viento 18 km/h


def test_condicion_30_30_30_con_viento_en_m_por_s() -> None:
    c = pd.DataFrame({"region_id": "05109", "fecha": pd.to_datetime(["2024-02-02", "2024-02-03"]),
                      "tmax": [25.0, 33.0], "hrmin": [60.0, 25.0], "viento_max": [3.0, 9.0],  # 9 m/s = 32,4 km/h
                      "precip": 0.0, "precip_7d": 0.0, "dias_sin_lluvia": 30})
    d = condiciones_clima(c, pd.Timestamp("2024-02-03")).iloc[0]
    assert d["viento_max_kmh"] == 32.4
    assert {"temp_sobre_30", "humedad_bajo_30", "viento_sobre_30", "condicion_30_30_30"} <= set(d["condiciones"])


def test_recomendaciones_por_clima() -> None:
    assert recomendaciones_clima([], "05") == []
    calor = recomendaciones_clima(["calor"], "05")
    assert calor == ["avisar_130", "faena_cero", "sin_fuentes_calor", "sin_quemas_05"]
    assert "faena_cero" not in recomendaciones_clima(["aire_seco"], "05")  # Faena Cero: calor o viento
    assert recomendaciones_clima(["sin_lluvia"], "13") == ["avisar_130"]
    # se combinan con las del sector sin repetir y con "avisar" primero
    todas = recomendaciones_completas(["interfaz"], "bajo", "05", ["viento"])
    assert todas[0] == "avisar_130" and len(todas) == len(set(todas)) and "entorno_vivienda" in todas


def test_nota_de_alertas_describe_el_orden_validado() -> None:
    from firecal.export.sectores import NOTA_ALERTAS

    assert "días con fuego previos" in NOTA_ALERTAS and "interfaz" in NOTA_ALERTAS
    assert "factores de exposición" not in NOTA_ALERTAS  # ese orden se descartó (no supera al azar en calibración)


def test_catalogo_cubre_todos_los_codigos() -> None:
    from firecal.sectores.recomendaciones import FUENTES

    for r in RECOMENDACIONES.values():
        assert r["fuente"] in FUENTES
    for c in CONDICIONES.values():
        assert c["fuente"] is None or c["fuente"] in FUENTES
