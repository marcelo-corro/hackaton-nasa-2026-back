"""Comunas de una región para el piloto de sectores."""

from __future__ import annotations

import geopandas as gpd

from firecal import config

LON_INSULAR = -75.0  # al oeste de esto: Juan Fernández, Isla de Pascua (fuera del piloto continental)


def comunas_region(codigo: str, comunas: gpd.GeoDataFrame | None = None) -> gpd.GeoDataFrame:
    """Comunas continentales cuyo `region_id` empieza con `codigo` (2 dígitos), en EPSG:4326."""
    if comunas is None:
        comunas = gpd.read_parquet(config.INTERIM_DIR / "comunas.parquet")
    c = comunas[comunas["region_id"].astype(str).str.startswith(codigo)].to_crs("EPSG:4326")
    punto = c.geometry.representative_point()
    c = c[punto.x > LON_INSULAR].copy()
    if c.empty:
        raise ValueError(f"No hay comunas continentales para la región {codigo}")
    c["region_id"] = c["region_id"].astype(str)
    return c.sort_values("region_id").reset_index(drop=True)
