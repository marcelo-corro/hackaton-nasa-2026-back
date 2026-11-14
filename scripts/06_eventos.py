"""Paso 6 del pipeline (A): agrupar focos en incendios y medir la coincidencia entre sensores.

Pregunta: ¿la diferencia entre VIIRS y MODIS es porque VIIRS parte el mismo incendio en más píxeles, o porque
ve incendios que MODIS no ve? Se agrupan los focos `uso_base` de cada sensor en eventos (2 km, 2 días) y se mide:
1. la razón Suomi NPP / MODIS contando focos y contando eventos, por año;
2. su sensibilidad a la distancia y a la ventana de días;
3. qué fracción de los incendios vistos por VIIRS ve también MODIS, por tamaño del incendio y por año.

Salidas: data/processed/eventos.parquet, docs/eventos.md y docs/figuras/eventos_deteccion.png.

Uso:
    python scripts/06_eventos.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from firecal import config  # noqa: E402
from firecal.events.agrupar import etiquetar_eventos, evento_detectado_por, resumir_eventos  # noqa: E402
from firecal.reportes import tabla_md  # noqa: E402

D_KM, T_DIAS = 2.0, 2.0          # definición de evento
D_COINC, T_COINC = 2.0, 1.0      # coincidencia entre sensores: otro sensor a <= 2 km y <= 1 día
BASE = (2013, 2017)              # años completos con MODIS estable y VIIRS
GRUPOS = {"MODIS": ["Terra", "Aqua"], "SNPP": ["SNPP"], "NOAA20": ["NOAA20"]}
TAMANOS = [0, 1, 3, 10, 50, 10**9]
ETIQUETAS_TAMANO = ["1 foco", "2-3", "4-10", "11-50", "más de 50"]


def eventos_de(focos: pd.DataFrame, d_km: float = D_KM, t_dias: float = T_DIAS) -> tuple[pd.DataFrame, object]:
    etiquetas = etiquetar_eventos(focos, d_km, t_dias)
    return resumir_eventos(focos, etiquetas), etiquetas


def figura(por_tamano: pd.DataFrame, por_anio: pd.DataFrame, ruta: Path) -> None:
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2), dpi=150, gridspec_kw={"width_ratios": [1, 1.4]})
    a1.bar(por_tamano.index.astype(str), por_tamano["MODIS también lo ve (%)"], color="#253494")
    for i, v in enumerate(por_tamano["MODIS también lo ve (%)"]):
        a1.text(i, v + 2, f"{v:.0f} %", ha="center", fontsize=8)
    a1.set_ylim(0, 110)
    a1.set_title(f"Incendios vistos por VIIRS que MODIS también ve\n(según tamaño, {BASE[0]}-{BASE[1]})", fontsize=10)
    a1.set_xlabel("Tamaño del incendio (focos VIIRS)")
    a1.set_ylabel("%")

    a2.plot(por_anio.index, por_anio["Incendios grandes (más de 10 focos)"], color="#a50026", marker="o", lw=2,
            label="Incendios grandes (más de 10 focos)")
    a2.plot(por_anio.index, por_anio["Todos"], color="#9e9e9e", marker="o", lw=1.5, label="Todos")
    a2.axvline(2017.5, color="#253494", ls=":", lw=1)
    a2.text(2017.7, 50, "MODIS cambia de\nprocesamiento y\nse desvía de órbita", color="#253494", fontsize=8)
    a2.set_ylim(0, 100)
    a2.set_title("Incendios vistos por VIIRS que MODIS también ve, por año", fontsize=10)
    a2.set_ylabel("%")
    a2.grid(alpha=0.3)
    a2.legend(fontsize=8, loc="lower left")
    fig.text(0.01, 0.01, f"Fuente: NASA FIRMS. Evento = focos a ≤{D_KM:.0f} km y ≤{T_DIAS:.0f} días; coincidencia = "
             f"foco del otro sensor a ≤{D_COINC:.0f} km y ≤{T_COINC:.0f} día.", fontsize=7, color="#555555")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta)
    plt.close(fig)


def main() -> int:
    columnas = ["lat", "lon", "fecha_local", "satelite", "uso_base", "region_id", "frp"]
    focos = pd.read_parquet(config.INTERIM_DIR / "focos_calidad.parquet", columns=columnas)
    focos = focos[focos["uso_base"] & focos["region_id"].notna()]
    por_grupo = {g: focos[focos["satelite"].isin(s)].reset_index(drop=True) for g, s in GRUPOS.items()}

    eventos, etiquetas = {}, {}
    for grupo, f in por_grupo.items():
        eventos[grupo], etiquetas[grupo] = eventos_de(f)
        print(f"{grupo}: {len(f):,} focos -> {len(eventos[grupo]):,} eventos")

    # Coincidencia entre sensores
    snpp, modis = por_grupo["SNPP"], por_grupo["MODIS"]
    ev_snpp = eventos["SNPP"]
    ev_snpp["visto_por_otro"] = evento_detectado_por(snpp, etiquetas["SNPP"], modis, D_COINC, T_COINC).reindex(
        ev_snpp["evento"]).to_numpy()
    ev_modis = eventos["MODIS"]
    ev_modis["visto_por_otro"] = evento_detectado_por(modis, etiquetas["MODIS"], snpp, D_COINC, T_COINC).reindex(
        ev_modis["evento"]).to_numpy()
    ev_n20 = eventos["NOAA20"]
    ev_n20["visto_por_otro"] = evento_detectado_por(por_grupo["NOAA20"], etiquetas["NOAA20"], snpp, D_COINC,
                                                    T_COINC).reindex(ev_n20["evento"]).to_numpy()

    for grupo, e in eventos.items():
        e["grupo"] = grupo
        e["anio"] = e["inicio"].dt.year
    tabla_eventos = pd.concat(eventos.values(), ignore_index=True)
    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    tabla_eventos.to_parquet(config.PROCESSED_DIR / "eventos.parquet", index=False)

    # 1. Razones por año
    focos_anio = {g: f.groupby(f["fecha_local"].dt.year).size() for g, f in por_grupo.items()}
    eventos_anio = {g: e.groupby("anio").size() for g, e in eventos.items()}
    razones = pd.DataFrame({
        "Focos SNPP/MODIS": focos_anio["SNPP"] / focos_anio["MODIS"],
        "Eventos SNPP/MODIS": eventos_anio["SNPP"] / eventos_anio["MODIS"],
        "Focos por evento MODIS": focos_anio["MODIS"] / eventos_anio["MODIS"],
        "Focos por evento SNPP": focos_anio["SNPP"] / eventos_anio["SNPP"],
    }).loc[2012:2025]
    razones.index.name = "año"

    # 2. Sensibilidad de la razón de eventos
    filas = []
    for d in (1, 2, 4, 8):
        for t in (1, 2, 4):
            e1, _ = eventos_de(snpp, d, t)
            e2, _ = eventos_de(modis, d, t)
            n1 = e1["inicio"].dt.year.between(*BASE).sum()
            n2 = e2["inicio"].dt.year.between(*BASE).sum()
            filas.append({"Distancia (km)": d, "Días": t, "razón": n1 / n2})
    sensibilidad = pd.DataFrame(filas).pivot(index="Distancia (km)", columns="Días", values="razón")
    sensibilidad.columns = [f"{c} día(s)" for c in sensibilidad.columns]

    # 3. Coincidencia por tamaño y por año
    ev_snpp["tamano"] = pd.cut(ev_snpp["n_focos"], TAMANOS, labels=ETIQUETAS_TAMANO)
    base = ev_snpp[ev_snpp["anio"].between(*BASE)]
    por_tamano = base.groupby("tamano", observed=True).agg(
        eventos=("evento", "size"), visto=("visto_por_otro", "mean"), frp=("frp_total", "median"))
    por_tamano = pd.DataFrame({
        "Incendios": por_tamano["eventos"],
        "% del total": 100 * por_tamano["eventos"] / por_tamano["eventos"].sum(),
        "MODIS también lo ve (%)": 100 * por_tamano["visto"],
        "FRP total mediana (MW)": por_tamano["frp"],
    })
    por_tamano.index.name = "Tamaño (focos VIIRS)"
    recientes = ev_snpp[ev_snpp["anio"] >= 2012]
    por_anio = pd.DataFrame({
        "Todos": 100 * recientes.groupby("anio")["visto_por_otro"].mean(),
        "Incendios grandes (más de 10 focos)": 100 * recientes[recientes["n_focos"] > 10].groupby("anio")[
            "visto_por_otro"].mean(),
    })
    por_anio.index.name = "año"
    modis_visto = 100 * ev_modis[ev_modis["anio"].between(*BASE)]["visto_por_otro"].mean()
    n20_visto = 100 * ev_n20[ev_n20["anio"].between(2019, 2025)]["visto_por_otro"].mean()

    # 4. Caso Viña del Mar, febrero 2024: incendios que tocan la comuna (un incendio puede abarcar varias)
    vina = []
    for grupo, f in por_grupo.items():
        en_vina = (f["region_id"].eq("05109").fillna(False) & (f["fecha_local"] >= "2024-02-01")
                   & (f["fecha_local"] < "2024-03-01")).to_numpy()
        ids = pd.unique(etiquetas[grupo][en_vina])
        tocados = eventos[grupo].set_index("evento").loc[ids] if len(ids) else eventos[grupo].iloc[0:0]
        mayor = tocados["n_focos"].idxmax() if len(ids) else None
        comunas = (f.loc[etiquetas[grupo] == mayor, "region_id"].nunique() if mayor is not None else 0)
        vina.append({
            "Sensor": grupo,
            "Incendios que tocan Viña": len(ids),
            "Focos dentro de Viña": int(en_vina.sum()),
            "Focos del mayor incendio (todas las comunas)": int(tocados["n_focos"].max()) if len(ids) else 0,
            "Comunas que abarca el mayor": int(comunas),
        })
    vina = pd.DataFrame(vina).set_index("Sensor")

    figura(por_tamano, por_anio, config.RAIZ / "docs" / "figuras" / "eventos_deteccion.png")

    g_ini = por_anio.loc[2012:2020, "Incendios grandes (más de 10 focos)"].mean()
    g_fin = por_anio.loc[2024:2025, "Incendios grandes (más de 10 focos)"].mean()
    r_focos = razones.loc[BASE[0]:BASE[1], "Focos SNPP/MODIS"].mean()
    r_eventos = razones.loc[BASE[0]:BASE[1], "Eventos SNPP/MODIS"].mean()
    chicos = por_tamano.iloc[0]
    generado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    reporte = [
        "# Focos vs. incendios: ¿por qué VIIRS ve más que MODIS?",
        f"_Generado por `scripts/06_eventos.py` el {generado}. No editar a mano: se regenera._",
        "",
        "## Resumen",
        f"- **Hipótesis:** VIIRS (375 m) parte un mismo incendio en más píxeles que MODIS (1 km); contando incendios "
        "en vez de focos, la diferencia debería acercarse a 1.",
        f"- **Resultado: se cumple solo en parte.** En {BASE[0]}-{BASE[1]} la razón Suomi NPP / MODIS baja de "
        f"**{r_focos:.1f}** (focos) a **{r_eventos:.1f}** (incendios), y con cualquier definición razonable de "
        f"incendio queda entre {sensibilidad.min().min():.1f} y {sensibilidad.max().max():.1f}, nunca cerca de 1.",
        f"- **La mayor parte de la diferencia es sensibilidad:** {chicos['% del total']:.0f} % de los incendios que ve "
        f"VIIRS son de un solo foco, y MODIS ve solo el **{chicos['MODIS también lo ve (%)']:.0f} %** de ellos; de "
        f"los incendios de más de 50 focos ve el **{por_tamano.iloc[-1]['MODIS también lo ve (%)']:.0f} %**.",
        f"- **La deriva de MODIS también se ve en incendios grandes:** en 2012-2020 MODIS veía en promedio el "
        f"**{g_ini:.0f} %** de los incendios grandes que veía VIIRS; en 2024-2025, el **{g_fin:.0f} %**.",
        "- **Consecuencia para el producto:** agrupar en incendios no armoniza los sensores; por eso la serie usa "
        "calibración ([armonizacion.md](armonizacion.md)). La serie en equivalente MODIS sub-representa los incendios "
        "chicos, que solo VIIRS ve bien.",
        "",
        "![Coincidencia entre sensores](figuras/eventos_deteccion.png)",
        "",
        "## 1. Razón entre sensores contando focos y contando incendios",
        f"Incendio (evento) = focos del mismo sensor a ≤{D_KM:.0f} km y ≤{T_DIAS:.0f} días, encadenados. MODIS = Terra + "
        "Aqua juntos. 2012 sin enero para VIIRS.",
        "",
        tabla_md(razones, 2),
        "",
        f"## 2. Sensibilidad de la razón de incendios ({BASE[0]}-{BASE[1]})",
        "",
        tabla_md(sensibilidad, 2),
        "",
        f"## 3. ¿Qué incendios vistos por VIIRS ve también MODIS? ({BASE[0]}-{BASE[1]})",
        f"Coincidencia: algún foco MODIS a ≤{D_COINC:.0f} km y ≤{T_COINC:.0f} día de algún foco del incendio.",
        "",
        tabla_md(por_tamano, 1),
        "",
        "Por año:",
        "",
        tabla_md(por_anio, 1),
        "",
        f"Al revés, VIIRS ve el **{modis_visto:.0f} %** de los incendios que ve MODIS ({BASE[0]}-{BASE[1]}): cada "
        "sensor ve incendios que el otro no, en parte porque pasan a horas distintas (Terra en la mañana; Aqua y "
        f"Suomi NPP después del mediodía). NOAA-20 ve el **{n20_visto:.0f} %** de los incendios de Suomi NPP "
        "(2019-2025), coherente con que ambos VIIRS ven casi lo mismo.",
        "",
        "## 4. Caso Viña del Mar, febrero de 2024 (comuna 05109)",
        "",
        tabla_md(vina, 0),
        "",
        "## 5. Límites",
        "- La definición de incendio es una aproximación (vecindario cuadrado y encadenamiento); dos incendios "
        "vecinos y simultáneos se cuentan como uno.",
        "- La coincidencia depende de la geolocalización: los píxeles MODIS del borde del barrido miden hasta ~3 km, "
        "así que a 2 km algunas coincidencias reales quedan fuera.",
        "- Se usan focos de vegetación con confianza nominal o alta (`uso_base`).",
        "",
    ]
    (config.RAIZ / "docs" / "eventos.md").write_text("\n".join(reporte), encoding="utf-8")

    print(f"\nRazón {BASE[0]}-{BASE[1]}: focos {r_focos:.2f}, eventos {r_eventos:.2f}")
    print(por_tamano.round(1).to_string())
    print(f"Grandes vistos por MODIS: 2012-2020 {g_ini:.0f} %, 2024-2025 {g_fin:.0f} %")
    print(vina.to_string())
    print("Reporte: docs/eventos.md  |  Figura: docs/figuras/eventos_deteccion.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
