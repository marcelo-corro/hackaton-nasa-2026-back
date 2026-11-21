"""Paso 4 del pipeline: marca la calidad de cada foco (no borra ninguno) y genera el reporte de calidad.

Entrada:  data/interim/focos_comuna.parquet (paso 3)
          ref/fuentes_persistentes.csv         máscara de fuentes fijas que FIRMS no marca (paso 4b, versionada)
Salidas:  data/interim/focos_calidad.parquet  focos con fecha local y marcas de calidad (ver firecal.calidad)
          docs/calidad_datos.md                reporte con las cifras que justifican las marcas

Uso:
    python scripts/04_marcar_calidad.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from firecal import config  # noqa: E402
from firecal.calidad import MARCAS, marcar_calidad, reporte_calidad  # noqa: E402
from firecal.fuentes_persistentes import RUTA_MASCARA, leer_mascara  # noqa: E402


def main() -> int:
    focos = pd.read_parquet(config.INTERIM_DIR / "focos_comuna.parquet")
    mascara = leer_mascara()
    if mascara is None:
        print(f"AVISO: no está {RUTA_MASCARA}; no se marcan fuentes persistentes (correr el paso 4b)")
    else:
        print(f"Máscara de fuentes persistentes: {len(mascara)} celdas ({RUTA_MASCARA.name})")
    marcados = marcar_calidad(focos, mascara)

    print("Marcas de calidad (% de focos):")
    print((marcados[MARCAS].mean() * 100).round(1).to_string())
    print(f"\nFocos para el conteo base (vegetación + confianza nominal/alta, sin fuentes persistentes): "
          f"{int(marcados['uso_base'].sum()):,}")

    salida = config.INTERIM_DIR / "focos_calidad.parquet"
    marcados.to_parquet(salida, index=False)
    print(f"Guardado: {salida}")

    reporte = config.RAIZ / "docs" / "calidad_datos.md"
    reporte.write_text(reporte_calidad(marcados), encoding="utf-8")
    print(f"Reporte: {reporte}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
