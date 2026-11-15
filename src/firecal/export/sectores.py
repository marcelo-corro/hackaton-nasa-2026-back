"""Exportación del piloto de sectores (A+) al contrato del front v0.3. Forma exacta en contracts/README.md.

Funciones puras que devuelven diccionarios o textos; `scripts/13_exportar_sectores.py` los escribe en public/.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import mapping

from firecal.export.contrato import VERSION_CONTRATO
from firecal.sectores.recomendaciones import (
    FACTORES_EXPOSICION, FUENTES, RASGOS, RECOMENDACIONES, UMBRAL_BOSQUE, UMBRAL_HISTORIAL_DIAS, UMBRAL_INTERFAZ,
    UMBRAL_PASTIZAL, UMBRAL_PENDIENTE, recomendaciones_sector,
)

TOLERANCIA_SECTORES = 0.0002  # grados (~20 m)
DECIMALES = 5
ARCHIVOS_SECTORES = {
    "riesgo_48h": "riesgo/48h.json",
    "riesgo_7d": "riesgo/7d.json",
    "sectores": "sectores/{region_id}.geojson",
    "sectores_focos": "sectores/{region_id}_focos.csv",
    "alertas": "alertas/{codigo_region}.json",
    "recomendaciones": "recomendaciones.json",
}
NOMBRE_HORIZONTE = {24: "24 h", 48: "48 h", 168: "7 días"}
NOTA_HORIZONTE = {
    24: "Probabilidad de al menos un foco en la comuna mañana.",
    48: "Probabilidad de al menos un foco en la comuna mañana o pasado.",
    168: "Probabilidad de al menos un foco en la comuna en los próximos 7 días. Orientativa: a 7 días el modelo "
         "supera poco a la climatología (usa el clima observado, no un pronóstico).",
}


def _pct(x: object) -> float | None:
    return None if x is None or pd.isna(x) else round(100 * float(x), 1)


def _fecha(x: object) -> str | None:
    return None if x is None or pd.isna(x) else pd.Timestamp(x).strftime("%Y-%m-%d")


def riesgo_horizonte(riesgo: pd.DataFrame, horas: int, info: dict, calculado_utc: str) -> dict:
    """riesgo/48h.json o riesgo/7d.json: misma forma que riesgo/ultimo.json más ventana, umbrales y métricas."""
    r = riesgo[(riesgo["horizonte_horas"] == horas) & (riesgo["valido_para"] == riesgo["valido_para"].max())]
    r = r.sort_values("region_id")
    h = info["horizontes"][str(horas)]
    v = h["ventaja_sobre_climatologia"]
    return {
        "contrato": VERSION_CONTRATO, "ejemplo": False, "calculado_utc": calculado_utc,
        "valido_para": h["valido_desde"], "valido_hasta": h["valido_hasta"], "horizonte_horas": horas,
        "modelo": str(r["modelo"].iloc[0]) if len(r) else info["modelo"],
        "umbrales": h["umbrales"],
        "metricas": {"periodo_prueba": info["periodo_prueba"], **h["prueba_modelo"],
                     "precision_media_climatologia": h["prueba_climatologia"]["precision_media"],
                     "ventaja_sobre_climatologia": v},
        "orientativo": bool(v < 1.2),
        "nota": NOTA_HORIZONTE[horas],
        "items": [{"region_id": str(x.region_id), "prob_foco": round(float(x.prob_foco), 3),
                   "percentil": None if pd.isna(x.percentil) else round(float(x.percentil), 1),
                   "nivel": str(x.nivel)} for x in r.itertuples()],
    }


def sectores_geojson(sectores_comuna, niveles: dict[int, str], codigo_region: str) -> dict:
    """sectores/{region_id}.geojson: un Feature por sector, en WGS84, con rasgos, capas, historial y
    recomendaciones por horizonte (dependen del nivel de la comuna: `niveles` = {horas: nivel})."""
    g = sectores_comuna.to_crs("EPSG:4326")
    feats = []
    for s, geom in zip(g.itertuples(), g.geometry):
        geom = shapely.set_precision(geom.simplify(TOLERANCIA_SECTORES, preserve_topology=True), 10 ** -DECIMALES)
        rasgos = list(s.rasgos)
        feats.append({"type": "Feature", "geometry": mapping(geom), "properties": {
            "sector_id": s.sector_id, "region_id": s.region_id, "area_km2": round(float(s.area_km2), 3),
            "lat": float(s.lat), "lon": float(s.lon),
            "rasgos": rasgos, "exposicion": int(sum(r in rasgos for r in FACTORES_EXPOSICION)),
            "pct_interfaz": _pct(s.frac_wui), "pct_pastizal": _pct(s.frac_pastizal),
            "pct_bosque_matorral": _pct(s.frac_arboles + s.frac_matorral), "pct_cultivo": _pct(s.frac_cultivo),
            "pct_construido": _pct(s.frac_construido),
            "pendiente_media": None if pd.isna(s.pendiente_media) else round(float(s.pendiente_media), 1),
            "dias_con_fuego": int(s.dias_con_fuego), "focos": int(s.focos), "ultimo_fuego": _fecha(s.ultimo_fuego),
            "incendios_grandes": int(s.incendios_grandes), "mayor_incendio_focos": int(s.mayor_incendio_focos),
            "recomendaciones": {str(h): recomendaciones_sector(rasgos, n, codigo_region) for h, n in niveles.items()},
        }})
    return {"type": "FeatureCollection", "contrato": VERSION_CONTRATO, "ejemplo": False,
            "region_id": str(sectores_comuna["region_id"].iloc[0]), "features": feats}


def focos_sector_csv(focos: pd.DataFrame) -> str:
    """sectores/{region_id}_focos.csv: focos de incendio para el heatmap (sin fuentes persistentes)."""
    f = pd.DataFrame({
        "fecha": focos["fecha_local"].dt.strftime("%Y-%m-%d"),
        "lat": focos["lat"].round(4), "lon": focos["lon"].round(4), "frp": focos["frp"].round(1),
        "focos_incendio": focos["focos_incendio"].astype(int), "sector_id": focos["sector_id"],
    }).sort_values(["fecha", "lat", "lon"])
    return f.to_csv(index=False, lineterminator="\n")


def _item_alerta(s: pd.Series, codigo_region: str) -> dict:
    return {"sector_id": s["sector_id"], "region_id": s["region_id"], "comuna": s["comuna"],
            "nivel_comuna": s["nivel"], "prob_foco_comuna": round(float(s["prob_foco"]), 3),
            "exposicion": int(s["exposicion"]), "rasgos": list(s["rasgos"]),
            "lat": float(s["lat"]), "lon": float(s["lon"]),
            "recomendaciones": recomendaciones_sector(list(s["rasgos"]), s["nivel"], codigo_region)}


def alertas_region(codigo_region: str, por_horizonte: dict[int, pd.DataFrame], comunas: list[dict],
                   calculado_utc: str, caso: dict | None = None) -> dict:
    """alertas/{codigo_region}.json: sectores a priorizar por horizonte y resumen por comuna."""
    return {
        "contrato": VERSION_CONTRATO, "ejemplo": False, "calculado_utc": calculado_utc,
        "codigo_region": codigo_region,
        "nota": "Orden de prioridad: comunas con mayor riesgo y, dentro de ellas, sectores con más factores de "
                "exposición (interfaz, vegetación, pendiente, historial). No es la probabilidad de que ese sector se "
                "queme.",
        "horizontes": {str(h): [_item_alerta(s, codigo_region) for _, s in d.iterrows()]
                       for h, d in por_horizonte.items()},
        "comunas": comunas,
        "caso": caso,
    }


def catalogo_recomendaciones() -> dict:
    """recomendaciones.json: textos de rasgos y recomendaciones, fuentes oficiales y umbrales."""
    return {
        "contrato": VERSION_CONTRATO, "ejemplo": False,
        "rasgos": RASGOS,
        "recomendaciones": {k: {"texto": v["texto"], "fuente": v["fuente"]} for k, v in RECOMENDACIONES.items()},
        "fuentes": FUENTES,
        "umbrales_rasgos": {"interfaz_pct": 100 * UMBRAL_INTERFAZ, "pastizal_pct": 100 * UMBRAL_PASTIZAL,
                            "bosque_matorral_pct": 100 * UMBRAL_BOSQUE, "pendiente_grados": UMBRAL_PENDIENTE,
                            "historial_dias": UMBRAL_HISTORIAL_DIAS},
        "fuentes_capas": {
            "vegetacion": "ESA WorldCover 2021 v200 (10 m)",
            "interfaz": "Schug et al. (2023), mapa global de interfaz urbano-forestal (10 m, ~2020)",
            "pendiente": "Copernicus DEM GLO-30 (30 m)",
            "focos": "NASA FIRMS, VIIRS Suomi NPP 2012-2025",
        },
    }


def niveles_por_comuna(riesgo: pd.DataFrame) -> dict[str, dict[int, str]]:
    """{region_id: {horas: nivel}} del valido_para más reciente."""
    r = riesgo[riesgo["valido_para"] == riesgo["valido_para"].max()]
    out: dict[str, dict[int, str]] = {}
    for x in r.itertuples():
        out.setdefault(str(x.region_id), {})[int(x.horizonte_horas)] = str(x.nivel)
    return out


def resumen_comunas(riesgo: pd.DataFrame, condiciones: pd.DataFrame, nombres: dict[str, str],
                    codigos: list[str]) -> list[dict]:
    """Por comuna del piloto: riesgo en cada horizonte y condiciones del clima observado del último día."""
    r = riesgo[riesgo["valido_para"] == riesgo["valido_para"].max()]
    cond = condiciones.set_index("region_id") if len(condiciones) else pd.DataFrame()
    out = []
    for rid in codigos:
        rr = r[r["region_id"] == rid]
        c = cond.loc[rid].to_dict() if rid in cond.index else None
        if c is not None:
            c = {k: (v if not isinstance(v, (np.floating, np.integer)) else v.item()) for k, v in c.items()}
        out.append({"region_id": rid, "nombre": nombres.get(rid),
                    "riesgo": {str(int(x.horizonte_horas)): {"prob_foco": round(float(x.prob_foco), 3),
                                                             "nivel": str(x.nivel)} for x in rr.itertuples()},
                    "clima_ultimo_dia": c})
    return out
