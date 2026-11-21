"""Paso 8b: valida el riesgo con pronósticos REALES de Open-Meteo (no corre a diario).

La prueba del paso 8 le da al modelo el clima OBSERVADO de los días que predice (NASA POWER): es una cota superior.
Este paso mide qué queda con lo que de verdad hay al publicar, en 2024-2025 (desde enero de 2024 Open-Meteo archiva sus
pronósticos por plazo: Previous Runs API) y en las 80 comunas con más días con fuego en 2022-2025:

  como antes            el clima del día t es el de t-4 (NASA POWER llega con ~4 días de rezago; se repetía)
  power al día          NASA POWER del día t (cota del relleno)
  open-meteo al día     el clima del día t lo pone Open-Meteo (su corrida más reciente)
  con pronóstico        lo anterior + el pronóstico de Open-Meteo para t+1 (y t+2) emitido 1 (y 2) días antes
  pronóstico perfecto   NASA POWER del día y de los días siguientes (cota superior)

Modelos entrenados como en el paso 8 (2012-2019, calibración 2020-2021, mismas variables).

Entradas: focos_calidad.parquet, comunas.parquet, clima_diario.parquet; baja (y guarda en
data/raw/openmeteo_archivo/{region_id}.json) una petición por comuna: 2 años de 12 variables horarias ≈ 62 "llamadas"
de Open-Meteo cada una (~5.000 en total; el límite gratis es 10.000 al día). Lo ya bajado no se repite.
Salidas: ref/validacion_pronostico.json (versionada; la cita el paso 8) y docs/pronostico_validacion.md.

Uso:
    python scripts/08b_validar_pronostico.py
"""

from __future__ import annotations

import importlib
import json
import sys
import time
import warnings
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8")
warnings.filterwarnings("ignore")

import geopandas as gpd  # noqa: E402
import pandas as pd  # noqa: E402
import requests  # noqa: E402

from firecal import config  # noqa: E402
from firecal.ingest.clima import puntos_representativos  # noqa: E402
from firecal.ingest.pronostico import ATRIBUCION, VARIABLES_HORARIAS, horario_a_diario  # noqa: E402
from firecal.model.evaluar import metricas  # noqa: E402
from firecal.model.variables import (  # noqa: E402
    VARIABLES_CLIMATOLOGIA, VARIABLES_MODELO_CLIMA, VARIABLES_MODELO_FIRMS, VARIABLES_PRONOSTICO, agregar_climatologia,
    bloque_clima, completar_con_noaa20, derivar_clima, tabla_base, variables_futuro,
)
from firecal.reportes import tabla_md  # noqa: E402

r08 = importlib.import_module("08_riesgo")
URL_ARCHIVO = "https://previous-runs-api.open-meteo.com/v1/forecast"
CACHE = config.DATA_DIR / "raw" / "openmeteo_archivo"
DESDE, HASTA = "2024-01-01", "2025-12-31"
EVAL_DESDE, EVAL_HASTA = "2024-01-08", "2025-12-29"
N_COMUNAS = 80
PLAZOS = {0: "", 1: "_previous_day1", 2: "_previous_day2"}
BASE = VARIABLES_MODELO_FIRMS + VARIABLES_CLIMATOLOGIA + VARIABLES_MODELO_CLIMA
VARIANTES = {"climatologia": "Climatología (lo normal)", "como_antes": "Como antes (clima de hace 4 días)",
             "power_al_dia": "NASA POWER al día", "open_meteo_al_dia": "Open-Meteo al día",
             "con_pronostico": "Open-Meteo al día + su pronóstico", "pronostico_perfecto": "Pronóstico perfecto (cota)"}


def elegir_comunas(focos: pd.DataFrame) -> list[str]:
    f = focos[(focos["satelite"] == "SNPP") & focos["uso_base"] & focos["region_id"].notna()
              & (focos["fecha_local"] >= "2022-01-01") & (focos["fecha_local"] < "2026-01-01")]
    dias = f.assign(dia=f["fecha_local"].dt.normalize()).groupby("region_id")["dia"].nunique()
    return dias.sort_values(ascending=False).head(N_COMUNAS).index.astype(str).tolist()


def bajar_archivo(puntos: pd.DataFrame) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = "preaviso"
    variables = [f"{b}{suf}" for b in VARIABLES_HORARIAS for suf in PLAZOS.values()]
    for _, p in puntos.iterrows():
        destino = CACHE / f"{p['region_id']}.json"
        if destino.exists():
            continue
        params = {"latitude": round(p["lat"], 4), "longitude": round(p["lon"], 4), "hourly": ",".join(variables),
                  "start_date": DESDE, "end_date": HASTA, "timezone": "America/Santiago", "wind_speed_unit": "ms"}
        r = s.get(URL_ARCHIVO, params=params, timeout=180)
        if r.status_code != 200:
            raise RuntimeError(f"Open-Meteo respondió {r.status_code} para {p['region_id']}: {r.text[:200]}")
        destino.write_text(r.text, encoding="utf-8")
        print(f"  bajado {p['region_id']}", flush=True)
        time.sleep(2)


def leer_archivo(comunas: list[str]) -> pd.DataFrame:
    """Diario por comuna y plazo (0 = corrida del día, 1 y 2 = emitido 1 y 2 días antes)."""
    partes = []
    for r in comunas:
        h = pd.DataFrame(json.loads((CACHE / f"{r}.json").read_text(encoding="utf-8"))["hourly"])
        for plazo, suf in PLAZOS.items():
            cols = {f"{b}{suf}": b for b in VARIABLES_HORARIAS}
            d = horario_a_diario(h[["time", *cols]].rename(columns=cols))
            partes.append(d.assign(region_id=r, plazo=plazo))
    om = pd.concat(partes, ignore_index=True)
    om["region_id"] = om["region_id"].astype("string")
    return om


def entrenar(tabla, ent, cal, objetivo, dias, cols):
    margen = pd.Timedelta(days=dias - 1)
    con_y = tabla[objetivo].notna()
    E = tabla[ent & con_y & (tabla["fecha"] <= pd.Timestamp(r08.FIN_ENTRENAMIENTO) - margen)]
    C = tabla[cal & con_y & (tabla["fecha"] <= pd.Timestamp(r08.FIN_CALIBRACION) - margen)]
    m = r08.hgb().fit(E[cols], E[objetivo])
    iso = r08.calibrar(m.predict_proba(C[cols])[:, 1], C[objetivo])
    clim = E.groupby(["region_id", "mes"])[objetivo].mean().rename("c")
    return m, iso, clim


def main() -> int:
    t0 = time.time()
    focos = pd.read_parquet(config.INTERIM_DIR / "focos_calidad.parquet",
                            columns=["region_id", "fecha_local", "satelite", "uso_base", "frp"])
    elegidas = elegir_comunas(focos)
    comunas_gdf = gpd.read_parquet(config.INTERIM_DIR / "comunas.parquet")
    puntos = puntos_representativos(comunas_gdf)
    bajar_archivo(puntos[puntos["region_id"].isin(elegidas)])
    om = leer_archivo(elegidas)
    print(f"Archivo de Open-Meteo: {om['region_id'].nunique()} comunas ({time.time() - t0:.0f} s)")

    focos, _ = completar_con_noaa20(focos)
    clima = bloque_clima(config.INTERIM_DIR / "clima_diario.parquet")
    tabla = tabla_base(focos, comunas_gdf, r08.INICIO, HASTA)
    ent = tabla["fecha"] <= r08.FIN_ENTRENAMIENTO
    cal = (tabla["fecha"] > r08.FIN_ENTRENAMIENTO) & (tabla["fecha"] <= r08.FIN_CALIBRACION)
    tabla = agregar_climatologia(tabla, ent).merge(clima, on=["region_id", "fecha"], how="left")
    tabla = tabla.merge(variables_futuro(clima), on=["region_id", "fecha"], how="left")
    sub = tabla[tabla["region_id"].isin(elegidas) & tabla["fecha"].between(EVAL_DESDE, EVAL_HASTA)].copy()
    clima_cols = VARIABLES_MODELO_CLIMA

    # Como antes: clima de t-4
    rez = clima.assign(fecha=clima["fecha"] + pd.Timedelta(days=4))
    antes = sub.drop(columns=clima_cols).merge(rez[["region_id", "fecha", *clima_cols]], on=["region_id", "fecha"],
                                               how="left")
    # Open-Meteo al día (plazo 0, con su propia lluvia de 7 días)
    o0 = derivar_clima(om[om["plazo"] == 0].drop(columns="plazo"))
    om_dia = sub.drop(columns=clima_cols).merge(o0[["region_id", "fecha", *clima_cols]], on=["region_id", "fecha"],
                                                how="left")
    # + pronóstico: t+1 emitido 1 día antes, t+2 emitido 2 días antes
    dia = {k: om[om["plazo"] == k].drop(columns="plazo") for k in (1, 2)}
    f1 = variables_futuro(dia[1])[["region_id", "fecha", *VARIABLES_PRONOSTICO["y24"]]]
    d1 = dia[1].assign(fecha=dia[1]["fecha"] - pd.Timedelta(days=1)).rename(
        columns={"tmax": "t1", "hrmin": "h1", "viento_max": "v1", "precip": "p1"})
    d2 = dia[2].assign(fecha=dia[2]["fecha"] - pd.Timedelta(days=2)).rename(
        columns={"tmax": "t2", "hrmin": "h2", "viento_max": "v2", "precip": "p2"})
    f2 = d1.merge(d2, on=["region_id", "fecha"])
    f2 = pd.DataFrame({"region_id": f2["region_id"], "fecha": f2["fecha"],
                       "tmax_f2": f2[["t1", "t2"]].max(axis=1), "hrmin_f2": f2[["h1", "h2"]].min(axis=1),
                       "viento_f2": f2[["v1", "v2"]].max(axis=1), "precip_f2": f2["p1"] + f2["p2"]})
    fut_cols = VARIABLES_PRONOSTICO["y24"] + VARIABLES_PRONOSTICO["y48"]
    con_pron = om_dia.drop(columns=fut_cols).merge(f1, on=["region_id", "fecha"], how="left").merge(
        f2, on=["region_id", "fecha"], how="left")

    completas = (sub[clima_cols + fut_cols].notna().all(axis=1).to_numpy()
                 & antes[clima_cols].notna().all(axis=1).to_numpy()
                 & om_dia[clima_cols].notna().all(axis=1).to_numpy()
                 & con_pron[fut_cols].notna().all(axis=1).to_numpy())
    print(f"Filas de evaluación: {completas.sum():,} ({time.time() - t0:.0f} s)")

    resultado = {"generado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "periodo": f"{EVAL_DESDE[:4]}-{EVAL_HASTA[:4]}", "desde": EVAL_DESDE, "hasta": EVAL_HASTA,
                 "comunas": len(elegidas), "filas": int(completas.sum()), "fuente": ATRIBUCION, "horizontes": {}}
    for obj, dias, horas in (("y24", 1, "24"), ("y48", 2, "48")):
        y = pd.Series(sub.loc[completas, obj].to_numpy())
        m0, iso0, clim = entrenar(tabla, ent, cal, obj, dias, BASE)
        m1, iso1, _ = entrenar(tabla, ent, cal, obj, dias, BASE + VARIABLES_PRONOSTICO[obj])
        pc = sub.loc[completas, ["region_id", "mes"]].join(clim, on=["region_id", "mes"])["c"].to_numpy()
        pred = lambda m, iso, df, cols: iso.predict(m.predict_proba(df.loc[completas, cols])[:, 1])  # noqa: E731
        p = {"climatologia": pc, "como_antes": pred(m0, iso0, antes, BASE), "power_al_dia": pred(m0, iso0, sub, BASE),
             "open_meteo_al_dia": pred(m0, iso0, om_dia, BASE),
             "con_pronostico": pred(m1, iso1, con_pron, BASE + VARIABLES_PRONOSTICO[obj]),
             "pronostico_perfecto": pred(m1, iso1, sub, BASE + VARIABLES_PRONOSTICO[obj])}
        resultado["horizontes"][horas] = {
            k: {x: round(v, 4) for x, v in metricas(y, pr).items() if x in ("auc", "precision_media", "captura_top10",
                                                                             "tasa_base")} for k, pr in p.items()}
        print(f"{horas} h listo ({time.time() - t0:.0f} s)", flush=True)

    ruta_ref = config.RAIZ / "ref" / "validacion_pronostico.json"
    ruta_ref.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")

    comp = o0.merge(clima, on=["region_id", "fecha"], suffixes=("_om", "_power"))
    diag = pd.DataFrame({v: {"Open-Meteo (media)": comp[f"{v}_om"].mean(), "NASA POWER (media)": comp[f"{v}_power"].mean(),
                             "Correlación": comp[[f"{v}_om", f"{v}_power"]].corr().iloc[0, 1]}
                         for v in ["tmax", "hrmin", "viento_max", "precip"]}).T
    diag.index.name = "Variable"
    tablas = {}
    for horas, res in resultado["horizontes"].items():
        t = pd.DataFrame(res).T.rename(index=VARIANTES)[["auc", "precision_media", "captura_top10"]]
        t.columns = ["AUC", "Precisión media", "Captura top 10 %"]
        t.index.name = "Variante"
        tablas[horas] = t
    h24 = resultado["horizontes"]["24"]
    texto = f"""# Riesgo con el pronóstico del tiempo real (Open-Meteo)

Generado por `scripts/08b_validar_pronostico.py` el {resultado['generado_utc'][:10]}. Resultado versionado en
`ref/validacion_pronostico.json` (lo cita el paso 8).

## Por qué
El modelo de riesgo usa el clima del día (NASA POWER) y, desde la v4, el de los días que predice. NASA POWER llega con
~4 días de rezago y no tiene el futuro: al publicar se repetía el último clima disponible. Ahora Open-Meteo rellena el
rezago (su corrida más reciente) y pone el pronóstico de mañana y pasado mañana. La prueba del paso 8 usa el clima
observado de esos días (cota superior); aquí se mide con lo que de verdad hay al publicar.

## Cómo
- **Período:** {EVAL_DESDE} a {EVAL_HASTA} (Open-Meteo archiva sus pronósticos por plazo desde enero de 2024).
- **Comunas:** las {len(elegidas)} con más días con fuego en 2022-2025 ({resultado['filas']:,} días-comuna con todos los
  datos). Las métricas no son comparables con las del paso 8 (otras comunas y años), sí entre variantes.
- **Pronóstico:** Previous Runs API de Open-Meteo, variables horarias resumidas por día como en el paso 5e; t+1 emitido
  1 día antes y t+2 emitido 2 días antes (al publicar, a las ~08 de Chile, el de t+1 es del mismo día: algo mejor).
- **Modelos:** los mismos del paso 8 (entrenados 2012-2019 con NASA POWER, calibrados 2020-2021).

## 24 h
{tabla_md(tablas['24'], 3)}

## 48 h
{tabla_md(tablas['48'], 3)}

## Conclusión
- A 24 h, la precisión media de lo que se publica pasa de **{h24['como_antes']['precision_media']:.3f}** (clima de hace 4
  días) a **{h24['con_pronostico']['precision_media']:.3f}** con el relleno y el pronóstico de Open-Meteo (la cota con el
  clima observado es {h24['pronostico_perfecto']['precision_media']:.3f}).
- Open-Meteo y NASA POWER no miden igual (tabla de abajo), pero el modelo entrenado con NASA POWER funciona casi igual
  con Open-Meteo: no hizo falta corregir sesgos.
- A 7 días no se usa pronóstico: con el clima real de la semana la ventaja sobre la climatología solo sube de ×1,09 a
  ×1,14 (experimento del 21-11-2026, docs/decisiones.md).

## Open-Meteo vs NASA POWER el mismo día (comunas y días de la validación)
{tabla_md(diag, 2)}

Fuente: {ATRIBUCION}, https://open-meteo.com. NASA POWER: ver docs/fuentes.md.
"""
    (config.RAIZ / "docs" / "pronostico_validacion.md").write_text(texto, encoding="utf-8")
    print(f"Listo: {ruta_ref} y docs/pronostico_validacion.md ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
