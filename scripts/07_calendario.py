"""Paso 7 del pipeline (B): calendario de actividad y anomalías por comuna.

Entrada: data/processed/serie_mensual.parquet (paso 5, de A)
Salida:  data/processed/calendario.parquet (contrato en contracts/interno.md)

Uso:
    python scripts/07_calendario.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd  # noqa: E402

from firecal import config  # noqa: E402
from firecal.anomalies.calendario import calcular_calendario  # noqa: E402
from firecal.contratos import validar_calendario, validar_serie_mensual  # noqa: E402


def main() -> int:
    serie = pd.read_parquet(config.PROCESSED_DIR / "serie_mensual.parquet")
    n_comunas = serie["region_id"].nunique()
    validar_serie_mensual(serie, n_comunas=n_comunas)
    print(f"Serie mensual: {len(serie):,} filas, {n_comunas} comunas, metodo={serie['metodo'].iloc[0]!r}")

    calendario = calcular_calendario(serie)
    validar_calendario(calendario, n_comunas=n_comunas)

    salida = config.PROCESSED_DIR / "calendario.parquet"
    calendario.to_parquet(salida, index=False)
    print(f"Guardado: {salida}")

    print("\nNiveles (% de comuna-mes):")
    print((calendario["nivel"].value_counts(normalize=True).reindex(["baja", "normal", "alta", "extrema"]) * 100)
          .round(1).to_string())

    vina = calendario[(calendario["region_id"] == "05109") & (calendario["mes"] == 2)].set_index("anio")
    print("\nViña del Mar (05109), febrero, 2020-2025:")
    print(vina.loc[2020:2025, ["armonizado", "mediana_historica", "percentil", "nivel"]].round(1).to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
