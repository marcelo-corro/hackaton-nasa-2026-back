from pathlib import Path

from firecal.ingest.firms import COLUMNAS, cargar_directorio

MODIS = (
    "latitude,longitude,brightness,scan,track,acq_date,acq_time,satellite,instrument,confidence,"
    "version,bright_t31,frp,daynight,type\n"
    "-33.05,-71.55,330.1,1.0,1.0,2024-02-02,0315,Terra,MODIS,85,61.03,290.0,40.5,N,0\n"
    "-33.06,-71.56,310.0,1.0,1.0,2024-02-01,1500,Aqua,MODIS,20,61.03,290.0,5.0,D,0\n"
)
VIIRS = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,confidence,"
    "version,bright_ti5,frp,daynight,type\n"
    "-33.05,-71.55,340.2,0.4,0.4,2024-02-02,0600,N,VIIRS,h,2,290.0,12.3,N,0\n"
)
ERROR_404 = '{"detail":"The file cannot be found","status":404,"title":"File Not Found"}'


def _escribir(directorio: Path) -> None:
    (directorio / "modis_2024_Chile.csv").write_text(MODIS, encoding="utf-8")
    (directorio / "viirs-snpp_2024_Chile.csv").write_text(VIIRS, encoding="utf-8")
    (directorio / "viirs-noaa20_2024_Chile.csv").write_text(ERROR_404, encoding="utf-8")
    (directorio / "vacio.csv").write_text("", encoding="utf-8")


def test_une_modis_y_viirs_y_omite_404(tmp_path: Path) -> None:
    _escribir(tmp_path)
    focos, omitidos = cargar_directorio(tmp_path)

    assert list(focos.columns) == COLUMNAS
    assert len(focos) == 3
    assert sorted(omitidos) == ["vacio.csv", "viirs-noaa20_2024_Chile.csv"]
    assert focos["sensor"].value_counts().to_dict() == {"MODIS": 2, "VIIRS": 1}


def test_confianza_en_escala_comun(tmp_path: Path) -> None:
    _escribir(tmp_path)
    focos, _ = cargar_directorio(tmp_path)

    modis = focos[focos["sensor"] == "MODIS"].set_index("hora_utc")
    assert modis.loc["0315", "confianza"] == "alta"
    assert modis.loc["1500", "confianza"] == "baja"
    viirs = focos[focos["sensor"] == "VIIRS"].iloc[0]
    assert viirs["confianza"] == "alta"
    assert viirs["satelite"] == "SNPP"


def test_orden_por_fecha_y_hora(tmp_path: Path) -> None:
    _escribir(tmp_path)
    focos, _ = cargar_directorio(tmp_path)

    assert focos["fecha"].is_monotonic_increasing
    assert focos.iloc[0]["hora_utc"] == "1500"  # 2024-02-01 va antes que 2024-02-02
