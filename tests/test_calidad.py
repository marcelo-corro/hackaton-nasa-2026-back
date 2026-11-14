import pandas as pd

from firecal.calidad import marcar_calidad, reporte_calidad


def _focos() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fecha": pd.to_datetime(["2024-01-15", "2024-07-15", "2024-01-15", "2024-01-15"]),
            "hora_utc": pd.Series(["0200", "0200", "1800", "0200"], dtype="string"),
            "lat": [-33.0, -33.0, -27.1, -33.0],
            "lon": [-71.5, -71.5, -109.4, -71.5],  # el tercero es Isla de Pascua
            "sensor": ["VIIRS", "VIIRS", "MODIS", "MODIS"],
            "satelite": ["SNPP", "SNPP", "Terra", "Aqua"],
            "confianza": pd.Series(["alta", "baja", "nominal", "alta"], dtype="string"),
            "area_pixel_km2": [0.14, 0.50, 1.2, 3.0],
            "frp": [5.0, 0.0, 10.0, 8.0],
            "dia_noche": pd.Series(["N", "N", "D", "N"], dtype="string"),
            "tipo": pd.Series([0, 0, 2, 0], dtype="Int8"),
            "version": pd.Series(["2", "2", "61.03", "61.03"], dtype="string"),
        }
    )


def test_fecha_local_con_horario_de_verano_e_isla_de_pascua() -> None:
    m = marcar_calidad(_focos())

    # 02:00 UTC del 15-ene es 23:00 del 14-ene en verano (UTC-3); en julio es 22:00 del 14-jul (UTC-4).
    assert m.loc[0, "fecha_local"] == pd.Timestamp("2024-01-14")
    assert m.loc[0, "fecha_hora_local"].hour == 23
    assert m.loc[1, "fecha_hora_local"].hour == 22
    assert m.loc[2, "zona_horaria"] == "Pacific/Easter"
    assert m.loc[2, "fecha_hora_local"].hour == 13  # 18:00 UTC = 13:00 en Isla de Pascua (UTC-5 en verano)


def test_marcas() -> None:
    m = marcar_calidad(_focos())

    assert m["es_vegetacion"].tolist() == [True, True, False, True]
    assert m["confianza_ok"].tolist() == [True, False, True, True]
    assert m["frp_valido"].tolist() == [True, False, True, True]
    assert m["pixel_grande"].tolist() == [False, True, False, True]  # VIIRS > 0,28 km², MODIS > 2 km²
    assert m["uso_base"].tolist() == [True, False, False, True]
    assert len(m) == 4  # no borra filas


def test_reporte_se_genera() -> None:
    texto = reporte_calidad(marcar_calidad(_focos()))

    assert "# Reporte de calidad" in texto
    assert "Duplicados exactos" in texto
