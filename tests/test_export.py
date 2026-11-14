import json
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from firecal.export.contrato import COLUMNAS_FOCOS_CSV, exportar

EJEMPLOS = Path(__file__).resolve().parents[1] / "contracts" / "ejemplos"
AHORA = datetime(2026, 11, 15, 3, 0, tzinfo=timezone.utc)


def _calendario(region_ids):
    """Calendario sintético completo (302 meses por comuna), con nulos donde el contrato los permite."""
    filas = []
    for region_id in region_ids:
        for m in pd.period_range("2000-11", "2025-12", freq="M"):
            filas.append(
                {"region_id": region_id, "anio": m.year, "mes": m.month, "modis": 3,
                 "viirs": None if m < pd.Period("2012-02") else 10, "armonizado": 3.26,
                 "armonizado_p05": 2.04, "armonizado_p95": 4.5, "metodo": "metodo_de_prueba",
                 "mediana_historica": 0.0, "percentil": 66.666, "nivel": "normal"}
            )
    df = pd.DataFrame(filas)
    df["modis"] = df["modis"].astype("Int64")
    df["viirs"] = df["viirs"].astype("Int64")
    return df


@pytest.fixture()
def insumos():
    comunas = gpd.GeoDataFrame(
        {
            "region_id": ["05101", "05109"],
            "nombre": ["Valparaíso", "Viña del Mar"],
            "region": ["Valparaíso", "Valparaíso"],
            "geometry": [box(-71.75, -33.2, -71.55, -33.0), box(-71.55, -33.1, -71.45, -32.95)],
        },
        crs=4326,
    )
    base = {"region_id": "05109", "lat": -33.0233, "lon": -71.56, "frp": 38.44}
    focos = pd.DataFrame(
        [
            {**base, "fecha": pd.Timestamp("2024-02-10"), "hora_utc": "0315", "sensor": "MODIS",
             "satelite": "Terra", "confianza": "alta", "tipo": 0, "es_vegetacion": True},
            {**base, "fecha": pd.Timestamp("2024-02-11"), "hora_utc": "0600", "sensor": "VIIRS",
             "satelite": "SNPP", "confianza": "baja", "tipo": 0, "es_vegetacion": True},
            {**base, "fecha": pd.Timestamp("2024-02-11"), "hora_utc": "0700", "sensor": "MODIS",
             "satelite": "Aqua", "confianza": "alta", "tipo": 2, "es_vegetacion": False},
            {**base, "region_id": None, "fecha": pd.Timestamp("2024-02-12"), "hora_utc": "0100", "sensor": "MODIS",
             "satelite": "Aqua", "confianza": "alta", "tipo": 0, "es_vegetacion": True},
        ]
    )
    return _calendario(["05101", "05109"]), comunas, focos


def _leer(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def test_claves_iguales_a_las_de_los_ejemplos(insumos, tmp_path):
    calendario, comunas, focos = insumos
    exportar(calendario, comunas, focos, tmp_path, ahora=AHORA)

    for archivo in ("manifest.json", "metricas.json", "riesgo/ultimo.json"):
        assert set(_leer(tmp_path / archivo)) == set(_leer(EJEMPLOS / archivo)), archivo

    generado, ejemplo = _leer(tmp_path / "calendario" / "05109.json"), _leer(EJEMPLOS / "calendario" / "05109.json")
    assert set(generado) == set(ejemplo)
    assert set(generado["registros"][0]) == set(ejemplo["registros"][0])

    geo, geo_ej = _leer(tmp_path / "regiones.geojson"), _leer(EJEMPLOS / "regiones.geojson")
    assert set(geo) == set(geo_ej)
    assert set(geo["features"][0]) == set(geo_ej["features"][0])
    assert set(geo["features"][0]["properties"]) == set(geo_ej["features"][0]["properties"])


def test_encabezado_de_focos_igual_al_de_los_ejemplos(insumos, tmp_path):
    exportar(*insumos, tmp_path, ahora=AHORA)
    ejemplo = (EJEMPLOS / "focos" / "05109.csv").read_text(encoding="utf-8").splitlines()[0]
    assert ejemplo == ",".join(COLUMNAS_FOCOS_CSV)
    assert (tmp_path / "focos" / "05109.csv").read_text(encoding="utf-8").splitlines()[0] == ejemplo


def test_focos_solo_vegetacion_con_comuna_y_comuna_sin_focos_solo_encabezado(insumos, tmp_path):
    exportar(*insumos, tmp_path, ahora=AHORA)
    crudo = (tmp_path / "focos" / "05109.csv").read_bytes()
    assert b"\r" not in crudo  # sin \r\n de Windows
    assert len(crudo.decode("utf-8").splitlines()) == 3  # encabezado + 2 de vegetación (incluye confianza baja)
    assert (tmp_path / "focos" / "05101.csv").read_text(encoding="utf-8").splitlines() == [",".join(COLUMNAS_FOCOS_CSV)]


def test_calendario_sin_huecos_nulos_como_null_y_tildes_sin_escapar(insumos, tmp_path):
    exportar(*insumos, tmp_path, ahora=AHORA)
    texto = (tmp_path / "calendario" / "05109.json").read_text(encoding="utf-8")
    assert "Viña del Mar" in texto
    registros = json.loads(texto)["registros"]
    assert len(registros) == 302
    assert registros[0]["viirs"] is None  # 2000-11
    assert registros[-1]["viirs"] == 10
    assert registros[0]["armonizado"] == 3.3 and registros[0]["percentil"] == 66.7  # 1 decimal


def test_sin_riesgo_ni_metricas_van_vacios_o_en_null(insumos, tmp_path):
    exportar(*insumos, tmp_path, ahora=AHORA)
    assert _leer(tmp_path / "riesgo" / "ultimo.json")["items"] == []
    metricas = _leer(tmp_path / "metricas.json")
    assert metricas["auc"] is None and metricas["modelo"] is None and metricas["ejemplo"] is False


def test_manifest_real(insumos, tmp_path):
    resumen = exportar(*insumos, tmp_path, ahora=AHORA)
    manifest = _leer(tmp_path / "manifest.json")
    assert manifest["ejemplo"] is False
    assert manifest["generado_utc"] == "2026-11-15T03:00:00Z"
    assert manifest["periodo"] == {"desde": "2000-11", "hasta": "2025-12"}
    assert manifest["regiones"] == ["05101", "05109"]
    assert resumen["comunas"] == 2 and resumen["archivos"] == 1 + 1 + 1 + 2 + 2 + 1 + 1  # index, geojson, manifest, 2+2, riesgo, metricas


def test_riesgo_publica_solo_el_valido_para_mas_reciente(insumos, tmp_path):
    riesgo = pd.DataFrame(
        {
            "region_id": ["05101", "05109", "05109"],
            "valido_para": pd.to_datetime(["2026-11-15", "2026-11-15", "2026-11-14"]),
            "horizonte_horas": [24, 24, 24],
            "prob_foco": [0.08, 0.21, 0.5],
            "percentil": [61.0, 88.0, 99.0],
            "nivel": ["medio", "alto", "muy_alto"],
            "modelo": ["riesgo_24h_v1"] * 3,
        }
    )
    exportar(*insumos, tmp_path, riesgo=riesgo, datos_metricas={"modelo": "riesgo_24h_v1", "auc": 0.79}, ahora=AHORA)
    datos = _leer(tmp_path / "riesgo" / "ultimo.json")
    assert datos["valido_para"] == "2026-11-15"
    assert [i["region_id"] for i in datos["items"]] == ["05101", "05109"]
    assert set(datos["items"][0]) == {"region_id", "prob_foco", "percentil", "nivel"}
    assert _leer(tmp_path / "metricas.json")["auc"] == 0.79
