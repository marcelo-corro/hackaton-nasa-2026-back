"""Paso 12 (sectores, piloto A+): qué hay en cada sector de 1 km de las comunas de una región.

Entradas: data/interim/comunas.parquet, data/interim/focos_calidad.parquet y las capas de data/raw/sectores/
(paso 11). Salidas (no se versionan):
- data/processed/sectores_<región>.parquet: un sector por fila, con geometría (CRS métrico), historial de focos,
  marca de fuente persistente, vegetación, interfaz con viviendas y pendiente.
- data/processed/sectores_<región>_focos.parquet: los focos de incendio (sin fuentes persistentes) con su sector,
  para el heatmap del front.

Todo es descriptivo: el sector no tiene probabilidad propia (ver docs/sectores.md).

Uso:
    python scripts/12_sectores.py              # región 05 (Valparaíso)
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from firecal import config  # noqa: E402
from firecal.sectores.capas import (  # noqa: E402
    CLASES_WORLDCOVER, CLASES_WUI, MAX_SIN_DATO_WUI, resumen_categorico, resumen_pendiente,
)
from firecal.model.variables import completar_con_noaa20  # noqa: E402
from firecal.sectores.caminos import distancia_urbano, leer_caminos, variables_caminos  # noqa: E402
from firecal.sectores.grilla import grilla_sectores  # noqa: E402
from firecal.sectores.historial import (  # noqa: E402
    asignar_sector, focos_con_evento, fuentes_persistentes, historial_por_sector,
)
from firecal.sectores.region import comunas_region  # noqa: E402

CAPAS = RAIZ / "data" / "raw" / "sectores"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="05")
    args = parser.parse_args()
    t0 = time.time()

    comunas = comunas_region(args.region)
    sectores = grilla_sectores(comunas)
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

    print("Vegetación (WorldCover)...", flush=True)
    veg = resumen_categorico(sorted((CAPAS / "worldcover").glob("*.tif")), sectores, CLASES_WORLDCOVER)
    print("Interfaz con viviendas (WUI)...", flush=True)
    wui = resumen_categorico(sorted((CAPAS / "wui").rglob("WUI.tif")), sectores, CLASES_WUI)
    print("Pendiente (Copernicus DEM)...", flush=True)
    pend = resumen_pendiente(sorted((CAPAS / "copernicus_dem").glob("*.tif")), sectores)

    tabla = (sectores.merge(historial, on="sector_id").merge(veg, on="sector_id").merge(wui, on="sector_id")
             .merge(pend, on="sector_id"))
    tabla["frac_combustible"] = tabla[["frac_arboles", "frac_matorral", "frac_pastizal"]].sum(axis=1)
    tabla["dist_urbano_km"] = distancia_urbano(tabla).to_numpy()
    ruta_caminos = CAPAS / "osm" / f"caminos_{args.region}.json"
    if ruta_caminos.exists():  # opcional: lo baja `11_descargar_capas.py --solo caminos` (modelo B)
        print("Caminos (OpenStreetMap)...", flush=True)
        tabla = tabla.merge(variables_caminos(tabla, leer_caminos(ruta_caminos)), on="sector_id")
    # WUI: fracciones sobre la parte del sector con dato; vacías si falta más de la mitad
    con_dato = 1 - tabla["frac_wui_sin_dato"]
    for c in ["frac_wui_bosque", "frac_wui_pastizal", "frac_no_wui"]:
        tabla[c] = (tabla[c] / con_dato).where(tabla["frac_wui_sin_dato"] <= MAX_SIN_DATO_WUI)
    tabla["frac_wui"] = tabla["frac_wui_bosque"] + tabla["frac_wui_pastizal"]
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
