"""Paso 4b: máscara de fuentes persistentes que FIRMS no marca (industria, minería, volcanes, rellenos).

No corre a diario: se mide con la historia y se versiona. Conviene repetirlo una vez al año (una fuente nueva no se
marca hasta entonces) y después rehacer la carga completa. Regla y parámetros: firecal.fuentes_persistentes.

Entrada:  data/interim/focos_calidad.parquet (paso 4; usa es_vegetacion y confianza_ok, no uso_base, para que la
          máscara no dependa de la anterior) y data/interim/comunas.parquet (nombres).
          ESA WorldCover 2021 v200 (10 m): solo ventanas de 1,5 km alrededor de cada celda con fuego repetido, por
          peticiones HTTP de rango a los mosaicos públicos (no se bajan los mosaicos).
Salidas:  ref/fuentes_persistentes.csv  la máscara (una fila por celda y grilla; versionada)
          docs/fuentes_persistentes.md  método y cifras

Uso:
    python scripts/04b_fuentes_persistentes.py
    python scripts/04b_fuentes_persistentes.py --desde 2012-02-01 --hasta 2026-01-01
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "4")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import rasterio  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402

from firecal import config  # noqa: E402
from firecal import fuentes_persistentes as fp  # noqa: E402
from firecal.events.agrupar import etiquetar_eventos  # noqa: E402
from firecal.reportes import tabla_md  # noqa: E402

WORLDCOVER = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
              "ESA_WorldCover_10m_2021_v200_{t}_Map.tif")
VEGETACION = [10, 20, 30, 40, 90, 95, 100]  # árboles, matorral, pastizal, cultivo, humedal, manglar, musgo y liquen
MEDIO_LADO_KM = 0.75
DOC = config.RAIZ / "docs" / "fuentes_persistentes.md"
ZONAS = {**{r: "Norte (15, 1, 2, 3)" for r in ["15", "01", "02", "03"]}, "04": "Coquimbo (4)",
         **{r: "Centro (5, 13, 6, 7)" for r in ["05", "13", "06", "07"]},
         **{r: "Sur (16, 8, 9, 14, 10)" for r in ["16", "08", "09", "14", "10"]},
         **{r: "Austral (11, 12)" for r in ["11", "12"]}}
# Comunas con incendios forestales o quemas agrícolas frecuentes: la máscara no debería tocarlas.
REFERENCIA = {"09202": "Collipulli", "08301": "Los Ángeles", "07401": "Linares", "07301": "Curicó", "04301": "Ovalle",
              "09101": "Temuco", "15201": "Putre", "15202": "General Lagos"}


def mosaico(lat: float, lon: float) -> str:
    la, lo = math.floor(lat / 3) * 3, math.floor(lon / 3) * 3
    return f"{'S' if la < 0 else 'N'}{abs(la):02d}{'W' if lo < 0 else 'E'}{abs(lo):03d}"


def frac_vegetacion(lat: float, lon: float) -> float:
    """Parte de los píxeles de WorldCover con vegetación en una ventana de 1,5 km; NaN si no se pudo leer."""
    dlat = MEDIO_LADO_KM / 111.0
    dlon = dlat / math.cos(math.radians(lat))
    for intento in range(3):
        try:
            with rasterio.open(f"/vsicurl/{WORLDCOVER.format(t=mosaico(lat, lon))}") as r:
                a = r.read(1, window=from_bounds(lon - dlon, lat - dlat, lon + dlon, lat + dlat, r.transform))
            a = a[a > 0]
            return float(np.isin(a, VEGETACION).mean()) if a.size else float("nan")
        except Exception:  # noqa: BLE001 (red: se reintenta y, si no, queda sin dato)
            time.sleep(2 * (intento + 1))
    return float("nan")


def miles(n) -> str:
    return f"{int(n):,}".replace(",", " ")


def dias_por_comuna(f: pd.DataFrame) -> pd.Series:
    return f.groupby("region_id")["dia"].nunique()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--desde", default="2012-02-01")
    ap.add_argument("--hasta", default="2026-01-01", help="exclusivo")
    args = ap.parse_args()
    t0 = time.time()

    todos = pd.read_parquet(config.INTERIM_DIR / "focos_calidad.parquet",
                            columns=["lat", "lon", "fecha_local", "dia_noche", "satelite", "region_id",
                                     "es_vegetacion", "confianza_ok"])
    todos = todos[todos["region_id"].notna()].copy()
    todos["region_id"] = todos["region_id"].astype(str)
    todos["dia"] = todos["fecha_local"].dt.normalize()
    base = todos[(todos["satelite"] == fp.SATELITE) & todos["es_vegetacion"] & todos["confianza_ok"]
                 & (todos["dia"] >= args.desde) & (todos["dia"] < args.hasta)].copy()
    base["evento"] = etiquetar_eventos(base)
    print(f"Focos {fp.SATELITE} de vegetación, {args.desde} a {args.hasta}: {len(base):,} ({time.time() - t0:.0f} s)")

    celdas = pd.concat([fp.metricas_celdas(base, d) for d in fp.DESFASES_M], ignore_index=True)
    print(f"Celdas con fuego repetido (>= {fp.MIN_DIAS} días de >= {fp.MIN_ANIOS} años): {len(celdas)}; "
          "leyendo WorldCover…")
    with ThreadPoolExecutor(max_workers=16) as ex:
        celdas["frac_vegetacion"] = list(ex.map(frac_vegetacion, celdas["lat"], celdas["lon"]))
    sin_dato = int(celdas["frac_vegetacion"].isna().sum())
    print(f"WorldCover leído ({time.time() - t0:.0f} s); celdas sin dato: {sin_dato}")
    if sin_dato > 0.05 * len(celdas):
        print("ERROR: más de 5 % de las celdas sin dato de WorldCover; revisar la conexión y repetir")
        return 1

    celdas = fp.clasificar(celdas)
    nombres = dict(pd.read_parquet(config.INTERIM_DIR / "comunas.parquet", columns=["region_id", "nombre"])
                   .astype(str).itertuples(index=False, name=None))
    celdas["comuna"] = celdas["region_id"].map(nombres)
    mascara = (celdas[celdas["persistente"]]
               .sort_values(["desfase_m", "region_id", "dias"], ascending=[True, True, False])[fp.COLUMNAS_MASCARA])
    fp.RUTA_MASCARA.parent.mkdir(parents=True, exist_ok=True)
    mascara.round({"lat": 5, "lon": 5, "frac_noche": 3, "frac_vegetacion": 3}).to_csv(fp.RUTA_MASCARA, index=False)
    print(f"Máscara: {len(mascara)} celdas → {fp.RUTA_MASCARA}")

    # Efecto: días con focos por comuna antes y después (Suomi NPP, mismo período)
    base["persistente"] = fp.en_fuente_persistente(base, mascara)
    antes, despues = dias_por_comuna(base), dias_por_comuna(base[~base["persistente"]])
    ef = pd.DataFrame({"Comuna": antes.index.map(nombres), "Días con focos": antes,
                       "Sin fuentes persistentes": despues.reindex(antes.index).fillna(0).astype(int)})
    ef["Días que se quitan (%)"] = (1 - ef["Sin fuentes persistentes"] / ef["Días con focos"]) * 100
    ef.index.name = "Código"
    afectadas = ef[ef["Días que se quitan (%)"] > 0]
    # Las que salen de uso_base: de vegetación y con confianza (las demás ya no se contaban), todos los sensores y años.
    veg = todos[todos["es_vegetacion"] & todos["confianza_ok"]]
    todos_masc = fp.en_fuente_persistente(veg, mascara)
    print(f"Detecciones {fp.SATELITE} marcadas: {base['persistente'].sum():,} ({base['persistente'].mean():.1%}); "
          f"comunas afectadas: {len(afectadas)}; detecciones de vegetación de todos los sensores y años que salen de "
          f"uso_base: {int(todos_masc.sum()):,} de {len(veg):,}")

    celdas["Zona"] = celdas["region_id"].str[:2].map(ZONAS)
    por_zona = celdas.groupby("Zona").agg(**{"Fuego repetido": ("persistente", "size"),
                                             "Sin vegetación": ("sin_vegetacion", "sum"),
                                             "Nocturna y fija": ("nocturna_fija", "sum"),
                                             "Persistentes": ("persistente", "sum")})
    lista = (mascara[mascara["desfase_m"] == 0].sort_values("dias", ascending=False).head(40)
             .assign(**{"% noche": lambda d: (d["frac_noche"] * 100).round(0),
                        "% vegetación": lambda d: (d["frac_vegetacion"] * 100).round(0)})
             [["comuna", "lat", "lon", "dias", "anios", "% noche", "% vegetación", "motivo"]]
             .rename(columns={"comuna": "Comuna", "dias": "Días", "anios": "Años", "motivo": "Motivo"})
             .set_index("Comuna"))
    ref = ef.reindex([r for r in REFERENCIA if r in ef.index])

    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    texto = f"""# Fuentes persistentes que FIRMS no marca

Generado por `scripts/04b_fuentes_persistentes.py` el {hoy}. Máscara: `ref/fuentes_persistentes.csv`.

## Por qué
FIRMS marca algunas fuentes fijas (`tipo` 2) y volcanes (`tipo` 1), pero no todas, y los focos casi en tiempo real no
traen esa marca. Refinerías, fundiciones, faenas mineras, rellenos sanitarios y volcanes se detectan año tras año en el
mismo lugar y se contaban como incendios: subían la serie, el riesgo y lo «normal» de comunas como Concón, Copiapó o
Calama. La regla de los sectores de Valparaíso (`firecal.sectores.historial`) ya las detectaba de noche; en el desierto
del norte las fuentes son diurnas y esa regla no las veía.

## Regla
Celdas de 1 km (UTM 19S) y otra grilla corrida 500 m, con focos {fp.SATELITE} de vegetación y confianza nominal o alta
entre {args.desde} y {args.hasta} (exclusivo):

- **Fuego repetido:** focos en >= {fp.MIN_DIAS} días de >= {fp.MIN_ANIOS} años distintos.
- **Fuente persistente:** fuego repetido y además
  - **sin vegetación:** < {fp.MAX_VEGETACION:.0%} de vegetación en ESA WorldCover 2021 (ventana de 1,5 km), o
  - **nocturna y fija:** >= {fp.MIN_NOCHE:.0%} de las detecciones de noche y nunca parte de un incendio de más de
    {fp.MAX_FOCOS_INCENDIO} focos o que pase de {fp.MAX_EXTENSION_KM} km.

Cada foco (de cualquier sensor, también los casi en tiempo real) que cae en una celda de la máscara queda marcado como
`fuente_persistente` en `firecal.calidad` y sale de `uso_base`: no se cuenta en la serie armonizada, el calendario, el
modelo de riesgo, los incendios activos ni lo «normal» de cada comuna.

## Celdas por zona (las dos grillas)
{tabla_md(por_zona)}

Celdas sin dato de WorldCover: {sin_dato} (no se marcan por la vía de la vegetación).

## Efecto ({fp.SATELITE}, {args.desde} a {args.hasta})
- Detecciones marcadas: **{miles(base['persistente'].sum())} de {miles(len(base))} ({base['persistente'].mean():.1%})**.
- Días-comuna con focos que se quitan: **{1 - despues.sum() / antes.sum():.1%}**; comunas con alguna celda: {len(afectadas)};
  con más de 25 % de sus días: {int((afectadas['Días que se quitan (%)'] > 25).sum())}.
- Detecciones de vegetación con confianza de todos los sensores y años (MODIS 2000-, VIIRS 2012-) que salen de
  `uso_base`: {miles(todos_masc.sum())} de {miles(len(veg))} ({todos_masc.mean():.1%}).

### Comunas donde más cambia
{tabla_md(afectadas.sort_values('Días que se quitan (%)', ascending=False).head(30).round(1), 1)}

### Comunas de referencia (incendios forestales o quemas agrícolas frecuentes; no deberían cambiar)
{tabla_md(ref.round(1), 1)}

## Celdas con más días (grilla sin desfase)
{tabla_md(lista, 3)}

## Límites
- La máscara es fija: una fuente nueva no se marca hasta repetir este paso (conviene una vez al año).
- WorldCover es de 2021. Un lugar que se quemó y quedó sin vegetación no cuenta como «sin vegetación» por un incendio
  aislado: la celda además tiene que repetirse en >= {fp.MIN_ANIOS} años.
- Un incendio real dentro de una celda de la máscara no se cuenta (son celdas de 1 km sin vegetación o con una fuente
  industrial; el efecto en las comunas de referencia está arriba).

Fuente de cobertura: Zanaga, D. et al. (2022). *ESA WorldCover 10 m 2021 v200*. https://doi.org/10.5281/zenodo.7254221
(CC BY 4.0), leída por rango desde `{WORLDCOVER.split('/v200')[0]}`.
"""
    DOC.write_text(texto, encoding="utf-8")
    print(f"Reporte: {DOC} ({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
