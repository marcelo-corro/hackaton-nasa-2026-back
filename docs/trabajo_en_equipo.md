# Trabajo en equipo · AIVital (NASA Space Apps 2026)

Guía para que el back y el front avancen en paralelo sin pisarse. Si recién llegas, lee esto completo
(15 minutos) y después la sección de tu rol.

## 1. Objetivo del proyecto

Desafío: [*Harmonization of MODIS and VIIRS Hot Spots*](https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/),
propuesto por CONAE.

**El problema.** Los satélites detectan focos de calor desde 2000, pero con dos sensores distintos: MODIS
(desde 2000, píxel de 1 km, al final de su vida útil) y VIIRS (desde 2012, píxel de 375 m, más sensible).
VIIRS ve ~3,5 veces más focos, y además las órbitas de MODIS se están desviando (~1 h desde 2020-2022), así que
la relación entre ambos cambia con los años. Si alguien mira los datos crudos, cree que hay más fuego cuando lo
que cambió es el satélite.

**Lo que construimos.** Una app web que:
1. **armoniza** MODIS y VIIRS en una sola serie comparable 2000-2025, con su incertidumbre;
2. muestra un **calendario de actividad de quema** (mes × año) por **comuna de Chile**;
3. marca qué meses son **anómalos** contra la historia de cada comuna y los compara con la **mediana histórica**;
4. permite **descargar** los focos en CSV;
5. estima el **riesgo de focos a 24-48 h** por comuna y **publica cuánto acierta** (si el tiempo alcanza).

**Para quién.** Equipos de prevención municipales, SENAPRED, brigadistas y gestores del territorio.

**Lo que nos diferencia.** No es "otro mapa con puntos rojos": la corrección entre sensores está medida y
validada con datos de Chile, y la app muestra sus propios límites y su desempeño.

## 2. Alcance

**Dentro (entrega del domingo 15-nov, 23:59 hora de Chile)**
- Chile: 345 comunas, de noviembre de 2000 a diciembre de 2025.
- Sensores: MODIS (Terra, Aqua) y VIIRS (Suomi NPP, NOAA-20).
- Serie mensual armonizada por comuna, calendario, anomalías y descarga de CSV.
- Riesgo a 24-48 h por comuna con sus métricas, o una diapositiva de "siguiente paso" si no alcanza.
- App web estática que lee archivos publicados en GitHub Pages.
- Fuentes citadas ([docs/fuentes.md](fuentes.md)) y demo en inglés (video de 30 s o hasta 7 láminas).

**Fuera (visión para el pitch, no se construye ahora)**
- Otros países (comparación con Argentina o California).
- Dibujar un área libre en el mapa (requiere una API).
- Otros sensores (GOES, Sentinel-3), actualización automática en tiempo real.
- Predecir dónde **empieza** un incendio: la mayoría de las igniciones son humanas.

## 3. Roles

| Rol | Quién | Lo que le pertenece |
|---|---|---|
| **A · Back, ciencia de datos** | Marcelo | `src/firecal/harmonize/`, `events/`, `model/`; scripts `05_armonizar`, `06_eventos`, `08_riesgo` |
| **B · Back, producto de datos** | David | `src/firecal/anomalies/`, `export/`, `ingest/clima.py`, `ingest/firms_nrt.py`; scripts `05p_serie_provisional`, `07_calendario`, `09_exportar`, `10_publicar` |
| **F · Front** | José | Repo del front. Su guía: [docs/guia_front.md](guia_front.md) |

**Archivos compartidos** (`config.py`, `pyproject.toml`, `README.md`, `docs/`, `contracts/`): cambios chicos, por
PR y **solo agregando**. Nunca reescribir lo que otro escribió sin hablarlo.

## 4. Cómo encaja todo

```
Pasos 1-4 (listos): datos → focos_calidad.parquet + comunas.parquet
                                   │
              ┌────────────────────┴───────────────────────────┐
              ▼                                                ▼
  [A] 05_armonizar  ──┐                            [B] 05p_serie_provisional (mientras A termina)
                      ├──► serie_mensual.parquet ◄─┘
                      │            │
                      │            ▼
                      │    [B] 07_calendario ──► calendario.parquet
                      │                                  │
  [B] clima_diario ──►│ [A] 08_riesgo ──► riesgo.parquet + metricas.json
                      │                                  │
                      │                                  ▼
                      │                     [B] 09_exportar ──► public/ (contrato v0.2)
                      │                                  │
                      │                     [B] 10_publicar ──► GitHub Pages ──► [F] front
```

Los contratos que unen cada flecha están en [contracts/interno.md](../contracts/interno.md) (back ↔ back) y
[contracts/README.md](../contracts/README.md) (back → front). Cada tabla compartida se valida con
`firecal.contratos` antes de guardarse.

## 5. Puesta en marcha (B, unos 20 minutos)

```bash
git clone https://github.com/marcelo-corro/aivital-incendios-back.git
cd aivital-incendios-back
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
cp .env.example .env
# opcional: copia los CSV de FIRMS del Drive (informes/datos_8B/firms/) a data/raw/firms/ para no bajarlos
.venv/Scripts/python scripts/01_descargar_datos.py
.venv/Scripts/python scripts/02_ingestar_firms.py
.venv/Scripts/python scripts/03_asignar_comunas.py
.venv/Scripts/python scripts/04_marcar_calidad.py
.venv/Scripts/python scripts/05_armonizar.py      # serie armonizada: la entrada de tu tarea B2
.venv/Scripts/python -m pytest
```

Lee también la sección "Calidad de los datos" del [README](../README.md) y el
[reporte de calidad](calidad_datos.md): explican por qué se cuenta con `uso_base` y por día local.

## 6. Tareas de B · David (en este orden)

Los tiempos son estimados para una persona.

### B1 · Serie mensual provisional (ya no hace falta)

> **Actualización (14-11):** la armonización (A1) ya está lista y `scripts/05_armonizar.py` genera la
> `serie_mensual.parquet` definitiva. **Sáltate B1 y parte por B2.** Lo que sigue queda solo como referencia.
**Objetivo:** que el calendario, la exportación y el front tengan datos reales desde hoy, sin esperar la
armonización de A.
- **Entradas:** `data/interim/focos_calidad.parquet`, `data/interim/comunas.parquet`.
- **Salida:** `data/processed/serie_mensual.parquet` (forma exacta en [contracts/interno.md](../contracts/interno.md)).
- **Pasos:**
  1. Filtrar `uso_base` y `region_id` no nulo. Mes y año desde `fecha_local`.
  2. Contar por `region_id`, año y mes: `modis` = satélites Terra + Aqua; `viirs` = solo Suomi NPP (`SNPP`).
  3. Armar la **grilla completa**: 345 comunas × 302 meses (2000-11 a 2025-12), con 0 donde no hay focos.
     `viirs` nulo antes de 2012.
  4. `armonizado` provisional: hasta 2011-12 = `modis`; desde 2012-01 = `viirs / 3,55`.
     `armonizado_p05` y `armonizado_p95` nulos. `metodo = "provisional_factor_unico"`.
  5. `validar_serie_mensual(df, n_comunas=345)` y guardar.
- **Script:** `scripts/05p_serie_provisional.py`. No debe sobrescribir una serie cuyo `metodo` no sea
  provisional, salvo con `--forzar` (así no pisa la versión de A).
- **Listo cuando:** el validador pasa, la tabla tiene 104.190 filas y en Viña del Mar (`05109`) febrero de 2024
  destaca claramente sobre los demás febreros.

### B2 · Calendario y anomalías (~2 h)
**Objetivo:** para cada comuna y mes, decir si fue bajo, normal, alto o extremo contra su propia historia.
- **Entrada:** `data/processed/serie_mensual.parquet`.
- **Salida:** `data/processed/calendario.parquet`.
- **Pasos:**
  1. En `src/firecal/anomalies/`, funciones puras (sin leer ni escribir archivos) que calculen, por comuna y mes
     del año, contra los **demás años**: `mediana_historica`, `percentil` con **rango medio para empates** y
     `nivel` (reglas en [contracts/interno.md](../contracts/interno.md)).
  2. Tests chicos: un mes en 0 contra otros ceros da percentil 50 y nivel `normal`; el máximo de la serie da
     `extrema`.
  3. `scripts/07_calendario.py`: lee, calcula, `validar_calendario(df, n_comunas=345)` y guarda.
- **Listo cuando:** pasan los tests y el validador, y Viña del Mar en febrero de 2024 sale `extrema`.

### B3 · Exportación al contrato del front (~3 h)
**Objetivo:** generar exactamente los archivos que lee el front.
- **Entradas:** `calendario.parquet`, `comunas.parquet`, `focos_calidad.parquet`; `riesgo.parquet` y
  `metricas.json` si existen.
- **Salida:** carpeta `public/` (o `PUBLIC_DIR` de `.env`) con la forma de [contracts/README.md](../contracts/README.md) v0.2.
- **Pasos:**
  1. `manifest.json` con `"ejemplo": false`, fecha de generación, período y lista de comunas.
  2. `regiones.geojson`: geometrías **simplificadas para la web** (tolerancia ~0,005°, coordenadas con
     4 decimales). Meta: menos de 3 MB en total.
  3. `calendario/{region_id}.json` para las 345 comunas (números con 1 decimal, UTF-8 sin escapar tildes ni ñ).
  4. `focos/{region_id}.csv` con los focos de vegetación (`es_vegetacion`) de todas las confianzas, para que el
     usuario filtre. `fecha` y `hora_utc` en UTC, como FIRMS. Comunas sin focos: CSV solo con el encabezado.
  5. `riesgo/ultimo.json` y `metricas.json`: si A todavía no los produce, `items` vacío y métricas en `null`.
  6. Un test que compare las claves de cada archivo generado con las de `contracts/ejemplos/`.
- **Script:** `scripts/09_exportar.py`. Al terminar, imprimir cuántos archivos y cuánto pesa `public/`.
- **Listo cuando:** `public/` tiene 345 calendarios, 345 CSV, manifest, GeoJSON, riesgo y métricas, y el test
  de claves pasa.

### B4 · Publicación en GitHub Pages (~45 min)
**Objetivo:** que los archivos de `public/` lleguen a la URL que ya usa el front.

**Ya está hecho (14-11):** el repo público
[marcelo-corro/aivital-incendios-datos](https://github.com/marcelo-corro/aivital-incendios-datos) con Pages activo
desde `main` (raíz, con `.nojekyll`). URL base: **https://marcelo-corro.github.io/aivital-incendios-datos**.
Hoy sirve los datos de ejemplo y responde con CORS abierto (`Access-Control-Allow-Origin: *`). José ya tiene la URL.
Pages solo es gratis en repos públicos: por eso este repo lleva **solo archivos generados**, nada de código,
`.env` ni llaves.

- **Pasos que faltan:**
  1. Aceptar la invitación de colaborador al repo de datos y clonarlo junto al repo del back.
  2. Agregar `DATOS_REPO_DIR` a tu `.env`, con la ruta del clon.
  3. `scripts/10_publicar.py`: borra el contenido publicado anterior (salvo `README.md`, `.nojekyll` y `.git`),
     copia `public/`, hace commit `datos AAAA-MM-DD HH:MM` y push. Antes de publicar, que verifique que
     `manifest.json` diga `"ejemplo": false`.
  4. Después del push, esperar ~1 minuto y abrir
     https://marcelo-corro.github.io/aivital-incendios-datos/manifest.json para confirmar la nueva fecha de
     `generado_utc`.
  5. Avisar a José que ya hay datos reales y actualizar el aviso "Estado actual" del README del repo de datos.
- **Listo cuando:** el front muestra las 345 comunas con datos reales desde esa URL.

### B5 · Clima diario por comuna, para el modelo de A (~2-3 h)
- **Fuente:** Open-Meteo Archive (ERA5), la misma que usó la prueba de Seba. Ya está citada en
  [docs/fuentes.md](fuentes.md); agrega ahí el uso nuevo. Licencia no comercial.
- **Pasos:**
  1. `src/firecal/ingest/clima.py`: por cada comuna, un punto **dentro** del polígono (`representative_point()`,
     no el centroide, que en comunas irregulares puede caer fuera).
  2. Variables diarias 2012-01-01 a 2025-12-31: `temperature_2m_max`, `relative_humidity_2m_min`,
     `wind_speed_10m_max`, `precipitation_sum`, en hora de Chile.
  3. Pedir de a pocas comunas por consulta, reintentar con espera si responde 429 y **guardar en caché por comuna**
     (`data/raw/clima/{region_id}.json`) para poder retomar si se corta.
  4. Salida: `data/interim/clima_diario.parquet` con `region_id, fecha_local, tmax, hrmin, viento_max, precip`.
- **Listo cuando:** 345 comunas × 5.114 días, sin huecos, y la fuente registrada.

### B6 · Focos de 2026 casi en tiempo real (opcional, ~1,5 h)
FIRMS Area API (`VIIRS_NOAA20_NRT`, `VIIRS_NOAA21_NRT`, `MODIS_NRT`) con la MAP_KEY en `.env`. Sirve para mostrar
el mes en curso en la demo. Extender el período del contrato a 2026 requiere avisar a F y subir la versión.

## 7. Tareas de A · Marcelo (para que B sepa qué viene y cuándo)

| Tarea | Salida | Cuándo la necesita B |
|---|---|---|
| A1 · Armonización ✅ **lista** (14-11): factor único calibrado en 2012-2017, validado fuera de muestra con 2016-2017 | `serie_mensual.parquet` definitiva + [`docs/armonizacion.md`](armonizacion.md) | Ya: es la entrada de B2 |
| A2 · Eventos ✅ **lista** (14-11): agrupar focos en incendios no iguala los sensores (razón 3,2 → 2,3); la diferencia es sobre todo sensibilidad a incendios chicos | Cifras para el pitch en [`docs/eventos.md`](eventos.md) | No la necesita |
| A3 · Riesgo a 24 h, 48 h y 7 días ✅ (14-11, noche): `hgb_firms_clima_v3` (14 variables, sin fuga), 24 h AUC 0,846 en 2022-2025; 7 días orientativo; necesita `data/interim/clima_diario.parquet` | `riesgo.parquet` (3 horizontes) + `metricas.json` + `riesgo_horizontes.json` + [`docs/riesgo.md`](riesgo.md) | Ya: B3 los exporta (`09` + `13`) |
| A5 · Piloto de sectores, Región de Valparaíso ✅ (14-11, noche) | `scripts/11`-`13`, [`docs/sectores.md`](sectores.md); en `public/`: `sectores/`, `alertas/05.json`, `riesgo/48h.json`, `riesgo/7d.json`, `recomendaciones.json` (contrato v0.3) | F: vista P3b de `guia_front.md` |
| A4 · Cifras y gráficos para el pitch | `docs/` | — |

## 8. Reglas de trabajo

- **Cada uno toca solo sus carpetas** (sección 3).
- **Una rama por tarea:** `feat/b1-serie-provisional`, `feat/a1-armonizacion`, etc. PR chico; lo revisa el otro
  integrante del back. **Se mezcla a `main` solo si `pytest` pasa.**
- **`main` siempre funciona:** de ahí sale la demo.
- **Los datos no viajan por git.** Cada uno los genera con los scripts. Si hace falta compartir un procesado
  pesado, va por el Drive del equipo.
- **Nunca** subir `.env`, llaves, tokens ni contraseñas.
- **Toda fuente nueva** se registra en [docs/fuentes.md](fuentes.md) antes de usarla en la demo o el pitch.
- **Cambiar un contrato:** proponerlo en el chat del equipo, subir la versión en el documento y avisar a quien lo
  usa **antes** de mezclarlo.
- **Si te bloqueas más de 30 minutos**, avisa en el chat. Siempre hay algo provisional que destraba al resto.

## 9. Ritmo (hora de Chile)

| Cuándo | Qué |
|---|---|
| Sáb 17:00 | Punto de control: B2 en curso (David), José con datos de ejemplo en pantalla |
| Sáb 21:00 | Punto de control: B2-B3 listos, primeros datos reales en Pages |
| Dom 09:00 | Punto de control: serie armonizada visible en la app (A1 ya está lista) |
| Dom 13:00 | Punto de control: riesgo (A3) dentro o descartado para la demo |
| Dom 17:00 | **Congelar funciones:** desde aquí solo arreglos |
| Dom 20:00 | Demo en inglés y video listos |
| Dom 22:00 | Envío con margen; repos públicos |
| Dom 23:59 | Cierre del envío |

Cada punto de control dura 5 minutos: qué terminó cada uno, qué lo bloquea y si cambió algún contrato.
