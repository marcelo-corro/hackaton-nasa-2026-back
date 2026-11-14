# aivital-incendios-back

Back del equipo **AIVital** para NASA Space Apps 2026, desafío
[*Harmonization of MODIS and VIIRS Hot Spots*](https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/)
(propuesto por CONAE).

Toma los focos de calor de FIRMS (MODIS desde 2000, VIIRS desde 2012), los **armoniza** para que el sensor deje
de importar, arma un **calendario de actividad de quema** por comuna con anomalías contra la historia y estima el
**riesgo de focos a 24-48 h**. El resultado son archivos estáticos que consume el front (repo aparte) según el
[contrato](contracts/README.md).

## Cómo correrlo

Requiere Python 3.11 o superior. En Windows, si `Activate.ps1` está bloqueado, usá el `python.exe` del venv por
ruta completa.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
cp .env.example .env
.venv/Scripts/python -m pytest
.venv/Scripts/python scripts/01_descargar_datos.py     # ~120 MB, datos públicos, sin cuenta
.venv/Scripts/python scripts/02_ingestar_firms.py
.venv/Scripts/python scripts/03_asignar_comunas.py     # ~1 min la primera vez
```

Las tablas de `data/interim/` usan tipos con nulos de pandas (`string`, `Int8`). Para filtrar, usá
`f.region_id.eq("05109").fillna(False)` en vez de `f.region_id == "05109"` combinado con `&`.

**Ojo al contar focos VIIRS:** Suomi NPP y NOAA-20 ven los mismos incendios con ~50 min de diferencia.
No los sumes: tratá cada satélite como una serie aparte (filtrá por `satelite`).

## Datos

Los datos **no se versionan** (`data/` está en `.gitignore`). Ver [data/README.md](data/README.md).
Cada fuente externa, con su URL, verificación y cita, está en [docs/fuentes.md](docs/fuentes.md).

- `scripts/01_descargar_datos.py` baja a `data/raw/` los focos FIRMS de Chile (MODIS 2000-2025, VIIRS Suomi NPP
  2012-2025 y NOAA-20 2018-2025) y las comunas de la BCN, y anota tamaño y SHA-256 de cada archivo.
- Si ya tenés los CSV de FIRMS del Drive del equipo (`informes/datos_8B/firms/`), copialos a `data/raw/firms/`
  y el script solo verifica su tamaño contra FIRMS en vez de bajarlos. Los `viirs-noaa20_*` del Drive son
  descargas fallidas (404): NOAA-20 está en FIRMS bajo la carpeta `viirs-jpss1`.

## Pipeline

| Paso | Script / módulo | Estado |
|---|---|---|
| 0. Ejemplos del contrato para el front | `scripts/00_generar_ejemplos_contrato.py` | Listo |
| 1. Descargar y verificar datos públicos | `scripts/01_descargar_datos.py` | Listo |
| 2. Unir CSV de FIRMS en una tabla | `scripts/02_ingestar_firms.py`, `firecal.ingest.firms` | Listo (821.539 focos) |
| 3. Asignar focos a comunas | `scripts/03_asignar_comunas.py`, `firecal.ingest.comunas` | Listo (99,998 % de los focos de vegetación) |
| 4. Armonización MODIS ↔ VIIRS | `firecal.harmonize` | Pendiente |
| 5. Agrupar focos en incendios | `firecal.events` | Pendiente (hipótesis) |
| 6. Calendario y anomalías | `firecal.anomalies` | Pendiente |
| 7. Riesgo 24-48 h | `firecal.model` | Pendiente |
| 8. Exportar al contrato | `firecal.export` | Pendiente |

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
