"""Paso 1 del pipeline: une los CSV anuales de FIRMS en data/interim/focos.parquet.

Uso:
    python scripts/01_ingestar_firms.py
La carpeta de entrada se toma de FIRMS_RAW_DIR en .env.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from firecal import config  # noqa: E402
from firecal.ingest.firms import cargar_directorio  # noqa: E402


def main() -> int:
    print(f"Leyendo FIRMS desde: {config.FIRMS_RAW_DIR}")
    focos, omitidos = cargar_directorio(config.FIRMS_RAW_DIR)

    if omitidos:
        print(f"Omitidos ({len(omitidos)}, vacíos o sin datos): {', '.join(omitidos)}")
    if focos.empty:
        print("No se encontraron focos.")
        return 1

    resumen = (
        focos.groupby(["sensor", "satelite"])
        .agg(focos=("lat", "size"), desde=("fecha", "min"), hasta=("fecha", "max"))
        .reset_index()
    )
    print(resumen.to_string(index=False))
    print("\nFocos por tipo (0 = vegetación):")
    print(focos.groupby(["sensor", "tipo"]).size().unstack(fill_value=0).to_string())

    config.INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    salida = config.INTERIM_DIR / "focos.parquet"
    focos.to_parquet(salida, index=False)
    print(f"\nGuardado: {salida} ({len(focos):,} filas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
