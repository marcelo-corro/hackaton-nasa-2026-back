"""comunas.json (contrato 0.8): las reglas del piloto de Valparaíso aplicadas a todas las comunas."""

import pandas as pd

from firecal.export.comunas import comunas_pais
from firecal.export.contrato import VERSION_CONTRATO

DIA = pd.Timestamp("2026-11-15")


def _riesgo() -> pd.DataFrame:
    filas = []
    for rid, niveles in {"05101": ("bajo", "medio", "medio"), "09202": ("alto", "alto", "medio"),
                         "13101": ("bajo", "bajo", "bajo")}.items():
        for h, n in zip((24, 48, 168), niveles):
            filas.append({"region_id": rid, "valido_para": DIA, "horizonte_horas": h, "prob_foco": 0.3 if n == "alto" else 0.02,
                          "nivel": n})
            filas.append({"region_id": rid, "valido_para": DIA - pd.Timedelta(days=1), "horizonte_horas": h,
                          "prob_foco": 0.9, "nivel": "muy_alto"})  # día anterior: no debe usarse
    return pd.DataFrame(filas)


def _condiciones() -> pd.DataFrame:
    base = {"fecha_clima": "2026-11-11", "tmax": 31.0, "tmax_percentil": 95, "hrmin": 25.0, "hrmin_percentil": 5,
            "viento_max": 3.0, "viento_max_kmh": 10.8, "viento_percentil": 40, "dias_sin_lluvia": 12,
            "dias_sin_lluvia_percentil": 60}
    return pd.DataFrame([{**base, "region_id": "05101", "condiciones": ["calor", "aire_seco"]},
                         {**base, "region_id": "09202", "condiciones": ["calor"]},
                         {**base, "region_id": "13101", "condiciones": []}])


def _datos() -> dict:
    nombres = {"05101": "Valparaíso", "09202": "Collipulli", "13101": "Santiago"}
    regiones = {"05101": "Región de Valparaíso", "09202": "Región de La Araucanía", "13101": "Región Metropolitana"}
    dias = {"09202": pd.Series(pd.to_datetime(["2026-11-14", "2026-11-14", "2025-11-03"]))}
    return comunas_pais(_riesgo(), _condiciones(), nombres, regiones, dias, DIA - pd.Timedelta(days=1),
                        pd.Timestamp("2026-11-11"), "2026-11-15T06:00:00Z")


def test_estructura_y_todas_las_comunas() -> None:
    d = _datos()
    assert d["contrato"] == VERSION_CONTRATO and d["ejemplo"] is False
    assert d["valido_para"] == "2026-11-15" and d["ultimo_dato_focos"] == "2026-11-14" and d["fecha_clima"] == "2026-11-11"
    assert [c["region_id"] for c in d["comunas"]] == ["05101", "09202", "13101"]
    c = d["comunas"][1]
    assert c["nombre"] == "Collipulli" and c["region"] == "Región de La Araucanía"
    assert set(c["riesgo"]) == {"24", "48", "168"} and c["riesgo"]["24"] == {"prob_foco": 0.3, "nivel": "alto"}
    for clave in ("clima_ultimo_dia", "recomendaciones_clima", "recomendaciones", "motivos", "fuego_activo",
                  "dias_con_fuego_7d", "ultimo_fuego", "pct_dias_con_fuego_mes"):
        assert clave in c


def test_recomendaciones_por_horizonte_y_region() -> None:
    cs = {c["region_id"]: c for c in _datos()["comunas"]}
    # Collipulli en nivel alto: avisar al 130 primero; fuera de Valparaíso, calendario de quemas y no la restricción 05
    assert cs["09202"]["recomendaciones"]["24"][0] == "avisar_130"
    assert "calendario_quemas" in cs["09202"]["recomendaciones"]["24"]
    assert "sin_quemas_05" not in cs["09202"]["recomendaciones"]["24"]
    # Valparaíso: la restricción de quemas de la región 05
    assert "sin_quemas_05" in cs["05101"]["recomendaciones"]["24"]
    # Santiago, bajo y sin condiciones de clima: sin recomendaciones (no se inventan)
    assert cs["13101"]["recomendaciones"] == {"24": [], "48": [], "168": []}
    assert cs["13101"]["clima_ultimo_dia"]["condiciones"] == []


def test_motivos_y_fuego_activo() -> None:
    cs = {c["region_id"]: c for c in _datos()["comunas"]}
    assert cs["09202"]["fuego_activo"] is True and cs["09202"]["ultimo_fuego"] == "2026-11-14"
    assert cs["09202"]["motivos"][0].startswith("Fuego activo")
    assert cs["13101"]["fuego_activo"] is False and cs["13101"]["ultimo_fuego"] is None
