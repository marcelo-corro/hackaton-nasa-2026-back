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
cp .env.example .env        # completar FIRMS_RAW_DIR
.venv/Scripts/python -m pytest
.venv/Scripts/python scripts/01_ingestar_firms.py
```

## Datos

Los datos **no se versionan** (`data/` está en `.gitignore`). Ver [data/README.md](data/README.md).

- Focos FIRMS de Chile 2000-2025: en el Drive del equipo, `informes/datos_8B/firms/`. Apuntá `FIRMS_RAW_DIR` a
  esa carpeta.
- Los archivos `viirs-noaa20_*` de esa carpeta son descargas fallidas (respuesta 404 guardada como `.csv`);
  la ingesta los omite.

## Pipeline

| Paso | Script / módulo | Estado |
|---|---|---|
| 0. Ejemplos del contrato para el front | `scripts/00_generar_ejemplos_contrato.py` | Listo |
| 1. Unir CSV de FIRMS en una tabla | `scripts/01_ingestar_firms.py`, `firecal.ingest.firms` | Listo |
| 2. Asignar focos a comunas | `firecal.ingest` | Pendiente (falta el shapefile) |
| 3. Armonización MODIS ↔ VIIRS | `firecal.harmonize` | Pendiente |
| 4. Agrupar focos en incendios | `firecal.events` | Pendiente (hipótesis) |
| 5. Calendario y anomalías | `firecal.anomalies` | Pendiente |
| 6. Riesgo 24-48 h | `firecal.model` | Pendiente |
| 7. Exportar al contrato | `firecal.export` | Pendiente |

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
