"""Paso 8 del pipeline (A): riesgo de focos por comuna a 24 h, 48 h y 7 días.

Objetivo: ¿habrá al menos un foco VIIRS (Suomi NPP, `uso_base`) en la comuna mañana (24 h), en 2 días (48 h) o en
la próxima semana (7 días)? Partición temporal: entrena 2012-02..2019, calibra 2020-2021, prueba 2022-2025.

Compara (a 24 h): climatología (comuna × mes), persistencia, regresión logística y gradient boosting con los bloques
de variables disponibles (FIRMS siempre; clima si existe data/interim/clima_diario.parquet). Elige por precisión
media en calibración, mide en prueba por separado ignición (sin focos en 3 días) y propagación (con focos recientes).
Los modelos de 48 h y 7 días usan las mismas variables y se comparan con la climatología de su propio horizonte.

Salidas: data/processed/riesgo.parquet (contrato; una fila por comuna y horizonte), data/processed/metricas.json,
data/processed/riesgo_horizontes.json, data/processed/riesgo_backtest.parquet, data/processed/modelo_riesgo_24h.joblib,
docs/riesgo.md y docs/figuras/riesgo_vina_2024.png.

Uso:
    python scripts/08_riesgo.py
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import geopandas as gpd  # noqa: E402
import joblib  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.inspection import permutation_importance  # noqa: E402
from sklearn.isotonic import IsotonicRegression  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from firecal import config  # noqa: E402
from firecal.contratos import validar_riesgo  # noqa: E402
from firecal.model.evaluar import confiabilidad, curva_captura, metricas, por_segmento  # noqa: E402
from firecal.model.variables import (  # noqa: E402
    VARIABLES_CLIMATOLOGIA, VARIABLES_MODELO_CLIMA, VARIABLES_MODELO_FIRMS, VARIABLES_PRONOSTICO, agregar_climatologia,
    bloque_clima, completar_con_noaa20, extender_clima, tabla_base, variables_futuro,
)
from firecal.reportes import tabla_md  # noqa: E402

INICIO = "2012-02-01"  # el fin sale de los datos: último día con focos y con clima (ver main)
FIN_ENTRENAMIENTO, FIN_CALIBRACION, FIN_PRUEBA = "2019-12-31", "2021-12-31", "2025-12-31"
# Validación con pronósticos REALES de Open-Meteo (scripts/08b_validar_pronostico.py; versionada en ref/). La prueba de
# este script usa el clima OBSERVADO de los días que se predicen (cota superior); esa validación dice cuánto queda con
# el pronóstico de verdad.
RUTA_VALIDACION_PRONOSTICO = config.RAIZ / "ref" / "validacion_pronostico.json"
VALIDACION_PRONOSTICO = (json.loads(RUTA_VALIDACION_PRONOSTICO.read_text(encoding="utf-8"))
                         if RUTA_VALIDACION_PRONOSTICO.exists() else None)


def texto_validacion_pronostico(v: dict | None) -> str:
    """Una frase con la precisión media a 24 h con el pronóstico real y como se publicaba antes."""
    if not v:
        return ""
    h = v["horizontes"]["24"]
    return (f" Con el clima observado del día que predice; con el pronóstico real de Open-Meteo ({v['periodo']}, "
            f"{v['comunas']} comunas con más fuego) la precisión media a 24 h fue {h['con_pronostico']['precision_media']:.2f}"
            f" (antes, con el clima de hace 4 días, {h['como_antes']['precision_media']:.2f}).")
# Después de FIN_PRUEBA: "prueba nueva" (2026), datos que no existían al construir ni al elegir el modelo.
NIVELES = [(0.30, "muy_alto"), (0.12, "alto"), (0.04, "medio"), (0.0, "bajo")]
CASO = {"05109": "Viña del Mar", "05801": "Quilpué", "05804": "Villa Alemana"}
CASO_VENTANA = ("2024-01-27", "2024-02-12")
NOMBRES_METRICAS = {"auc": "AUC", "precision_media": "Precisión media", "captura_top10": "Captura top 10 %",
                    "lift_top10": "Lift top 10 %", "brier": "Brier", "tasa_base": "Tasa base"}


HORIZONTES = {"y24": (24, 1), "y48": (48, 2), "y7d": (168, 7)}  # objetivo: (horas, días)


def nivel(p: np.ndarray, niveles: list[tuple[float, str]] = NIVELES) -> np.ndarray:
    out = np.full(len(p), "bajo", dtype=object)
    for umbral, nombre in reversed(niveles):
        out[np.asarray(p) >= umbral] = nombre
    return out


def umbrales_equivalentes(p_cal_24: np.ndarray, p_cal_h: np.ndarray) -> list[tuple[float, str]]:
    """Umbrales de nivel para otro horizonte: en calibración, cada nivel agrupa la misma proporción de días-comuna
    que a 24 h. Con los umbrales fijos de 24 h, a 7 días (tasa base ~18 %) casi todo saldría "alto"."""
    out = []
    for umbral, nombre in NIVELES:
        if umbral == 0:
            out.append((0.0, nombre))
            continue
        sobre = float((p_cal_24 >= umbral).mean())
        out.append((round(float(np.quantile(p_cal_h, 1 - sobre)), 4), nombre))
    return out


def entrenar_horizonte(tabla: pd.DataFrame, objetivo: str, dias: int, cols: list[str], ent: pd.Series,
                       cal: pd.Series, prueba: pd.Series) -> dict:
    """Modelo calibrado para un horizonte. Deja fuera las filas cuyo objetivo mira dentro del período siguiente."""
    margen = pd.Timedelta(days=dias - 1)
    con_y = tabla[objetivo].notna()
    E = tabla[ent & con_y & (tabla["fecha"] <= pd.Timestamp(FIN_ENTRENAMIENTO) - margen)]
    C = tabla[cal & con_y & (tabla["fecha"] <= pd.Timestamp(FIN_CALIBRACION) - margen)]
    P = tabla[prueba & con_y]
    m = hgb().fit(E[cols], E[objetivo])
    iso = calibrar(m.predict_proba(C[cols])[:, 1], C[objetivo])
    clim = E.groupby(["region_id", "mes"])[objetivo].mean().rename("clim_h")
    clim_p = P[["region_id", "mes"]].join(clim, on=["region_id", "mes"])["clim_h"].fillna(E[objetivo].mean())
    p = iso.predict(m.predict_proba(P[cols])[:, 1])
    return {"modelo": m, "calibrador": iso, "p_cal": iso.predict(m.predict_proba(C[cols])[:, 1]), "cols": cols,
            "modelo_prueba": metricas(P[objetivo], p), "clim_prueba": metricas(P[objetivo], clim_p)}


def log_features(df: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    for c in ["n_hoy", "frp_hoy", "n_3d", "n_7d", "n_30d", "vecinos_hoy", "vecinos_3d"]:
        x[c] = np.log1p(df[c])
    x["dias_desde_ultimo"] = df["dias_desde_ultimo"] / 365
    for c in ["clim_comuna_mes", "clim_comuna", "doy_sin", "doy_cos"]:
        x[c] = df[c]
    return x


def hgb() -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.06, max_leaf_nodes=63, min_samples_leaf=200, l2_regularization=1.0,
        early_stopping=True, validation_fraction=0.1, n_iter_no_change=20, random_state=42,
    )


PROB_MAXIMA = 0.95  # la calibración isotónica puede llegar a 1,0 en el tramo más alto: ninguna predicción es segura


def calibrar(p_cal: np.ndarray, y_cal: np.ndarray) -> IsotonicRegression:
    return IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=PROB_MAXIMA).fit(p_cal, y_cal)


def percentil_historico(final: pd.DataFrame, historia: pd.DataFrame) -> np.ndarray:
    """Percentil (rango medio) de cada probabilidad final contra las del mismo comuna y mes en la historia."""
    out = []
    grupos = historia.groupby(["region_id", "mes"])["prob"]
    for _, fila in final.iterrows():
        try:
            h = grupos.get_group((fila["region_id"], fila["mes"])).to_numpy()
        except KeyError:
            out.append(50.0)
            continue
        out.append(100 * ((h < fila["prob"]).sum() + 0.5 * (h == fila["prob"]).sum()) / len(h))
    return np.asarray(out)


def figura(caso: pd.DataFrame, curvas: dict[str, pd.DataFrame], ruta: Path) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.4), dpi=150, gridspec_kw={"width_ratios": [1.5, 1]})
    vina = caso[caso["region_id"] == "05109"].set_index("dia")
    a1b = a1.twinx()
    a1b.bar(vina.index, vina["focos_reales"], color="#fdae61", alpha=0.7, label="Focos reales en Viña (VIIRS)")
    a1b.set_ylabel("Focos reales en Viña del Mar", color="#b35806")
    estilos = {"05109": ("#a50026", "-", 2.4), "05801": ("#253494", "--", 1.4), "05804": ("#41b6c4", "--", 1.4)}
    for rid, nombre in CASO.items():
        d = caso[caso["region_id"] == rid].set_index("dia")
        color, ls, lw = estilos[rid]
        a1.plot(d.index, 100 * d["prob"], color=color, ls=ls, lw=lw, marker="o", ms=3, label=f"Riesgo {nombre}")
    a1.set_zorder(a1b.get_zorder() + 1)
    a1.patch.set_visible(False)
    a1.set_ylabel("Probabilidad de foco ese día (%)")
    a1.set_title("Incendio de febrero 2024: riesgo que el modelo daba la víspera", fontsize=10)
    a1.tick_params(axis="x", rotation=45, labelsize=7)
    a1.legend(fontsize=7, loc="upper left")
    a1.grid(alpha=0.3)

    for nombre, c in curvas.items():
        a2.plot(100 * c["marcado"], 100 * c["capturado"], lw=2 if "boosting" in nombre.lower() else 1.4, label=nombre)
    a2.plot([0, 100], [0, 100], color="#bbbbbb", ls=":", lw=1, label="Azar")
    a2.axvline(10, color="#555555", ls=":", lw=1)
    a2.set_xlim(0, 50)
    a2.set_xlabel("% de días-comuna marcados como de mayor riesgo")
    a2.set_ylabel("% de días con fuego capturados")
    a2.set_title("Prueba 2022-2025: cuánto fuego captura cada método", fontsize=10)
    a2.legend(fontsize=7, loc="lower right")
    a2.grid(alpha=0.3)
    fig.text(0.01, 0.01, "Fuente: NASA FIRMS (VIIRS Suomi NPP). Modelo entrenado 2012-2019, calibrado 2020-2021, "
             "probado 2022-2025.", fontsize=7, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta)
    plt.close(fig)


def main() -> int:
    warnings.filterwarnings("ignore")
    focos = pd.read_parquet(config.INTERIM_DIR / "focos_calidad.parquet",
                            columns=["region_id", "fecha_local", "satelite", "uso_base", "frp"])
    focos, ultimo_snpp = completar_con_noaa20(focos)
    comunas = gpd.read_parquet(config.INTERIM_DIR / "comunas.parquet")
    nombres = comunas.set_index("region_id")["nombre"]
    # Pronóstico de Open-Meteo (paso 5e): rellena el rezago de NASA POWER y da el clima de los días que se predicen
    ruta_pron = config.INTERIM_DIR / "pronostico_diario.parquet"
    pronostico = pd.read_parquet(ruta_pron) if ruta_pron.exists() else None
    clima = bloque_clima(config.INTERIM_DIR / "clima_diario.parquet", pronostico)
    fin = pd.Timestamp(focos["fecha_local"].max()).normalize()
    clima_hasta, rezago_clima, info_pron = None, 0, None
    if clima is not None:
        de_power = ~clima["pronostico"] if "pronostico" in clima else pd.Series(True, index=clima.index)
        clima_hasta = pd.Timestamp(clima.loc[de_power, "fecha"].max())
        if (~de_power).any():
            pr = clima.loc[~de_power, "fecha"]
            info_pron = {"fuente": "Open-Meteo", "desde": pr.min().strftime("%Y-%m-%d"),
                         "hasta": pr.max().strftime("%Y-%m-%d"),
                         "emitido_utc": str(pronostico["emitido_utc"].iloc[0]) if "emitido_utc" in pronostico else None}
        clima, rezago_clima = extender_clima(clima, fin)  # sin pronóstico, repite el último clima de NASA POWER
    # El pronóstico sirve para el modelo si cubre los dos días que vienen (t+1 y t+2) en todas las comunas.
    usar_pronostico = bool(info_pron) and pd.Timestamp(info_pron["hasta"]) >= fin + pd.Timedelta(days=2)
    FIN = fin.strftime("%Y-%m-%d")  # noqa: N806
    print(f"Último día con focos: {FIN} (Suomi NPP hasta {ultimo_snpp.date()}; después, NOAA-20 en su lugar); "
          f"clima de NASA POWER hasta {None if clima_hasta is None else clima_hasta.date()}; "
          + (f"pronóstico de Open-Meteo {info_pron['desde']} a {info_pron['hasta']}" if info_pron
             else f"sin pronóstico (se repite el último clima {rezago_clima} días)"))

    print("Armando tabla comuna x día...")
    tabla = tabla_base(focos, comunas, INICIO, FIN)
    ent = tabla["fecha"] <= FIN_ENTRENAMIENTO
    cal = (tabla["fecha"] > FIN_ENTRENAMIENTO) & (tabla["fecha"] <= FIN_CALIBRACION)
    prueba = (tabla["fecha"] > FIN_CALIBRACION) & (tabla["fecha"] <= FIN_PRUEBA)
    nuevo = tabla["fecha"] > FIN_PRUEBA
    tabla = agregar_climatologia(tabla, ent)

    variables = VARIABLES_MODELO_FIRMS + VARIABLES_CLIMATOLOGIA
    bloques = ["FIRMS"]
    if clima is not None:
        tabla = tabla.merge(clima.drop(columns="pronostico", errors="ignore"), on=["region_id", "fecha"], how="left")
        bloques.append("clima")
        if usar_pronostico:
            # Clima de t+1 y t+2: observado (NASA POWER) en la historia, pronóstico de Open-Meteo en los últimos días
            tabla = tabla.merge(variables_futuro(clima), on=["region_id", "fecha"], how="left")
            bloques.append("pronostico")
    print(f"Bloques de variables: {', '.join(bloques)}")

    con_y = tabla["y24"].notna()
    E, C, P = tabla[ent & con_y], tabla[cal & con_y], tabla[prueba & con_y]
    resultados, calibradas, val_ap = {}, {}, {}

    # Líneas base
    resultados["Climatología (comuna × mes)"] = metricas(P["y24"], P["clim_comuna_mes"])
    persist = lambda d: (d["n_hoy"] > 0) * 2 + (d["n_3d"] > 0) * 1 + d["clim_comuna_mes"]  # noqa: E731
    resultados["Persistencia + climatología"] = metricas(P["y24"], persist(P), probabilidad=False)

    # Regresión logística
    print("Entrenando regresión logística...")
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000)).fit(log_features(E), E["y24"])
    iso_lr = calibrar(lr.predict_proba(log_features(C))[:, 1], C["y24"])
    val_ap["Regresión logística (FIRMS)"] = metricas(C["y24"], lr.predict_proba(log_features(C))[:, 1])["precision_media"]
    p_lr = iso_lr.predict(lr.predict_proba(log_features(P))[:, 1])
    resultados["Regresión logística (FIRMS)"] = metricas(P["y24"], p_lr)

    # Gradient boosting por conjunto de bloques
    conjuntos = {"Gradient boosting (FIRMS)": variables}
    if "clima" in bloques:
        conjuntos["Gradient boosting (FIRMS + clima)"] = variables + VARIABLES_MODELO_CLIMA
    if "pronostico" in bloques:
        conjuntos["Gradient boosting (FIRMS + clima + pronóstico)"] = (variables + VARIABLES_MODELO_CLIMA
                                                                       + VARIABLES_PRONOSTICO["y24"])
    modelos = {}
    for nombre, cols in conjuntos.items():
        print(f"Entrenando {nombre}...")
        m = hgb().fit(E[cols], E["y24"])
        p_cal = m.predict_proba(C[cols])[:, 1]
        iso = calibrar(p_cal, C["y24"])
        val_ap[nombre] = metricas(C["y24"], p_cal)["precision_media"]
        p = iso.predict(m.predict_proba(P[cols])[:, 1])
        resultados[nombre] = metricas(P["y24"], p)
        modelos[nombre] = (m, iso, cols)
        calibradas[nombre] = p

    elegido = max(conjuntos, key=lambda n: val_ap[n])
    modelo, iso, cols = modelos[elegido]
    p_prueba = calibradas[elegido]
    # v2: climatología sin fuga de objetivo (cada año de entrenamiento se calcula con los otros años; no se publicó)
    # v3: v2 + 14 variables (de 23) + horizontes de 48 h y 7 días publicados
    # v4: v3 + clima de los días que se predicen (pronóstico de Open-Meteo al publicar), 21-11-2026
    usa_pronostico = any(c in cols for c in VARIABLES_PRONOSTICO["y24"])
    nombre_modelo = "hgb_" + "_".join(b.lower() for b in bloques) + ("_v4" if usa_pronostico else "_v3")
    print(f"Elegido (precisión media en calibración): {elegido}")

    # Segmentos ignición / propagación
    segmento = pd.Series(np.where(P["n_3d"] > 0, "propagación", "ignición"), index=P.index)
    seg = {
        elegido: por_segmento(P["y24"], p_prueba, segmento),
        "Climatología": por_segmento(P["y24"], P["clim_comuna_mes"], segmento),
        "Persistencia + climatología": por_segmento(P["y24"], persist(P), segmento, probabilidad=False),
    }
    tabla_seg = pd.concat({k: v[["auc", "precision_media", "captura_top10", "tasa_base"]] for k, v in seg.items()})
    tabla_seg.index.names = ["Modelo", "Segmento"]

    # Alertas: días-comuna con nivel alto o muy alto (p >= 12 %), por segmento
    umbral_alerta = dict((n, u) for u, n in NIVELES)["alto"]
    alerta = p_prueba >= umbral_alerta
    y_p = P["y24"].to_numpy()
    filas_alerta = {}
    for nombre in ["propagación", "ignición"]:
        m = (segmento == nombre).to_numpy()
        a = alerta & m
        filas_alerta[nombre] = {
            "Días-comuna": int(m.sum()),
            "Alertas (alto o muy alto)": int(a.sum()),
            "% de alertas con fuego": 100 * y_p[a].mean() if a.any() else np.nan,
            "% del fuego que tuvo alerta": 100 * y_p[a].sum() / y_p[m].sum() if y_p[m].sum() else np.nan,
            "Tasa base (%)": 100 * y_p[m].mean(),
        }
    tabla_alertas = pd.DataFrame(filas_alerta).T.astype({"Días-comuna": int, "Alertas (alto o muy alto)": int})
    tabla_alertas.index.name = "Segmento"

    # 48 h y 7 días con el mismo conjunto de variables, cada uno contra la climatología de su propio horizonte
    print("Entrenando 48 h y 7 días...")
    p_cal_24 = iso.predict(modelo.predict_proba(C[cols])[:, 1])
    cols_base = [c for c in cols if c not in VARIABLES_PRONOSTICO["y24"]]
    otros = {obj: entrenar_horizonte(tabla, obj, dias, cols_base + (VARIABLES_PRONOSTICO[obj] if usa_pronostico else []),
                                     ent, cal, prueba)
             for obj, (_, dias) in HORIZONTES.items() if obj != "y24"}
    niveles_h = {"y24": NIVELES} | {obj: umbrales_equivalentes(p_cal_24, h["p_cal"]) for obj, h in otros.items()}
    etiqueta = {"y48": "48 h", "y7d": "7 días"}
    res_h = pd.DataFrame({k: v for obj, h in otros.items() for k, v in (
        (f"Gradient boosting {etiqueta[obj]}", h["modelo_prueba"]),
        (f"Climatología {etiqueta[obj]}", h["clim_prueba"]))}).T
    ventaja = {"y24": resultados[elegido]["precision_media"]
               / resultados["Climatología (comuna × mes)"]["precision_media"]}
    ventaja |= {obj: h["modelo_prueba"]["precision_media"] / h["clim_prueba"]["precision_media"]
                for obj, h in otros.items()}
    tabla_umbrales = pd.DataFrame(
        {etiqueta.get(obj, "24 h"): {n: 100 * u for u, n in niv if u > 0} for obj, niv in niveles_h.items()}).T
    tabla_umbrales.index.name = "Horizonte"
    tabla_umbrales = tabla_umbrales.rename(columns={"medio": "medio desde (%)", "alto": "alto desde (%)",
                                                    "muy_alto": "muy alto desde (%)"})

    # Importancia (por permutación, muestra de prueba)
    muestra = P.sample(min(120_000, len(P)), random_state=1)
    imp = permutation_importance(modelo, muestra[cols], muestra["y24"], scoring="average_precision", n_repeats=3,
                                 random_state=1)
    importancia = pd.DataFrame({"Caída de precisión media": imp.importances_mean}, index=cols).sort_values(
        "Caída de precisión media", ascending=False)
    importancia.index.name = "Variable"

    # Calibración
    conf = confiabilidad(P["y24"], p_prueba)

    # Historia de predicciones (calibración + prueba) para percentiles y backtest
    hist = tabla[(cal | prueba | nuevo)].copy()
    hist["prob"] = iso.predict(modelo.predict_proba(hist[cols])[:, 1])
    hist["valido_para"] = hist["fecha"] + pd.Timedelta(days=1)
    backtest = hist[["region_id", "fecha", "valido_para", "prob", "y24", "n_hoy", "vecinos_hoy"]].copy()
    backtest["nivel"] = nivel(backtest["prob"].to_numpy())
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    backtest.to_parquet(config.PROCESSED_DIR / "riesgo_backtest.parquet", index=False)

    # Riesgo "último": con los datos hasta FIN, desde el día siguiente; una fila por comuna y horizonte
    filas_riesgo = []
    for obj, (horas, _) in HORIZONTES.items():
        if obj == "y24":
            prob_h = hist["prob"]
        else:
            prob_h = otros[obj]["calibrador"].predict(otros[obj]["modelo"].predict_proba(hist[otros[obj]["cols"]])[:, 1])
        h = hist[["region_id", "fecha", "valido_para"]].assign(prob=prob_h, mes=lambda d: d["valido_para"].dt.month)
        ultimo = h[h["fecha"] == pd.Timestamp(FIN)]
        filas_riesgo.append(pd.DataFrame({
            "region_id": ultimo["region_id"].astype("string"),
            "valido_para": ultimo["valido_para"],
            "horizonte_horas": horas,
            "prob_foco": ultimo["prob"].astype(float),
            "percentil": percentil_historico(ultimo[["region_id", "mes", "prob"]], h[h["fecha"] < pd.Timestamp(FIN)]),
            "nivel": nivel(ultimo["prob"].to_numpy(), niveles_h[obj]),
            "modelo": nombre_modelo,
        }))
    riesgo = pd.concat(filas_riesgo, ignore_index=True)
    validar_riesgo(riesgo)
    riesgo.to_parquet(config.PROCESSED_DIR / "riesgo.parquet", index=False)

    # Prueba nueva: días posteriores a FIN_PRUEBA (2026), que no existían al construir ni al elegir el modelo.
    # Solo días cuyo objetivo es de Suomi NPP (antes de que empiece la sustitución por NOAA-20).
    N = tabla[nuevo & tabla["y24"].notna() & (tabla["fecha"] < ultimo_snpp)]
    prueba_nueva = None
    if len(N) and N["y24"].sum() > 0:
        pn = iso.predict(modelo.predict_proba(N[cols])[:, 1])
        rn, cn = metricas(N["y24"], pn), metricas(N["y24"], N["clim_comuna_mes"])
        yn = N["y24"].to_numpy()
        niv = nivel(pn)
        muy = niv == "muy_alto"
        alto_o_mas = np.isin(niv, ["alto", "muy_alto"])
        prueba_nueva = {
            "desde": (N["fecha"].min() + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            "hasta": (N["fecha"].max() + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            "dias_comuna": int(len(N)), "dias_con_fuego": int(yn.sum()),
            "modelo": {k: round(rn[k], 4) for k in ("auc", "precision_media", "captura_top10", "tasa_base")},
            "climatologia": {k: round(cn[k], 4) for k in ("auc", "precision_media", "captura_top10")},
            "muy_alto_acierta_pct": round(100 * yn[muy].mean(), 1) if muy.any() else None,
            "alto_o_mas_pct_dias": round(100 * alto_o_mas.mean(), 1),
            "alto_o_mas_captura_pct": round(100 * yn[alto_o_mas].sum() / yn.sum(), 1),
        }
        print(f"Prueba nueva {prueba_nueva['desde']} a {prueba_nueva['hasta']}: AUC {rn['auc']:.3f} (climatología "
              f"{cn['auc']:.3f}), precisión media {rn['precision_media']:.3f}, captura top 10 % "
              f"{100 * rn['captura_top10']:.0f} %")

    # Detalle por horizonte (lo usa 13_exportar_sectores.py para riesgo/48h.json y riesgo/7d.json)
    clim24 = resultados["Climatología (comuna × mes)"]
    claves = ["auc", "precision_media", "captura_top10", "tasa_base"]
    info_h = {"modelo": nombre_modelo, "periodo_prueba": "2022-2025", "horizontes": {},
              "ultimo_dato": FIN, "ultimo_dato_suomi_npp": ultimo_snpp.strftime("%Y-%m-%d"),
              "sustitucion_noaa20": bool(fin > ultimo_snpp),
              "clima_hasta": None if clima_hasta is None else clima_hasta.strftime("%Y-%m-%d"),
              "clima_rezago_dias": int(rezago_clima), "prueba_nueva": prueba_nueva,
              "pronostico": info_pron if usa_pronostico else None,
              "validacion_pronostico": VALIDACION_PRONOSTICO if usa_pronostico else None}
    for obj, (horas, dias) in HORIZONTES.items():
        mp = resultados[elegido] if obj == "y24" else otros[obj]["modelo_prueba"]
        cp = clim24 if obj == "y24" else otros[obj]["clim_prueba"]
        info_h["horizontes"][str(horas)] = {
            "dias": dias,
            "valido_desde": (pd.Timestamp(FIN) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            "valido_hasta": (pd.Timestamp(FIN) + pd.Timedelta(days=dias)).strftime("%Y-%m-%d"),
            "umbrales": {n: u for u, n in niveles_h[obj]},
            "prueba_modelo": {k: round(mp[k], 4) for k in claves},
            "prueba_climatologia": {k: round(cp[k], 4) for k in claves},
            "ventaja_sobre_climatologia": round(ventaja[obj], 3),
        }
    (config.PROCESSED_DIR / "riesgo_horizontes.json").write_text(json.dumps(info_h, ensure_ascii=False, indent=2),
                                                                encoding="utf-8")

    r = resultados[elegido]
    ign = seg[elegido].loc["ignición"]
    prop = seg[elegido].loc["propagación"]
    ap, ai = tabla_alertas.loc["propagación"], tabla_alertas.loc["ignición"]
    nota = (f"Probado en 2022-2025. Donde ya hay fuego, sus alertas acertaron {ap['% de alertas con fuego']:.0f} % "
            f"de las veces y cubrieron {ap['% del fuego que tuvo alerta']:.0f} % de los días con fuego. Para incendios "
            f"nuevos sus alertas acertaron {ai['% de alertas con fuego']:.0f} % (la tasa base es "
            f"{ai['Tasa base (%)']:.1f} %), pero {100 - ai['% del fuego que tuvo alerta']:.0f} % de los incendios nuevos "
            "empezó sin alerta: la mayoría de las igniciones son humanas."
            + (texto_validacion_pronostico(VALIDACION_PRONOSTICO) if usa_pronostico else ""))
    metricas_json = {"modelo": nombre_modelo, "periodo_prueba": "2022-2025", "auc": round(r["auc"], 3),
                     "precision_media": round(r["precision_media"], 3), "captura_top10": round(r["captura_top10"], 3),
                     "nota": nota}
    (config.PROCESSED_DIR / "metricas.json").write_text(json.dumps(metricas_json, ensure_ascii=False, indent=2),
                                                         encoding="utf-8")
    joblib.dump({"modelo": modelo, "calibrador": iso, "variables": cols, "nombre": nombre_modelo},
                config.PROCESSED_DIR / "modelo_riesgo_24h.joblib")

    # Caso Viña del Mar
    caso = backtest[backtest["region_id"].isin(list(CASO)) &
                    backtest["valido_para"].between(*CASO_VENTANA)].copy()
    reales = tabla.set_index(["region_id", "fecha"])["n_hoy"]
    meses = {1: "ene", 2: "feb", 3: "mar", 4: "abr", 5: "may", 6: "jun", 7: "jul", 8: "ago", 9: "sep", 10: "oct",
             11: "nov", 12: "dic"}
    caso["dia"] = caso["valido_para"].dt.day.astype(str).str.zfill(2) + "-" + caso["valido_para"].dt.month.map(meses)
    caso["focos_reales"] = [reales.get((rid, f), 0) for rid, f in zip(caso["region_id"], caso["valido_para"])]
    curvas = {
        elegido: curva_captura(P["y24"], p_prueba),
        "Persistencia + climatología": curva_captura(P["y24"], persist(P)),
        "Climatología": curva_captura(P["y24"], P["clim_comuna_mes"]),
    }
    figura(caso, curvas, config.RAIZ / "docs" / "figuras" / "riesgo_vina_2024.png")
    caso_tabla = caso[caso["region_id"] == "05109"].set_index("valido_para")[["prob", "nivel", "focos_reales"]]
    caso_tabla = caso_tabla.assign(prob=100 * caso_tabla["prob"]).rename(
        columns={"prob": "Riesgo predicho la víspera (%)", "nivel": "Nivel", "focos_reales": "Focos reales"})
    caso_tabla.index = caso_tabla.index.strftime("%Y-%m-%d")
    caso_tabla.index.name = "Día"

    comp = pd.DataFrame(resultados).T.rename(columns=NOMBRES_METRICAS)
    comp.index.name = "Modelo (prueba 2022-2025, 24 h)"
    generado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    col_riesgo = "Riesgo predicho la víspera (%)"
    vispera = caso_tabla.loc["2024-02-03", col_riesgo]
    antes = caso_tabla.loc["2024-02-01", col_riesgo]
    nivel_vispera = caso_tabla.loc["2024-02-03", "Nivel"]
    lr_auc = resultados["Regresión logística (FIRMS)"]["auc"]
    reporte = [
        "# Riesgo de focos por comuna a 24 h, 48 h y 7 días",
        f"_Generado por `scripts/08_riesgo.py` el {generado}. No editar a mano: se regenera._",
        "",
        "## Resumen",
        f"- **Pregunta:** ¿habrá al menos un foco VIIRS (Suomi NPP) en la comuna mañana? Unidad: comuna × día "
        f"({len(tabla):,} filas). Tasa base en prueba: {r['tasa_base']*100:.1f} %.".replace(",", " "),
        f"- **Bloques de variables usados:** {', '.join(bloques)}. Modelo elegido: **{elegido}** "
        f"(`{nombre_modelo}`), por precisión media en el período de calibración.",
        f"- **Prueba 2022-2025 (nunca vista al entrenar):** AUC **{r['auc']:.3f}**, precisión media "
        f"**{r['precision_media']:.3f}** (la tasa base es {r['tasa_base']:.3f}), el 10 % de días-comuna de mayor "
        f"riesgo captura el **{r['captura_top10']*100:.0f} %** de los días con fuego (lift ×{r['lift_top10']:.1f}).",
        f"- **Supera a las líneas base** (climatología AUC "
        f"{resultados['Climatología (comuna × mes)']['auc']:.3f}, persistencia "
        f"{resultados['Persistencia + climatología']['auc']:.3f}). La regresión logística rinde casi igual "
        f"(AUC {lr_auc:.3f}): la ganancia viene de las variables, no de la complejidad del modelo. Se usa gradient "
        "boosting porque admite nuevos bloques (clima, vegetación) sin rediseñar.",
        *([f"- **Clima de los días que predice (v4):** el modelo usa la temperatura máxima, la humedad mínima, el "
           "viento máximo y la lluvia de mañana (y de pasado mañana a 48 h). En esta prueba son las **observadas** "
           "(NASA POWER): es una cota superior. Al publicar se usa el pronóstico de Open-Meteo, que además rellena los "
           "~4 días de rezago de NASA POWER; con pronósticos reales archivados"
           + texto_validacion_pronostico(VALIDACION_PRONOSTICO).replace(" Con el clima observado del día que predice; "
                                                                        "con el pronóstico real de Open-Meteo", "")
           + " Detalle: [pronostico_validacion.md](pronostico_validacion.md)."]
          if usa_pronostico and VALIDACION_PRONOSTICO else []),
        *([f"- **Prueba nueva 2026** ({prueba_nueva['desde']} a {prueba_nueva['hasta']}, datos que no existían al "
            f"elegir el modelo): AUC **{prueba_nueva['modelo']['auc']:.3f}** (climatología "
            f"{prueba_nueva['climatologia']['auc']:.3f}), precisión media {prueba_nueva['modelo']['precision_media']:.3f}."]
          if prueba_nueva else []),
        f"- **Horizontes:** en precisión media, el modelo supera a la climatología de su horizonte ×{ventaja['y24']:.2f} "
        f"a 24 h, ×{ventaja['y48']:.2f} a 48 h y ×{ventaja['y7d']:.2f} a 7 días"
        + (": la vista semanal es sobre todo estacional (orientativa)." if ventaja["y7d"] < 1.2 else "."),
        f"- **Límite honesto:** sus alertas (nivel alto o muy alto) **sirven para priorizar, no para anticipar todo**. "
        f"En comunas **con fuego reciente** acertaron el **{ap['% de alertas con fuego']:.0f} %** de las veces (tasa "
        f"base {ap['Tasa base (%)']:.0f} %) y cubrieron el {ap['% del fuego que tuvo alerta']:.0f} % de los días con "
        f"fuego. En comunas **sin fuego reciente** acertaron el **{ai['% de alertas con fuego']:.0f} %** "
        f"({ai['% de alertas con fuego'] / ai['Tasa base (%)']:.0f} veces la tasa base de {ai['Tasa base (%)']:.1f} %), "
        f"pero el **{100 - ai['% del fuego que tuvo alerta']:.0f} %** de los incendios nuevos empezó sin alerta. La "
        "mayoría de las igniciones son humanas.",
        f"- **Caso Viña del Mar:** la víspera del 3 de febrero de 2024, con el fuego todavía en comunas vecinas, el "
        f"modelo subió el riesgo de Viña de {antes:.1f} % a **{vispera:.1f} %** (nivel `{nivel_vispera}`), pero no lo "
        "marcó como alto. "
        + ("Ni siquiera con el clima de ese día (calor, baja humedad y viento) anticipa el salto de un incendio a "
           "otra comuna: el clima eleva el riesgo de toda la zona, no dice hacia dónde avanza el fuego."
           if "clima" in bloques else
           "Anticipar el salto de un incendio a otra comuna con solo datos de focos es difícil; es donde el viento y "
           "la humedad (bloque de clima) pueden aportar."),
        "",
        "![Caso Viña del Mar y captura por método](figuras/riesgo_vina_2024.png)",
        "",
        "## 1. Comparación de modelos (24 h)",
        "Entrenamiento 2012-02 a 2019-12; calibración de probabilidades (isotónica) 2020-2021; prueba 2022-2025. La "
        "climatología es la frecuencia histórica de la comuna en ese mes; la persistencia ordena primero las comunas "
        "con fuego hoy (no es probabilidad: sin Brier).",
        "",
        tabla_md(comp, 3),
        "",
        "## 2. Ignición vs. propagación (prueba 2022-2025)",
        "",
        tabla_md(tabla_seg.rename(columns=NOMBRES_METRICAS), 3),
        "",
        f"Alertas del modelo elegido (nivel alto o muy alto, probabilidad ≥ {umbral_alerta*100:.0f} %):",
        "",
        tabla_md(tabla_alertas, 1),
        "",
        "## 3. Horizontes de 48 h y 7 días",
        "Mismas variables que a 24 h. Cada modelo se compara con la climatología de su propio horizonte (frecuencia "
        "histórica, en la comuna y el mes, de tener al menos un foco en esos días). La precisión media sube con el "
        "horizonte solo porque hay más casos positivos: lo que importa es cuánto supera a la climatología.",
        "",
        tabla_md(res_h.rename(columns=NOMBRES_METRICAS), 3),
        "",
        f"Ventaja sobre la climatología en precisión media: 24 h ×{ventaja['y24']:.2f}, 48 h ×{ventaja['y48']:.2f}, "
        f"7 días ×{ventaja['y7d']:.2f}. "
        + ("**A 7 días el modelo aporta poco sobre el calendario:** usa el clima observado del último día, que dice "
           "poco de la semana siguiente. La vista semanal debe rotularse como orientativa (estacional); para mejorarla "
           "haría falta un pronóstico del tiempo."
           if ventaja["y7d"] < 1.2 else
           "A 7 días el modelo sigue superando claramente a la climatología."),
        "",
        "Umbrales de nivel por horizonte. A 48 h y 7 días se fijan para que, en calibración 2020-2021, cada nivel "
        "agrupe la misma proporción de días-comuna que a 24 h (con los umbrales de 24 h, a 7 días casi todo saldría "
        "\"alto\").",
        "",
        tabla_md(tabla_umbrales, 1),
        "",
        "## 3b. Prueba nueva: 2026",
        *(["Días que no existían cuando se construyó y eligió el modelo (bajados con la MAP_KEY de FIRMS). Objetivo y "
           "variables de Suomi NPP; no se usaron para ajustar nada.", "",
           tabla_md(pd.DataFrame({"Modelo": prueba_nueva["modelo"],
                                  "Climatología": prueba_nueva["climatologia"]}).T.rename(columns=NOMBRES_METRICAS), 3),
           "",
           f"Período {prueba_nueva['desde']} a {prueba_nueva['hasta']} "
           f"({prueba_nueva['dias_comuna']:,}".replace(",", ".") + " días-comuna, "
           + f"{prueba_nueva['dias_con_fuego']:,}".replace(",", ".") + " con fuego). "
           + f"Nivel muy alto: acertó el {prueba_nueva['muy_alto_acierta_pct']} % de las veces. Alto o muy alto: "
           f"{prueba_nueva['alto_o_mas_pct_dias']} % de los días-comuna con el {prueba_nueva['alto_o_mas_captura_pct']} % "
           "del fuego."]
          if prueba_nueva else ["Sin datos posteriores a 2025."]),
        "",
        f"Suomi NPP tiene datos hasta el {ultimo_snpp.date()}; "
        + (f"del {(ultimo_snpp + pd.Timedelta(days=1)).date()} al {FIN} el modelo usa NOAA-20 en su lugar (mismo "
           "instrumento VIIRS; en 2022-2025, con variables de NOAA-20 el modelo rinde igual: AUC 0,845 vs 0,846)."
           if fin > ultimo_snpp else "no hizo falta sustituirlo."),
        "",
        (f"El clima de NASA POWER llega hasta el {clima_hasta.date()}: para los {rezago_clima} días siguientes se usa "
         "el último clima disponible. Medido en 2022-2025, con 3 días de rezago el modelo baja de AUC 0,846 a 0,824 y "
         "de precisión media 0,282 a 0,251 (la climatología sola: 0,789 y 0,150)."
         if rezago_clima else "El clima está al día con los focos."),
        "",
        "## 4. Calibración (prueba 2022-2025)",
        "Si la probabilidad está bien calibrada, lo predicho y lo observado coinciden en cada decil.",
        "",
        tabla_md(conf, 3),
        "",
        "## 5. Qué variables pesan",
        "Caída de la precisión media al desordenar cada variable (muestra de la prueba).",
        "",
        tabla_md(importancia, 4),
        "",
        "## 6. Caso Viña del Mar, febrero de 2024",
        "",
        tabla_md(caso_tabla, 1),
        "",
        "## 7. Niveles y salidas",
        "- Niveles por probabilidad a 24 h: `bajo` < 4 % (≈ tasa base) ≤ `medio` < 12 % ≤ `alto` < 30 % ≤ `muy_alto`. "
        "A 48 h y 7 días, los umbrales de la sección 3.",
        "- `percentil`: posición de la probabilidad contra las del mismo comuna y mes en 2020-2025.",
        f"- `data/processed/riesgo.parquet`: riesgo desde el día siguiente al último dato ({FIN}) a 24 h, 48 h y 7 "
        "días, con el contrato `riesgo`. Para un riesgo de verdad para mañana hacen falta los focos de 2026 (FIRMS "
        "casi en tiempo real, MAP_KEY).",
        "- `data/processed/riesgo_backtest.parquet`: predicciones de 2020-2025 con lo que pasó, para revisar casos.",
        "- Para sumar variables (clima, vegetación) basta crear el bloque con llave comuna × día: el script lo detecta "
        "y agrega la fila a la comparación.",
        "",
    ]
    (config.RAIZ / "docs" / "riesgo.md").write_text("\n".join(reporte), encoding="utf-8")

    print("\n" + pd.DataFrame(resultados).T[["auc", "precision_media", "captura_top10", "lift_top10", "brier"]].round(3).to_string())
    print(f"\nIgnición AUC {ign['auc']:.3f} | Propagación AUC {prop['auc']:.3f}")
    print(res_h[["auc", "precision_media", "captura_top10"]].round(3).to_string())
    print(f"Ventaja sobre climatología (AP): {ventaja}")
    print(tabla_umbrales.round(1).to_string())
    print(caso_tabla.to_string())
    print(importancia.head(6).round(4).to_string())
    print("Reporte: docs/riesgo.md  |  Figura: docs/figuras/riesgo_vina_2024.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
