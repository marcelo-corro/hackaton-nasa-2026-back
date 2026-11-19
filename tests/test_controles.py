"""Controles antes de que la actualización diaria publique sola."""

import json
from datetime import date

from firecal.export.controles import controles_publicacion

HOY = date(2026, 11, 19)


def _public(tmp_path, valido="2026-11-19", n=345, contrato="0.8", clima="2026-11-16"):
    p = tmp_path / "public"
    for d in ("riesgo", "avance", "alertas"):
        (p / d).mkdir(parents=True, exist_ok=True)

    def escribir(ruta, datos):
        (p / ruta).write_text(json.dumps(datos), encoding="utf-8")

    escribir("manifest.json", {"contrato": contrato, "ejemplo": False, "datos": {"clima_hasta": clima}})
    items = [{"region_id": f"{i:05d}", "prob_foco": 0.1, "nivel": "bajo"} for i in range(n)]
    for ruta in ("riesgo/ultimo.json", "riesgo/48h.json", "riesgo/7d.json"):
        escribir(ruta, {"valido_para": valido, "items": items})
    escribir("comunas.json", {"comunas": [{"region_id": i["region_id"]} for i in items]})
    escribir("regiones.geojson", {"features": [{}] * 345})
    for ruta in ("avance/activos.json", "alertas/05.json", "recomendaciones.json"):
        escribir(ruta, {})
    (p / "index.html").write_text("<html></html>", encoding="utf-8")
    return p


def test_todo_en_orden(tmp_path):
    assert controles_publicacion(_public(tmp_path), HOY, "0.8", llave="abc123") == ([], [])


def test_datos_atrasados_no_se_publican(tmp_path):
    errores, _ = controles_publicacion(_public(tmp_path, valido="2026-11-15"), HOY, "0.8")
    assert any("no se actualizaron" in e for e in errores)


def test_acepta_un_dia_de_atraso_de_firms(tmp_path):
    assert controles_publicacion(_public(tmp_path, valido="2026-11-18"), HOY, "0.8")[0] == []


def test_faltan_comunas(tmp_path):
    errores, _ = controles_publicacion(_public(tmp_path, n=300), HOY, "0.8")
    assert any("300 comunas" in e for e in errores)


def test_contrato_distinto(tmp_path):
    errores, _ = controles_publicacion(_public(tmp_path, contrato="0.7"), HOY, "0.8")
    assert any("contrato" in e for e in errores)


def test_la_llave_no_puede_publicarse(tmp_path):
    p = _public(tmp_path)
    (p / "avance" / "activos.json").write_text('{"nota": "abc123"}', encoding="utf-8")
    errores, _ = controles_publicacion(p, HOY, "0.8", llave="abc123")
    assert any("MAP_KEY" in e and "avance/activos.json" in e for e in errores)


def test_falta_un_archivo(tmp_path):
    p = _public(tmp_path)
    (p / "comunas.json").unlink()
    assert "falta comunas.json" in controles_publicacion(p, HOY, "0.8")[0]


def test_clima_muy_atrasado_es_aviso_no_error(tmp_path):
    errores, avisos = controles_publicacion(_public(tmp_path, clima="2026-11-01"), HOY, "0.8")
    assert errores == [] and any("NASA POWER" in a for a in avisos)
