"""Paso 12c (sectores, modelo B): ¿un modelo ubica el fuego dentro de la comuna mejor que el orden del A+?

Salidas: data/processed/modelo_b_<región>.json (métricas) y data/processed/sectores_<región>_b.parquet (por sector,
para el día siguiente al último dato: `prob_condicional` = si hay fuego en la comuna, probabilidad de que caiga en el
sector; `prob_grande` = si hay fuego en el sector, probabilidad de que sea parte de un incendio de más de 10 focos).

Punto de control acordado: el B se muestra como predicción SOLO si, en calibración 2020-2021, captura más fuego en el
10 % de sectores de cada comuna que el orden del A+ (historial previo, luego interfaz), medido sobre los mismos días.
Se reporta además una línea base "cerca del fuego reciente" y, por separado, ignición (sin fuego en la comuna en los
3 días previos) y propagación. La prueba 2022-2025 se mira una sola vez, con `--prueba`, después de decidir.

Entrenar, calibrar y validar usa solo datos hasta 2025, que no cambian de un día a otro: lo entrenado se guarda en
data/processed/modelo_b_<región>.joblib (no se versiona; en Actions va en la caché) con la huella de esos datos
(firecal.sectores.modelo_b.huella_entrenamiento). Si la huella calza, solo se predice el día siguiente; si cambió (por
ejemplo, tras una carga completa o con otra versión de scikit-learn), se vuelve a entrenar. --reentrenar lo fuerza.

Uso:
    python scripts/12c_modelo_sectores.py              # entrenamiento 2012-2019, mide en calibración
    python scripts/12c_modelo_sectores.py --prueba     # además mide en prueba 2022-2025 (una vez)
    python scripts/12c_modelo_sectores.py --reentrenar # entrena aunque la huella calce
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import warnings
from pathlib import Path

import geopandas as gpd
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score, roc_auc_score

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from firecal import config  # noqa: E402
from firecal.sectores.grilla import CRS_METRICO  # noqa: E402
from firecal.sectores.modelo_b import (  # noqa: E402
    VARIABLES_B, captura_top, dia_entero, etiqueta_grande, huella_entrenamiento, tabla_condicional,
)

FIN_ENT, FIN_CAL = pd.Timestamp("2019-12-31"), pd.Timestamp("2021-12-31")
FIN_PRUEBA = pd.Timestamp("2025-12-31")  # la prueba del modelo B queda en 2022-2025 (comparable con lo publicado)


def ultimo_dato() -> pd.Timestamp:
    """Último día con datos, el mismo que usó 08_riesgo.py (se predice el día siguiente)."""
    ruta = config.PROCESSED_DIR / "riesgo_horizontes.json"
    return pd.Timestamp(json.loads(ruta.read_text(encoding="utf-8")).get("ultimo_dato", "2025-12-31"))
SEMILLAS = (42, 7, 123)
VERSION_B = 1  # subir si cambia el entrenamiento o la validación (obliga a reentrenar aunque los datos sean iguales)


def hgb(seed: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=100,
                                          l2_regularization=1.0, early_stopping=True, validation_fraction=0.1,
                                          n_iter_no_change=30, random_state=seed)


def hgb_grande(seed: int) -> HistGradientBoostingClassifier:
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=15, min_samples_leaf=40,
                                          early_stopping=True, random_state=seed)


def descripcion_entrenamiento(prueba: bool) -> str:
    """Todo lo que, además de los datos, cambia lo entrenado o las métricas guardadas (va en la huella)."""
    return "|".join([f"modelo_b-v{VERSION_B}", f"sklearn-{sklearn.__version__}", f"prueba={prueba}",
                     f"{FIN_ENT.date()}/{FIN_CAL.date()}/{FIN_PRUEBA.date()}", str(SEMILLAS), ",".join(VARIABLES_B),
                     repr(sorted(hgb(0).get_params().items())), repr(sorted(hgb_grande(0).get_params().items()))])


def evaluar(t: pd.DataFrame, puntajes: dict[str, np.ndarray]) -> pd.DataFrame:
    filas = {}
    for seg, m in (("todos", np.ones(len(t), bool)), ("ignición", t["comuna_con_fuego_reciente"].to_numpy() == 0),
                   ("propagación", t["comuna_con_fuego_reciente"].to_numpy() == 1)):
        tt = t[m]
        fila = {"sector-días con fuego": int(tt["y"].sum())}
        for nombre, p in puntajes.items():
            fila[nombre] = 100 * captura_top(tt, p[m])
        filas[seg] = fila
    return pd.DataFrame(filas).T


def entrenar(s, f, xy_f, xy_s, prueba: bool, t0: float) -> dict:
    """Entrena, mide y calibra el modelo B y el de incendio grande (lo que no cambia a diario)."""
    t = tabla_condicional(s, f, xy_f, xy_s)
    print(f"Tabla: {len(t):,} filas, {int(t['y'].sum()):,} sector-días con fuego, "
          f"{t.groupby(['region_id', 'dia']).ngroups:,} comuna-días ({time.time() - t0:.0f} s)")

    E, C = t[t["fecha"] <= FIN_ENT], t[(t["fecha"] > FIN_ENT) & (t["fecha"] <= FIN_CAL)]
    P = t[(t["fecha"] > FIN_CAL) & (t["fecha"] <= FIN_PRUEBA)]
    modelos, p_cal, p_pru = [], [], []
    for seed in SEMILLAS:
        m = hgb(seed).fit(E[VARIABLES_B], E["y"])
        modelos.append(m)
        p_cal.append(m.predict_proba(C[VARIABLES_B])[:, 1])
        p_pru.append(m.predict_proba(P[VARIABLES_B])[:, 1])
    base_a = lambda d: d["hist_dias"].to_numpy() + d["frac_wui"].fillna(0).to_numpy() / 10  # noqa: E731  orden A+
    cercania = lambda d: -d["dist_foco_reciente_km"].to_numpy() + d["hist_dias"].to_numpy() / 1e4  # noqa: E731

    def tabla(d, ps):
        r = evaluar(d, {"Orden A+ (historial, luego interfaz)": base_a(d), "Cerca del fuego reciente": cercania(d),
                        **{f"Modelo B (semilla {sd})": p for sd, p in zip(SEMILLAS, ps)}})
        cols_b = [c for c in r.columns if c.startswith("Modelo B")]
        r["Modelo B (promedio)"] = r[cols_b].mean(axis=1)
        r["Modelo B (desv.)"] = r[cols_b].std(axis=1, ddof=0)
        return r.drop(columns=cols_b)

    pd.set_option("display.width", 220)
    rc = tabla(C, p_cal)
    print("\nCALIBRACIÓN 2020-2021: % del fuego en el 10 % de sectores con mayor puntaje de su comuna (azar 10 %)")
    print(rc.round(1).to_string())
    ap = np.mean([average_precision_score(C["y"], p) for p in p_cal])
    print(f"Precisión media del modelo B en calibración: {ap:.4f} (tasa base {C['y'].mean():.4f})")
    gana = rc.loc["todos", "Modelo B (promedio)"] > rc.loc["todos", "Orden A+ (historial, luego interfaz)"]
    print(f"PUNTO DE CONTROL: el modelo B {'SUPERA' if gana else 'NO supera'} al orden del A+ en calibración.")

    resultado = {"calibracion": rc.round(2).to_dict(), "pasa_punto_de_control": bool(gana),
                 "precision_media_cal": round(float(ap), 4)}
    if prueba:
        rp = tabla(P, p_pru)
        print("\nPRUEBA 2022-2025 (una vez)")
        print(rp.round(1).to_string())
        resultado["prueba"] = rp.round(2).to_dict()

    # Tamaño: si hay fuego en el sector, ¿es parte de un incendio de más de 10 focos?
    q = t[t["y"] == 1].copy()
    q["grande"] = etiqueta_grande(q, f)
    qE, qC, qP = (q[q["fecha"] <= FIN_ENT], q[(q["fecha"] > FIN_ENT) & (q["fecha"] <= FIN_CAL)],
                  q[(q["fecha"] > FIN_CAL) & (q["fecha"] <= FIN_PRUEBA)])
    modelos_g = [hgb_grande(sd).fit(qE[VARIABLES_B], qE["grande"]) for sd in SEMILLAS]
    prom_g = lambda d: np.mean([m.predict_proba(d[VARIABLES_B])[:, 1] for m in modelos_g], axis=0)  # noqa: E731
    resultado["grande"] = {}
    for nombre, d in (("calibracion", qC), ("prueba", qP)) if prueba else (("calibracion", qC),):
        p = prom_g(d)
        fila = {}
        for seg, mk in (("todos", np.ones(len(d), bool)), ("ignicion", d["comuna_con_fuego_reciente"].to_numpy() == 0),
                        ("propagacion", d["comuna_con_fuego_reciente"].to_numpy() == 1)):
            fila[seg] = {"n": int(mk.sum()), "tasa_grandes": round(float(d["grande"].to_numpy()[mk].mean()), 3),
                         "auc": round(float(roc_auc_score(d["grande"].to_numpy()[mk], p[mk])), 3)}
        resultado["grande"][nombre] = fila
        print(f"Incendio grande, {nombre}: " + ", ".join(f"{k} AUC {v['auc']:.3f} (n={v['n']})" for k, v in fila.items()))

    # Probabilidades calibradas en 2020-2021 (isotónica), para predecir el día siguiente al último dato
    prom_b = lambda d: np.mean([m.predict_proba(d[VARIABLES_B])[:, 1] for m in modelos], axis=0)  # noqa: E731
    iso_b = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=0.95).fit(prom_b(C), C["y"])
    iso_g = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=0.95).fit(prom_g(qC), qC["grande"])
    return {"modelos": modelos, "modelos_g": modelos_g, "iso_b": iso_b, "iso_g": iso_g, "resultado": resultado}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="05")
    parser.add_argument("--prueba", action="store_true", help="mide también en 2022-2025 (una vez, tras decidir)")
    parser.add_argument("--reentrenar", action="store_true", help="entrena aunque la huella de los datos calce")
    args = parser.parse_args()
    warnings.filterwarnings("ignore")
    t0 = time.time()

    s = gpd.read_parquet(config.PROCESSED_DIR / f"sectores_{args.region}.parquet")
    s = s[~s["fuente_persistente"]].reset_index(drop=True)
    f = pd.read_parquet(config.PROCESSED_DIR / f"sectores_{args.region}_focos.parquet")
    f = f[f["sector_id"].isin(set(s["sector_id"]))].reset_index(drop=True)
    xy_s = np.column_stack([s.geometry.representative_point().x, s.geometry.representative_point().y])
    pf = gpd.GeoSeries(gpd.points_from_xy(f["lon"], f["lat"]), crs="EPSG:4326").to_crs(CRS_METRICO)
    xy_f = np.column_stack([pf.x, pf.y])
    ruta_modelo = config.PROCESSED_DIR / f"modelo_b_{args.region}.joblib"
    huella = huella_entrenamiento(s, f, FIN_PRUEBA, descripcion_entrenamiento(args.prueba))
    guardado = joblib.load(ruta_modelo) if ruta_modelo.exists() and not args.reentrenar else None
    if guardado is not None and guardado.get("huella") == huella:
        print(f"Datos de entrenamiento sin cambios (huella {huella[:12]}): se usa el modelo B entrenado el "
              f"{guardado['entrenado_utc']}; solo se predice el día siguiente.")
        e = guardado
        print("CALIBRACIÓN 2020-2021 (guardada): % del fuego en el 10 % de sectores con mayor puntaje de su comuna")
        print(pd.DataFrame(e["resultado"]["calibracion"]).round(1).to_string())
    else:
        print("Modelo B: " + ("se reentrena (--reentrenar)" if args.reentrenar else
                              "no hay modelo guardado o cambiaron sus datos de entrenamiento: se entrena"), flush=True)
        e = entrenar(s, f, xy_f, xy_s, args.prueba, t0)
        joblib.dump({**e, "huella": huella, "entrenado_utc": pd.Timestamp.now("UTC").strftime("%Y-%m-%d %H:%M UTC")},
                    ruta_modelo, compress=3)
    modelos, modelos_g, iso_b, iso_g = e["modelos"], e["modelos_g"], e["iso_b"], e["iso_g"]
    resultado = dict(e["resultado"])
    prom_b = lambda d: np.mean([m.predict_proba(d[VARIABLES_B])[:, 1] for m in modelos], axis=0)  # noqa: E731
    prom_g = lambda d: np.mean([m.predict_proba(d[VARIABLES_B])[:, 1] for m in modelos_g], axis=0)  # noqa: E731
    FIN_DATOS = ultimo_dato()  # noqa: N806
    dia_pred = int(dia_entero(pd.Series([FIN_DATOS + pd.Timedelta(days=1)]))[0])
    tp = tabla_condicional(s, f, xy_f, xy_s, pares=[(rid, dia_pred) for rid in sorted(s["region_id"].unique())])
    salida = pd.DataFrame({
        "sector_id": tp["sector_id"],
        "prob_condicional": iso_b.predict(prom_b(tp)),
        "prob_grande": iso_g.predict(prom_g(tp)),
    })
    salida["fecha_prediccion"] = (FIN_DATOS + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    salida.to_parquet(config.PROCESSED_DIR / f"sectores_{args.region}_b.parquet", index=False)
    resultado["prediccion"] = {"fecha": salida["fecha_prediccion"].iloc[0], "sectores": len(salida),
                               "modelo": "sectores_b_v1"}
    print(f"Predicción {salida['fecha_prediccion'].iloc[0]}: prob_condicional media {salida['prob_condicional'].mean():.4f}, "
          f"prob_grande media {salida['prob_grande'].mean():.3f}")
    (config.PROCESSED_DIR / f"modelo_b_{args.region}.json").write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nListo en {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
