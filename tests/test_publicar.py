import json

import pytest

from firecal.export.publicar import PublicacionError, sincronizar, verificar_destino, verificar_origen


def _public(tmp_path, ejemplo=False, comunas=("05101", "05109"), faltan_focos=0, con_index=True):
    carpeta = tmp_path / "public"
    (carpeta / "calendario").mkdir(parents=True)
    (carpeta / "focos").mkdir()
    for c in comunas:
        (carpeta / "calendario" / f"{c}.json").write_text("{}", encoding="utf-8")
    for c in comunas[: len(comunas) - faltan_focos]:
        (carpeta / "focos" / f"{c}.csv").write_text("fecha\n", encoding="utf-8")
    (carpeta / "manifest.json").write_text(
        json.dumps({"ejemplo": ejemplo, "regiones": list(comunas), "generado_utc": "2026-11-15T03:00:00Z"}),
        encoding="utf-8",
    )
    (carpeta / "regiones.geojson").write_text("{}", encoding="utf-8")
    if con_index:
        (carpeta / "index.html").write_text("<html>nuevo</html>", encoding="utf-8")
    return carpeta


def _repo(tmp_path):
    repo = tmp_path / "datos"
    (repo / ".git").mkdir(parents=True)
    (repo / "README.md").write_text("readme del repo de datos", encoding="utf-8")
    (repo / "LICENSE").write_text("licencia de los datos", encoding="utf-8")
    (repo / ".nojekyll").write_text("", encoding="utf-8")
    (repo / "calendario").mkdir()
    (repo / "calendario" / "99999.json").write_text("viejo", encoding="utf-8")
    (repo / "viejo.json").write_text("viejo", encoding="utf-8")
    return repo


def test_acepta_datos_reales_completos(tmp_path):
    assert verificar_origen(_public(tmp_path))["generado_utc"] == "2026-11-15T03:00:00Z"


def test_rechaza_datos_de_ejemplo(tmp_path):
    with pytest.raises(PublicacionError, match="ejemplo"):
        verificar_origen(_public(tmp_path, ejemplo=True))


def test_rechaza_si_falta_el_manifest(tmp_path):
    with pytest.raises(PublicacionError, match="09_exportar"):
        verificar_origen(tmp_path / "no_existe")


def test_rechaza_si_faltan_archivos_de_alguna_comuna(tmp_path):
    with pytest.raises(PublicacionError, match="focos"):
        verificar_origen(_public(tmp_path, faltan_focos=1))


def test_no_vacia_una_carpeta_que_no_es_un_clon(tmp_path):
    carpeta = tmp_path / "cualquiera"
    carpeta.mkdir()
    (carpeta / "importante.txt").write_text("no borrar", encoding="utf-8")
    with pytest.raises(PublicacionError, match="no es un clon"):
        verificar_destino(carpeta)
    with pytest.raises(PublicacionError):
        sincronizar(_public(tmp_path), carpeta)
    assert (carpeta / "importante.txt").exists()


def test_sincroniza_reemplaza_lo_publicado_y_conserva_readme_licencia_nojekyll_y_git(tmp_path):
    publico, repo = _public(tmp_path), _repo(tmp_path)
    sincronizar(publico, repo)

    assert (repo / "README.md").read_text(encoding="utf-8") == "readme del repo de datos"
    assert (repo / "LICENSE").read_text(encoding="utf-8") == "licencia de los datos"
    assert (repo / ".nojekyll").exists() and (repo / ".git").is_dir()
    assert not (repo / "viejo.json").exists()
    assert not (repo / "calendario" / "99999.json").exists()
    assert sorted(p.name for p in (repo / "calendario").glob("*")) == ["05101.json", "05109.json"]
    assert (repo / "manifest.json").exists() and (repo / "regiones.geojson").exists()


def test_conserva_la_automatizacion_de_github(tmp_path):
    publico, repo = _public(tmp_path), _repo(tmp_path)
    flujo = repo / ".github" / "workflows" / "actualizar.yml"
    flujo.parent.mkdir(parents=True)
    flujo.write_text("name: diario", encoding="utf-8")
    sincronizar(publico, repo)
    assert flujo.read_text(encoding="utf-8") == "name: diario"


def test_crea_nojekyll_si_no_estaba(tmp_path):
    publico, repo = _public(tmp_path), _repo(tmp_path)
    (repo / ".nojekyll").unlink()
    sincronizar(publico, repo)
    assert (repo / ".nojekyll").exists()


def test_rechaza_si_falta_el_index_html(tmp_path):
    with pytest.raises(PublicacionError, match="index.html"):
        verificar_origen(_public(tmp_path, con_index=False))


def test_el_index_html_no_se_borra_al_publicar_y_reemplaza_al_anterior(tmp_path):
    publico, repo = _public(tmp_path), _repo(tmp_path)
    (repo / "index.html").write_text("<html>viejo</html>", encoding="utf-8")
    sincronizar(publico, repo)
    assert (repo / "index.html").read_text(encoding="utf-8") == "<html>nuevo</html>"
    sincronizar(publico, repo)  # una segunda publicación tampoco lo pierde
    assert (repo / "index.html").exists()
