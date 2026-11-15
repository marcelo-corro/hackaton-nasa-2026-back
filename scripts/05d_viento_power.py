"""Paso 5d: dirección y velocidad diaria del viento por comuna (NASA POWER), para el cono de avance (paso 14).

Variables de POWER: WD10M (dirección media diaria del viento a 10 m, en grados, de DÓNDE viene: 0 = norte, 90 = este)
y WS10M (velocidad media diaria a 10 m, m/s). Mismo punto por comuna que el paso 5b. Caché en data/raw/viento_power/.

Salida: data/interim/viento_diario.parquet (region_id, fecha_local, viento_dir, viento_vel).

Uso:
    python scripts/05d_viento_power.py --hasta 2026-11-15
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import geopandas as gpd  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from firecal import config  # noqa: E402
from firecal.ingest.clima import FECHA_DESDE, VALOR_FALTANTE, descargar_clima, puntos_representativos  # noqa: E402

VARIABLES = ["WD10M", "WS10M"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--desde", default=FECHA_DESDE)
    parser.add_argument("--hasta", default=datetime.now(timezone.utc).date().isoformat())
    args = parser.parse_args()
    puntos = puntos_representativos(gpd.read_parquet(config.INTERIM_DIR / "comunas.parquet"))
    cache = config.DATA_DIR / "raw" / "viento_power"
    nuevas = descargar_clima(puntos, cache, desde=args.desde, hasta=args.hasta, variables=VARIABLES)
    print(f"Comunas descargadas ahora: {nuevas}")
    partes = []
    for rid in puntos["region_id"]:
        p = json.loads((cache / f"{rid}.json").read_text(encoding="utf-8"))["parameter"]
        fechas = sorted(p["WD10M"])
        d = pd.DataFrame({"region_id": rid, "fecha_local": pd.to_datetime(fechas, format="%Y%m%d"),
                          "viento_dir": pd.Series(p["WD10M"]).reindex(fechas).astype(float).to_numpy(),
                          "viento_vel": pd.Series(p["WS10M"]).reindex(fechas).astype(float).to_numpy()})
        partes.append(d.replace(VALOR_FALTANTE, np.nan).dropna())
    v = pd.concat(partes, ignore_index=True)
    v["region_id"] = v["region_id"].astype("string")
    ruta = config.INTERIM_DIR / "viento_diario.parquet"
    v.to_parquet(ruta, index=False)
    print(f"Guardado: {ruta} ({len(v):,} filas, {v['fecha_local'].min().date()} a {v['fecha_local'].max().date()})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
