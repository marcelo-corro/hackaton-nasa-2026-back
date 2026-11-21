"""Alertas v0.5: lista diaria de comunas y sectores a priorizar, en dos niveles.

Reglas (las mismas para el día publicado y para la simulación de 12d_validar_alertas.py):
- **fuego_activo:** la comuna tuvo focos (sin fuentes persistentes) en los 3 días previos. Va primero, sin importar el
  nivel del modelo, y sus sectores se ordenan por cercanía al foco reciente más cercano. Elegido con calibración
  2020-2021: en días con fuego activo, "cerca del fuego reciente" puso el 88 % del fuego del día siguiente en el 10 % de
  sectores, contra 27 % del orden por historial (12c_modelo_sectores.py).
- **alerta:** comuna en nivel alto o muy alto (modelo por comuna). Sectores por días con fuego previos y, a igualdad,
  más interfaz (orden validado en 12b_validar_sectores.py).
- **vigilancia:** comuna en nivel medio. Mismo orden, menos sectores.
- Nivel bajo: no entra. Si ninguna comuna califica, la lista va vacía.

Simulación 2020-2025 (12d_validar_alertas.py, docs/alertas_validacion.md): con ~12 sectores por día (0,07 % del
territorio) la lista v0.5 tuvo el 6,9 % del fuego del día siguiente en la prueba 2022-2025 (14,3 % en calibración),
contra 4,7 % de la v0.4 con 25 sectores. El 92 % de los días en alto o muy alto ya tenía fuego activo: el nivel
"alerta" sin fuego es raro y suele venir de comunas con industria que el modelo por comuna aún cuenta.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

TEXTO_TIPO = {"fuego_activo": "Fuego activo", "alerta": "Alerta", "vigilancia": "Vigilancia"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
ORDEN_NIVEL = {"bajo": 0, "medio": 1, "alto": 2, "muy_alto": 3}
TIPOS = ["fuego_activo", "alerta", "vigilancia"]
DIAS_FUEGO_ACTIVO = 3
SECTORES_POR_COMUNA = {"fuego_activo": 5, "alerta": 5, "vigilancia": 3}
MAX_COMUNAS = {"fuego_activo": 15, "alerta": 15, "vigilancia": 10}
TOPE_KM = 30.0


def tipo_comuna(nivel: str, fuego_activo: bool) -> str | None:
    if fuego_activo:
        return "fuego_activo"
    if ORDEN_NIVEL.get(nivel, 0) >= ORDEN_NIVEL["alto"]:
        return "alerta"
    if nivel == "medio":
        return "vigilancia"
    return None


def armar_lista(sectores: pd.DataFrame, xy_sectores: np.ndarray, riesgo: pd.DataFrame, hist_dias: np.ndarray,
                xy_focos_recientes: np.ndarray, comunas_fuego_activo: set[str]) -> pd.DataFrame:
    """Lista de un día. `sectores` (sin fuentes persistentes) trae sector_id, region_id y frac_wui, alineado con
    `xy_sectores` (coordenadas métricas) y `hist_dias` (días con fuego del sector hasta el último dato). `riesgo` trae
    region_id, prob_foco y nivel de UN horizonte. Devuelve una fila por sector listado, en orden."""
    r = riesgo.assign(region_id=riesgo["region_id"].astype(str))
    r["tipo"] = [tipo_comuna(n, rid in comunas_fuego_activo) for n, rid in zip(r["nivel"], r["region_id"])]
    r = r[r["tipo"].notna()].copy()
    if r.empty:
        return pd.DataFrame(columns=["orden", "tipo", "region_id", "sector_id", "nivel", "prob_foco", "motivo_orden",
                                     "dist_foco_reciente_km", "hist_dias"])
    r["_t"] = r["tipo"].map({t: i for i, t in enumerate(TIPOS)})
    r["_n"] = r["nivel"].map(ORDEN_NIVEL)
    r = r.sort_values(["_t", "_n", "prob_foco", "region_id"], ascending=[True, False, False, True])
    r = pd.concat([g.head(MAX_COMUNAS[t]) for t, g in r.groupby("tipo", sort=False)])

    region = sectores["region_id"].astype(str).to_numpy()
    wui = sectores["frac_wui"].fillna(0).to_numpy()
    if len(xy_focos_recientes):
        dist, _ = cKDTree(xy_focos_recientes).query(xy_sectores)
        dist = np.minimum(dist / 1000, TOPE_KM)
    else:
        dist = np.full(len(sectores), TOPE_KM)
    filas = []
    for c in r.itertuples():
        idx = np.flatnonzero(region == c.region_id)
        if c.tipo == "fuego_activo":
            orden = np.lexsort((-hist_dias[idx], dist[idx]))  # cercanía y, a igualdad, historial
            motivo = "cerca_fuego_reciente"
        else:
            orden = np.lexsort((-wui[idx], -hist_dias[idx]))  # historial y, a igualdad, interfaz
            motivo = "historial_interfaz"
        for i in idx[orden][:SECTORES_POR_COMUNA[c.tipo]]:
            filas.append({"tipo": c.tipo, "region_id": c.region_id, "sector_id": sectores["sector_id"].iat[i],
                          "nivel": c.nivel, "prob_foco": float(c.prob_foco), "motivo_orden": motivo,
                          "dist_foco_reciente_km": round(float(dist[i]), 2), "hist_dias": int(hist_dias[i])})
    out = pd.DataFrame(filas)
    out.insert(0, "orden", np.arange(1, len(out) + 1))
    return out


def motivos_comuna(dias_fuego: pd.Series, ultimo_dato: pd.Timestamp, mes_objetivo: int, condiciones: list[str],
                   textos_condicion: dict[str, str], inicio_datos: pd.Timestamp,
                   etiqueta_clima: str = "Clima del último día") -> dict:
    """Hechos verificables que acompañan el nivel de una comuna (no son el peso de cada variable en el modelo).

    `dias_fuego`: fechas (normalizadas) con focos en la comuna, sin fuentes persistentes, hasta `ultimo_dato`.
    """
    d = pd.to_datetime(pd.Series(dias_fuego)).dt.normalize().drop_duplicates()
    d = d[d <= ultimo_dato]
    ult7 = d[d > ultimo_dato - pd.Timedelta(days=7)]
    activo = bool((d > ultimo_dato - pd.Timedelta(days=DIAS_FUEGO_ACTIVO)).any())
    # Temporada: % de los días de ese mes (en el período con datos) en que hubo focos en la comuna
    dias_mes = pd.date_range(inicio_datos, ultimo_dato, freq="D")
    dias_mes = dias_mes[dias_mes.month == mes_objetivo]
    pct_mes = 100 * d[d.dt.month == mes_objetivo].nunique() / len(dias_mes) if len(dias_mes) else None
    motivos = []
    if activo:
        motivos.append(f"Fuego activo: focos en los últimos {DIAS_FUEGO_ACTIVO} días (último el "
                       f"{d.max().strftime('%d-%m-%Y')})")
    elif len(ult7):
        motivos.append(f"Focos en la última semana ({len(ult7)} {'día' if len(ult7) == 1 else 'días'})")
    if condiciones:
        textos = [textos_condicion.get(c, c) for c in condiciones]
        motivos.append(f"{etiqueta_clima}: " + ", ".join(t[:1].lower() + t[1:] for t in textos))
    if pct_mes is not None:
        motivos.append(f"En {MESES[mes_objetivo - 1]}, la comuna tuvo focos el {pct_mes:.0f} % de los días "
                       f"({inicio_datos.year}-{ultimo_dato.year})")
    return {"fuego_activo": activo, "dias_con_fuego_7d": int(len(ult7)),
            "ultimo_fuego": None if d.empty else d.max().strftime("%Y-%m-%d"),
            "pct_dias_con_fuego_mes": None if pct_mes is None else round(pct_mes, 1), "motivos": motivos}


def lista_v04(sectores: pd.DataFrame, riesgo: pd.DataFrame, hist_dias: np.ndarray, n: int = 25) -> pd.DataFrame:
    """La regla publicada hasta la v0.4, para comparar: 25 sectores, comunas por nivel y probabilidad (sin importar si
    el nivel es bajo), hasta 5 por comuna, orden fijo por historial e interfaz."""
    r = riesgo.assign(region_id=riesgo["region_id"].astype(str), _n=riesgo["nivel"].map(ORDEN_NIVEL))
    r = r.sort_values(["_n", "prob_foco", "region_id"], ascending=[False, False, True])
    region = sectores["region_id"].astype(str).to_numpy()
    wui = sectores["frac_wui"].fillna(0).to_numpy()
    filas = []
    for c in r.itertuples():
        idx = np.flatnonzero(region == c.region_id)
        for i in idx[np.lexsort((-wui[idx], -hist_dias[idx]))][:5]:
            filas.append({"region_id": c.region_id, "sector_id": sectores["sector_id"].iat[i], "nivel": c.nivel})
        if len(filas) >= n:
            break
    return pd.DataFrame(filas[:n])
