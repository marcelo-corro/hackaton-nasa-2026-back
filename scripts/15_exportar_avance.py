"""Paso 15: zona probable de avance de los incendios activos de Chile → public/avance/activos.json (contrato 0.7).

Se corre DESPUÉS de 09_exportar.py y 13_exportar_sectores.py, y ANTES de 10_publicar.py.

Por cada incendio con focos en los últimos 3 días: el centro de sus focos más recientes, dos círculos (2,5 km cubrieron
el ~70 % de los avances del día siguiente en la prueba 2022-2026; 3,6 km, el ~85 %) y el viento del día. La flecha de
viento se muestra SOLO con viento fuerte: ahí el avance siguió el viento el ~36 % de las veces (al azar, 25 %). No se
publica un cono: con estos datos, la dirección se acierta poco (ver docs/avance_validacion.md).

Entradas: focos_calidad.parquet, viento_diario.parquet (paso 5d), avance_params.json (paso 14), riesgo_horizontes.json
(paso 8), sectores_05.parquet (fuentes persistentes del piloto de Valparaíso; las del resto del país ya vienen
fuera de `uso_base`, ver firecal.fuentes_persistentes).

Uso:
    python scripts/15_exportar_avance.py
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
from firecal.avance import ficha_avance, incendios_activos  # noqa: E402
from firecal.export.contrato import VERSION_CONTRATO  # noqa: E402
from firecal.model.variables import completar_con_noaa20  # noqa: E402
from firecal.sectores.historial import focos_con_evento  # noqa: E402

RUTA = "avance/activos.json"


def main() -> int:
    publico, pr = config.PUBLIC_DIR, config.PROCESSED_DIR
    ruta_manifest = publico / "manifest.json"
    if not ruta_manifest.exists():
        print("Falta public/manifest.json: corre primero 09_exportar.py y 13_exportar_sectores.py.")
        return 1
    info = json.loads((pr / "riesgo_horizontes.json").read_text(encoding="utf-8"))
    params = json.loads((pr / "avance_params.json").read_text(encoding="utf-8"))
    ultimo = pd.Timestamp(info["ultimo_dato"])

    focos = pd.read_parquet(config.INTERIM_DIR / "focos_calidad.parquet",
                            columns=["lat", "lon", "fecha_local", "satelite", "uso_base", "frp", "region_id"])
    focos, _ = completar_con_noaa20(focos)
    ev = focos_con_evento(focos)
    ev = ev[ev["region_id"].notna() & (ev["fecha_local"] <= ultimo + pd.Timedelta(days=1))]
    # Fuera: focos en sectores marcados como fuente persistente (industria) del piloto de Valparaíso
    ruta_s = pr / "sectores_05.parquet"
    if ruta_s.exists():
        s = gpd.read_parquet(ruta_s)
        pers = s[s["fuente_persistente"]].to_crs("EPSG:4326")
        pts = gpd.GeoDataFrame(ev, geometry=gpd.points_from_xy(ev["lon"], ev["lat"]), crs="EPSG:4326")
        dentro = gpd.sjoin(pts[["geometry"]], pers[["geometry"]], predicate="within", how="inner").index.unique()
        ev = ev.drop(index=dentro)
    act = incendios_activos(ev, ultimo)

    viento = pd.read_parquet(config.INTERIM_DIR / "viento_diario.parquet").rename(columns={"fecha_local": "fecha"})
    viento["region_id"] = viento["region_id"].astype(str)
    comunas = gpd.read_parquet(config.INTERIM_DIR / "comunas.parquet")
    nombres = dict(zip(comunas["region_id"].astype(str), comunas["nombre"]))
    regiones = dict(zip(comunas["region_id"].astype(str), comunas["region"]))
    incendios = []
    for _, inc in act.sort_values(["ultimo_foco", "focos_ultimo_dia"], ascending=[False, False]).iterrows():
        rid = inc["region_id"]
        incendios.append({
            "id": f"{rid}-{pd.Timestamp(inc['inicio']):%Y%m%d}-{int(inc['evento'])}",
            "region_id": rid, "comuna": nombres.get(rid), "region": regiones.get(rid),
            "lat": inc["lat"], "lon": inc["lon"],
            "inicio": f"{pd.Timestamp(inc['inicio']):%Y-%m-%d}", "ultimo_foco": f"{pd.Timestamp(inc['ultimo_foco']):%Y-%m-%d}",
            "focos_ultimo_dia": inc["focos_ultimo_dia"], "focos_incendio": inc["focos_incendio"],
            "dias_con_focos": inc["dias_con_focos"],
            **ficha_avance(inc, viento[viento["region_id"] == rid], params),
        })
    coma = lambda x: f"{x:.1f}".replace(".", ",")  # noqa: E731
    salida = {
        "contrato": VERSION_CONTRATO, "ejemplo": False,
        "calculado_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ultimo_dato": info["ultimo_dato"],
        "nota": (f"Incendios con focos satelitales (VIIRS) en los 3 días hasta el {info['ultimo_dato']}. Círculos: en "
                 f"2022-2026, el frente nuevo del día siguiente cayó dentro de {coma(params['radios_km']['p75'])} km el "
                 f"{params['cobertura_prueba_pct']['p75']:.0f} % de las veces y dentro de "
                 f"{coma(params['radios_km']['p90'])} km el {params['cobertura_prueba_pct']['p90']:.0f} %. Flecha de viento "
                 f"solo con viento fuerte (desde {coma(params['viento_fuerte_desde_ms'])} m/s): ahí el avance siguió el "
                 f"viento el {params['acierto_45_viento_fuerte_prueba_pct']:.0f} % de las veces (al azar, 25 %). No es un "
                 "cono: con estos datos la dirección se acierta poco. No incluye las fuentes fijas que se repiten año "
                 "tras año (industria, minería, volcanes); una fuente nueva puede aparecer hasta que se actualice esa "
                 "lista."),
        "validacion": {"radios_km": params["radios_km"], "cobertura_prueba_pct": params["cobertura_prueba_pct"],
                       "viento_fuerte_desde_ms": params["viento_fuerte_desde_ms"],
                       "acierto_45_viento_fuerte_prueba_pct": params["acierto_45_viento_fuerte_prueba_pct"],
                       "acierto_45_azar_pct": 25.0, "periodo_prueba": "2022-2026"},
        "incendios": incendios,
    }
    ruta = publico / RUTA
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(salida, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    m = json.loads(ruta_manifest.read_text(encoding="utf-8"))
    m["contrato"] = VERSION_CONTRATO
    m["archivos"]["avance"] = RUTA
    ruta_manifest.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
    fuertes = sum(i["mostrar_flecha"] for i in incendios)
    print(f"{len(incendios)} incendios activos (focos hasta {info['ultimo_dato']}); {fuertes} con flecha de viento; "
          f"región 05: {sum(i['region_id'].startswith('05') for i in incendios)} -> {ruta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
