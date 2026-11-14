import re

from firecal.export.indice import RUTAS, index_html, modelo_usa_clima

MANIFEST = {
    "contrato": "0.2", "ejemplo": False, "generado_utc": "2026-11-14T19:20:13Z",
    "periodo": {"desde": "2000-11", "hasta": "2025-12"}, "regiones": ["05101", "05109"],
}
RIESGO = {"valido_para": "2026-01-01", "horizonte_horas": 24, "modelo": "hgb_firms_v1", "items": [{"region_id": "05101"}]}
NOTA = "Probado en 2022-2025. Para incendios nuevos sus alertas acertaron 14 % & la mayoría empezó sin alerta."
METRICAS = {"modelo": "hgb_firms_v1", "auc": 0.827, "periodo_prueba": "2022-2025", "nota": NOTA}
RIESGO_CLIMA = {**RIESGO, "modelo": "hgb_firms_clima_v1"}
METRICAS_CLIMA = {**METRICAS, "modelo": "hgb_firms_clima_v1"}


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


def test_siempre_incluye_las_citas_de_firms_y_bcn():
    for riesgo, metricas in ((RIESGO, METRICAS), (RIESGO_CLIMA, METRICAS_CLIMA), ({"items": []}, {"auc": None})):
        html = index_html(MANIFEST, riesgo, metricas)
        assert "Fire Information for Resource Management System" in html  # FIRMS
        assert "10.1016/j.rse.2016.02.054" in html and "10.1016/j.rse.2013.12.008" in html
        assert "Biblioteca del Congreso Nacional" in html and "bcn.cl/siit/mapas_vectoriales" in html  # BCN


def test_cita_de_nasa_power_solo_si_el_modelo_usa_clima():
    sin_clima = index_html(MANIFEST, RIESGO, METRICAS)  # hgb_firms_v1
    assert "POWER" not in sin_clima and "power.larc.nasa.gov" not in sin_clima

    con_clima = index_html(MANIFEST, RIESGO_CLIMA, METRICAS_CLIMA)  # hgb_firms_clima_v1
    assert "Prediction Of Worldwide Energy Resources (POWER)" in con_clima and "power.larc.nasa.gov" in con_clima


def test_sin_modelo_publicado_no_cita_power():
    assert "POWER" not in index_html(MANIFEST, {"items": []}, {"auc": None})


def test_modelo_usa_clima_mira_los_componentes_del_nombre():
    assert modelo_usa_clima(RIESGO_CLIMA, None) and modelo_usa_clima(None, METRICAS_CLIMA)
    assert not modelo_usa_clima(RIESGO, METRICAS) and not modelo_usa_clima(None, None)
    assert not modelo_usa_clima({"modelo": "hgb_firms_climatologia_v1"}, None)  # "clima" como parte de otra palabra


def test_limites_usa_la_nota_de_metricas_y_no_un_texto_fijo():
    html = index_html(MANIFEST, RIESGO, METRICAS)
    assert "Probado en 2022-2025. Para incendios nuevos sus alertas acertaron 14 % &amp; la mayoría" in html  # escapado
    assert "anticipa bien cómo se propaga" not in html  # el texto fijo anterior ya no está
    otra = index_html(MANIFEST, RIESGO, {**METRICAS, "nota": "Otra nota distinta."})
    assert "Otra nota distinta." in otra and "Probado en 2022-2025" not in otra


def test_sin_nota_no_hay_bullet_de_modelo():
    html = index_html(MANIFEST, RIESGO, {**METRICAS, "nota": None})
    assert "<li></li>" not in html and "Probado en" not in html


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


def test_sin_metricas_dice_modelo_en_validacion():
    for metricas in (None, {}, {"auc": None}, {"auc": None, "nota": "Pendiente: todavía no hay modelo validado."}):
        html = index_html(MANIFEST, {"items": []}, metricas)
        assert "Modelo en validación" in html, metricas
        assert "Pendiente: todavía no hay modelo validado." not in html  # se reemplaza, no se repite


def test_con_metricas_no_aparece_modelo_en_validacion():
    html = index_html(MANIFEST, RIESGO, METRICAS)
    assert "Modelo en validación" not in html and "Probado en 2022-2025" in html


def test_la_cita_de_power_trae_la_version_y_la_fecha_de_acceso():
    html = index_html(MANIFEST, RIESGO_CLIMA, METRICAS_CLIMA)
    assert "Daily 2.10.3 version on 2026/11/14" in html


def test_con_el_modelo_publicado_hoy_la_portada_cita_power_y_muestra_su_nota():
    riesgo = {**RIESGO, "modelo": "hgb_firms_clima_v1"}
    metricas = {"modelo": "hgb_firms_clima_v1", "auc": 0.837, "periodo_prueba": "2022-2025", "nota": "Nota <real> & prueba."}
    html = index_html(MANIFEST, riesgo, metricas)
    assert "Prediction Of Worldwide Energy Resources (POWER)" in html
    assert "Nota &lt;real&gt; &amp; prueba." in html and "AUC 0.837" in html
