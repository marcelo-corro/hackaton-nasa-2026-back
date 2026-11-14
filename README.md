# aivital-incendios-back

Back del equipo **AIVital** para NASA Space Apps 2026, desafío
[*Harmonization of MODIS and VIIRS Hot Spots*](https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/)
(propuesto por CONAE).

Toma los focos de calor de FIRMS (MODIS desde 2000, VIIRS desde 2012), los **armoniza** para que el sensor deje
de importar, arma un **calendario de actividad de quema** por comuna con anomalías contra la historia y estima el
**riesgo de focos a 24-48 h**. El resultado son archivos estáticos que consume el front (repo aparte) según el
[contrato](contracts/README.md), publicados en
**https://marcelo-corro.github.io/aivital-incendios-datos** (repo público
[aivital-incendios-datos](https://github.com/marcelo-corro/aivital-incendios-datos); hoy con datos de ejemplo).

## Empieza aquí

| Si eres… | Lee |
|---|---|
| Del equipo, recién llegando | [docs/trabajo_en_equipo.md](docs/trabajo_en_equipo.md): objetivo, alcance, roles, tareas y horarios |
| Back | Tu sección de tareas en esa guía y [contracts/interno.md](contracts/interno.md) |
| Front | [docs/guia_front.md](docs/guia_front.md) y el [contrato v0.2](contracts/README.md) |
| Quien prepara el pitch | [docs/calidad_datos.md](docs/calidad_datos.md), [docs/fuentes.md](docs/fuentes.md) y [docs/decisiones.md](docs/decisiones.md) |

## Cómo correrlo

Requiere Python 3.11 o superior. En Windows, si `Activate.ps1` está bloqueado, usa el `python.exe` del venv por
ruta completa.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
cp .env.example .env
.venv/Scripts/python -m pytest
.venv/Scripts/python scripts/01_descargar_datos.py     # ~120 MB, datos públicos, sin cuenta
.venv/Scripts/python scripts/02_ingestar_firms.py
.venv/Scripts/python scripts/03_asignar_comunas.py     # ~1 min la primera vez
.venv/Scripts/python scripts/04_marcar_calidad.py      # marcas de calidad + docs/calidad_datos.md
.venv/Scripts/python scripts/05_armonizar.py           # serie armonizada + docs/armonizacion.md
```

Las tablas de `data/interim/` usan tipos con nulos de pandas (`string`, `Int8`). Para filtrar, usa
`f.region_id.eq("05109").fillna(False)` en vez de `f.region_id == "05109"` combinado con `&`.

**Ojo al contar focos VIIRS:** Suomi NPP y NOAA-20 ven los mismos incendios con ~50 min de diferencia.
No los sumes: trata cada satélite como una serie aparte (filtra por `satelite`).

## Datos

Los datos **no se versionan** (`data/` está en `.gitignore`). Ver [data/README.md](data/README.md).
Cada fuente externa, con su URL, verificación y cita, está en [docs/fuentes.md](docs/fuentes.md).

- `scripts/01_descargar_datos.py` baja a `data/raw/` los focos FIRMS de Chile (MODIS 2000-2025, VIIRS Suomi NPP
  2012-2025 y NOAA-20 2018-2025) y las comunas de la BCN, y anota tamaño y SHA-256 de cada archivo.
- Si ya tienes los CSV de FIRMS del Drive del equipo (`informes/datos_8B/firms/`), cópialos a `data/raw/firms/`
  y el script solo verifica su tamaño contra FIRMS en vez de bajarlos. Los `viirs-noaa20_*` del Drive son
  descargas fallidas (404): NOAA-20 está en FIRMS bajo la carpeta `viirs-jpss1`.

## Pipeline

A = back, ciencia de datos · B = back, producto de datos (ver [roles](docs/trabajo_en_equipo.md#3-roles)).

| Paso | Script / módulo | Quién | Estado |
|---|---|---|---|
| 0. Ejemplos del contrato para el front | `scripts/00_generar_ejemplos_contrato.py` | — | Listo (v0.2) |
| 1. Descargar y verificar datos públicos | `scripts/01_descargar_datos.py` | — | Listo |
| 2. Unir CSV de FIRMS en una tabla | `scripts/02_ingestar_firms.py`, `firecal.ingest.firms` | — | Listo (821.539 focos) |
| 3. Asignar focos a comunas | `scripts/03_asignar_comunas.py`, `firecal.ingest.comunas` | — | Listo (99,998 % de los focos de vegetación) |
| 4. Marcar calidad + fecha local | `scripts/04_marcar_calidad.py`, `firecal.calidad` | — | Listo ([reporte](docs/calidad_datos.md)) |
| 5p. Serie mensual provisional | `scripts/05p_serie_provisional.py` | B | Ya no hace falta (la serie armonizada existe) |
| 5. Armonización MODIS ↔ VIIRS | `scripts/05_armonizar.py`, `firecal.harmonize` | A | Listo ([reporte](docs/armonizacion.md)) |
| 6. Agrupar focos en incendios | `scripts/06_eventos.py`, `firecal.events` | A | Pendiente (A2, hipótesis) |
| 7. Calendario y anomalías | `scripts/07_calendario.py`, `firecal.anomalies` | B | Pendiente (B2) |
| 8. Riesgo 24-48 h | `scripts/08_riesgo.py`, `firecal.model` | A | Pendiente (A3; necesita B5) |
| 9. Exportar al contrato | `scripts/09_exportar.py`, `firecal.export` | B | Pendiente (B3) |
| 10. Publicar en GitHub Pages | `scripts/10_publicar.py` | B | Repo y Pages listos con ejemplos; falta el script (B4) |

Las tablas que se pasan entre pasos y sus validadores (`firecal.contratos`) están en
[contracts/interno.md](contracts/interno.md).

### Calidad de los datos

El paso 4 **no borra focos: los marca** (`es_vegetacion`, `confianza_ok`, `frp_valido`, `pixel_grande`,
`uso_base`) y agrega `fecha_local` en hora de Chile. Cada análisis filtra con reglas escritas y prueba cuánto
cambia el resultado con y sin cada filtro. Regla por defecto para contar focos: `uso_base` (vegetación y
confianza nominal o alta). Lo que muestra el [reporte de calidad](docs/calidad_datos.md):

- ~19 % de los focos no son vegetación (industria, faenas, volcanes): se excluyen del conteo.
- Las órbitas de Terra y Aqua (MODIS) se desvían ~1 h desde 2020-2022; las de VIIRS no. Por eso la razón
  VIIRS/MODIS cambia con los años: **un factor calibrado con todo el período no sirve**. La armonización calibra
  solo con 2012-2017 (MODIS estable) y desde 2018 usa VIIRS convertido ([detalle](docs/armonizacion.md)).
- La versión de procesamiento de MODIS cambia en 2018 y 2023 (posibles saltos en la serie).

## Estructura

```
├── contracts/        # contrato con el front + ejemplos con datos inventados
├── data/             # NO se sube: raw/, interim/, processed/
├── docs/             # decisiones del equipo
├── notebooks/        # exploración (uno por persona)
├── scripts/          # pasos del pipeline, en orden
├── src/firecal/      # código reutilizable
│   ├── ingest/       # FIRMS, clima, comunas
│   ├── harmonize/    # calibración MODIS <-> VIIRS
│   ├── events/       # focos -> incendios
│   ├── anomalies/    # calendario y anomalías
│   ├── model/        # riesgo 24-48 h
│   └── export/       # JSON/CSV para el front
└── tests/
```

## Reglas de trabajo

- `main` siempre funciona: de ahí sale la demo.
- Una rama corta por tarea (`feat/armonizacion`, `feat/comunas`) y un PR chico por rama.
- **Nunca** subir `.env`, llaves, tokens ni contraseñas.
- Notebooks: `notebooks/NN-nombre-tema.ipynb`. Instalar `nbstripout` una vez por clon
  (`.venv/Scripts/python -m nbstripout --install`) para no subir salidas. Lo que funciona pasa a `src/`.
- Cambios de forma en los archivos del front: subir la versión del contrato y avisar antes de mezclar.
