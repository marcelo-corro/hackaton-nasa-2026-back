"""Paso 12 (sectores, piloto A+): qué hay en cada sector de 1 km de las comunas de una región.

Entradas: data/interim/comunas.parquet, data/interim/focos_calidad.parquet y, solo cuando hay que calcular los
atributos fijos, las capas de data/raw/sectores/ (paso 11). Salidas (no se versionan):
- data/processed/sectores_<región>_fijo.parquet (+ .json con su huella): grilla y resumen de las capas. No cambian a
  diario: se calculan si faltan, si cambió su huella (límites de las comunas o versión del cálculo) o con
  --rehacer-fijo (la carga completa lo pasa al volver a bajar las capas). Ver firecal.sectores.fijo.
- data/processed/sectores_<región>.parquet: un sector por fila, con geometría (CRS métrico), historial de focos,
  marca de fuente persistente, vegetación, interfaz con viviendas y pendiente.
- data/processed/sectores_<región>_focos.parquet: los focos de incendio (sin fuentes persistentes) con su sector,
  para el heatmap del front.

Todo es descriptivo: el sector no tiene probabilidad propia (ver docs/sectores.md).

Uso:
    python scripts/12_sectores.py                    # región 05 (Valparaíso)
    python scripts/12_sectores.py --rehacer-fijo     # recalcula también los atributos fijos (necesita las capas)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from firecal import config  # noqa: E402
from firecal.model.variables import completar_con_noaa20  # noqa: E402
from firecal.sectores.fijo import (  # noqa: E402
    COLUMNAS_GRILLA, calcular_fijo, guardar_fijo, huella_fijo, leer_fijo,
)
from firecal.sectores.historial import (  # noqa: E402
    asignar_sector, focos_con_evento, fuentes_persistentes, historial_por_sector,
)
from firecal.sectores.region import comunas_region  # noqa: E402

CAPAS = RAIZ / "data" / "raw" / "sectores"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="05")
    parser.add_argument("--rehacer-fijo", action="store_true", help="recalcula la grilla y el resumen de las capas")
    args = parser.parse_args()
    t0 = time.time()

    comunas = comunas_region(args.region)
    huella = huella_fijo(comunas)
    fijo = None if args.rehacer_fijo else leer_fijo(args.region, huella)
    if fijo is None:
        print(f"Atributos fijos de la región {args.region}: se calculan "
              f"({'pedido con --rehacer-fijo' if args.rehacer_fijo else 'faltan o cambió su huella'})", flush=True)
        fijo = calcular_fijo(comunas, CAPAS, args.region, avisar=lambda t: print(t, flush=True))
        guardar_fijo(fijo, args.region, huella)
    else:
        print(f"Atributos fijos de la región {args.region}: sin cambios (huella {huella[:12]}), se leen del archivo")
    sectores = fijo[COLUMNAS_GRILLA]
    print(f"Región {args.region}: {len(comunas)} comunas, {len(sectores):,} sectores de 1 km ({time.time() - t0:.0f} s)")

    focos = pd.read_parquet(config.INTERIM_DIR / "focos_calidad.parquet",
                            columns=["lat", "lon", "fecha_local", "satelite", "uso_base", "frp", "region_id",
                                     "dia_noche"])
    focos, ultimo_snpp = completar_con_noaa20(focos)  # sin Suomi NPP, NOAA-20 en su lugar (ver firecal.model)
    print(f"Suomi NPP hasta {ultimo_snpp.date()}; focos hasta {focos['fecha_local'].max().date()}")
    focos_sector = asignar_sector(focos_con_evento(focos), sectores)
    persistentes = fuentes_persistentes(focos_sector)
    es_persistente = focos_sector["sector_id"].isin(set(persistentes["sector_id"]))
    print(f"Focos en sectores: {len(focos_sector):,}; fuentes persistentes probables: {len(persistentes)} sectores, "
          f"{es_persistente.sum():,} detecciones excluidas del historial")
    incendios = focos_sector[~es_persistente]
    historial = historial_por_sector(incendios, sectores)
    historial["fuente_persistente"] = historial["sector_id"].isin(set(persistentes["sector_id"]))
    historial = historial.merge(persistentes[["sector_id", "dias"]].rename(columns={"dias": "dias_persistente"}),
                                on="sector_id", how="left")
    historial["dias_persistente"] = historial["dias_persistente"].fillna(0).astype(int)

    # Mismo orden de columnas de siempre: grilla, historial y después lo fijo
    capas = fijo.drop(columns=[c for c in COLUMNAS_GRILLA if c != "sector_id"])
    tabla = gpd.GeoDataFrame(sectores.merge(historial, on="sector_id").merge(capas, on="sector_id"),
                             geometry="geometry", crs=fijo.crs)
    nombres = dict(zip(comunas["region_id"], comunas["nombre"]))
    tabla.insert(2, "comuna", tabla["region_id"].map(nombres))

    salida = config.PROCESSED_DIR / f"sectores_{args.region}.parquet"
    tabla.to_parquet(salida)
    incendios.drop(columns=["uso_base", "satelite"]).to_parquet(
        config.PROCESSED_DIR / f"sectores_{args.region}_focos.parquet", index=False)

    sin_dato = {c: int(tabla[c].isna().sum()) for c in ["frac_arboles", "frac_wui", "pendiente_media"]}
    print(f"\n{salida.name}: {len(tabla):,} sectores | sin dato: {sin_dato} | {time.time() - t0:.0f} s")
    resumen = tabla[["frac_combustible", "frac_pastizal", "frac_construido", "frac_wui", "pendiente_media",
                     "dias_con_fuego"]].describe().round(3)
    print(resumen.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
