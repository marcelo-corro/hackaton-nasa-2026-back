import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from firecal.sectores.capas import resumen_categorico
from firecal.sectores.grilla import CRS_METRICO, grilla_sectores
from firecal.sectores.historial import fuentes_persistentes, historial_por_sector


def _comuna_metrica(rid: str, x0: float, y0: float, ancho: float, alto: float) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({"region_id": [rid]}, geometry=[box(x0, y0, x0 + ancho, y0 + alto)], crs=CRS_METRICO)


def test_grilla_cubre_la_comuna_y_recorta_bordes() -> None:
    # 2,5 km × 1,5 km desde (500, 0): celdas de 1 km recortadas en los bordes
    c = _comuna_metrica("05101", 500, 0, 2500, 1500).to_crs("EPSG:4326")
    s = grilla_sectores(c)

    assert s["sector_id"].is_unique
    assert abs(s["area_km2"].sum() - 2.5 * 1.5) < 0.01
    assert s["area_km2"].max() <= 1.0 + 1e-6
    assert set(s["region_id"]) == {"05101"}
    assert s["sector_id"].str.startswith("05101_").all()


def test_grilla_descarta_astillas() -> None:
    # sobresale 10 m (1 % de una celda) hacia la celda vecina: esa astilla no es un sector
    c = _comuna_metrica("05101", 0, 0, 1010, 1000).to_crs("EPSG:4326")
    s = grilla_sectores(c)
    assert len(s) == 1


def _focos_sector(sector: str, fechas: list[str], noche: bool, focos_incendio: int = 1) -> pd.DataFrame:
    return pd.DataFrame({"sector_id": sector, "fecha_local": pd.to_datetime(fechas),
                         "dia_noche": "N" if noche else "D", "frp": 1.0, "focos_incendio": focos_incendio,
                         "evento": range(len(fechas))})


def test_fuente_persistente_vs_incendio() -> None:
    fechas = [f"{a}-{m:02d}-15" for a in range(2013, 2019) for m in (3, 7)]  # 12 días en 6 años
    industria = _focos_sector("A", fechas, noche=True)
    quema_diurna = _focos_sector("B", fechas, noche=False)
    incendio_grande = _focos_sector("C", fechas, noche=True, focos_incendio=40)
    pocos_dias = _focos_sector("D", fechas[:5], noche=True)
    p = fuentes_persistentes(pd.concat([industria, quema_diurna, incendio_grande, pocos_dias]))

    assert set(p["sector_id"]) == {"A"}


def test_historial_por_sector_incluye_sectores_sin_fuego() -> None:
    sectores = pd.DataFrame({"sector_id": ["A", "B"]})
    f = _focos_sector("A", ["2024-02-02", "2024-02-02", "2024-02-03"], noche=False, focos_incendio=50)
    f["evento"] = 7
    h = historial_por_sector(f, sectores).set_index("sector_id")

    assert h.loc["A", "dias_con_fuego"] == 2
    assert h.loc["A", "focos"] == 3
    assert h.loc["A", "incendios_grandes"] == 1
    assert h.loc["B", "dias_con_fuego"] == 0
    assert h.loc["B", "incendios_grandes"] == 0


def test_resumen_categorico_fracciones(tmp_path) -> None:
    # ráster de 2 km × 1 km en píxeles de 10 m: mitad izquierda clase 30 (pastizal), derecha clase 50 (construido)
    a = np.full((100, 200), 50, dtype=np.uint8)
    a[:, :100] = 30
    ruta = tmp_path / "wc.tif"
    with rasterio.open(ruta, "w", driver="GTiff", width=200, height=100, count=1, dtype="uint8", crs=CRS_METRICO,
                       transform=from_origin(0, 1000, 10, 10)) as dst:
        dst.write(a, 1)
    # los sectores particionan el territorio (no se traslapan), como los de grilla_sectores
    sectores = gpd.GeoDataFrame({"sector_id": ["izq", "centro", "der"]},
                                geometry=[box(0, 0, 500, 1000), box(500, 0, 1500, 1000), box(1500, 0, 2000, 1000)],
                                crs=CRS_METRICO)
    d = resumen_categorico([ruta], sectores, {30: "pastizal", 50: "construido"}).set_index("sector_id")

    assert d.loc["izq", "frac_pastizal"] == 1.0
    assert d.loc["der", "frac_construido"] == 1.0
    assert abs(d.loc["centro", "frac_pastizal"] - 0.5) < 1e-9
