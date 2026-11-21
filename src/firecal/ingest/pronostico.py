"""Pronóstico del tiempo por comuna desde Open-Meteo (https://open-meteo.com, CC BY 4.0). Fuente en docs/fuentes.md.

Para qué: NASA POWER publica con ~4 días de rezago y no tiene los días que se predicen. Open-Meteo rellena esos días
(su corrida más reciente para los días pasados) y da el pronóstico de hoy y mañana. Medido en 2024-2025 con pronósticos
archivados (docs/pronostico_validacion.md): con el relleno y el pronóstico, la precisión media del riesgo a 24 h que se
publica sube de 0,25 a 0,32 en las 80 comunas con más fuego.

Mismo punto por comuna que NASA POWER (`firecal.ingest.clima.puntos_representativos`). Se piden variables horarias en
hora de Chile y se resumen por día como en la validación: temperatura máxima, humedad relativa mínima, viento máximo
(m/s) y precipitación del día; un día cuenta solo si tiene al menos MIN_HORAS horas.

Salida de `pedir_pronostico`: region_id, fecha, tmax, hrmin, viento_max, precip (mismas unidades que clima_diario).
"""

from __future__ import annotations

import time

import pandas as pd
import requests

URL = "https://api.open-meteo.com/v1/forecast"
VARIABLES_HORARIAS = ["temperature_2m", "relative_humidity_2m", "wind_speed_10m", "precipitation"]
MIN_HORAS = 20
LOTE = 50  # comunas por petición (Open-Meteo acepta varias coordenadas separadas por coma)
ATRIBUCION = "Weather data by Open-Meteo.com (CC BY 4.0)"


def horario_a_diario(horario: pd.DataFrame) -> pd.DataFrame:
    """Resumen diario de las variables horarias de Open-Meteo (`time` en hora local)."""
    h = horario.assign(fecha=pd.to_datetime(horario["time"]).dt.normalize())
    d = h.groupby("fecha").agg(tmax=("temperature_2m", "max"), hrmin=("relative_humidity_2m", "min"),
                               viento_max=("wind_speed_10m", "max"), precip=("precipitation", "sum"),
                               horas=("temperature_2m", "count"))
    return d[d["horas"] >= MIN_HORAS].drop(columns="horas").reset_index()


def pedir_pronostico(puntos: pd.DataFrame, dias_atras: int = 7, dias_adelante: int = 4,
                     sesion: requests.Session | None = None, reintentos: int = 3) -> pd.DataFrame:
    """Clima diario de Open-Meteo para cada punto (region_id, lat, lon): los últimos `dias_atras` días y hoy más los
    `dias_adelante - 1` siguientes. Lanza una excepción si una petición falla tras los reintentos."""
    s = sesion or requests.Session()
    partes = []
    for i in range(0, len(puntos), LOTE):
        lote = puntos.iloc[i:i + LOTE]
        params = {"latitude": ",".join(f"{v:.4f}" for v in lote["lat"]),
                  "longitude": ",".join(f"{v:.4f}" for v in lote["lon"]),
                  "hourly": ",".join(VARIABLES_HORARIAS), "timezone": "America/Santiago", "wind_speed_unit": "ms",
                  "past_days": dias_atras, "forecast_days": dias_adelante}
        for intento in range(reintentos + 1):
            r = s.get(URL, params=params, timeout=90)
            if r.status_code == 200:
                break
            if intento == reintentos or r.status_code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"Open-Meteo respondió {r.status_code}: {r.text[:200]}")
            time.sleep(5 * (intento + 1))
        datos = r.json()
        datos = datos if isinstance(datos, list) else [datos]
        if len(datos) != len(lote):
            raise RuntimeError(f"Open-Meteo devolvió {len(datos)} ubicaciones de {len(lote)}")
        for rid, d in zip(lote["region_id"], datos):
            partes.append(horario_a_diario(pd.DataFrame(d["hourly"])).assign(region_id=str(rid)))
        time.sleep(1)
    salida = pd.concat(partes, ignore_index=True)
    salida["region_id"] = salida["region_id"].astype("string")
    return salida[["region_id", "fecha", "tmax", "hrmin", "viento_max", "precip"]]
