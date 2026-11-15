"""Paso 14: ¿se puede anticipar hacia dónde avanza un incendio activo? Valida la dirección del cono de avance.

Datos: pares (incendio, día d) con frente nuevo en d+1 en todo Chile (firecal.avance.pares_avance) y el viento diario
de NASA POWER (paso 5d). Reglas que se comparan (todas con lo conocido al final del día d, salvo la cota):
- azar: 25 % de aciertos a ±45°;
- viento a favor (día d);
- persistencia: hacia donde avanzó el día anterior (solo incendios que ya avanzaban);
- combinada: promedio circular de viento y persistencia;
- cota: viento a favor del día d+1 (un pronóstico perfecto; no se puede usar en vivo).
Criterio fijado antes de mirar la prueba: la regla elegida en calibración (2012-2021) debe acertar a ±45° claramente más
que el azar (límite inferior del intervalo de 95 % sobre 25 %). La prueba (2022-2026) se mira una vez.

Salidas: docs/avance_validacion.md y data/processed/avance_params.json (regla, apertura y largo del cono).

Uso:
    python scripts/14_validar_avance.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows (cp1252) no imprime "→" ni "±"
from firecal import config  # noqa: E402
from firecal.avance import a_favor_del_viento, error_angular  # noqa: E402
from firecal.reportes import tabla_md  # noqa: E402

FIN_CAL = pd.Timestamp("2021-12-31")


def media_circular(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    ra, rb = np.radians(a), np.radians(b)
    return np.degrees(np.arctan2(np.sin(ra) + np.sin(rb), np.cos(ra) + np.cos(rb))) % 360


def resumen(err: np.ndarray) -> dict:
    err = err[~np.isnan(err)]
    n = len(err)
    p45 = float((err <= 45).mean()) if n else np.nan
    ic = 1.96 * np.sqrt(p45 * (1 - p45) / n) if n else np.nan
    return {"n": n, "% a ±45°": 100 * p45, "IC95 inferior": 100 * (p45 - ic), "% a ±90°": 100 * float((err <= 90).mean()),
            "error mediano (°)": float(np.median(err)) if n else np.nan}


def main() -> int:
    p = pd.read_parquet(config.PROCESSED_DIR / "avance_pares.parquet")
    v = pd.read_parquet(config.INTERIM_DIR / "viento_diario.parquet").rename(columns={"fecha_local": "fecha"})
    v["region_id"] = v["region_id"].astype(str)
    p["region_id"] = p["region_id"].astype(str)
    p = p.merge(v, on=["region_id", "fecha"], how="left")
    v1 = v.assign(fecha=v["fecha"] - pd.Timedelta(days=1)).rename(columns={"viento_dir": "viento_dir_d1",
                                                                           "viento_vel": "viento_vel_d1"})
    p = p.merge(v1, on=["region_id", "fecha"], how="left").dropna(subset=["viento_dir"])
    p["pred_viento"] = a_favor_del_viento(p["viento_dir"])
    p["pred_viento_d1"] = a_favor_del_viento(p["viento_dir_d1"])
    p["pred_comb"] = np.where(p["rumbo_previo"].notna(), media_circular(p["pred_viento"], p["rumbo_previo"]),
                              p["pred_viento"])
    for c in ("viento", "viento_d1", "comb"):
        p[f"err_{c}"] = error_angular(p[f"pred_{c}"], p["rumbo_real"])
    p["err_persistencia"] = error_angular(p["rumbo_previo"], p["rumbo_real"])

    cal, pru = p[p["fecha"] <= FIN_CAL], p[p["fecha"] > FIN_CAL]
    filas = {}
    for nombre, d in (("Calibración 2012-2021", cal), ("Prueba 2022-2026", pru)):
        conprev = d[d["rumbo_previo"].notna()]
        filas[(nombre, "Viento a favor (día d), todos")] = resumen(d["err_viento"].to_numpy())
        filas[(nombre, "Cota: viento del día d+1, todos")] = resumen(d["err_viento_d1"].to_numpy())
        filas[(nombre, "Viento a favor, ya avanzaba")] = resumen(conprev["err_viento"].to_numpy())
        filas[(nombre, "Persistencia, ya avanzaba")] = resumen(conprev["err_persistencia"].to_numpy())
        filas[(nombre, "Combinada, ya avanzaba")] = resumen(conprev["err_comb"].to_numpy())
    t = pd.DataFrame(filas).T
    t.index.names = ["Período", "Regla"]

    # Elección en calibración: entre viento y combinada para incendios que ya avanzaban
    cal_prev = cal[cal["rumbo_previo"].notna()]
    usar_comb = (cal_prev["err_comb"] <= 45).mean() > (cal_prev["err_viento"] <= 45).mean()
    cal["err_elegida"] = np.where(cal["rumbo_previo"].notna() & usar_comb, cal["err_comb"], cal["err_viento"])
    pru = pru.assign(err_elegida=np.where(pru["rumbo_previo"].notna() & usar_comb, pru["err_comb"], pru["err_viento"]))
    r_cal, r_pru = resumen(cal["err_elegida"].to_numpy()), resumen(pru["err_elegida"].to_numpy())
    pasa = r_cal["IC95 inferior"] > 25
    print(t.round(1).to_string())
    print(f"\nRegla elegida en calibración: {'combinada si ya avanzaba, viento si no' if usar_comb else 'viento a favor'}")
    print(f"Calibración: {r_cal['% a ±45°']:.1f} % a ±45° (IC95 inf {r_cal['IC95 inferior']:.1f}) → "
          f"{'PASA' if pasa else 'NO PASA'} | Prueba: {r_pru['% a ±45°']:.1f} % (IC95 inf {r_pru['IC95 inferior']:.1f})")

    # Por velocidad del viento (terciles de calibración): ¿con viento fuerte acierta más?
    cortes = np.quantile(cal["viento_vel"], [1 / 3, 2 / 3])
    etiqueta = lambda x: np.select([x < cortes[0], x < cortes[1]], ["suave", "medio"], "fuerte")  # noqa: E731
    por_vel = {}
    for nombre, d in (("Calibración", cal), ("Prueba", pru)):
        for nivel_v, g in d.groupby(etiqueta(d["viento_vel"])):
            por_vel[(nombre, nivel_v)] = {**resumen(g["err_elegida"].to_numpy()),
                                          "avance mediano (km/día)": float(g["km"].median()),
                                          "avance p75 (km/día)": float(g["km"].quantile(0.75))}
    tv = pd.DataFrame(por_vel).T
    tv.index.names = ["Período", "Viento"]
    print(tv.round(1).to_string())

    # Cono (calibración): apertura = error mediano (la mitad de los avances reales cae dentro); largo por viento
    # Zona probable de avance: radios de calibración y cuánto cubren en la prueba
    radios = {f"p{q}": round(float(cal["km"].quantile(q / 100)), 2) for q in (75, 90)}
    cobertura = {k: round(100 * float((pru["km"] <= r).mean()), 1) for k, r in radios.items()}
    fuerte_pru = pru[pru["viento_vel"] >= cortes[1]]
    print(f"Radios de calibración {radios} cubren en prueba {cobertura} %")
    params = {
        "radios_km": radios, "cobertura_prueba_pct": cobertura,
        "viento_fuerte_desde_ms": round(float(cortes[1]), 2),
        "acierto_45_viento_fuerte_prueba_pct": round(100 * float((fuerte_pru["err_elegida"] <= 45).mean()), 1),
        "regla": "combinada" if usar_comb else "viento",
        "pasa": bool(pasa),
        "semiapertura_grados": round(float(np.median(cal["err_elegida"])), 1),
        "cortes_viento_ms": [round(float(c), 2) for c in cortes],
        "largo_km": {n: {"mediana": round(float(g["km"].median()), 2), "p75": round(float(g["km"].quantile(0.75)), 2)}
                     for n, g in cal.groupby(etiqueta(cal["viento_vel"]))},
        "calibracion": {k: round(float(x), 2) for k, x in r_cal.items()},
        "prueba": {k: round(float(x), 2) for k, x in r_pru.items()},
    }
    (config.PROCESSED_DIR / "avance_params.json").write_text(json.dumps(params, ensure_ascii=False, indent=2),
                                                             encoding="utf-8")
    generado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (config.RAIZ / "docs" / "avance_validacion.md").write_text("\n".join([
        "# Validación de la dirección de avance (cono)",
        f"_Generado por `scripts/14_validar_avance.py` el {generado}. No editar a mano._",
        "",
        f"{len(p):,} avances día a día de incendios en Chile (frente nuevo del día siguiente a más de 0,75 km). Al azar, "
        "el 25 % cae a ±45° y el 50 % a ±90°; error mediano al azar: 90°.".replace(",", "."),
        "",
        tabla_md(t, 1), "",
        f"Regla elegida en calibración: **{'combinada (viento + persistencia) si el incendio ya avanzaba; viento si no' if usar_comb else 'viento a favor'}**. "
        f"Calibración: {r_cal['% a ±45°']:.1f} % a ±45° → **{'pasa' if pasa else 'no pasa'}** el criterio. "
        f"Prueba 2022-2026: {r_pru['% a ±45°']:.1f} % a ±45° (error mediano {r_pru['error mediano (°)']:.0f}°).",
        "",
        "Por velocidad del viento (terciles de calibración):", "",
        tabla_md(tv, 1), "",
    ]), encoding="utf-8")
    print("Reporte: docs/avance_validacion.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
