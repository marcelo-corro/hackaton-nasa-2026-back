"""Paso 12b (sectores): ¿la prioridad por exposición ubica el fuego dentro de la comuna mejor que el azar?

Para cada día-sector con fuego (sin fuentes persistentes) en un período de evaluación, mira si su sector está en el
10 % de sectores de su comuna con mayor puntaje. Sin fuga: el historial se cuenta SOLO antes del período evaluado;
las capas fijas (vegetación 2021, interfaz ~2020, pendiente) no dependen del fuego. Los umbrales de los rasgos se
fijaron antes de esta prueba (firecal.sectores.recomendaciones) y no se ajustan con ella.

Rankings comparados (desempates por orden de las columnas):
- azar: 10 % por definición;
- historial: días con fuego antes del período;
- interfaz: fracción del sector en interfaz casas-vegetación;
- exposición: n.º de factores (interfaz, pastizal, bosque/matorral, pendiente, historial previo), luego interfaz;
- historial, luego interfaz: días con fuego antes del período; los empates (la mayoría, sectores sin fuego previo)
  se ordenan por interfaz.
El orden que usa la app se elige mirando SOLO calibración 2020-2021; la prueba 2022-2025 se informa una vez.

Salida: docs/sectores_validacion.md (tabla) y salida por pantalla.

Uso:
    python scripts/12b_validar_sectores.py            # región 05
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
from firecal import config  # noqa: E402
from firecal.reportes import tabla_md  # noqa: E402
from firecal.sectores.recomendaciones import FACTORES_EXPOSICION, UMBRAL_HISTORIAL_DIAS, rasgos_sector  # noqa: E402

PERIODOS = {"calibración 2020-2021": ("2020-01-01", "2021-12-31"), "prueba 2022-2025": ("2022-01-01", "2025-12-31")}
FRACCION = 0.10


def captura(sectores: pd.DataFrame, eventos: pd.DataFrame, orden: list[str]) -> float:
    """Fracción de los días-sector con fuego que caen en el 10 % superior (por comuna) según `orden`."""
    top = set()
    for _, g in sectores.groupby("region_id"):
        k = max(1, int(round(FRACCION * len(g))))
        top |= set(g.sort_values(orden, ascending=False).head(k)["sector_id"])
    return float(eventos["sector_id"].isin(top).mean()) if len(eventos) else float("nan")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--region", default="05")
    args = parser.parse_args()
    rng = np.random.default_rng(0)

    s = gpd.read_parquet(config.PROCESSED_DIR / f"sectores_{args.region}.parquet")
    s = s[~s["fuente_persistente"]].copy()
    s["azar"] = rng.random(len(s))  # desempate final, para que los empates no favorezcan el orden del archivo
    f = pd.read_parquet(config.PROCESSED_DIR / f"sectores_{args.region}_focos.parquet")
    f = f[f["sector_id"].isin(set(s["sector_id"]))].assign(dia=lambda d: d["fecha_local"].dt.normalize())

    filas = []
    for nombre, (ini, fin) in PERIODOS.items():
        previo = f[f["dia"] < ini]
        dias_previos = previo.groupby("sector_id")["dia"].nunique()
        grandes_previos = previo[previo["focos_incendio"] > 10].groupby("sector_id")["evento"].nunique()
        d = s.copy()
        d["dias_con_fuego"] = d["sector_id"].map(dias_previos).fillna(0)
        d["incendios_grandes"] = d["sector_id"].map(grandes_previos).fillna(0)
        d["rasgos"] = rasgos_sector(d)
        d["exposicion"] = d["rasgos"].apply(lambda r: sum(x in r for x in FACTORES_EXPOSICION))
        d["frac_wui0"] = d["frac_wui"].fillna(0)
        ev = f[(f["dia"] >= ini) & (f["dia"] <= fin)].drop_duplicates(["sector_id", "dia"])
        filas.append({
            "Período": nombre, "Días-sector con fuego": len(ev),
            "Azar": 100 * FRACCION,
            "Historial previo": 100 * captura(d, ev, ["dias_con_fuego", "azar"]),
            "Interfaz": 100 * captura(d, ev, ["frac_wui0", "azar"]),
            "Exposición (n.º de factores)": 100 * captura(d, ev, ["exposicion", "frac_wui0", "azar"]),
            "Historial, luego interfaz": 100 * captura(d, ev, ["dias_con_fuego", "frac_wui0", "azar"]),
        })
        tasa = d.assign(quemado=d["sector_id"].isin(set(ev["sector_id"]))).groupby("exposicion")["quemado"].agg(
            ["size", "mean"])
        print(f"\n{nombre}: sectores con fuego según n.º de factores (historial solo antes del período)")
        print((tasa.assign(mean=100 * tasa["mean"]).rename(columns={"size": "sectores", "mean": "% con fuego"})
               .round(1).to_string()))
    t = pd.DataFrame(filas).set_index("Período")
    print("\n% de los días-sector con fuego que cae en el 10 % de sectores con mayor puntaje de su comuna")
    print(t.round(1).to_string())

    generado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    texto = [
        "# Validación de la prioridad por sector (piloto Región de Valparaíso)",
        f"_Generado por `scripts/12b_validar_sectores.py` el {generado}. No editar a mano._",
        "",
        "¿Qué % de los días-sector con fuego cae en el 10 % de sectores de su comuna con mayor puntaje? El azar da "
        "10 %. Historial contado solo antes de cada período (sin fuga); capas fijas: vegetación, interfaz, pendiente. "
        f"Rasgos: umbrales fijados antes de esta prueba; historial = fuego en ≥ {UMBRAL_HISTORIAL_DIAS} días o algún "
        "incendio grande. Fuentes persistentes (probable industria) excluidas.",
        "",
        tabla_md(t, 1),
        "",
    ]
    (config.RAIZ / "docs" / "sectores_validacion.md").write_text("\n".join(texto), encoding="utf-8")
    print("\nReporte: docs/sectores_validacion.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
