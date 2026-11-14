import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, box

from firecal.ingest.comunas import asignar_comunas, preparar_comunas


def _bcn() -> gpd.GeoDataFrame:
    """Imita el shapefile de la BCN: una zona sin demarcar, una comuna válida y una con geometría inválida."""
    corbata = Polygon([(-71.75, -33.20), (-71.55, -33.00), (-71.55, -33.20), (-71.75, -33.00), (-71.75, -33.20)])
    return gpd.GeoDataFrame(
        {
            "cod_comuna": [0, 5109, 5101],
            "Comuna": ["Zona sin demarcar", "Viña del Mar", "Valparaíso"],
            "Provincia": ["Zona sin demarcar", "Valparaíso", "Valparaíso"],
            "Region": ["Zona sin demarcar", "Región de Valparaíso", "Región de Valparaíso"],
            "codregion": [0, 5, 5],
        },
        geometry=[box(-73.5, -49.5, -73.0, -49.0), box(-71.58, -33.08, -71.45, -32.95), corbata],
        crs="EPSG:4326",
    )


def test_preparar_excluye_zona_sin_demarcar_y_repara() -> None:
    comunas = preparar_comunas(_bcn())

    assert comunas["region_id"].tolist() == ["05101", "05109"]
    assert comunas.is_valid.all()
    assert (comunas["area_km2"] > 0).all()
    assert comunas.crs.to_epsg() == 4326


def _focos() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "lat": [-33.00, -33.10, -33.00, -33.00],
            "lon": [-71.50, -71.72, -71.445, -75.00],  # Viña, Valparaíso, ~470 m al este de Viña, mar abierto
        }
    )


def test_asignar_dentro_cercana_y_fuera() -> None:
    focos = asignar_comunas(_focos(), preparar_comunas(_bcn()), tolerancia_m=1000)

    assert focos["region_id"].tolist()[:3] == ["05109", "05101", "05109"]
    assert pd.isna(focos["region_id"].iloc[3])
    assert focos["asignacion"].tolist()[:3] == ["dentro", "dentro", "cercana"]


def test_sin_tolerancia_no_asigna_cercanos() -> None:
    focos = asignar_comunas(_focos(), preparar_comunas(_bcn()), tolerancia_m=0)

    assert pd.isna(focos["region_id"].iloc[2])
    assert focos["region_id"].notna().sum() == 2
