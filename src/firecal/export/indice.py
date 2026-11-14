"""`index.html` del repo de datos: página estática, sin JavaScript, que explica qué hay y cómo citarlo.

Sin esta página, abrir la URL base de GitHub Pages da 404 (el repo solo tiene archivos de datos). Se genera junto
al resto de `public/`, así `10_publicar.py` la copia en cada publicación y no se borra.
"""

from __future__ import annotations

from html import escape

# Textos de agradecimiento y cita: los mismos de docs/fuentes.md
FIRMS_AGRADECIMIENTO = (
    "We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System "
    "(FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Land, Atmosphere Near real-time Capability for "
    "Earth observations (LANCE) (https://earthdata.nasa.gov/lance) and NASA's Earth Science Data and Information "
    "System (ESDIS)."
)
FIRMS_CITAS = [
    "Giglio, L., Schroeder, W., & Justice, C. O. (2016). The collection 6 MODIS active fire detection algorithm "
    "and fire products. Remote Sensing of Environment, 178, 31-41. https://doi.org/10.1016/j.rse.2016.02.054",
    "Schroeder, W., Oliva, P., Giglio, L., & Csiszar, I. A. (2014). The New VIIRS 375m active fire detection data "
    "product: algorithm description and initial assessment. Remote Sensing of Environment, 143, 85-96. "
    "https://doi.org/10.1016/j.rse.2013.12.008",
]
BCN_CITA = (
    "Biblioteca del Congreso Nacional de Chile, División comunal: polígonos de las comunas de Chile. "
    "https://www.bcn.cl/siit/mapas_vectoriales. Material referencial."
)
POWER_CITA = (
    "The data was obtained from National Aeronautics and Space Administration (NASA) Langley Research Center's "
    "Prediction Of Worldwide Energy Resources (POWER) project funded through the NASA Earth Science Division. "
    "https://power.larc.nasa.gov/"
)

RUTAS = [
    ("manifest.json", "Versión del contrato, fecha de generación, período y lista de comunas."),
    ("regiones.geojson", "Contorno simplificado de cada comuna (WGS84)."),
    ("calendario/{region_id}.json", "Matriz mes × año por comuna: focos MODIS y VIIRS, serie armonizada con "
     "incertidumbre, mediana histórica, percentil y nivel."),
    ("focos/{region_id}.csv", "Focos de vegetación de la comuna, para descargar."),
    ("riesgo/ultimo.json", "Riesgo de focos a 24 h por comuna."),
    ("metricas.json", "Desempeño del modelo de riesgo."),
]

ESTILO = """
:root { --fondo: #ffffff; --texto: #1f2328; --suave: #59636e; --borde: #d1d9e0; --enlace: #0b5cad; --caja: #f6f8fa; }
@media (prefers-color-scheme: dark) {
  :root { --fondo: #0d1117; --texto: #e6edf3; --suave: #9198a1; --borde: #3d444d; --enlace: #58a6ff; --caja: #151b23; }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--fondo); color: var(--texto);
  font: 16px/1.55 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 46rem; margin: 0 auto; padding: 2rem 1rem 3rem; }
h1 { font-size: 1.6rem; margin: 0 0 .25rem; }
h2 { font-size: 1.15rem; margin: 2rem 0 .5rem; padding-top: .5rem; border-top: 1px solid var(--borde); }
a { color: var(--enlace); overflow-wrap: anywhere; }
code { background: var(--caja); border: 1px solid var(--borde); border-radius: 4px; padding: .05rem .3rem;
  font-size: .9em; overflow-wrap: anywhere; }
.suave { color: var(--suave); }
.estado { background: var(--caja); border: 1px solid var(--borde); border-radius: 8px; padding: .75rem 1rem; }
.estado p { margin: .25rem 0; }
table { width: 100%; border-collapse: collapse; margin: .5rem 0; }
th, td { text-align: left; vertical-align: top; padding: .45rem .5rem; border-bottom: 1px solid var(--borde); }
th { font-size: .85rem; color: var(--suave); font-weight: 600; }
td:first-child { white-space: nowrap; }
@media (max-width: 36rem) { td:first-child { white-space: normal; } }
ul { padding-left: 1.2rem; }
li { margin: .35rem 0; }
"""


def _fila_ruta(ruta: str, descripcion: str) -> str:
    enlace = escape(ruta)
    # Las rutas con {region_id} son plantillas: se muestran como texto y se da un ejemplo enlazado.
    if "{region_id}" in ruta:
        ejemplo = ruta.replace("{region_id}", "05109")
        celda = f'<code>{enlace}</code><br><span class="suave">ej. <a href="{escape(ejemplo)}">{escape(ejemplo)}</a></span>'
    else:
        celda = f'<a href="{enlace}">{enlace}</a>'
    return f"<tr><td>{celda}</td><td>{escape(descripcion)}</td></tr>"


def modelo_usa_clima(riesgo: dict | None, metricas: dict | None) -> bool:
    """True si el modelo publicado usa el bloque de clima.

    `08_riesgo.py` arma el nombre con los bloques de variables (`hgb_firms_v1`, `hgb_firms_clima_v1`), así que
    basta mirar si "clima" es uno de sus componentes. Sin modelo publicado, no hay clima que citar.
    """
    modelo = (riesgo or {}).get("modelo") or (metricas or {}).get("modelo") or ""
    return "clima" in str(modelo).lower().split("_")


def index_html(manifest: dict, riesgo: dict | None = None, metricas: dict | None = None) -> str:
    """Devuelve el HTML de la portada. `manifest`, `riesgo` y `metricas` son los JSON ya construidos.

    La cita de NASA POWER aparece solo si el modelo publicado usa clima, y la nota sobre lo que el riesgo
    predice bien o mal es la de `metricas.json` (no un texto fijo).
    """
    periodo = manifest.get("periodo", {})
    lineas_estado = [
        f"<p><strong>Datos reales de {len(manifest.get('regiones', []))} comunas de Chile</strong> "
        f"(contrato v{escape(str(manifest.get('contrato', '')))}).</p>",
        f"<p>Período: {escape(str(periodo.get('desde', '?')))} a {escape(str(periodo.get('hasta', '?')))}. "
        f"Generado: <code>{escape(str(manifest.get('generado_utc', '?')))}</code> (UTC).</p>",
    ]
    if riesgo and riesgo.get("items"):
        lineas_estado.append(
            f"<p>Riesgo a {escape(str(riesgo.get('horizonte_horas')))} h para el "
            f"<code>{escape(str(riesgo.get('valido_para')))}</code> "
            f"(modelo <code>{escape(str(riesgo.get('modelo')))}</code>). Los datos de focos llegan hasta el último día del "
            "período, así que el riesgo es para el día siguiente a ese límite; no es un pronóstico en tiempo real.</p>"
        )
    else:
        lineas_estado.append("<p>Riesgo a 24 h: pendiente.</p>")
    if metricas and metricas.get("auc") is not None:
        lineas_estado.append(
            f"<p>Métricas del modelo (prueba {escape(str(metricas.get('periodo_prueba')))}): "
            f"AUC {escape(str(metricas.get('auc')))}, <a href=\"metricas.json\">ver detalle</a>.</p>"
        )

    filas = "\n".join(_fila_ruta(r, d) for r, d in RUTAS)
    citas_firms = "\n".join(f"<li>{escape(c)}</li>" for c in FIRMS_CITAS)
    cita_power = (
        f"<li><strong>NASA POWER</strong> (clima diario, insumo del modelo de riesgo). {escape(POWER_CITA)}</li>"
        if modelo_usa_clima(riesgo, metricas)
        else ""
    )
    nota_modelo = str((metricas or {}).get("nota") or "").strip()
    limite_modelo = f"<li>{escape(nota_modelo)}</li>" if nota_modelo else ""

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AIVital · Datos de focos de calor de Chile</title>
<meta name="description" content="Focos de calor MODIS y VIIRS armonizados por comuna de Chile, con calendario de actividad y riesgo a 24 h. Datos abiertos del equipo AIVital (NASA Space Apps 2026).">
<style>{ESTILO}</style>
</head>
<body>
<main>
<h1>AIVital · Datos de focos de calor de Chile</h1>
<p class="suave">NASA Space Apps Challenge 2026 · desafío
<a href="https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/">Harmonization of MODIS and VIIRS Hot Spots</a></p>

<div class="estado">
{chr(10).join(lineas_estado)}
</div>

<h2>Qué es esto</h2>
<p>Esta dirección no es una aplicación: es el repositorio de <strong>archivos de datos</strong> que lee la app del equipo.
Contiene los focos de calor satelitales de Chile (MODIS desde 2000 y VIIRS desde 2012), <strong>armonizados</strong>
para que el cambio de sensor no parezca un cambio de fuego, un <strong>calendario de actividad</strong> por comuna
(mes × año) con su nivel frente a la historia, y una estimación del <strong>riesgo de focos a 24 h</strong>.
Las cifras armonizadas están en <em>focos equivalentes MODIS</em>.</p>

<h2>Archivos</h2>
<p>Todos están bajo esta misma dirección y se pueden leer desde otros sitios (CORS abierto).
<code>{{region_id}}</code> es el código único territorial de la comuna, 5 dígitos (<code>05109</code> = Viña del Mar).</p>
<table>
<thead><tr><th>Ruta</th><th>Contenido</th></tr></thead>
<tbody>
{filas}
</tbody>
</table>

<h2>Fuentes y citas</h2>
<ul>
<li><strong>NASA FIRMS</strong> (focos de calor MODIS y VIIRS). {escape(FIRMS_AGRADECIMIENTO)}
<ul>
{citas_firms}
</ul></li>
<li><strong>Biblioteca del Congreso Nacional de Chile (BCN)</strong> (límites comunales). {escape(BCN_CITA)}</li>
{cita_power}
</ul>

<h2>Límites</h2>
<ul>
<li>Se cuentan <strong>detecciones</strong> de vegetación con confianza nominal o alta, no incendios ni superficie quemada.</li>
<li>A escala de una comuna y un mes el error de la armonización es alto; conviene mirar agregados y el intervalo
<code>armonizado_p05</code>–<code>armonizado_p95</code>.</li>
{limite_modelo}
</ul>

<p class="suave">Estos archivos se generan automáticamente; no se editan a mano.</p>
</main>
</body>
</html>
"""
