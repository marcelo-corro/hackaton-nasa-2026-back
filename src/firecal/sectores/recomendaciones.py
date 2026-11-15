"""Rasgos de cada sector, recomendaciones oficiales y prioridad de alertas (piloto A+).

Qué es y qué no es:
- Los RASGOS describen el sector (qué hay): interfaz con viviendas, tipo de vegetación, pendiente, historial. Los
  umbrales son criterios del proyecto, documentados aquí y en docs/sectores.md; no son probabilidades.
- Las RECOMENDACIONES son textos generales de fuentes oficiales (CONAF, SENAPRED, MINVU), elegidos según los rasgos
  del sector y el nivel de riesgo de la comuna. No se inventan medidas ni cifras: si una fuente no se pudo leer
  completa, la recomendación no lleva números.
- La PRIORIDAD de alertas ordena primero las comunas por riesgo (modelo validado) y, dentro de cada comuna, los
  sectores por días con fuego previos y, a igualdad, por fracción de interfaz con viviendas. Ese orden se eligió en
  calibración 2020-2021 entre cuatro alternativas (scripts/12b_validar_sectores.py): el 10 % de sectores con mayor
  puntaje concentró el 26 % de los días-sector con fuego en 2020-2021 y el 29 % en la prueba 2022-2025 (azar: 10 %).
  Contar factores de exposición NO ordenaba mejor (12 % en calibración), así que `exposicion` es solo descriptivo.
  No es la probabilidad de que el sector se queme.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Umbrales de rasgos (criterio del proyecto)
UMBRAL_INTERFAZ = 0.25      # >= 25 % del sector es interfaz casas-vegetación (WUI clases 1-4)
UMBRAL_PASTIZAL = 0.40      # >= 40 % del sector es pastizal (WorldCover 30)
UMBRAL_BOSQUE = 0.50        # >= 50 % árboles + matorral (WorldCover 10 + 20)
UMBRAL_PENDIENTE = 15.0     # pendiente media >= 15 grados
UMBRAL_HISTORIAL_DIAS = 2   # fuego en >= 2 días desde 2012 (o algún incendio grande)

RASGOS = {
    "interfaz": "Casas junto a o entre la vegetación (interfaz urbano-forestal)",
    "pastizal": "Predomina el pastizal",
    "bosque_matorral": "Predomina bosque o matorral (la fuente no separa bosque nativo de plantación)",
    "pendiente": "Pendiente fuerte: el fuego avanza más rápido ladera arriba y el acceso es difícil",
    "historial": "Ha tenido fuego desde 2012",
    "fuente_persistente": "Detecciones satelitales persistentes, probablemente industriales (no se cuentan como "
                          "incendios)",
}
FACTORES_EXPOSICION = ["interfaz", "pastizal", "bosque_matorral", "pendiente", "historial"]

FUENTES = {
    "conaf_uso_fuego": {
        "nombre": "CONAF, Actualización: situación del uso del fuego como quema controlada (consultado 14-11-2026)",
        "url": "https://www.conaf.cl/actualizacion-situacion-uso-del-fuego-en-regiones/"},
    "conaf_sitio": {"nombre": "CONAF, número de emergencias (pie del sitio oficial)", "url": "https://www.conaf.cl/"},
    "senapred_preparate": {
        "nombre": "SENAPRED, Prepárate con SENAPRED: incendios forestales",
        "url": "https://bibliogrd.senapred.gob.cl/bitstream/handle/1671/8866/06_preparate_con_senapred_incendios_forestales_esp.pdf"},
    "minvu_barrios": {
        "nombre": "MINVU, Chile se prepara: barrios (díptico, 2024)",
        "url": "https://www.minvu.gob.cl/wp-content/uploads/2024/12/DIPTICO-chile-se-prepara-BARRIOS.pdf"},
    "conaf_comunidad": {
        "nombre": "CONAF, programa Comunidad Preparada frente a los incendios forestales",
        "url": "https://www.conaf.cl/conaf-desarrolla-el-programa-comunidad-preparada-frente-a-los-incendios-forestales-con-vecinos-y-vecinas-de-zonas-de-interfaz/"},
}

RECOMENDACIONES = {
    "entorno_vivienda": {"texto": "Mantener despejados de pasto seco, hojas y ramas los alrededores de las viviendas.",
                         "fuente": "senapred_preparate"},
    "sin_colillas": {"texto": "No fumar ni botar colillas o fósforos cerca de la vegetación.",
                     "fuente": "senapred_preparate"},
    "sin_quemas_05": {"texto": "No hacer quemas: en la Región de Valparaíso el uso del fuego está restringido hasta el "
                               "31 de mayo de 2027.", "fuente": "conaf_uso_fuego"},
    "calendario_quemas": {"texto": "Antes de cualquier quema, revisar si está permitida en la comuna y tramitar el "
                                   "Comprobante de Aviso de Quema en CONAF.", "fuente": "conaf_uso_fuego"},
    "plan_barrio": {"texto": "Organizar con la junta de vecinos un plan de prevención con zonas seguras y rutas de "
                             "evacuación despejadas.", "fuente": "minvu_barrios"},
    "comunidad_preparada": {"texto": "Sumarse a los talleres de CONAF para zonas de interfaz (programa Comunidad "
                                     "Preparada).", "fuente": "conaf_comunidad"},
    "avisar_130": {"texto": "Ante humo o fuego, avisar de inmediato al 130 (CONAF).", "fuente": "conaf_sitio"},
}
REGIONES_CON_QUEMAS_RESTRINGIDAS = {"05"}  # según CONAF al 14-11-2026 (hasta el 31-05-2027)
ORDEN_NIVEL = {"bajo": 0, "medio": 1, "alto": 2, "muy_alto": 3}


def rasgos_sector(s: pd.DataFrame) -> pd.Series:
    """Lista de códigos de rasgo por sector (columnas de sectores_<región>.parquet)."""
    marcas = pd.DataFrame({
        "interfaz": s["frac_wui"].fillna(0) >= UMBRAL_INTERFAZ,
        "pastizal": s["frac_pastizal"] >= UMBRAL_PASTIZAL,
        "bosque_matorral": (s["frac_arboles"] + s["frac_matorral"]) >= UMBRAL_BOSQUE,
        "pendiente": s["pendiente_media"] >= UMBRAL_PENDIENTE,
        "historial": (s["dias_con_fuego"] >= UMBRAL_HISTORIAL_DIAS) | (s["incendios_grandes"] > 0),
        "fuente_persistente": s["fuente_persistente"].astype(bool),
    }, index=s.index)
    return marcas.apply(lambda fila: [r for r in RASGOS if fila[r]], axis=1)


def recomendaciones_sector(rasgos: list[str], nivel_comuna: str, region: str) -> list[str]:
    """Códigos de recomendación según rasgos del sector y nivel de riesgo de la comuna (en orden de prioridad)."""
    alto = ORDEN_NIVEL.get(nivel_comuna, 0) >= ORDEN_NIVEL["alto"]
    vegetacion = bool({"pastizal", "bosque_matorral"} & set(rasgos))
    out = []
    if alto:
        out.append("avisar_130")
    if "interfaz" in rasgos:
        out.append("entorno_vivienda")
    if vegetacion or "interfaz" in rasgos:
        out.append("sin_quemas_05" if region in REGIONES_CON_QUEMAS_RESTRINGIDAS else "calendario_quemas")
        out.append("sin_colillas")
    if "interfaz" in rasgos and (alto or "historial" in rasgos or "pendiente" in rasgos):
        out.append("plan_barrio")
        out.append("comunidad_preparada")
    return out


def prioridad_alertas(sectores: pd.DataFrame, riesgo_comuna: pd.DataFrame, n: int = 25) -> pd.DataFrame:
    """Sectores a priorizar: primero las comunas con mayor nivel y probabilidad; dentro, los sectores con más días con
    fuego previos y, a igualdad, más interfaz (orden validado, ver docstring del módulo). Excluye fuentes
    persistentes. `riesgo_comuna` trae region_id, prob_foco y nivel para UN horizonte; `sectores`, el historial
    contado SOLO hasta el día anterior a la predicción."""
    d = sectores.merge(riesgo_comuna[["region_id", "prob_foco", "nivel"]], on="region_id", how="inner")
    d = d[~d["fuente_persistente"]].copy()
    d["exposicion"] = d["rasgos"].apply(lambda r: sum(x in r for x in FACTORES_EXPOSICION))
    d["_nivel"] = d["nivel"].map(ORDEN_NIVEL)
    d["_wui"] = d["frac_wui"].fillna(0)
    d = d.sort_values(["_nivel", "prob_foco", "dias_con_fuego", "_wui", "sector_id"],
                      ascending=[False, False, False, False, True])
    # como mucho 5 sectores por comuna, para que la lista cubra varias comunas
    d = d.groupby("region_id", sort=False).head(5).head(n)
    return d.drop(columns=["_nivel", "_wui"])


def condiciones_clima(clima: pd.DataFrame, fecha: pd.Timestamp) -> pd.DataFrame:
    """Clima observado de `fecha` por comuna y su percentil contra el mismo mes de todos los años disponibles.

    `clima` viene de firecal.model.variables.bloque_clima (region_id, fecha, tmax, hrmin, viento_max, precip,
    precip_7d, dias_sin_lluvia). Devuelve una fila por comuna con valores, percentiles y marcas de condición extrema
    (calor: tmax >= p90; aire seco: hrmin <= p10; viento: viento_max >= p90; sin lluvia: días sin lluvia >= p90).
    Todo contra el mismo mes, porque en verano casi todo Chile central pasa semanas sin llover.
    """
    c = clima.copy()
    c["mes"] = c["fecha"].dt.month
    dia = c[c["fecha"] == fecha]
    hist = c[c["mes"] == fecha.month]
    filas = []
    for r in dia.itertuples():
        h = hist[hist["region_id"] == r.region_id]

        def pct(col: str) -> float:
            v = h[col].dropna().to_numpy()
            x = getattr(r, col)
            return float(100 * ((v < x).sum() + 0.5 * (v == x).sum()) / len(v)) if len(v) and pd.notna(x) else np.nan

        p_t, p_h, p_v, p_s = pct("tmax"), pct("hrmin"), pct("viento_max"), pct("dias_sin_lluvia")
        filas.append({
            "region_id": r.region_id, "fecha_clima": fecha.strftime("%Y-%m-%d"),
            "tmax": round(float(r.tmax), 1), "tmax_percentil": round(p_t),
            "hrmin": round(float(r.hrmin), 0), "hrmin_percentil": round(p_h),
            "viento_max": round(float(r.viento_max), 1), "viento_percentil": round(p_v),
            "dias_sin_lluvia": int(r.dias_sin_lluvia), "dias_sin_lluvia_percentil": round(p_s),
            "condiciones": [k for k, ok in (("calor", p_t >= 90), ("aire_seco", p_h <= 10), ("viento", p_v >= 90),
                                            ("sin_lluvia", p_s >= 90)) if ok],
        })
    return pd.DataFrame(filas)
