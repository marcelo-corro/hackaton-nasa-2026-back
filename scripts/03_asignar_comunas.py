"""Paso 3 del pipeline: asigna cada foco a su comuna.

Entradas:  data/interim/focos.parquet (paso 2) y el shapefile de comunas de la BCN (paso 1).
Salidas:   data/interim/comunas.parquet       comunas limpias en EPSG:4326 (se reutiliza en corridas siguientes)
           data/interim/focos_comuna.parquet  focos con region_id y asignacion

Uso:
    python scripts/03_asignar_comunas.py
    python scripts/03_asignar_comunas.py --rehacer-comunas      # vuelve a preparar el shapefile
    python scripts/03_asignar_comunas.py --tolerancia-m 0       # sin asignar focos costeros cercanos
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402

from firecal import config  # noqa: E402
from firecal.ingest.comunas import asignar_comunas, cargar_comunas  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rehacer-comunas", action="store_true", help="volver a preparar el shapefile de la BCN")
    parser.add_argument("--tolerancia-m", type=float, default=1000, help="distancia máxima para focos costeros")
    args = parser.parse_args()

    comunas_parquet = config.INTERIM_DIR / "comunas.parquet"
    if comunas_parquet.exists() and not args.rehacer_comunas:
        comunas = gpd.read_parquet(comunas_parquet)
        print(f"Comunas: {len(comunas)} (desde {comunas_parquet.name})")
    else:
        print(f"Preparando comunas desde {config.COMUNAS_SHP} (tarda ~1 min)...")
        comunas = cargar_comunas(config.COMUNAS_SHP)
        config.INTERIM_DIR.mkdir(parents=True, exist_ok=True)
        comunas.to_parquet(comunas_parquet, index=False)
        print(f"Comunas: {len(comunas)}, {comunas['area_km2'].sum():,.0f} km² -> {comunas_parquet}")

    focos = pd.read_parquet(config.INTERIM_DIR / "focos.parquet")
    focos = asignar_comunas(focos, comunas, tolerancia_m=args.tolerancia_m)

    resumen = (
        focos.assign(asignacion=focos["asignacion"].fillna("sin comuna"))
        .groupby(["tipo", "asignacion"], dropna=False)
        .size()
        .unstack(fill_value=0)
    )
    resumen["% asignado"] = (100 * (1 - resumen.get("sin comuna", 0) / resumen.sum(axis=1))).round(2)
    print("\nAsignación por tipo de foco (0 = vegetación):")
    print(resumen.to_string())

    vegetacion = focos[(focos["tipo"] == 0) & focos["region_id"].notna()]
    nombres = comunas.set_index("region_id")["nombre"]
    top = vegetacion.groupby(["region_id", "sensor"]).size().unstack(fill_value=0)
    top = top.assign(nombre=top.index.map(nombres)).sort_values("VIIRS", ascending=False).head(10)
    print("\nComunas con más focos de vegetación (todo el período):")
    print(top[["nombre", "MODIS", "VIIRS"]].to_string())

    salida = config.INTERIM_DIR / "focos_comuna.parquet"
    focos.to_parquet(salida, index=False)
    print(f"\nGuardado: {salida} ({len(focos):,} focos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
