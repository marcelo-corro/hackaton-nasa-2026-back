import re

from firecal.export.indice import RUTAS, index_html

MANIFEST = {
    "contrato": "0.2", "ejemplo": False, "generado_utc": "2026-11-14T19:20:13Z",
    "periodo": {"desde": "2000-11", "hasta": "2025-12"}, "regiones": ["05101", "05109"],
}
RIESGO = {"valido_para": "2026-01-01", "horizonte_horas": 24, "modelo": "hgb_firms_v1", "items": [{"region_id": "05101"}]}
METRICAS = {"auc": 0.827, "periodo_prueba": "2022-2025"}


def test_es_estatico_sin_javascript():
    html = index_html(MANIFEST, RIESGO, METRICAS)
    assert "<script" not in html.lower()
    assert not re.search(r"\son[a-z]+\s*=", html.lower())  # ni onclick, onload...
    assert 'href="http' in html and "src=" not in html  # sin recursos externos que cargar


def test_tiene_estructura_basica_y_utf8():
    html = index_html(MANIFEST, RIESGO, METRICAS)
    assert html.startswith("<!doctype html>") and '<html lang="es">' in html and '<meta charset="utf-8">' in html
    assert "viewport" in html and "<title>" in html and 'name="description"' in html
    assert "armonizados" in html and "calendario de actividad" in html and "riesgo de focos a 24 h" in html


def test_lista_todas_las_rutas_con_enlace():
    html = index_html(MANIFEST, RIESGO, METRICAS)
    for ruta, _ in RUTAS:
        assert ruta.replace("{region_id}", "05109") in html or ruta in html
    for ruta in ("manifest.json", "regiones.geojson", "riesgo/ultimo.json", "metricas.json"):
        assert f'href="{ruta}"' in html
    assert 'href="calendario/05109.json"' in html and 'href="focos/05109.csv"' in html


def test_incluye_las_tres_citas_obligatorias():
    html = index_html(MANIFEST, RIESGO, METRICAS)
    assert "Fire Information for Resource Management System" in html  # FIRMS
    assert "10.1016/j.rse.2016.02.054" in html and "10.1016/j.rse.2013.12.008" in html
    assert "Biblioteca del Congreso Nacional" in html and "bcn.cl/siit/mapas_vectoriales" in html  # BCN
    assert "Prediction Of Worldwide Energy Resources (POWER)" in html and "power.larc.nasa.gov" in html  # POWER


def test_muestra_el_estado_real_desde_el_manifest():
    html = index_html(MANIFEST, RIESGO, METRICAS)
    assert "2 comunas" in html and "2000-11" in html and "2025-12" in html
    assert "2026-11-14T19:20:13Z" in html
    assert "2026-01-01" in html and "hgb_firms_v1" in html and "0.827" in html


def test_sin_riesgo_ni_metricas_dice_pendiente():
    html = index_html(MANIFEST, {"items": []}, {"auc": None})
    assert "pendiente" in html.lower()
    assert "AUC" not in html


def test_escapa_el_contenido_dinamico():
    html = index_html({**MANIFEST, "generado_utc": "<b>x</b>"}, RIESGO, METRICAS)
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html
