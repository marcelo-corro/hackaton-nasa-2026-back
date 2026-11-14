"""Paso 5b (B): clima diario por comuna (NASA POWER) para el modelo de riesgo de A.

Entrada: data/interim/comunas.parquet
Caché:   data/raw/clima_power/{region_id}.json (se puede cortar y retomar)
Salida:  data/interim/clima_diario.parquet  (region_id, fecha_local, tmax, hrmin, hr_media, viento_max, precip)
         `hrmin` es una aproximación (POWER no entrega humedad mínima); ver firecal.ingest.clima.

Uso:
    python scripts/05b_clima_diario.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import geopandas as gpd  # noqa: E402

from firecal import config  # noqa: E402
from firecal.ingest.clima import clima_diario, descargar_clima, huecos, puntos_representativos  # noqa: E402


def main() -> int:
    comunas = gpd.read_parquet(config.INTERIM_DIR / "comunas.parquet")
    puntos = puntos_representativos(comunas)
    cache = config.DATA_DIR / "raw" / "clima_power"

    nuevas = descargar_clima(puntos, cache)  # si falla, lo ya bajado queda en caché: volver a correr retoma
    print(f"Comunas descargadas ahora: {nuevas}")

    clima = clima_diario(puntos, cache)
    problemas = huecos(clima, n_comunas=len(puntos))
    if problemas:
        print("Huecos en el clima:\n- " + "\n- ".join(problemas))
        return 1

    salida = config.INTERIM_DIR / "clima_diario.parquet"
    clima.to_parquet(salida, index=False)
    print(f"Guardado: {salida} ({len(clima):,} filas, {clima['region_id'].nunique()} comunas, sin huecos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
