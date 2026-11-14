"""Paso 9 del pipeline (B): exporta al contrato del front (carpeta public/).

Entradas: data/processed/calendario.parquet, data/interim/comunas.parquet, data/interim/focos_calidad.parquet
          y, si existen, data/processed/riesgo.parquet y data/processed/metricas.json (de A)
Salida:   PUBLIC_DIR (por defecto ./public) con la forma de contracts/README.md

Uso:
    python scripts/09_exportar.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402

from firecal import config  # noqa: E402
from firecal.contratos import validar_calendario, validar_riesgo  # noqa: E402
from firecal.export.contrato import COLUMNAS_FOCOS_CSV, LIMITE_GEOJSON_MB, exportar  # noqa: E402


def main() -> int:
    calendario = pd.read_parquet(config.PROCESSED_DIR / "calendario.parquet")
    validar_calendario(calendario)
    comunas = gpd.read_parquet(config.INTERIM_DIR / "comunas.parquet")
    focos = pd.read_parquet(
        config.INTERIM_DIR / "focos_calidad.parquet", columns=["region_id", "es_vegetacion", *COLUMNAS_FOCOS_CSV]
    )

    riesgo = None
    ruta_riesgo = config.PROCESSED_DIR / "riesgo.parquet"
    if ruta_riesgo.exists():
        riesgo = pd.read_parquet(ruta_riesgo)
        validar_riesgo(riesgo)
    else:
        print("Aviso: no hay riesgo.parquet (A3 pendiente); riesgo/ultimo.json irá con items vacío.")

    datos_metricas = None
    ruta_metricas = config.PROCESSED_DIR / "metricas.json"
    if ruta_metricas.exists():
        datos_metricas = json.loads(ruta_metricas.read_text(encoding="utf-8"))
    else:
        print("Aviso: no hay metricas.json (A3 pendiente); las métricas irán en null.")

    resumen = exportar(calendario, comunas, focos, config.PUBLIC_DIR, riesgo=riesgo, datos_metricas=datos_metricas)

    print(f"\nExportado a {config.PUBLIC_DIR}")
    print(f"  {resumen['archivos']:,} archivos, {resumen['tamano_mb']:.1f} MB en total, {resumen['comunas']} comunas")
    print(f"  regiones.geojson: {resumen['geojson_mb']:.2f} MB (meta: < {LIMITE_GEOJSON_MB:.0f} MB)")
    if resumen["geojson_mb"] > LIMITE_GEOJSON_MB:
        print("  ATENCIÓN: el GeoJSON supera la meta; subir la tolerancia de simplificación.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
