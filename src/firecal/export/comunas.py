"""comunas.json (contrato 0.8): riesgo, clima, motivos y recomendaciones de las 345 comunas del país.

Son las mismas reglas del bloque `comunas` de alertas/{codigo_region}.json del piloto de Valparaíso, ahora para todo
Chile (no hay sectores fuera del piloto):
- riesgo por horizonte (24 h, 48 h y 7 días) del último día calculado;
- clima del día que se predice (pronóstico de Open-Meteo) o, si no hay pronóstico, el observado del último día, con sus
  condiciones extremas (firecal.sectores.recomendaciones.condiciones_clima);
- hechos verificables que acompañan el nivel (firecal.sectores.alertas.motivos_comuna): fuego activo, focos de la
  última semana, clima del último día y frecuencia histórica de focos en el mes;
- recomendaciones por horizonte: las de un sector sin rasgos (recomendaciones_completas con rasgos vacíos), es decir,
  por el clima del último día y "avisar al 130" si el nivel de la comuna es alto o muy alto. La restricción de quemas se
  nombra solo en las regiones que la tienen; en el resto, el calendario de quemas de CONAF.
No hay reglas nuevas: todo sale de funciones ya validadas y probadas para el piloto.
"""

from __future__ import annotations

import pandas as pd

from firecal.export.contrato import VERSION_CONTRATO
from firecal.export.sectores import resumen_comunas
from firecal.sectores.alertas import motivos_comuna
from firecal.sectores.recomendaciones import CONDICIONES, recomendaciones_completas

ARCHIVO_COMUNAS = "comunas.json"
INICIO_DATOS = pd.Timestamp("2012-02-01")  # primer día con VIIRS Suomi NPP en la serie (igual que el paso 13)
_NOTA_RESTO = ("y hechos que acompañan el nivel de cada comuna; no son el peso de cada variable en el modelo. Las "
               "recomendaciones dependen del clima de ese día y del nivel de la comuna en cada horizonte. Los focos no "
               "incluyen las fuentes fijas que se repiten año tras año (industria, minería, volcanes); una fuente nueva "
               "puede aparecer hasta que se actualice esa lista.")
NOTA_COMUNAS = "Clima observado del último día con datos (NASA POWER) " + _NOTA_RESTO
NOTA_COMUNAS_PRONOSTICO = ("Clima pronosticado del día que se predice (Open-Meteo; las marcas «alta para la época» se "
                           "comparan con la historia de NASA POWER) " + _NOTA_RESTO)
ETIQUETA_CLIMA = {False: "Clima del último día", True: "Clima pronosticado"}


def fecha_clima_a_mostrar(clima: pd.DataFrame | None, fecha_dato: pd.Timestamp) -> tuple[pd.Timestamp | None, bool]:
    """El día cuyo clima se muestra y guía las recomendaciones, y si es pronóstico.

    Con pronóstico (bloque_clima con Open-Meteo), el día que se predice (`fecha_dato` + 1); si no, el último día con
    clima observado, como antes.
    """
    if clima is None or clima.empty:
        return None, False
    destino = pd.Timestamp(fecha_dato) + pd.Timedelta(days=1)
    if "pronostico" in clima and (clima["fecha"] == destino).any():
        return destino, True
    observado = clima[~clima["pronostico"].astype(bool)] if "pronostico" in clima else clima
    return min(pd.Timestamp(fecha_dato), pd.Timestamp(observado["fecha"].max())), False


def comunas_pais(riesgo: pd.DataFrame, condiciones: pd.DataFrame, nombres: dict[str, str], regiones: dict[str, str],
                 dias_fuego: dict[str, pd.Series], fecha_dato: pd.Timestamp, fecha_clima: pd.Timestamp | None,
                 ahora: str, inicio_datos: pd.Timestamp = INICIO_DATOS, clima_pronostico: bool = False) -> dict:
    """Contenido de comunas.json.

    `riesgo`: riesgo.parquet (region_id, valido_para, horizonte_horas, prob_foco, nivel); se usa el último día.
    `condiciones`: salida de condiciones_clima para `fecha_clima` (una fila por comuna; puede faltar alguna).
    `nombres` y `regiones`: nombre de la comuna y de su región por código de comuna.
    `dias_fuego`: por comuna, las fechas con focos de incendio (sin las fuentes persistentes conocidas).
    `fecha_dato`: último día con focos (el día anterior al riesgo).
    `clima_pronostico`: True si `condiciones` son del pronóstico del día que se predice (fecha_clima_a_mostrar).
    """
    r = riesgo[riesgo["valido_para"] == riesgo["valido_para"].max()]
    codigos = sorted(r["region_id"].astype(str).unique())
    cond_map = dict(zip(condiciones["region_id"], condiciones["condiciones"])) if len(condiciones) else {}
    textos = {k: v["texto"] for k, v in CONDICIONES.items()}
    mes = pd.Timestamp(r["valido_para"].max()).month
    vacia = pd.Series(dtype="datetime64[ns]")
    salida = []
    for reg in sorted({c[:2] for c in codigos}):   # la región define la regla de quemas
        cods = [c for c in codigos if c[:2] == reg]
        cond_reg = condiciones[condiciones["region_id"].isin(cods)] if len(condiciones) else condiciones
        for c in resumen_comunas(r, cond_reg, nombres, cods, reg):
            conds = list(cond_map.get(c["region_id"], []))
            c["region"] = regiones.get(c["region_id"])
            c["recomendaciones"] = {h: recomendaciones_completas([], v["nivel"], reg, conds) for h, v in c["riesgo"].items()}
            c.update(motivos_comuna(dias_fuego.get(c["region_id"], vacia), fecha_dato, mes, conds, textos, inicio_datos,
                                    ETIQUETA_CLIMA[clima_pronostico]))
            salida.append(c)
    return {
        "contrato": VERSION_CONTRATO, "ejemplo": False, "calculado_utc": ahora,
        "valido_para": pd.Timestamp(r["valido_para"].max()).strftime("%Y-%m-%d"),
        "ultimo_dato_focos": pd.Timestamp(fecha_dato).strftime("%Y-%m-%d"),
        "fecha_clima": None if fecha_clima is None else pd.Timestamp(fecha_clima).strftime("%Y-%m-%d"),
        "clima_pronostico": bool(clima_pronostico),  # aditivo (21-11-2026)
        "nota": NOTA_COMUNAS_PRONOSTICO if clima_pronostico else NOTA_COMUNAS,
        "comunas": salida,
    }
