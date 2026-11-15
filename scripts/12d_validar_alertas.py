"""Paso 12d (sectores): simula la lista de alertas de cada día 2020-2025 y mide cuánto fuego del día siguiente cubre.

Compara la regla publicada hasta la v0.4 (25 sectores siempre, comunas por nivel aunque sea bajo, orden fijo) con la
v0.5 (firecal.sectores.alertas: fuego activo primero por cercanía, alerta y vigilancia, sin nivel bajo). Para cada día
t usa solo lo conocido hasta t: el riesgo a 24 h del backtest del modelo (riesgo_backtest.parquet), el historial de
focos hasta t y los focos de t-2 a t. Mide contra los focos del día t+1 (sin fuentes persistentes).

Salida: docs/alertas_validacion.md y data/processed/alertas_validacion_<región>.json.

Uso:
    python scripts/12d_validar_alertas.py              # región 05
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from firecal import config  # noqa: E402
from firecal.reportes import tabla_md  # noqa: E402
from firecal.sectores.alertas import DIAS_FUEGO_ACTIVO, armar_lista, lista_v04  # noqa: E402
from firecal.sectores.grilla import CRS_METRICO  # noqa: E402
from firecal.sectores.modelo_b import Historial, dia_entero  # noqa: E402

PERIODOS = {"Calibración 2020-2021": ("2020-01-01", "2021-12-30"), "Prueba 2022-2025": ("2022-01-01", "2025-12-30")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="05")
    args = parser.parse_args()
    t0 = time.time()

    s = gpd.read_parquet(config.PROCESSED_DIR / f"sectores_{args.region}.parquet")
    s = s[~s["fuente_persistente"]].reset_index(drop=True)
    xy_s = np.column_stack([s.geometry.representative_point().x, s.geometry.representative_point().y])
    codigos = set(s["region_id"].astype(str))
    f = pd.read_parquet(config.PROCESSED_DIR / f"sectores_{args.region}_focos.parquet")
    f = f[f["sector_id"].isin(set(s["sector_id"]))].reset_index(drop=True)
    pf = gpd.GeoSeries(gpd.points_from_xy(f["lon"], f["lat"]), crs="EPSG:4326").to_crs(CRS_METRICO)
    xy_f = np.column_stack([pf.x, pf.y])
    dia_f = dia_entero(f["fecha_local"])
    pos = pd.Series(np.arange(len(s)), index=s["sector_id"])
    pos_f = pos[f["sector_id"]].to_numpy()
    hist = Historial(pos_f, dia_f)
    todos = np.arange(len(s))
    fuego_por_dia = {d: (set(g["sector_id"]), set(g["region_id"].astype(str)))
                     for d, g in f.assign(d=dia_f).groupby("d")}
    bt = pd.read_parquet(config.PROCESSED_DIR / "riesgo_backtest.parquet")
    bt = bt[bt["region_id"].astype(str).isin(codigos)].rename(columns={"prob": "prob_foco"})
    bt["d"] = dia_entero(bt["fecha"])

    # Prueba nueva 2026: hasta la víspera del último día de Suomi NPP (la verdad del día siguiente sigue siendo SNPP)
    info = json.loads((config.PROCESSED_DIR / "riesgo_horizontes.json").read_text(encoding="utf-8"))
    ultimo_snpp = pd.Timestamp(info.get("ultimo_dato_suomi_npp", "2025-12-31"))
    if ultimo_snpp > pd.Timestamp("2026-01-02"):
        PERIODOS[f"Prueba nueva 2026 (hasta {(ultimo_snpp - pd.Timedelta(days=1)).date()})"] = (
            "2026-01-01", (ultimo_snpp - pd.Timedelta(days=2)).strftime("%Y-%m-%d"))

    filas = []
    for d, rd in bt.groupby("d"):
        hd = hist.contar(todos, np.zeros(len(s), np.int64), np.full(len(s), d + 1))  # días con fuego hasta t
        rec = (dia_f >= d - DIAS_FUEGO_ACTIVO + 1) & (dia_f <= d)
        activas = set(f.loc[rec, "region_id"].astype(str))
        v5 = armar_lista(s, xy_s, rd[["region_id", "prob_foco", "nivel"]], hd, xy_f[rec], activas)
        v4 = lista_v04(s, rd[["region_id", "prob_foco", "nivel"]], hd)
        fs, fc = fuego_por_dia.get(d + 1, (set(), set()))
        al = v5[v5["tipo"].isin(["fuego_activo", "alerta"])] if len(v5) else v5
        fila = {"d": d, "fuego_sectores": len(fs), "fuego_comunas": len(fc),
                "v4_sect": len(v4), "v4_hit": len(fs & set(v4["sector_id"])),
                "v5_sect": len(v5), "v5_hit": len(fs & set(v5["sector_id"])) if len(v5) else 0,
                "v5al_sect": len(al), "v5al_hit": len(fs & set(al["sector_id"])) if len(al) else 0,
                "v5_vacia": int(len(v5) == 0)}
        for tipo in ("fuego_activo", "alerta", "vigilancia"):
            sub = v5[v5["tipo"] == tipo] if len(v5) else v5
            com = set(sub["region_id"]) if len(sub) else set()
            fila[f"com_{tipo}"] = len(com)
            fila[f"com_{tipo}_hit"] = len(fc & com)
            fila[f"sect_{tipo}"] = len(sub)
            fila[f"sect_{tipo}_hit"] = len(fs & set(sub["sector_id"])) if len(sub) else 0
        com_v4 = set(v4["region_id"])
        fila["com_v4"], fila["com_v4_hit"] = len(com_v4), len(fc & com_v4)
        filas.append(fila)
    t = pd.DataFrame(filas)
    t["fecha"] = np.datetime64("2012-01-01", "D") + t["d"].to_numpy().astype("timedelta64[D]")
    n_sect = len(s)

    resumen = {}
    for nombre, (ini, fin) in PERIODOS.items():
        p = t[(t["fecha"] >= ini) & (t["fecha"] <= fin)]
        fs, fc = p["fuego_sectores"].sum(), p["fuego_comunas"].sum()
        pct = lambda a, b: 100 * a / b if b else float("nan")  # noqa: E731
        resumen[nombre] = {
            "Días": len(p),
            "Sector-días con fuego al día siguiente": int(fs),
            "v0.4: % del fuego en los sectores listados": pct(p["v4_hit"].sum(), fs),
            "v0.4: sectores listados por día": p["v4_sect"].mean(),
            "v0.4: % de los sectores listados que tuvo fuego": pct(p["v4_hit"].sum(), p["v4_sect"].sum()),
            "v0.5: % del fuego en sectores de alerta (fuego activo + alerta)": pct(p["v5al_hit"].sum(), fs),
            "v0.5: % del fuego en todos los sectores listados": pct(p["v5_hit"].sum(), fs),
            "v0.5: sectores listados por día": p["v5_sect"].mean(),
            "v0.5: % de los sectores listados que tuvo fuego": pct(p["v5_hit"].sum(), p["v5_sect"].sum()),
            "v0.5: % de los sectores de fuego activo que tuvo fuego": pct(p["sect_fuego_activo_hit"].sum(),
                                                                          p["sect_fuego_activo"].sum()),
            "v0.5: % de los sectores de alerta (modelo) que tuvo fuego": pct(p["sect_alerta_hit"].sum(),
                                                                             p["sect_alerta"].sum()),
            "v0.5: % de los sectores de vigilancia que tuvo fuego": pct(p["sect_vigilancia_hit"].sum(),
                                                                        p["sect_vigilancia"].sum()),
            "v0.5: días con lista vacía (%)": 100 * p["v5_vacia"].mean(),
            "Comuna-días con fuego al día siguiente": int(fc),
            "v0.5: % de esas comunas en fuego activo o alerta": pct(p["com_fuego_activo_hit"].sum()
                                                                     + p["com_alerta_hit"].sum(), fc),
            "v0.5: % en fuego activo, alerta o vigilancia": pct(p["com_fuego_activo_hit"].sum() + p["com_alerta_hit"].sum()
                                                                + p["com_vigilancia_hit"].sum(), fc),
            "v0.4: % de esas comunas en la lista": pct(p["com_v4_hit"].sum(), fc),
        }
    r = pd.DataFrame(resumen)
    pd.set_option("display.width", 200)
    print(r.round(2).to_string())
    print(f"\nTotal de sectores (sin fuentes persistentes): {n_sect:,}. Listo en {time.time() - t0:.0f} s")

    generado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (config.RAIZ / "docs" / "alertas_validacion.md").write_text("\n".join([
        "# Simulación de la lista de alertas (piloto Región de Valparaíso)",
        f"_Generado por `scripts/12d_validar_alertas.py` el {generado}. No editar a mano._",
        "",
        "Cada día t se arma la lista con lo conocido hasta t (riesgo a 24 h del modelo, historial y focos de t-2 a t) y se "
        f"mide contra los focos de t+1. {n_sect:,} sectores en total (sin fuentes persistentes). v0.4: 25 sectores "
        "siempre, orden fijo. v0.5: fuego activo primero (cercanía), alerta (alto o muy alto) y vigilancia (medio); "
        "sin nivel bajo.".replace(",", "."),
        "",
        tabla_md(r, 1),
        "",
    ]), encoding="utf-8")
    (config.PROCESSED_DIR / f"alertas_validacion_{args.region}.json").write_text(
        json.dumps({k: {kk: (round(float(vv), 2) if vv == vv else None) for kk, vv in v.items()}
                    for k, v in resumen.items()}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Reporte: docs/alertas_validacion.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
