"""Paso 16: riesgo, clima, motivos y recomendaciones de las 345 comunas → public/comunas.json (contrato 0.8).

Se corre DESPUÉS de 09_exportar.py, 13_exportar_sectores.py y 15_exportar_avance.py, y ANTES de 10_publicar.py.

Lleva a todo el país el bloque `comunas` que hasta la v0.7 solo tenía el piloto de Valparaíso (alertas/05.json), con
las mismas reglas (ver firecal.export.comunas). No hay sectores fuera del piloto.

Entradas: riesgo.parquet y riesgo_horizontes.json (paso 8), clima_diario.parquet (paso 5c), focos_calidad.parquet
(paso 4), comunas.parquet y sectores_05.parquet (fuentes persistentes del piloto de Valparaíso; las del resto del
país ya vienen fuera de `uso_base`, ver firecal.fuentes_persistentes).

Uso:
    python scripts/16_exportar_comunas.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from firecal import config  # noqa: E402
from firecal.contratos import validar_riesgo  # noqa: E402
from firecal.export.comunas import ARCHIVO_COMUNAS, INICIO_DATOS, comunas_pais  # noqa: E402
from firecal.export.contrato import VERSION_CONTRATO  # noqa: E402
from firecal.model.variables import bloque_clima, completar_con_noaa20  # noqa: E402
from firecal.sectores.historial import focos_con_evento  # noqa: E402
from firecal.sectores.recomendaciones import condiciones_clima  # noqa: E402


def main() -> int:
    publico, pr = config.PUBLIC_DIR, config.PROCESSED_DIR
    ruta_manifest = publico / "manifest.json"
    if not ruta_manifest.exists():
        print("Falta public/manifest.json: corre primero scripts/09_exportar.py.")
        return 1
    riesgo = pd.read_parquet(pr / "riesgo.parquet")
    validar_riesgo(riesgo)
    ultimo = riesgo[riesgo["valido_para"] == riesgo["valido_para"].max()]
    fecha_dato = pd.Timestamp(ultimo["valido_para"].max()) - pd.Timedelta(days=1)  # último día con focos (igual que el paso 13)

    clima = bloque_clima(config.INTERIM_DIR / "clima_diario.parquet")
    fecha_clima = min(fecha_dato, pd.Timestamp(clima["fecha"].max())) if clima is not None else None
    cond = condiciones_clima(clima, fecha_clima) if clima is not None else pd.DataFrame()

    comunas = gpd.read_parquet(config.INTERIM_DIR / "comunas.parquet")
    nombres = dict(zip(comunas["region_id"].astype(str), comunas["nombre"]))
    regiones = dict(zip(comunas["region_id"].astype(str), comunas["region"]))

    # Focos de incendio (como el paso 15): sin Suomi NPP desde su corte (NOAA-20 en su lugar), agrupados en eventos y
    # sin las detecciones en sectores marcados como fuente persistente (industria) del piloto de Valparaíso.
    focos = pd.read_parquet(config.INTERIM_DIR / "focos_calidad.parquet",
                            columns=["lat", "lon", "fecha_local", "satelite", "uso_base", "frp", "region_id"])
    focos, _ = completar_con_noaa20(focos)
    ev = focos_con_evento(focos)
    ev = ev[ev["region_id"].notna() & (ev["fecha_local"] >= INICIO_DATOS)
            & (ev["fecha_local"] < fecha_dato + pd.Timedelta(days=1))]
    ruta_s = pr / "sectores_05.parquet"
    if ruta_s.exists():
        s = gpd.read_parquet(ruta_s)
        pers = s[s["fuente_persistente"]].to_crs("EPSG:4326")
        pts = gpd.GeoDataFrame(ev, geometry=gpd.points_from_xy(ev["lon"], ev["lat"]), crs="EPSG:4326")
        dentro = gpd.sjoin(pts[["geometry"]], pers[["geometry"]], predicate="within", how="inner").index.unique()
        ev = ev.drop(index=dentro)
    dias_fuego = {str(rid): g["fecha_local"].dt.normalize() for rid, g in ev.groupby(ev["region_id"].astype(str))}

    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    datos = comunas_pais(riesgo, cond, nombres, regiones, dias_fuego, fecha_dato, fecha_clima, ahora)
    ruta = publico / ARCHIVO_COMUNAS
    ruta.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    m = json.loads(ruta_manifest.read_text(encoding="utf-8"))
    m["contrato"] = VERSION_CONTRATO
    m["archivos"]["comunas"] = ARCHIVO_COMUNAS
    ruta_manifest.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

    cs = datos["comunas"]
    con_rec = sum(1 for c in cs if c["recomendaciones"].get("24"))
    print(f"{ARCHIVO_COMUNAS}: {len(cs)} comunas, clima del {datos['fecha_clima']}, "
          f"{sum(c['fuego_activo'] for c in cs)} con fuego activo, {sum(bool(c['clima_ultimo_dia'] and c['clima_ultimo_dia']['condiciones']) for c in cs)} "
          f"con alguna condición de clima, {con_rec} con recomendaciones a 24 h; {ruta.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
