"""Paso 13 (sectores, piloto A+): agrega a public/ los archivos de sectores, alertas, riesgo a 48 h y 7 días.

Se corre DESPUÉS de 09_exportar.py (que vacía y rehace public/) y ANTES de 10_publicar.py. Agrega al manifest las
rutas nuevas y deja el contrato en 0.3 (cambio aditivo: los archivos de la v0.2 no cambian de forma).

Entradas: data/processed/sectores_<región>.parquet y _focos.parquet (paso 12), riesgo.parquet,
riesgo_horizontes.json y riesgo_backtest.parquet (paso 8), data/interim/clima_diario.parquet.

Uso:
    python scripts/13_exportar_sectores.py            # región 05 (Valparaíso)
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from firecal import config  # noqa: E402
from firecal.contratos import validar_riesgo  # noqa: E402
from firecal.export.contrato import VERSION_CONTRATO  # noqa: E402
from firecal.export.sectores import (  # noqa: E402
    ARCHIVOS_SECTORES, alertas_region, catalogo_recomendaciones, focos_sector_csv, niveles_por_comuna,
    resumen_comunas, riesgo_horizonte, sectores_geojson,
)
from firecal.model.variables import bloque_clima  # noqa: E402
from firecal.sectores.recomendaciones import (  # noqa: E402
    condiciones_clima, prioridad_alertas, rasgos_sector, recomendaciones_completas,
)

CASO_FECHA = "2024-02-04"  # incendio de Viña del Mar, Quilpué y Villa Alemana, activo desde el 2 de febrero


def _json(ruta: Path, datos: dict) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="05")
    args = parser.parse_args()
    publico = config.PUBLIC_DIR
    ruta_manifest = publico / "manifest.json"
    if not ruta_manifest.exists():
        print("Falta public/manifest.json: corre primero scripts/09_exportar.py.")
        return 1

    pr = config.PROCESSED_DIR
    sectores = gpd.read_parquet(pr / f"sectores_{args.region}.parquet")
    focos = pd.read_parquet(pr / f"sectores_{args.region}_focos.parquet")
    riesgo = pd.read_parquet(pr / "riesgo.parquet")
    validar_riesgo(riesgo)
    info = json.loads((pr / "riesgo_horizontes.json").read_text(encoding="utf-8"))
    backtest = pd.read_parquet(pr / "riesgo_backtest.parquet")
    clima = bloque_clima(config.INTERIM_DIR / "clima_diario.parquet")
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sectores["rasgos"] = rasgos_sector(sectores)
    ruta_b = pr / f"sectores_{args.region}_b.parquet"
    modelo_b = None
    if ruta_b.exists():  # modelo B (paso 12c): probabilidad dentro de la comuna y de incendio grande
        sectores = sectores.merge(pd.read_parquet(ruta_b), on="sector_id", how="left")
        sectores["percentil_en_comuna"] = 100 * sectores.groupby("region_id")["prob_condicional"].rank(pct=True)
        modelo_b = json.loads((pr / f"modelo_b_{args.region}.json").read_text(encoding="utf-8"))
    codigos = sorted(sectores["region_id"].unique())
    nombres = dict(zip(sectores["region_id"], sectores["comuna"]))
    niveles = niveles_por_comuna(riesgo)

    # Riesgo a 48 h y 7 días (todas las comunas del país, como riesgo/ultimo.json)
    for horas, clave in ((48, "riesgo_48h"), (168, "riesgo_7d")):
        _json(publico / ARCHIVOS_SECTORES[clave], riesgo_horizonte(riesgo, horas, info, ahora))

    # Clima observado del último día por comuna (condiciones y recomendaciones por clima)
    ultimo = riesgo[riesgo["valido_para"] == riesgo["valido_para"].max()]
    fecha_clima = pd.Timestamp(ultimo["valido_para"].max()) - pd.Timedelta(days=1)
    clima_region = clima[clima["region_id"].isin(codigos)] if clima is not None else None
    cond = condiciones_clima(clima_region, fecha_clima) if clima_region is not None else pd.DataFrame()
    cond_map = dict(zip(cond["region_id"], cond["condiciones"])) if len(cond) else {}

    # Sectores y focos por comuna
    ult24 = riesgo[(riesgo["valido_para"] == riesgo["valido_para"].max()) & (riesgo["horizonte_horas"] == 24)]
    prob24 = dict(zip(ult24["region_id"].astype(str), ult24["prob_foco"].astype(float)))
    for rid in codigos:
        s = sectores[sectores["region_id"] == rid]
        _json(publico / ARCHIVOS_SECTORES["sectores"].format(region_id=rid),
              sectores_geojson(s, niveles.get(rid, {}), args.region, cond_map.get(rid, []), prob24.get(rid)))
        f = focos[focos["region_id"].astype(str) == rid]
        ruta = publico / ARCHIVOS_SECTORES["sectores_focos"].format(region_id=rid)
        ruta.write_text(focos_sector_csv(f), encoding="utf-8")

    # Alertas por horizonte (valido_para más reciente)
    por_horizonte = {h: prioridad_alertas(sectores, ultimo[ultimo["horizonte_horas"] == h]) for h in (24, 48, 168)}
    comunas = resumen_comunas(riesgo, cond, nombres, codigos, args.region)

    # Caso histórico: cómo se habría visto la lista de prioridad (24 h) y qué pasó ese día
    bt = backtest[(backtest["valido_para"] == pd.Timestamp(CASO_FECHA)) & backtest["region_id"].isin(codigos)]
    bt = bt.rename(columns={"prob": "prob_foco"})
    # sin fuga: el historial del caso se cuenta solo con focos ANTERIORES al día evaluado
    previo = focos[focos["fecha_local"].dt.normalize() < pd.Timestamp(CASO_FECHA)]
    s_caso = sectores.copy()
    s_caso["dias_con_fuego"] = s_caso["sector_id"].map(
        previo.assign(d=previo["fecha_local"].dt.normalize()).groupby("sector_id")["d"].nunique()).fillna(0)
    s_caso["incendios_grandes"] = s_caso["sector_id"].map(
        previo[previo["focos_incendio"] > 10].groupby("sector_id")["evento"].nunique()).fillna(0)
    s_caso["rasgos"] = rasgos_sector(s_caso)
    lista_caso = prioridad_alertas(s_caso, bt)
    con_fuego = set(focos.loc[focos["fecha_local"].dt.normalize() == pd.Timestamp(CASO_FECHA), "sector_id"])
    vispera = pd.Timestamp(CASO_FECHA) - pd.Timedelta(days=1)
    cond_caso = condiciones_clima(clima_region, vispera) if clima_region is not None else pd.DataFrame()
    cond_caso_map = dict(zip(cond_caso["region_id"], cond_caso["condiciones"])) if len(cond_caso) else {}
    caso = {
        "fecha": CASO_FECHA, "horizonte_horas": 24,
        "descripcion": "Incendio de Viña del Mar, Quilpué y Villa Alemana (activo desde el 2 de febrero de 2024). "
                       "Lista de prioridad que habría dado el sistema con los datos del día anterior.",
        "items": [{"sector_id": x.sector_id, "comuna": x.comuna, "nivel_comuna": x.nivel,
                   "prob_foco_comuna": round(float(x.prob_foco), 3), "exposicion": int(x.exposicion),
                   "rasgos": list(x.rasgos), "condiciones_clima": list(cond_caso_map.get(x.region_id, [])),
                   "recomendaciones": recomendaciones_completas(list(x.rasgos), x.nivel, args.region,
                                                                cond_caso_map.get(x.region_id, [])),
                   "tuvo_fuego_ese_dia": x.sector_id in con_fuego}
                  for x in lista_caso.itertuples()],
        "sectores_con_fuego_ese_dia": sorted(con_fuego),
    }
    _json(publico / ARCHIVOS_SECTORES["alertas"].format(codigo_region=args.region),
          alertas_region(args.region, por_horizonte, comunas, ahora, caso, cond_map))
    _json(publico / ARCHIVOS_SECTORES["recomendaciones"], catalogo_recomendaciones())

    # Manifest: rutas nuevas y lista de comunas con sectores
    m = json.loads(ruta_manifest.read_text(encoding="utf-8"))
    m["contrato"] = VERSION_CONTRATO
    m["archivos"].update(ARCHIVOS_SECTORES)
    m["sectores"] = {"codigo_region": args.region, "regiones": codigos}
    if modelo_b:
        cal, pru = modelo_b["calibracion"], modelo_b.get("prueba", {})
        orden_a = "Orden A+ (historial, luego interfaz)"
        m["sectores"]["modelo_b"] = {
            "modelo": modelo_b["prediccion"]["modelo"], "fecha_prediccion": modelo_b["prediccion"]["fecha"],
            "captura_top10_prueba": {"modelo_b": pru.get("Modelo B (promedio)", {}).get("todos"),
                                     "orden_a": pru.get(orden_a, {}).get("todos"), "azar": 10.0},
            "auc_incendio_grande_prueba": modelo_b["grande"].get("prueba", {}).get("todos", {}).get("auc"),
            "auc_incendio_grande_ignicion_prueba": modelo_b["grande"].get("prueba", {}).get("ignicion", {}).get("auc"),
            "nota": "Prueba 2022-2025: el 10 % de sectores con mayor probabilidad de cada comuna concentró el "
                    f"{pru.get('Modelo B (promedio)', {}).get('todos', 0):.0f} % del fuego (azar 10 %). Ordena mejor "
                    "cuando ya hay fuego cerca; con fuego nuevo no supera al orden por historial. La probabilidad de "
                    "incendio grande distingue bien (AUC "
                    f"{modelo_b['grande'].get('prueba', {}).get('ignicion', {}).get('auc', 0):.2f} en fuegos nuevos).",
        }
    ruta_manifest.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

    tam = sum(p.stat().st_size for d in ("sectores", "alertas") for p in (publico / d).glob("*")) / 1e6
    print(f"Sectores: {len(codigos)} comunas, {len(sectores):,} sectores; {tam:.1f} MB en sectores/ y alertas/")
    for h, d in por_horizonte.items():
        print(f"  alertas {h} h: {len(d)} sectores en {d['region_id'].nunique()} comunas; niveles {d['nivel'].value_counts().to_dict()}")
    acierto = sum(i["tuvo_fuego_ese_dia"] for i in caso["items"])
    print(f"  caso {CASO_FECHA}: {len(caso['items'])} sectores en la lista, {acierto} tuvieron focos ese día; "
          f"{len(con_fuego)} sectores con focos en total")
    print(f"  clima {fecha_clima.date()}: condiciones por comuna {dict(cond_map)}")
    print(f"  clima víspera del caso ({vispera.date()}): " + str({k: v for k, v in cond_caso_map.items() if v}))
    print(f"Manifest actualizado a contrato {VERSION_CONTRATO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
