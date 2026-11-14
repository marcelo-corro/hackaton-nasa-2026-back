"""Paso 5 del pipeline (A): armonización MODIS <-> VIIRS.

1. Cuenta focos `uso_base` por comuna, mes local y satélite.
2. Valida fuera de muestra los métodos de conversión VIIRS (Suomi NPP) -> MODIS (Terra + Aqua):
   calibra con 2012-03..2015-12 y prueba con 2016-01..2017-12 (período estable de ambos sensores).
3. Hace lo mismo para Terra -> Terra + Aqua (calibra 2003-2008, prueba 2009-2011), para los meses sin Aqua.
4. Elige el método de menor error región-mes fuera de muestra (si hay empate, el más simple) y lo reajusta con
   todo el período estable.
5. Mide cuánto se desvía MODIS observado respecto de lo esperado desde 2018 (deriva y cambio de versión).
6. Arma la serie mensual armonizada, la valida contra el contrato y guarda:
   data/processed/serie_mensual.parquet, data/processed/calibracion.json,
   docs/armonizacion.md y docs/figuras/armonizacion_chile.png

Uso:
    python scripts/05_armonizar.py
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
import warnings
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from firecal import config  # noqa: E402
from firecal.contratos import validar_serie_mensual  # noqa: E402
from firecal.harmonize.calibracion import FactorPorGrupo, metodos_candidatos  # noqa: E402
from firecal.harmonize.conteos import conteos_mensuales  # noqa: E402
from firecal.harmonize.evaluacion import metricas  # noqa: E402
from firecal.harmonize.serie import CORTE_MODIS, INICIO_AQUA, construir_serie  # noqa: E402
from firecal.reportes import tabla_md  # noqa: E402

VIIRS_CAL, VIIRS_TRAIN, VIIRS_VALID = ("2012-03", "2017-12"), ("2012-03", "2015-12"), ("2016-01", "2017-12")
TERRA_CAL, TERRA_TRAIN, TERRA_VALID = ("2003-01", "2011-12"), ("2003-01", "2008-12"), ("2009-01", "2011-12")
NOAA20_CAL = ("2019-01", "2025-12")
EMPATE = 0.005  # diferencias de error región-mes menores que esto se consideran empate

COLUMNAS_METRICAS = {
    "sesgo_total": "Sesgo total",
    "wape_comuna_mes": "Error comuna-mes",
    "wape_region_mes": "Error región-mes",
    "wape_nacional_mes": "Error nacional-mes",
    "corr_nacional_mensual": "Correlación nacional",
    "cobertura_90": "Cobertura 90 %",
}


def ventana(df: pd.DataFrame, desde: str, hasta: str) -> pd.DataFrame:
    p = df["periodo"]
    return df[(p >= pd.Period(desde, freq="M")) & (p <= pd.Period(hasta, freq="M"))]


def comparar(train: pd.DataFrame, valid: pd.DataFrame, x: str, y: str) -> pd.DataFrame:
    filas = []
    for metodo in metodos_candidatos(x, y):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            metodo.ajustar(train)
            pred = metodo.predecir(valid)
            bajo, alto = metodo.intervalo(valid)
        filas.append({"Método": metodo.nombre, **metricas(valid, y, pred, bajo, alto)})
    return pd.DataFrame(filas).set_index("Método")


def elegir(tabla: pd.DataFrame) -> str:
    """Menor error región-mes; entre los empatados, el primero de la lista (el más simple)."""
    mejor = tabla["wape_region_mes"].min()
    return str(tabla.index[tabla["wape_region_mes"] <= mejor + EMPATE][0])


def reajustar(nombre: str, x: str, y: str, datos: pd.DataFrame):
    metodo = next(m for m in metodos_candidatos(x, y) if m.nombre == nombre)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return metodo.ajustar(datos)


def describir(metodo, ventana_cal: tuple[str, str]) -> dict:
    info = {"nombre": metodo.nombre, "x": metodo.x, "y": metodo.y, "calibrado": list(ventana_cal),
            "alpha": metodo.alpha}
    if isinstance(metodo, FactorPorGrupo):
        info |= {"grupo": metodo.grupo, "razon_global": metodo.razon_global,
                 "razones": {str(k): v for k, v in metodo.razones.items()}}
    return info


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")


def deriva_modis(m: pd.DataFrame, conv_viirs) -> pd.DataFrame:
    """Observado / esperado - 1 por año: cuánto cuenta MODIS respecto de lo que VIIRS indica que debería contar."""
    cal = ventana(m, *VIIRS_CAL)
    filas = {}
    esperado = {"MODIS (Terra + Aqua)": conv_viirs.predecir(m)}
    for sat in ("terra", "aqua"):
        esperado[sat.capitalize()] = FactorPorGrupo("snpp", sat).ajustar(cal).predecir(m)
    obs = {"MODIS (Terra + Aqua)": m["modis"], "Terra": m["terra"], "Aqua": m["aqua"]}
    validos = m["snpp"].notna() & (m["periodo"] >= pd.Period("2012-03", freq="M"))
    for nombre in obs:
        o = obs[nombre][validos].astype(float).groupby(m.loc[validos, "anio"]).sum()
        e = esperado[nombre][validos].astype(float).groupby(m.loc[validos, "anio"]).sum()
        filas[nombre] = (o / e - 1) * 100
    tabla = pd.DataFrame(filas)
    tabla.index.name = "año"
    return tabla


def figura(serie: pd.DataFrame, conv_viirs, ruta: Path) -> None:
    anual = serie.groupby("anio")[["modis", "viirs", "armonizado"]].sum(min_count=1).astype(float)
    anual = anual.loc[2001:]  # 2000 solo tiene noviembre y diciembre
    tramo = serie["anio"] >= int(CORTE_MODIS[:4])
    mu = serie.loc[tramo, "armonizado"]
    var = (mu + conv_viirs.alpha * mu**2).groupby(serie.loc[tramo, "anio"]).sum()
    sd = np.sqrt(var)

    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=150)
    ax.plot(anual.index, anual["modis"], color="#9e9e9e", lw=1.8, marker="o", ms=3, label="MODIS observado (crudo)")
    viirs = anual["viirs"]
    ax.plot(viirs.index, viirs, color="#e66101", lw=1.8, marker="o", ms=3, label="VIIRS Suomi NPP (crudo)")
    ax.plot(anual.index, anual["armonizado"], color="#253494", lw=2.6, label="Serie armonizada (equivalente MODIS)")
    ax.fill_between(sd.index, (anual.loc[sd.index, "armonizado"] - 1.645 * sd).clip(lower=0),
                    anual.loc[sd.index, "armonizado"] + 1.645 * sd, color="#253494", alpha=0.18,
                    label="Intervalo 90 % (convertido desde VIIRS)")
    ax.axvline(2012, color="#e66101", ls=":", lw=1)
    ax.axvline(int(CORTE_MODIS[:4]) - 0.5, color="#253494", ls=":", lw=1)
    ax.text(2012.1, ax.get_ylim()[1] * 0.93, "entra VIIRS", color="#e66101", fontsize=8)
    ax.text(int(CORTE_MODIS[:4]) - 0.4, ax.get_ylim()[1] * 0.85, "MODIS se desvía:\nse usa VIIRS convertido",
            color="#253494", fontsize=8)
    ax.set_yscale("log")
    ax.set_xlim(anual.index.min() - 0.5, anual.index.max() + 0.5)
    ax.set_title("Focos de vegetación por año en Chile: crudos vs. armonizados", fontsize=11)
    ax.set_ylabel("Focos por año (escala log)")
    ax.grid(alpha=0.3, which="both")
    ax.legend(fontsize=8, loc="lower right")
    fig.text(0.01, 0.01, "Fuente: NASA FIRMS (MODIS C6.1, VIIRS 375 m). Focos de vegetación con confianza nominal o alta. "
             "MODIS crudo 2001-2002: solo Terra (Aqua desde jul-2002). VIIRS 2012: desde febrero.", fontsize=7,
             color="#555555")
    fig.tight_layout()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta)
    plt.close(fig)


def main() -> int:
    focos = pd.read_parquet(config.INTERIM_DIR / "focos_calidad.parquet")
    comunas = pd.read_parquet(config.INTERIM_DIR / "comunas.parquet", columns=["region_id", "cod_region"])
    m = conteos_mensuales(focos, comunas)
    m["modis"] = (m["terra"] + m["aqua"]).astype("Int64")  # nulo antes de Aqua: solo para calibrar

    print("Validación VIIRS -> MODIS (calibra 2012-03..2015-12, prueba 2016-2017)...")
    t_viirs = comparar(ventana(m, *VIIRS_TRAIN), ventana(m, *VIIRS_VALID), "snpp", "modis")
    elegido_viirs = elegir(t_viirs)
    conv_viirs = reajustar(elegido_viirs, "snpp", "modis", ventana(m, *VIIRS_CAL))

    print("Validación Terra -> Terra + Aqua (calibra 2003-2008, prueba 2009-2011)...")
    t_terra = comparar(ventana(m, *TERRA_TRAIN), ventana(m, *TERRA_VALID), "terra", "modis")
    elegido_terra = elegir(t_terra)
    conv_terra = reajustar(elegido_terra, "terra", "modis", ventana(m, *TERRA_CAL))

    deriva = deriva_modis(m, conv_viirs)
    conv_noaa20 = FactorPorGrupo("noaa20", "snpp").ajustar(ventana(m, *NOAA20_CAL))
    n20 = ventana(m, "2018-04", "2025-12").dropna(subset=["noaa20", "snpp"])
    noaa20_anual = n20.groupby("anio")[["noaa20", "snpp"]].sum().astype(float)
    noaa20_anual["NOAA-20 / Suomi NPP"] = noaa20_anual["noaa20"] / noaa20_anual["snpp"]
    noaa20_anual.index.name = "año"

    metodo = f"{slug(elegido_viirs)}_snpp_{VIIRS_CAL[0][:4]}-{VIIRS_CAL[1][:4]}_v1"
    serie = construir_serie(m, conv_viirs, conv_terra, metodo=metodo)
    validar_serie_mensual(serie, n_comunas=len(comunas))

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    serie.to_parquet(config.PROCESSED_DIR / "serie_mensual.parquet", index=False)
    generado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    calibracion = {
        "generado_utc": generado,
        "metodo": metodo,
        "unidad": "focos equivalentes MODIS (Terra + Aqua, órbita nominal, procesamiento previo a 2018)",
        "inicio_aqua": INICIO_AQUA,
        "corte_modis": CORTE_MODIS,
        "viirs_a_modis": describir(conv_viirs, VIIRS_CAL),
        "terra_a_modis": describir(conv_terra, TERRA_CAL),
        "noaa20_a_snpp": describir(conv_noaa20, NOAA20_CAL),
    }
    (config.PROCESSED_DIR / "calibracion.json").write_text(json.dumps(calibracion, ensure_ascii=False, indent=2),
                                                          encoding="utf-8")

    ruta_figura = config.RAIZ / "docs" / "figuras" / "armonizacion_chile.png"
    figura(serie, conv_viirs, ruta_figura)

    v = t_viirs.loc[elegido_viirs]
    reporte = [
        "# Armonización MODIS ↔ VIIRS",
        f"_Generado por `scripts/05_armonizar.py` el {generado}. No editar a mano: se regenera._",
        "",
        "## Resumen",
        f"- **Serie:** {serie['region_id'].nunique()} comunas × {serie.groupby('region_id').size().iloc[0]} meses "
        f"({serie['anio'].min()}-{serie['mes'].iloc[0]:02d} a {serie['anio'].max()}-12), en **focos equivalentes MODIS**: "
        "lo que habrían contado Terra + Aqua con su órbita nominal y su procesamiento previo a 2018.",
        f"- **Método elegido:** {elegido_viirs}. Razón VIIRS/MODIS = **{conv_viirs.razon_global:.2f}** "
        f"(calibrada {VIIRS_CAL[0]} a {VIIRS_CAL[1]})."
        if isinstance(conv_viirs, FactorPorGrupo) else f"- **Método elegido:** {elegido_viirs}.",
        f"- **Validación fuera de muestra (2016-2017):** sesgo {v['sesgo_total']*100:+.1f} %, error región-mes "
        f"{v['wape_region_mes']*100:.1f} %, error nacional-mes {v['wape_nacional_mes']*100:.1f} %, "
        f"correlación nacional {v['corr_nacional_mensual']:.3f}, cobertura del intervalo del 90 % "
        f"{v['cobertura_90']*100:.0f} %.",
        "- **Hallazgo:** los métodos más complejos (por región, por mes, modelos de conteo) no mejoran fuera de "
        "muestra: las diferencias por región y temporada que se ven al calibrar no se repiten de un año a otro. Lo "
        "decisivo es calibrar en el período en que MODIS todavía es estable.",
        "",
        "| Período | Serie armonizada | Por qué |",
        "|---|---|---|",
        f"| 2000-11 a {pd.Period(INICIO_AQUA, freq='M') - 1} | Terra convertido a Terra + Aqua ({elegido_terra}) | "
        "Aqua todavía no existía |",
        f"| {INICIO_AQUA} a {pd.Period(CORTE_MODIS, freq='M') - 1} | MODIS observado (Terra + Aqua) | Referencia estable |",
        f"| {CORTE_MODIS} en adelante | VIIRS Suomi NPP convertido a escala MODIS | MODIS cambia de procesamiento en "
        "2018 y su órbita se desvía; VIIRS es estable |",
        "",
        "![Focos por año: crudos vs. armonizados](figuras/armonizacion_chile.png)",
        "",
        "## 1. VIIRS → MODIS: comparación de métodos",
        "Calibración 2012-03 a 2015-12, prueba 2016-01 a 2017-12 (incluye los megaincendios de 2017). Errores "
        "relativos ponderados (suma de errores absolutos / suma observada). Regla de elección: menor error "
        f"región-mes; con diferencias menores a {EMPATE*100:.1f} puntos, el método más simple.",
        "",
        tabla_md(t_viirs.rename(columns=COLUMNAS_METRICAS), 3),
        "",
        "## 2. Terra → Terra + Aqua (meses antes de Aqua)",
        "Calibración 2003-2008, prueba 2009-2011.",
        "",
        tabla_md(t_terra.rename(columns=COLUMNAS_METRICAS), 3),
        "",
        "## 3. Deriva de MODIS: cuánto cuenta respecto de lo esperado según VIIRS (%)",
        "Negativo = MODIS detecta menos de lo que debería. Cerca de 0 en 2012-2017 (período de calibración); desde 2018 "
        "refleja el cambio de procesamiento y la deriva de órbita (ver [calidad_datos.md](calidad_datos.md)).",
        "",
        tabla_md(deriva, 1),
        "",
        "## 4. Continuidad de VIIRS: NOAA-20 frente a Suomi NPP",
        f"Factor NOAA-20 / Suomi NPP calibrado {NOAA20_CAL[0]} a {NOAA20_CAL[1]}: **{conv_noaa20.razon_global:.3f}**. "
        "Guardado en `data/processed/calibracion.json` para cuando Suomi NPP deje de entregar datos. No se usa en la "
        "serie actual (Suomi NPP cubre hasta 2025) y nunca se suman ambos satélites.",
        "",
        tabla_md(noaa20_anual[["NOAA-20 / Suomi NPP"]], 3),
        "",
        "## 5. Límites",
        "- La conversión supone que la relación VIIRS/MODIS de 2012-2017 se mantiene. VIIRS es estable en ese "
        "período y después; la validación cubre dos años, uno de ellos extremo (2017).",
        f"- Los meses de 2000-11 a {pd.Period(INICIO_AQUA, freq='M') - 1} (solo Terra) son los menos precisos: error "
        f"nacional-mes {t_terra.loc[elegido_terra, 'wape_nacional_mes']*100:.0f} % en la prueba, contra "
        f"{v['wape_nacional_mes']*100:.1f} % de la conversión desde VIIRS. Sus intervalos son más anchos.",
        "- A escala de una comuna y un mes el error es alto (ver la tabla); para decidir conviene mirar agregados "
        "(región, temporada, año) y el intervalo `armonizado_p05`-`armonizado_p95`.",
        "- Desde 2018 la serie es un valor esperado (más suave) y antes es un conteo observado: los percentiles que "
        "mezclan ambos períodos deben leerse con cuidado.",
        "- Se cuentan **detecciones** de vegetación con confianza nominal o alta (`uso_base`), no incendios ni "
        "superficie quemada.",
        "",
    ]
    (config.RAIZ / "docs" / "armonizacion.md").write_text("\n".join(reporte), encoding="utf-8")

    print("\nVIIRS -> MODIS (prueba 2016-2017):")
    print(t_viirs[["sesgo_total", "wape_region_mes", "wape_nacional_mes", "cobertura_90"]].round(3).to_string())
    print(f"Elegido: {elegido_viirs}  |  Terra -> Terra + Aqua: {elegido_terra}")
    print("\nDeriva de MODIS (%):")
    print(deriva.loc[2016:].round(1).to_string())
    print(f"\nSerie: {len(serie):,} filas, método {metodo} -> {config.PROCESSED_DIR / 'serie_mensual.parquet'}")
    print("Reporte: docs/armonizacion.md  |  Figura: docs/figuras/armonizacion_chile.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
