import numpy as np
import pandas as pd
from pyproj import Transformer

from firecal import fuentes_persistentes as fp
from firecal.calidad import marcar_calidad

_A_GEO = Transformer.from_crs(fp.CRS_METRICO, "EPSG:4326", always_xy=True)


def _punto(x: float, y: float) -> tuple[float, float]:
    """(lon, lat) de un punto en metros UTM 19S."""
    lon, lat = _A_GEO.transform(x, y)
    return float(lon), float(lat)


def _focos_celda(x: float, y: float, fechas: list[str], noche: bool, evento0: int, mismo_evento: bool = False,
                 dx_m: float = 0.0) -> pd.DataFrame:
    """Un foco por fecha en la celda que contiene (x, y); cada uno su propio incendio salvo `mismo_evento`."""
    filas = []
    for i, d in enumerate(fechas):
        lon, lat = _punto(x + (dx_m * i if mismo_evento else 0.0), y)
        filas.append({"lat": lat, "lon": lon, "fecha_local": pd.Timestamp(d), "dia_noche": "N" if noche else "D",
                      "region_id": "05101", "evento": evento0 if mismo_evento else evento0 + i})
    return pd.DataFrame(filas)


# 12 días en 6 años distintos
FECHAS = [f"{a}-0{m}-10" for a in range(2014, 2020) for m in (1, 2)]


def test_metricas_y_clasificacion() -> None:
    nocturna = _focos_celda(300_500, 6_340_500, FECHAS, noche=True, evento0=0)
    desierto = _focos_celda(302_500, 6_340_500, FECHAS, noche=False, evento0=100)
    campo = _focos_celda(304_500, 6_340_500, FECHAS, noche=False, evento0=200)
    pocas = _focos_celda(306_500, 6_340_500, FECHAS[:8], noche=True, evento0=300)
    # De noche y repetida, pero sus focos son parte de un incendio que llega a 5,5 km de la celda: no es fija
    incendio = _focos_celda(310_500, 6_340_500, FECHAS, noche=True, evento0=400, mismo_evento=True)
    avance = _focos_celda(313_500, 6_340_500, ["2019-02-11"], noche=True, evento0=400, mismo_evento=True, dx_m=0)
    lejos = _focos_celda(316_000, 6_340_500, ["2019-02-12"], noche=True, evento0=400, mismo_evento=True, dx_m=0)
    focos = pd.concat([nocturna, desierto, campo, pocas, incendio, avance, lejos], ignore_index=True)

    c = fp.metricas_celdas(focos, 0)
    assert set(zip(c["cx"], c["cy"])) == {(300, 6340), (302, 6340), (304, 6340), (310, 6340)}  # "pocas" no repite
    c = c.set_index("cx")
    assert c.loc[300, "dias"] == 12 and c.loc[300, "anios"] == 6 and c.loc[300, "frac_noche"] == 1.0
    assert c.loc[310, "mayor_incendio"] == 14 and c.loc[310, "mayor_extension_km"] >= 5

    c["frac_vegetacion"] = pd.Series({300: 0.8, 302: 0.02, 304: 0.9, 310: 0.9})
    k = fp.clasificar(c.reset_index()).set_index("cx")
    assert k.loc[300, "motivo"] == "nocturna_fija"
    assert k.loc[302, "motivo"] == "sin_vegetacion"
    assert not k.loc[304, "persistente"]
    assert not k.loc[310, "persistente"]


def test_sin_dato_de_vegetacion_no_marca_por_esa_via() -> None:
    c = pd.DataFrame({"frac_vegetacion": [np.nan], "frac_noche": [0.0], "mayor_incendio": [1],
                      "mayor_extension_km": [0.0]})
    assert not fp.clasificar(c).loc[0, "persistente"]


def test_marca_focos_en_cualquiera_de_las_dos_grillas() -> None:
    mascara = pd.DataFrame({"desfase_m": [0, 500], "cx": [300, 303], "cy": [6340, 6341]})
    puntos = [_punto(300_200, 6_340_200),  # celda (300, 6340) de la grilla sin desfase
              _punto(302_600, 6_340_600),  # (302, 6340) sin desfase; (303, 6341) en la corrida 500 m
              _punto(305_000, 6_345_000)]  # fuera de la máscara
    focos = pd.DataFrame({"lon": [p[0] for p in puntos], "lat": [p[1] for p in puntos]})
    assert fp.en_fuente_persistente(focos, mascara).tolist() == [True, True, False]
    assert not fp.en_fuente_persistente(focos, None).any()


def test_calidad_saca_las_fuentes_persistentes_de_uso_base() -> None:
    lon, lat = _punto(300_200, 6_340_200)
    focos = pd.DataFrame({
        "fecha": pd.to_datetime(["2024-01-15"] * 3),
        "hora_utc": pd.Series(["0200"] * 3, dtype="string"),
        "lat": [lat, lat, -33.0], "lon": [lon, lon, -71.5],
        "sensor": ["VIIRS"] * 3, "satelite": ["SNPP"] * 3,
        "confianza": pd.Series(["alta"] * 3, dtype="string"),
        "area_pixel_km2": [0.14] * 3, "frp": [5.0] * 3,
        "dia_noche": pd.Series(["N"] * 3, dtype="string"),
        "tipo": pd.Series([0, 2, 0], dtype="Int8"),  # el segundo ya lo marca FIRMS como fuente fija
        "version": pd.Series(["2"] * 3, dtype="string"),
    })
    mascara = pd.DataFrame({"desfase_m": [0], "cx": [300], "cy": [6340]})
    m = marcar_calidad(focos, mascara)
    assert m["fuente_persistente"].tolist() == [True, False, False]  # solo marca lo que FIRMS dejó como vegetación
    assert m["uso_base"].tolist() == [False, False, True]
    assert marcar_calidad(focos)["uso_base"].tolist() == [True, False, True]  # sin máscara, como antes


def test_mascara_versionada_bien_formada() -> None:
    m = fp.leer_mascara()
    assert m is not None, "falta ref/fuentes_persistentes.csv (correr scripts/04b_fuentes_persistentes.py)"
    assert list(m.columns) == fp.COLUMNAS_MASCARA
    assert set(m["desfase_m"]) <= set(fp.DESFASES_M)
    assert not m.duplicated(["desfase_m", "cx", "cy"]).any()
    assert ((m["dias"] >= fp.MIN_DIAS) & (m["anios"] >= fp.MIN_ANIOS)).all()
    assert m["motivo"].isin(["sin_vegetacion", "nocturna_fija", "sin_vegetacion+nocturna_fija"]).all()
    assert m["region_id"].str.fullmatch(r"\d{5}").all()
