# Contratos internos del back

Tablas que se pasan entre etapas del pipeline. Viven en `data/` (no se versionan): cada integrante las genera
corriendo los scripts en orden. Quien produce una tabla compartida **la valida antes de guardarla** con
`firecal.contratos` (si la forma cambia, el validador falla en la máquina de quien la cambió).

Para el contrato con el front (archivos publicados), ver [README.md](README.md).

## Mapa de tablas

| Tabla | La produce | La usa | Validador |
|---|---|---|---|
| `data/interim/focos_calidad.parquet` | paso 4 (listo) | armonización, exportación de focos, modelo | columnas en `firecal/calidad.py` |
| `data/interim/comunas.parquet` | paso 3 (listo) | exportación (GeoJSON), modelo | columnas en `firecal/ingest/comunas.py` |
| `data/processed/serie_mensual.parquet` | `05_armonizar.py` (A) o `05p_serie_provisional.py` (B) | `07_calendario.py` (B) | `validar_serie_mensual` |
| `data/processed/calendario.parquet` | `07_calendario.py` (B) | `09_exportar.py` (B) | `validar_calendario` |
| `data/processed/riesgo.parquet` | `08_riesgo.py` (A) | `09_exportar.py` (B) | `validar_riesgo` |
| `data/processed/metricas.json` | `08_riesgo.py` (A) | `09_exportar.py` (B) | — |

A = ciencia de datos (armonización y modelos). B = producto de datos (calendario, exportación y publicación).
Detalle del reparto: [docs/trabajo_en_equipo.md](../docs/trabajo_en_equipo.md).

## serie_mensual.parquet

Una fila por **comuna × mes**: las 345 comunas, de 2000-11 a 2025-12 (302 meses). **Grilla completa**: un mes
sin focos va con 0, no se omite.

| Columna | Tipo | Regla |
|---|---|---|
| `region_id` | string | CUT de 5 dígitos (`"05109"`) |
| `anio`, `mes` | int | año y mes **locales** (se cuentan por `fecha_local`, no por la fecha UTC) |
| `modis` | Int64 | focos MODIS **Terra + Aqua** con `uso_base`, sin armonizar |
| `viirs` | Int64 | focos VIIRS de **Suomi NPP** con `uso_base`, sin armonizar; nulo antes de 2012-02 (Suomi NPP empieza el 20-ene-2012). NOAA-20 no se suma |
| `armonizado` | float | serie armonizada en **focos equivalentes MODIS**; nunca nula ni negativa. En la versión de A: Terra convertido hasta 2002-06, MODIS observado 2002-07 a 2017-12, VIIRS convertido desde 2018-01 ([detalle](../docs/armonizacion.md)) |
| `armonizado_p05`, `armonizado_p95` | float | intervalo de incertidumbre; puede ser nulo en la versión provisional |
| `metodo` | string | un solo valor para toda la tabla: `provisional_factor_unico` (B) o el nombre del método de A |

`uso_base` = vegetación (`tipo == 0`) y confianza nominal o alta. Ver [docs/calidad_datos.md](../docs/calidad_datos.md).

## calendario.parquet

Las columnas de `serie_mensual` más:

| Columna | Tipo | Regla |
|---|---|---|
| `mediana_historica` | float | mediana de `armonizado` para el **mismo mes** en los **demás años** de esa comuna |
| `percentil` | float 0-100 | posición del mes contra el mismo mes de los demás años, con rango medio para empates: `100 × (n_menores + 0,5 × n_iguales) / n_otros_años` |
| `nivel` | string | `baja` si percentil < 25; `normal` < 75; `alta` < 95; `extrema` ≥ 95 |

El rango medio importa: en comunas con pocos incendios hay muchos meses en 0, y sin él un 0 contra otros ceros
saldría como "baja" en vez de "normal".

## riesgo.parquet

| Columna | Tipo | Regla |
|---|---|---|
| `region_id` | string | CUT de 5 dígitos |
| `valido_para` | datetime | día local al que se refiere el pronóstico |
| `horizonte_horas` | int | 24 o 48 |
| `prob_foco` | float 0-1 | probabilidad de al menos un foco en la comuna en el horizonte |
| `percentil` | float 0-100 | cómo se compara con la historia de esa comuna en esa época del año |
| `nivel` | string | `bajo`, `medio`, `alto` o `muy_alto` |
| `modelo` | string | nombre y versión del modelo |

Una fila por comuna y `valido_para`. La exportación publica solo el `valido_para` más reciente.

## metricas.json

Mismos campos que `metricas.json` del contrato con el front, sin `contrato` ni `ejemplo`:
`modelo`, `periodo_prueba`, `auc`, `precision_media`, `captura_top10`, `nota`. Mientras no haya modelo validado,
no existe y la exportación publica las métricas en `null`.
