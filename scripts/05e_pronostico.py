"""Paso 5e: pronóstico del tiempo por comuna (Open-Meteo) para el riesgo del día.

Pide a Open-Meteo los días desde el último de NASA POWER (rellenan su rezago; al menos 7) y hoy y los 3 siguientes (el
clima de los días que se predicen), en el mismo punto por comuna que NASA POWER. Ver firecal.ingest.pronostico.

Si Open-Meteo falla, NO detiene la actualización: borra el pronóstico anterior (no sirve para otro día) y el paso 8
vuelve a lo de antes (repetir el último clima de NASA POWER, con modelos sin pronóstico).

Salida: data/interim/pronostico_diario.parquet (region_id, fecha, tmax, hrmin, viento_max, precip, emitido_utc).

Uso:
    python scripts/05e_pronostico.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402

from firecal import config  # noqa: E402
from firecal.ingest.clima import puntos_representativos  # noqa: E402
from firecal.ingest.pronostico import pedir_pronostico  # noqa: E402

SALIDA = config.INTERIM_DIR / "pronostico_diario.parquet"


def main() -> int:
    puntos = puntos_representativos(gpd.read_parquet(config.INTERIM_DIR / "comunas.parquet"))
    ahora = datetime.now(timezone.utc)
    emitido = ahora.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Días hacia atrás: desde el último día de NASA POWER (Open-Meteo entrega hasta 92), al menos 7
    ruta_clima = config.INTERIM_DIR / "clima_diario.parquet"
    atras = 7
    if ruta_clima.exists():
        ultimo = pd.read_parquet(ruta_clima, columns=["fecha_local"])["fecha_local"].max()
        atras = int(min(92, max(7, (pd.Timestamp(ahora.date()) - pd.Timestamp(ultimo)).days + 1)))
    try:
        p = pedir_pronostico(puntos, dias_atras=atras)
    except Exception as e:  # noqa: BLE001 (red o servicio caído: la actualización sigue sin pronóstico)
        SALIDA.unlink(missing_ok=True)
        print(f"AVISO: no se pudo bajar el pronóstico de Open-Meteo ({e}); el riesgo se calcula sin pronóstico")
        return 0
    p["emitido_utc"] = emitido
    p.to_parquet(SALIDA, index=False)
    print(f"Pronóstico de Open-Meteo: {p['region_id'].nunique()} comunas, {p['fecha'].min().date()} a "
          f"{p['fecha'].max().date()} ({len(p):,} filas) → {SALIDA}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
