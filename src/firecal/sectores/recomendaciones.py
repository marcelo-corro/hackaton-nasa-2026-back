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
    # Verificadas por Seba y Kathy leyendo el documento (15-11-2026): página y frase en docs/fuentes.md, sección 3c
    "senapred_preparate": {
        "nombre": "SENAPRED, Prepárate con SENAPRED: incendios forestales (pág. 2)",
        "url": "https://bibliogrd.senapred.gob.cl/bitstream/handle/1671/8866/06_preparate_con_senapred_incendios_forestales_esp.pdf"},
    "minvu_barrios": {
        "nombre": "MINVU, Chile se prepara: barrios (díptico 2024, con recomendaciones de CONAF)",
        "url": "https://www.minvu.gob.cl/wp-content/uploads/2024/12/DIPTICO-chile-se-prepara-BARRIOS.pdf"},
    "conaf_comunidad": {
        "nombre": "CONAF, programa Comunidad Preparada frente a los incendios forestales (nota de CONAF O'Higgins, "
                  "2-5-2025)",
        "url": "https://www.conaf.cl/conaf-desarrolla-el-programa-comunidad-preparada-frente-a-los-incendios-forestales-con-vecinos-y-vecinas-de-zonas-de-interfaz/"},
    "conaf_faena_cero": {
        "nombre": "CONAF y Ministerio de Agricultura, llamado preventivo a aplicar Faena Cero (31-12-2025)",
        "url": "https://www.conaf.cl/ministerio-de-agricultura-y-conaf-realizan-un-llamado-preventivo-a-aplicar-faena-cero-para-reducir-el-riesgo-de-incendios-forestales/"},
    "conaf_valparaiso": {
        "nombre": "CONAF, llamado a prevenir incendios forestales en Valparaíso (11-12-2025)",
        "url": "https://www.conaf.cl/subsecretario-de-agricultura-refuerza-el-llamado-a-prevenir-incendios-forestales-en-valparaiso/"},
    "dmc_umbrales": {
        "nombre": "Dirección Meteorológica de Chile, monitoreo de variables meteorológicas asociadas al riesgo de "
                  "incendios forestales",
        "url": "https://climatologia.meteochile.gob.cl/application/diarioc/mapaRiesgoIncendiosHoy"},
}

RECOMENDACIONES = {
    "entorno_vivienda": {"texto": "Mantener los alrededores de las viviendas despejados de vegetación y desechos que se "
                                  "puedan quemar.", "fuente": "senapred_preparate"},
    "poda": {"texto": "Podar los árboles enfermos, secos o a menos de 3 metros de las casas, y mantener 2 a 3 metros "
                      "entre árboles, ramas inferiores, el suelo y las viviendas.", "fuente": "minvu_barrios"},
    "sin_colillas": {"texto": "No fumar ni botar colillas o fósforos cerca de la vegetación.",
                     "fuente": "senapred_preparate"},
    "sin_quemas_05": {"texto": "No hacer quemas: en la Región de Valparaíso el uso del fuego está restringido hasta el "
                               "31 de mayo de 2027.", "fuente": "conaf_uso_fuego"},
    "calendario_quemas": {"texto": "Antes de cualquier quema, revisar si está permitida en la comuna y tramitar el "
                                   "Comprobante de Aviso de Quema en CONAF.", "fuente": "conaf_uso_fuego"},
    "plan_barrio": {"texto": "Organizar con la junta de vecinos un plan de prevención con zonas seguras y rutas de "
                             "evacuación despejadas.", "fuente": "minvu_barrios"},
    "comunidad_preparada": {"texto": "Informarse sobre el programa Comunidad Preparada de CONAF, que prepara a "
                                     "comunidades de zonas de interfaz con cuatro talleres de prevención.",
                            "fuente": "conaf_comunidad"},
    "avisar_130": {"texto": "Ante cualquier foco, avisar de inmediato al 130 (CONAF), al 132 (Bomberos) o al 133 "
                            "(Carabineros).", "fuente": "conaf_valparaiso"},
    # Por condición del clima (comuna)
    "faena_cero": {"texto": "Evitar trabajos con maquinaria o herramientas que produzcan chispas o calor (galleteras, "
                            "soldadoras, desbrozadoras) en las horas de mayor temperatura, en especial entre las 12:00 "
                            "y las 18:00.", "fuente": "conaf_faena_cero"},
    "sin_fuentes_calor": {"texto": "Evitar fuentes de calor cerca de la vegetación; no usar globos de los deseos ni "
                                   "fuegos artificiales.", "fuente": "conaf_faena_cero"},
}

# Condiciones del clima observado del último día (comuna). Las relativas comparan con el mismo mes de 2012-2025; las
# absolutas usan los umbrales de la Dirección Meteorológica de Chile (que aclara que no pronostica incendios). Con
# NASA POWER (~50 km, humedad mínima aproximada) son una referencia, no una medición local.
CONDICIONES = {
    "calor": {"texto": "Temperatura máxima entre el 10 % más alto para este mes", "fuente": None},
    "aire_seco": {"texto": "Humedad entre el 10 % más bajo para este mes", "fuente": None},
    "viento": {"texto": "Viento entre el 10 % más fuerte para este mes", "fuente": None},
    "sin_lluvia": {"texto": "Racha sin lluvia entre el 10 % más larga para este mes", "fuente": None},
    "temp_sobre_30": {"texto": "Temperatura máxima sobre 30 °C", "fuente": "dmc_umbrales"},
    "humedad_bajo_30": {"texto": "Humedad mínima bajo 30 % (aproximada)", "fuente": "dmc_umbrales"},
    "viento_sobre_30": {"texto": "Viento máximo sobre 30 km/h", "fuente": "dmc_umbrales"},
    "condicion_30_30_30": {"texto": "Se superan los tres umbrales de la Dirección Meteorológica (más de 30 °C, humedad "
                                    "bajo 30 %, viento sobre 30 km/h): condiciones favorables a la propagación. No es "
                                    "un pronóstico de incendio.", "fuente": "dmc_umbrales"},
}
CONDICIONES_CALOR = {"calor", "temp_sobre_30", "condicion_30_30_30"}
CONDICIONES_VIENTO = {"viento", "viento_sobre_30", "condicion_30_30_30"}
CONDICIONES_SECO = {"aire_seco", "humedad_bajo_30", "condicion_30_30_30"}
KMH_POR_MS = 3.6
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
        if "bosque_matorral" in rasgos:  # casas junto a árboles: indicaciones de poda del MINVU
            out.append("poda")
    if vegetacion or "interfaz" in rasgos:
        out.append("sin_quemas_05" if region in REGIONES_CON_QUEMAS_RESTRINGIDAS else "calendario_quemas")
        out.append("sin_colillas")
    if "interfaz" in rasgos and (alto or "historial" in rasgos or "pendiente" in rasgos):
        out.append("plan_barrio")
        out.append("comunidad_preparada")
    return out


def recomendaciones_clima(condiciones: list[str], region: str) -> list[str]:
    """Códigos de recomendación por el clima del último día en la comuna (Faena Cero y fuentes de calor de CONAF)."""
    c = set(condiciones)
    out = []
    if c:
        out.append("avisar_130")
    if c & (CONDICIONES_CALOR | CONDICIONES_VIENTO):
        out.append("faena_cero")
    if c & (CONDICIONES_CALOR | CONDICIONES_SECO | CONDICIONES_VIENTO):
        out.append("sin_fuentes_calor")
        out.append("sin_quemas_05" if region in REGIONES_CON_QUEMAS_RESTRINGIDAS else "calendario_quemas")
    return out


def recomendaciones_completas(rasgos: list[str], nivel_comuna: str, region: str,
                              condiciones: list[str] | None = None) -> list[str]:
    """Las del sector (rasgos + nivel) y las del clima de la comuna, sin repetir; "avisar" siempre primero."""
    todas = recomendaciones_clima(condiciones or [], region) + recomendaciones_sector(rasgos, nivel_comuna, region)
    unicas = list(dict.fromkeys(todas))
    return sorted(unicas, key=lambda r: r != "avisar_130")


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
    Todo contra el mismo mes, porque en verano casi todo Chile central pasa semanas sin llover. Suma las marcas de
    los umbrales de la DMC (>30 °C, <30 % de humedad, >30 km/h) y `condicion_30_30_30` si se cumplen los tres.
    `viento_max` viene en m/s (NASA POWER); se publica también en km/h.
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
        kmh = float(r.viento_max) * KMH_POR_MS
        dmc = {"temp_sobre_30": r.tmax > 30, "humedad_bajo_30": r.hrmin < 30, "viento_sobre_30": kmh > 30}
        relativas = {"calor": p_t >= 90, "aire_seco": p_h <= 10, "viento": p_v >= 90, "sin_lluvia": p_s >= 90}
        condiciones = [k for k, ok in (relativas | dmc).items() if ok]
        if all(dmc.values()):
            condiciones.append("condicion_30_30_30")
        filas.append({
            "region_id": r.region_id, "fecha_clima": fecha.strftime("%Y-%m-%d"),
            "tmax": round(float(r.tmax), 1), "tmax_percentil": round(p_t),
            "hrmin": round(float(r.hrmin), 0), "hrmin_percentil": round(p_h),
            "viento_max": round(float(r.viento_max), 1), "viento_max_kmh": round(kmh, 1), "viento_percentil": round(p_v),
            "dias_sin_lluvia": int(r.dias_sin_lluvia), "dias_sin_lluvia_percentil": round(p_s),
            "condiciones": condiciones,
        })
    return pd.DataFrame(filas)
