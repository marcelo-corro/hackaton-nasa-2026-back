"""Paso 5c: clima diario del año en curso (NASA POWER) y lo suma a data/interim/clima_diario.parquet.

Mismas variables y mismo punto por comuna que el paso 5b (2012-2025), a otra caché: data/raw/clima_power_<año>/.
NASA POWER publica con unos días de retraso: los días sin dato (-999) quedan fuera y se informa el último día completo
(el que sirve para el riesgo de mañana).

Uso:
    python scripts/05c_clima_reciente.py                          # 1 de enero del año en curso hasta hoy
    python scripts/05c_clima_reciente.py --desde 2026-01-01 --hasta 2026-11-15
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402

from firecal import config  # noqa: E402
from firecal.ingest.clima import (  # noqa: E402
    COLUMNAS, COLUMNAS_NUMERICAS, clima_diario, descargar_clima, puntos_representativos,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    hoy = datetime.now(timezone.utc).date()
    parser.add_argument("--desde", default=f"{hoy.year}-01-01")
    parser.add_argument("--hasta", default=hoy.isoformat())
    args = parser.parse_args()

    comunas = gpd.read_parquet(config.INTERIM_DIR / "comunas.parquet")
    puntos = puntos_representativos(comunas)
    cache = config.DATA_DIR / "raw" / f"clima_power_{args.desde[:4]}"
    nuevas = descargar_clima(puntos, cache, desde=args.desde, hasta=args.hasta)
    print(f"Comunas descargadas ahora: {nuevas} (caché {cache.name})")

    reciente = clima_diario(puntos, cache)
    completos = reciente.dropna(subset=COLUMNAS_NUMERICAS)
    por_dia = completos.groupby("fecha_local")["region_id"].nunique()
    dias_completos = por_dia[por_dia == len(puntos)].index
    ultimo = dias_completos.max() if len(dias_completos) else None
    reciente = completos[completos["fecha_local"].isin(dias_completos)]
    print(f"Clima {args.desde} a {args.hasta}: {len(dias_completos)} días completos; último día completo: "
          f"{None if ultimo is None else ultimo.date()}")

    ruta = config.INTERIM_DIR / "clima_diario.parquet"
    base = pd.read_parquet(ruta)
    base = base[base["fecha_local"] < pd.Timestamp(args.desde)]  # lo del año en curso se reemplaza entero
    clima = pd.concat([base, reciente[COLUMNAS]], ignore_index=True).sort_values(["region_id", "fecha_local"])
    clima["region_id"] = clima["region_id"].astype("string")
    clima.to_parquet(ruta, index=False)
    print(f"Guardado: {ruta} ({len(clima):,} filas, {clima['fecha_local'].min().date()} a "
          f"{clima['fecha_local'].max().date()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
