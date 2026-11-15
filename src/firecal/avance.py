"""Dirección de avance de un incendio activo: datos para validarla y el cono que se publica.

Verdad (lo que se intenta predecir): en un incendio (evento de firecal.events) con focos el día d y el día d+1, el
"frente nuevo" son los focos de d+1 a más de `SEPARACION_FRENTE_KM` de todo foco de d. La dirección real de avance va
del centro de los focos de d al centro del frente nuevo; la distancia, lo mismo en km.

Predictores (todos conocidos al final del día d):
- viento a favor: la dirección hacia donde sopla el viento del día d (NASA POWER WD10M indica de dónde viene: se suma
  180°);
- persistencia: la dirección en que avanzó el día anterior (d-1 → d), si el incendio ya avanzaba.
Error angular: diferencia absoluta entre direcciones (0-180°). Al azar, el 25 % cae a ±45° y el 50 % a ±90°.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

KM_LAT = 110.57
KM_LON = 111.32
SEPARACION_FRENTE_KM = 0.75  # dos píxeles VIIRS: menos que eso es el mismo frente
DISTANCIA_MINIMA_KM = 0.5    # avances más cortos son ruido de posición


def rumbo(dx_km: np.ndarray, dy_km: np.ndarray) -> np.ndarray:
    """Rumbo en grados desde el norte, en sentido horario (0 = N, 90 = E)."""
    return np.degrees(np.arctan2(dx_km, dy_km)) % 360


def error_angular(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Diferencia absoluta entre dos rumbos, entre 0 y 180 grados."""
    return np.abs((np.asarray(a) - np.asarray(b) + 180) % 360 - 180)


def a_favor_del_viento(direccion_origen: np.ndarray) -> np.ndarray:
    """La dirección meteorológica dice de dónde viene el viento; el fuego avanza hacia donde va: +180°."""
    return (np.asarray(direccion_origen) + 180) % 360


def _xy(lat: np.ndarray, lon: np.ndarray, lat0: float) -> np.ndarray:
    return np.column_stack([lon * KM_LON * np.cos(np.radians(lat0)), lat * KM_LAT])


def incendios_activos(focos: pd.DataFrame, ultimo_dato: pd.Timestamp, dias: int = 3) -> pd.DataFrame:
    """Incendios (eventos) con focos en los últimos `dias` días hasta `ultimo_dato`, uno por fila: centro de los focos
    de su día más reciente (origen del círculo), comuna más frecuente ese día, fechas y cantidad de focos."""
    f = focos.assign(dia=focos["fecha_local"].dt.normalize())
    f = f[f["dia"] <= ultimo_dato]
    activos = f.loc[f["dia"] > ultimo_dato - pd.Timedelta(days=dias), "evento"].unique()
    filas = []
    for ev, e in f[f["evento"].isin(activos)].groupby("evento"):
        ult = e["dia"].max()
        u = e[e["dia"] == ult]
        filas.append({"evento": ev, "region_id": str(u["region_id"].mode().iat[0]),
                      "lat": round(float(u["lat"].mean()), 5), "lon": round(float(u["lon"].mean()), 5),
                      "ultimo_foco": ult, "focos_ultimo_dia": int(len(u)), "inicio": e["dia"].min(),
                      "focos_incendio": int(len(e)), "dias_con_focos": int(e["dia"].nunique())})
    return pd.DataFrame(filas)


def ficha_avance(inc: pd.Series, viento: pd.DataFrame, params: dict) -> dict:
    """Zona probable de avance de un incendio activo: dos círculos validados y, solo con viento fuerte, la flecha.

    `viento`: viento diario de la comuna (fecha, viento_dir = de dónde viene, viento_vel en m/s); se usa el último día
    con dato hasta el último foco. `params`: data/processed/avance_params.json (paso 14)."""
    v = viento[viento["fecha"] <= inc["ultimo_foco"]].sort_values("fecha").tail(1)
    tiene = len(v) == 1
    vel = float(v["viento_vel"].iat[0]) if tiene else None
    fuerte = bool(tiene and vel >= params["viento_fuerte_desde_ms"])
    return {
        "radio_km_70": params["radios_km"]["p75"], "radio_km_85": params["radios_km"]["p90"],
        "viento": None if not tiene else {
            "fecha": pd.Timestamp(v["fecha"].iat[0]).strftime("%Y-%m-%d"),
            "desde_grados": round(float(v["viento_dir"].iat[0]), 0),
            "hacia_grados": round(float(a_favor_del_viento(v["viento_dir"].iat[0])), 0),
            "velocidad_ms": round(vel, 1), "fuerte": fuerte},
        "mostrar_flecha": fuerte,
    }


def pares_avance(focos: pd.DataFrame) -> pd.DataFrame:
    """Una fila por (incendio, día d) con focos en d y frente nuevo en d+1.

    `focos` trae evento, lat, lon, fecha_local y region_id. Devuelve evento, fecha (d), region_id (comuna más frecuente
    en d), centro de d, rumbo y distancia del avance, focos de d y del frente nuevo, y el rumbo del avance anterior
    (NaN si el día anterior no hubo avance medido)."""
    f = focos.assign(dia=focos["fecha_local"].dt.normalize())
    filas = []
    for ev, g in f.groupby("evento"):
        dias = sorted(g["dia"].unique())
        if len(dias) < 2:
            continue
        por_dia = {d: g[g["dia"] == d] for d in dias}
        previo = np.nan
        for d0, d1 in zip(dias[:-1], dias[1:]):
            if (d1 - d0) != np.timedelta64(1, "D"):
                previo = np.nan
                continue
            a, b = por_dia[d0], por_dia[d1]
            lat0 = float(a["lat"].mean())
            xa, xb = _xy(a["lat"].to_numpy(), a["lon"].to_numpy(), lat0), _xy(b["lat"].to_numpy(), b["lon"].to_numpy(), lat0)
            dist, _ = cKDTree(xa).query(xb)
            nuevo = xb[dist > SEPARACION_FRENTE_KM]
            if not len(nuevo):
                previo = np.nan
                continue
            c0, c1 = xa.mean(axis=0), nuevo.mean(axis=0)
            dx, dy = c1 - c0
            km = float(np.hypot(dx, dy))
            if km < DISTANCIA_MINIMA_KM:
                previo = np.nan
                continue
            rb = float(rumbo(dx, dy))
            filas.append({"evento": ev, "fecha": d0, "region_id": a["region_id"].mode().iat[0],
                          "lat": lat0, "lon": float(a["lon"].mean()), "rumbo_real": rb, "km": km,
                          "focos_d": len(a), "focos_frente": len(nuevo), "rumbo_previo": previo})
            previo = rb
    return pd.DataFrame(filas)
