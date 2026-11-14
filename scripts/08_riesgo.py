"""Paso 8 del pipeline (A): riesgo de focos a 24-48 h por comuna.

Objetivo: ¿habrá al menos un foco VIIRS (Suomi NPP, `uso_base`) en la comuna mañana (24 h) / en 2 días (48 h)?
Partición temporal: entrena 2012-02..2019, calibra 2020-2021, prueba 2022-2025 (incluye 2023 y Viña 2024).

Compara: climatología (comuna × mes), persistencia, regresión logística y gradient boosting con los bloques de
variables disponibles (FIRMS siempre; clima si existe data/interim/clima_diario.parquet). Elige por precisión media
en calibración, mide en prueba por separado ignición (sin focos en 3 días) y propagación (con focos recientes).

Salidas: data/processed/riesgo.parquet (contrato), data/processed/metricas.json, data/processed/riesgo_backtest.parquet,
data/processed/modelo_riesgo_24h.joblib, docs/riesgo.md y docs/figuras/riesgo_vina_2024.png.

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
    VARIABLES_CLIMA, VARIABLES_CLIMATOLOGIA, VARIABLES_FIRMS, agregar_climatologia, bloque_clima, tabla_base,
)
from firecal.reportes import tabla_md  # noqa: E402

INICIO, FIN = "2012-02-01", "2025-12-31"
FIN_ENTRENAMIENTO, FIN_CALIBRACION = "2019-12-31", "2021-12-31"
NIVELES = [(0.30, "muy_alto"), (0.12, "alto"), (0.04, "medio"), (0.0, "bajo")]
CASO = {"05109": "Viña del Mar", "05801": "Quilpué", "05804": "Villa Alemana"}
CASO_VENTANA = ("2024-01-27", "2024-02-12")
NOMBRES_METRICAS = {"auc": "AUC", "precision_media": "Precisión media", "captura_top10": "Captura top 10 %",
                    "lift_top10": "Lift top 10 %", "brier": "Brier", "tasa_base": "Tasa base"}


def nivel(p: np.ndarray) -> np.ndarray:
    out = np.full(len(p), "bajo", dtype=object)
    for umbral, nombre in reversed(NIVELES):
        out[np.asarray(p) >= umbral] = nombre
    return out


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
    comunas = gpd.read_parquet(config.INTERIM_DIR / "comunas.parquet")
    nombres = comunas.set_index("region_id")["nombre"]

    print("Armando tabla comuna x día...")
    tabla = tabla_base(focos, comunas, INICIO, FIN)
    ent = tabla["fecha"] <= FIN_ENTRENAMIENTO
    cal = (tabla["fecha"] > FIN_ENTRENAMIENTO) & (tabla["fecha"] <= FIN_CALIBRACION)
    prueba = tabla["fecha"] > FIN_CALIBRACION
    tabla = agregar_climatologia(tabla, ent)

    variables = VARIABLES_FIRMS + VARIABLES_CLIMATOLOGIA
    bloques = ["FIRMS"]
    clima = bloque_clima(config.INTERIM_DIR / "clima_diario.parquet")
    if clima is not None:
        tabla = tabla.merge(clima, on=["region_id", "fecha"], how="left")
        bloques.append("clima")
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
        conjuntos["Gradient boosting (FIRMS + clima)"] = variables + VARIABLES_CLIMA
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
    nombre_modelo = "hgb_" + "_".join(b.lower() for b in bloques) + "_v1"
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

    # 48 h con el mismo conjunto de variables
    print("Entrenando 48 h...")
    con_y48 = tabla["y48"].notna()
    E48, C48, P48 = tabla[ent & con_y48], tabla[cal & con_y48], tabla[prueba & con_y48]
    m48 = hgb().fit(E48[cols], E48["y48"])
    iso48 = calibrar(m48.predict_proba(C48[cols])[:, 1], C48["y48"])
    p48 = iso48.predict(m48.predict_proba(P48[cols])[:, 1])
    res48 = pd.DataFrame({"Gradient boosting 48 h": metricas(P48["y48"], p48),
                          "Climatología 48 h": metricas(P48["y48"], P48["clim_comuna_mes"])}).T

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
    hist = tabla[(cal | prueba)].copy()
    hist["prob"] = iso.predict(modelo.predict_proba(hist[cols])[:, 1])
    hist["valido_para"] = hist["fecha"] + pd.Timedelta(days=1)
    backtest = hist[["region_id", "fecha", "valido_para", "prob", "y24", "n_hoy", "vecinos_hoy"]].copy()
    backtest["nivel"] = nivel(backtest["prob"].to_numpy())
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    backtest.to_parquet(config.PROCESSED_DIR / "riesgo_backtest.parquet", index=False)

    # Riesgo "último": con los datos hasta FIN, para el día siguiente
    ultimo = hist[hist["fecha"] == pd.Timestamp(FIN)].copy()
    ultimo["mes"] = ultimo["valido_para"].dt.month
    hist_pct = hist[hist["fecha"] < pd.Timestamp(FIN)].assign(mes=lambda d: d["valido_para"].dt.month)
    riesgo = pd.DataFrame({
        "region_id": ultimo["region_id"].astype("string"),
        "valido_para": ultimo["valido_para"],
        "horizonte_horas": 24,
        "prob_foco": ultimo["prob"].astype(float),
        "percentil": percentil_historico(ultimo[["region_id", "mes", "prob"]], hist_pct),
        "nivel": nivel(ultimo["prob"].to_numpy()),
        "modelo": nombre_modelo,
    })
    validar_riesgo(riesgo)
    riesgo.to_parquet(config.PROCESSED_DIR / "riesgo.parquet", index=False)

    r = resultados[elegido]
    ign = seg[elegido].loc["ignición"]
    prop = seg[elegido].loc["propagación"]
    ap, ai = tabla_alertas.loc["propagación"], tabla_alertas.loc["ignición"]
    nota = (f"Probado en 2022-2025. Donde ya hay fuego, sus alertas acertaron {ap['% de alertas con fuego']:.0f} % "
            f"de las veces y cubrieron {ap['% del fuego que tuvo alerta']:.0f} % de los días con fuego. Para incendios "
            f"nuevos sus alertas acertaron {ai['% de alertas con fuego']:.0f} % (la tasa base es "
            f"{ai['Tasa base (%)']:.1f} %), pero {100 - ai['% del fuego que tuvo alerta']:.0f} % de los incendios nuevos "
            "empezó sin alerta: la mayoría de las igniciones son humanas.")
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
        "# Riesgo de focos a 24-48 h por comuna",
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
        f"- **Límite honesto:** sus alertas (nivel alto o muy alto) **sirven para priorizar, no para anticipar todo**. "
        f"En comunas **con fuego reciente** acertaron el **{ap['% de alertas con fuego']:.0f} %** de las veces (tasa "
        f"base {ap['Tasa base (%)']:.0f} %) y cubrieron el {ap['% del fuego que tuvo alerta']:.0f} % de los días con "
        f"fuego. En comunas **sin fuego reciente** acertaron el **{ai['% de alertas con fuego']:.0f} %** "
        f"({ai['% de alertas con fuego'] / ai['Tasa base (%)']:.0f} veces la tasa base de {ai['Tasa base (%)']:.1f} %), "
        f"pero el **{100 - ai['% del fuego que tuvo alerta']:.0f} %** de los incendios nuevos empezó sin alerta. La "
        "mayoría de las igniciones son humanas.",
        f"- **Caso Viña del Mar:** la víspera del 3 de febrero de 2024, con el fuego todavía en comunas vecinas, el "
        f"modelo subió el riesgo de Viña de {antes:.1f} % a **{vispera:.1f} %** (nivel `{nivel_vispera}`), pero no lo "
        "marcó como alto. Anticipar el salto de un incendio a otra comuna con solo datos de focos es difícil; es "
        "donde el viento y la humedad (bloque de clima) pueden aportar.",
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
        "## 3. Horizonte de 48 h",
        "",
        tabla_md(res48.rename(columns=NOMBRES_METRICAS), 3),
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
        "- Niveles por probabilidad: `bajo` < 4 % (≈ tasa base) ≤ `medio` < 12 % ≤ `alto` < 30 % ≤ `muy_alto`.",
        "- `percentil`: posición de la probabilidad contra las del mismo comuna y mes en 2020-2025.",
        f"- `data/processed/riesgo.parquet`: riesgo para el día siguiente al último dato ({FIN}), con el contrato "
        "`riesgo`. Para un riesgo de verdad para mañana hacen falta los focos de 2026 (FIRMS casi en tiempo real, "
        "MAP_KEY).",
        "- `data/processed/riesgo_backtest.parquet`: predicciones de 2020-2025 con lo que pasó, para revisar casos.",
        "- Para sumar variables (clima, vegetación) basta crear el bloque con llave comuna × día: el script lo detecta "
        "y agrega la fila a la comparación.",
        "",
    ]
    (config.RAIZ / "docs" / "riesgo.md").write_text("\n".join(reporte), encoding="utf-8")

    print("\n" + pd.DataFrame(resultados).T[["auc", "precision_media", "captura_top10", "lift_top10", "brier"]].round(3).to_string())
    print(f"\nIgnición AUC {ign['auc']:.3f} | Propagación AUC {prop['auc']:.3f}")
    print(res48[["auc", "precision_media", "captura_top10"]].round(3).to_string())
    print(caso_tabla.to_string())
    print(importancia.head(6).round(4).to_string())
    print("Reporte: docs/riesgo.md  |  Figura: docs/figuras/riesgo_vina_2024.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
