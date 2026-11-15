# Contrato back → front · versión 0.8

> Guía para quien hace el front: [docs/guia_front.md](../docs/guia_front.md).

**Cambios**
- 0.8 (15-11-2026): **aditivo**. Nuevo `comunas.json` (en `manifest.archivos.comunas`): riesgo, clima del último
  día, motivos y recomendaciones de las **345 comunas** (antes solo las 36 del piloto, dentro de `alertas/05.json`).
  Detalle al final.
- 0.7 (15-11-2026): **aditivo**. Nuevo `avance/activos.json` (en `manifest.archivos.avance`): incendios activos de
  Chile con su zona probable de avance (círculos validados) y el viento. Detalle al final.
- 0.6 (15-11-2026): **aditivo**. `manifest.json` suma `datos`: de qué fecha es cada fuente (los datos ya no terminan
  el 31-12-2025: llegan hasta ayer con la MAP_KEY de FIRMS). Detalle al final.
- 0.5 (15-11-2026): **alertas por tipo**. La forma de los archivos no cambia (solo suma campos), pero la lista de
  `alertas/{codigo_region}.json` ahora puede venir **vacía** o con otro largo que 25. Suma `tipo`, `motivo_orden` y
  `dist_foco_reciente_km` por ítem, `listas` y `validacion` por archivo, y `fuego_activo`, `motivos` y datos de
  temporada por comuna. Detalle al final.
- 0.4 (15-11-2026): **aditivo**. Los sectores y las alertas suman los campos del modelo B (probabilidad por sector y
  de incendio grande) y el manifest suma `sectores.modelo_b` con sus métricas. Detalle al final.
- 0.3 (14-11-2026): **aditivo** (los archivos de la 0.2 no cambian de forma). Suma riesgo a 48 h y 7 días y el piloto
  de sectores de la Región de Valparaíso: `riesgo/48h.json`, `riesgo/7d.json`, `sectores/{region_id}.geojson`,
  `sectores/{region_id}_focos.csv`, `alertas/{codigo_region}.json`, `recomendaciones.json`. El manifest agrega sus
  rutas en `archivos` y la lista de comunas con sectores en `sectores.regiones`. Detalle al final.
- 0.2 (14-11-2026): `calendario` agrega `mediana_historica` por registro (el desafío pide comparar el mes
  actual con la mediana histórica).
- 0.1 (14-11-2026): primera versión.

El back publica **archivos estáticos** (JSON, GeoJSON y CSV). El front solo los lee: no depende de un servidor
corriendo. Todos los archivos viven bajo una URL base que se acordará al publicar (GitHub Pages o Release).

Mientras el back no tenga datos reales, `contracts/ejemplos/` trae archivos con **la forma exacta del contrato
pero con números inventados** (`"ejemplo": true`). Se regeneran con `python scripts/00_generar_ejemplos_contrato.py`.

Cualquier cambio de forma sube la versión (`"contrato"`) y se avisa al front antes de mezclarlo en `main`.

## Archivos

| Archivo | Qué trae |
|---|---|
| `manifest.json` | Versión del contrato, fecha de generación, período cubierto, lista de regiones y rutas |
| `regiones.geojson` | Contorno simplificado de cada comuna |
| `calendario/{region_id}.json` | Matriz mes × año: focos MODIS, VIIRS, armonizados con incertidumbre, percentil y nivel |
| `riesgo/ultimo.json` | Riesgo de foco para mañana por comuna |
| `focos/{region_id}.csv` | Focos individuales para descargar (lo pide el desafío) |
| `metricas.json` | Cuánto acierta el modelo, para mostrarlo en la app |

`region_id` es el código único territorial (CUT) de la comuna, como texto de 5 dígitos (ej. `"05109"`, Viña del Mar).

## manifest.json

```json
{
  "contrato": "0.3",
  "ejemplo": false,
  "generado_utc": "2026-11-15T03:00:00Z",
  "periodo": {"desde": "2000-11", "hasta": "2025-12"},
  "regiones": ["05101", "05109"],
  "archivos": {
    "regiones": "regiones.geojson",
    "calendario": "calendario/{region_id}.json",
    "riesgo": "riesgo/ultimo.json",
    "focos": "focos/{region_id}.csv",
    "metricas": "metricas.json"
  }
}
```

## regiones.geojson

`FeatureCollection` en WGS84 (EPSG:4326). Cada `Feature` tiene `properties`:
`region_id` (string), `nombre` (string), `region` (string, región administrativa), `pais` (`"CL"`).

## calendario/{region_id}.json

```json
{
  "contrato": "0.3",
  "ejemplo": false,
  "region_id": "05109",
  "nombre": "Viña del Mar",
  "unidad": "focos de vegetación (tipo 0) por mes",
  "unidad_armonizada": "equivalente MODIS",
  "metodo_armonizacion": "razon_zona_mes_v1",
  "registros": [
    {"anio": 2024, "mes": 2, "modis": 12, "viirs": 41, "armonizado": 12.4,
     "armonizado_p05": 10.6, "armonizado_p95": 14.3, "mediana_historica": 3.1,
     "percentil": 97, "nivel": "extrema"}
  ]
}
```

- Hay un registro por cada mes del período (sin huecos; un mes sin focos vale 0, no `null`).
- `modis` = focos MODIS de Terra + Aqua; `viirs` = focos VIIRS de Suomi NPP (NOAA-20 no se suma: ve los
  mismos incendios). Ambos son conteos crudos, sin armonizar.
- `mediana_historica`: mediana de `armonizado` para ese mismo mes en los demás años. Es la referencia para
  decir "este febrero va 4 veces sobre lo normal" (`armonizado / mediana_historica`).
- `modis` es `null` cuando no hay MODIS (antes de nov-2000 o después de su fin); `viirs` es `null` antes de 2012.
- `armonizado`, `armonizado_p05` y `armonizado_p95` son números decimales; el front redondea al mostrar.
- `percentil`: posición del mes contra el mismo mes de los demás años (0-100).
- `nivel` (umbrales provisionales, a confirmar): `baja` < 25 ≤ `normal` < 75 ≤ `alta` < 95 ≤ `extrema`.

## riesgo/ultimo.json

```json
{
  "contrato": "0.3",
  "ejemplo": false,
  "calculado_utc": "2026-11-15T03:00:00Z",
  "valido_para": "2026-11-15",
  "horizonte_horas": 24,
  "modelo": "riesgo_24h_v1",
  "items": [
    {"region_id": "05109", "prob_foco": 0.12, "percentil": 77, "nivel": "medio"}
  ]
}
```

- `prob_foco`: probabilidad de al menos un foco en la comuna en el horizonte (0-1).
- `percentil`: cómo se compara con la historia de esa comuna en esa época del año.
- `nivel`: `bajo` (< 4 %, cerca de la tasa base) | `medio` (4-12 %) | `alto` (12-30 %) | `muy_alto` (≥ 30 %), según
  `prob_foco`. La probabilidad máxima es 0,95: el modelo nunca dice "seguro".
- Mientras no haya focos de 2026 en tiempo casi real, `valido_para` es el día siguiente al último dato (2026-01-01).

## focos/{region_id}.csv

Columnas, en este orden: `fecha,hora_utc,lat,lon,sensor,satelite,confianza,frp,tipo`

- `fecha` en formato `YYYY-MM-DD`, `hora_utc` como `HHMM`.
- `sensor`: `MODIS` | `VIIRS`. `satelite`: `Terra` | `Aqua` | `SNPP` | `NOAA20` | `NOAA21`.
- `confianza`: `baja` | `nominal` | `alta` (misma escala para ambos sensores).

## metricas.json

```json
{
  "contrato": "0.3",
  "ejemplo": false,
  "modelo": "riesgo_24h_v1",
  "periodo_prueba": "2022-2025",
  "auc": 0.79,
  "precision_media": 0.47,
  "captura_top10": 0.31,
  "nota": "Texto corto para mostrar en la app sobre qué predice bien y qué no."
}
```

Mientras no haya modelo validado, las métricas van en `null` y el front muestra "pendiente".

---

## v0.3 · Riesgo a 48 h y 7 días y sectores (piloto Región de Valparaíso)

En `manifest.json`:

```json
"archivos": {"...": "...", "riesgo_48h": "riesgo/48h.json", "riesgo_7d": "riesgo/7d.json",
             "sectores": "sectores/{region_id}.geojson", "sectores_focos": "sectores/{region_id}_focos.csv",
             "alertas": "alertas/{codigo_region}.json", "recomendaciones": "recomendaciones.json"},
"sectores": {"codigo_region": "05", "regiones": ["05101", "05109", "..."]}
```

Solo las comunas de `sectores.regiones` tienen archivos de sectores. Si `sectores` no está en el manifest, el piloto no
se publicó y el front oculta esa vista.

### riesgo/48h.json y riesgo/7d.json

Misma forma que `riesgo/ultimo.json` (todas las comunas del país), más:

```json
{
  "valido_para": "2026-01-01", "valido_hasta": "2026-01-07", "horizonte_horas": 168,
  "umbrales": {"muy_alto": 0.7914, "alto": 0.5233, "medio": 0.2281, "bajo": 0.0},
  "metricas": {"periodo_prueba": "2022-2025", "auc": 0.817, "precision_media": 0.490, "captura_top10": 0.345,
               "tasa_base": 0.163, "precision_media_climatologia": 0.444, "ventaja_sobre_climatologia": 1.103},
  "orientativo": true,
  "nota": "Probabilidad de al menos un foco en la comuna en los próximos 7 días. Orientativa: ..."
}
```

- `prob_foco`: probabilidad de al menos un foco en la comuna entre `valido_para` y `valido_hasta`.
- `nivel` usa los `umbrales` de ESE horizonte (no los de 24 h): cada nivel agrupa la misma proporción de días-comuna
  que a 24 h. **No comparar probabilidades entre horizontes**: a 7 días siempre son más altas.
- `orientativo: true` → mostrar el aviso de `nota` (a 7 días el modelo supera poco a la climatología).

### sectores/{region_id}.geojson

`FeatureCollection` (WGS84) con un `Feature` por sector (celda de 1 km recortada a la comuna). `properties`:

| Campo | Tipo | Qué es |
|---|---|---|
| `sector_id` | string | `{region_id}_{ix}_{iy}` |
| `area_km2`, `lat`, `lon` | número | superficie y un punto dentro del sector |
| `rasgos` | lista | códigos de `recomendaciones.json → rasgos` (ej. `["interfaz", "pastizal", "historial"]`) |
| `exposicion` | 0-5 | n.º de rasgos de exposición. **Descriptivo**: no ordena ni es probabilidad |
| `pct_interfaz`, `pct_pastizal`, `pct_bosque_matorral`, `pct_cultivo`, `pct_construido` | 0-100 o `null` | % del sector |
| `pendiente_media` | grados | |
| `dias_con_fuego`, `focos`, `incendios_grandes`, `mayor_incendio_focos` | entero | historial 2012-2025 (VIIRS Suomi NPP) |
| `ultimo_fuego` | `YYYY-MM-DD` o `null` | |
| `recomendaciones` | objeto | `{"24": [...], "48": [...], "168": [...]}`: códigos de recomendación según los rasgos del sector, el nivel de la comuna en cada horizonte y el clima del último día en la comuna ("avisar" siempre primero) |

**El sector no tiene probabilidad.** Para colorear el mapa usar el historial (`dias_con_fuego`) o un rasgo, con la
leyenda "historial" o "qué hay en el sector", nunca "probabilidad".

### sectores/{region_id}_focos.csv

Para el heatmap. Columnas: `fecha,lat,lon,frp,focos_incendio,sector_id` (VIIRS Suomi NPP 2012-2025, sin fuentes
industriales persistentes). `focos_incendio` = tamaño del incendio al que pertenece el foco (> 10 = grande).

### alertas/{codigo_region}.json

```json
{
  "codigo_region": "05", "nota": "Orden de prioridad: ...",
  "horizontes": {"24": [{"sector_id": "05102_-1018_-188", "region_id": "05102", "comuna": "Casablanca",
                         "nivel_comuna": "alto", "prob_foco_comuna": 0.125, "exposicion": 2,
                         "rasgos": ["pastizal", "historial"], "lat": -33.289, "lon": -71.394,
                         "recomendaciones": ["avisar_130", "sin_quemas_05", "sin_colillas"]}],
                 "48": [], "168": []},
  "comunas": [{"region_id": "05109", "nombre": "Viña del Mar",
               "riesgo": {"24": {"prob_foco": 0.01, "nivel": "bajo"}, "48": {}, "168": {}},
               "clima_ultimo_dia": {"fecha_clima": "2025-12-31", "tmax": 30.6, "tmax_percentil": 97, "hrmin": 25,
                                    "hrmin_percentil": 12, "viento_max": 5.0, "viento_max_kmh": 17.9,
                                    "viento_percentil": 40, "dias_sin_lluvia": 88, "dias_sin_lluvia_percentil": 50,
                                    "condiciones": ["calor", "temp_sobre_30", "humedad_bajo_30"]},
               "recomendaciones_clima": ["avisar_130", "faena_cero", "sin_fuentes_calor", "sin_quemas_05"]}],
  "caso": {"fecha": "2024-02-04", "items": [{"...": "...", "tuvo_fuego_ese_dia": false}],
           "sectores_con_fuego_ese_dia": ["..."]}
}
```

- Listas en orden de prioridad (hasta 25, máximo 5 por comuna): comunas con mayor nivel y probabilidad; dentro, sectores
  con más días con fuego previos y, a igualdad, más interfaz. **No** es la probabilidad de que ese sector se queme.
- `condiciones` (texto de cada código en `recomendaciones.json → condiciones`): `calor`, `aire_seco`, `viento`,
  `sin_lluvia` (entre el 10 % más extremo para ese mes) y los umbrales de la Dirección Meteorológica de Chile
  `temp_sobre_30`, `humedad_bajo_30`, `viento_sobre_30` y `condicion_30_30_30` (los tres juntos). Clima de NASA POWER
  (~50 km, humedad mínima aproximada): es una referencia, no una medición local. `viento_max` en m/s y
  `viento_max_kmh` en km/h.
- `recomendaciones_clima`: códigos de recomendación por el clima de la comuna (Faena Cero de CONAF, fuentes de calor,
  quemas, avisar). Ya vienen sumadas en las `recomendaciones` de cada sector y de cada alerta: el front no tiene que
  combinarlas.
- `caso`: cómo se habría visto la lista el 4-feb-2024 y qué sectores tuvieron fuego. Ese día ninguno de la lista lo
  tuvo (ver `docs/sectores.md`): si se muestra, mostrarlo así.

### recomendaciones.json

`rasgos` (código → texto), `condiciones` (código → `{texto, fuente}`; `fuente` es `null` en las relativas al mes),
`recomendaciones` (código → `{texto, fuente}`), `fuentes` (código → `{nombre, url}`), `umbrales_rasgos` y
`fuentes_capas`. El front muestra el texto y enlaza la fuente; no inventa recomendaciones.

---

## v0.4 · Modelo B: probabilidad por sector y de incendio grande

Si `manifest.sectores.modelo_b` existe, cada `Feature` de `sectores/{region_id}.geojson` suma:

| Campo | Qué es |
|---|---|
| `prob_si_fuego_en_comuna` | Si hay fuego en la comuna el día siguiente, probabilidad de que caiga en este sector (0-1, calibrada) |
| `prob_fuego_24h` | Probabilidad de fuego en el sector mañana = probabilidad de la comuna a 24 h × la anterior (valores chicos: un sector es 1 km²) |
| `prob_incendio_grande` | Si hay fuego en este sector, probabilidad de que sea parte de un incendio grande (más de 10 focos) |
| `percentil_en_comuna` | Posición de `prob_si_fuego_en_comuna` dentro de la comuna (0-100): **úsalo para colorear el mapa** |

Los ítems de `alertas/{codigo_region}.json → horizontes` suman `prob_si_fuego_en_comuna` y `prob_incendio_grande`.
**El orden de la lista no cambia** (sigue el del A+: en la prueba, con fuego nuevo, ordenó mejor que el modelo B).

`manifest.sectores.modelo_b`:

```json
{"modelo": "sectores_b_v1", "fecha_prediccion": "2026-01-01",
 "captura_top10_prueba": {"modelo_b": 44.52, "orden_a": 39.34, "azar": 10.0},
 "auc_incendio_grande_prueba": 0.866, "auc_incendio_grande_ignicion_prueba": 0.83,
 "nota": "Prueba 2022-2025: el 10 % de sectores con mayor probabilidad de cada comuna concentró el 45 % del fuego ..."}
```

- Para 48 h y 7 días no hay `prob_fuego_*` por sector: se muestra `prob_si_fuego_en_comuna` junto al riesgo de la comuna.
- Mostrar `nota` cerca del mapa. No decir que el modelo "predice dónde empieza un incendio".

---

## v0.5 · Alertas por tipo (fuego activo, alerta, vigilancia)

Cambia **cómo se arma** la lista de `alertas/{codigo_region}.json → horizontes[h]`:

| Tipo (`tipo`) | Qué comunas | Orden de sus sectores (`motivo_orden`) | Sectores por comuna |
|---|---|---|---|
| `fuego_activo` | Focos (sin industria) en los 3 días previos, **cualquiera sea su nivel** | `cerca_fuego_reciente`: más cerca del foco reciente primero | hasta 5 |
| `alerta` | Nivel alto o muy alto, sin fuego activo | `historial_interfaz` | hasta 5 |
| `vigilancia` | Nivel medio, sin fuego activo | `historial_interfaz` | hasta 3 |

Las comunas en nivel **bajo no entran**: la lista puede venir **vacía**. Orden: primero `fuego_activo`, luego `alerta`,
luego `vigilancia`; dentro de cada tipo, por nivel y probabilidad. Los ítems `fuego_activo` traen además
`dist_foco_reciente_km`.

Nuevos campos del archivo:

```json
"listas": {"24": {"tipo_lista": "alertas", "titulo": "Alertas para mañana", "comunas_fuego_activo": 4,
                  "comunas_alerta": 0, "comunas_vigilancia": 0, "vacia": false, "mensaje": null},
           "48": {...}, "168": {"tipo_lista": "prioridades_semana", "titulo": "Prioridades de la semana (orientativo)", ...}},
"validacion": {"periodo": "2022-2025", "pct_fuego_dia_siguiente_en_lista": 6.92, "sectores_por_dia": 12.02,
               "pct_territorio_por_dia": 0.067, "pct_fuego_en_lista_regla_anterior": 4.68,
               "pct_dias_sin_alertas": 20.96, "nota": "Simulación 2022-2025: la lista marcó en promedio 12 sectores ..."}
```

- `listas[h].titulo`: usarlo como título. A 7 días es **"Prioridades de la semana (orientativo)"**, no "alertas".
- Si `listas[h].vacia` es `true`, mostrar `listas[h].mensaje` en vez de la lista.
- `validacion.nota`: el respaldo de la lista, para la ficha de metodología o el pitch.

En cada elemento de `comunas[]`:

| Campo | Qué es |
|---|---|
| `fuego_activo` | Hubo focos (sin industria) en los 3 días previos |
| `dias_con_fuego_7d`, `ultimo_fuego` | Días con focos en la última semana y fecha del último |
| `pct_dias_con_fuego_mes` | % de los días de ese mes (2012-2025) con focos en la comuna |
| `motivos` | Lista de textos listos para mostrar: fuego activo o reciente, clima del último día y temporada. Son hechos verificables que acompañan el nivel, no el peso de cada variable en el modelo |

---

## v0.6 · Frescura de los datos (`manifest.datos`)

```json
"datos": {"valido_para": "2026-11-15", "ultimo_dato_focos": "2026-11-14", "ultimo_dato_suomi_npp": "2026-11-01",
          "sustitucion_noaa20": true, "clima_hasta": "2026-11-11", "clima_rezago_dias": 3,
          "prueba_nueva": {"desde": "2026-01-02", "hasta": "2026-11-01", "auc": 0.83, "auc_climatologia": 0.79,
                           "precision_media": 0.25},
          "nota": "Focos satelitales hasta el 2026-11-14. Suomi NPP no tiene datos desde ... El clima (NASA POWER) ..."}
```

- `valido_para`: el día del riesgo publicado (el primero de cada horizonte). Ya no es el 1-ene-2026.
- `nota`: texto listo para mostrar junto a la fecha ("de qué fecha son los datos"). Mostrarlo siempre.
- `prueba_nueva`: cómo le fue al modelo en 2026, con datos que no existían cuando se eligió (para Metodología/pitch).
  Los valores del ejemplo son ilustrativos: usar los del archivo.

---

## v0.7 · Incendios activos y zona probable de avance (`avance/activos.json`)

```json
{"contrato": "0.7", "ultimo_dato": "2026-11-14", "nota": "Incendios con focos satelitales (VIIRS) en los 3 días ...",
 "validacion": {"radios_km": {"p75": 2.53, "p90": 3.63}, "cobertura_prueba_pct": {"p75": 68.9, "p90": 85.4},
                "viento_fuerte_desde_ms": 3.18, "acierto_45_viento_fuerte_prueba_pct": 35.7, "acierto_45_azar_pct": 25.0},
 "incendios": [{"id": "05301-20261113-123", "region_id": "05705", "comuna": "Putaendo", "region": "Región de Valparaíso",
                "lat": -32.6, "lon": -70.7, "inicio": "2026-11-13", "ultimo_foco": "2026-11-13",
                "focos_ultimo_dia": 3, "focos_incendio": 3, "dias_con_focos": 1,
                "radio_km_70": 2.53, "radio_km_85": 3.63,
                "viento": {"fecha": "2026-11-12", "desde_grados": 217, "hacia_grados": 37, "velocidad_ms": 1.5, "fuerte": false},
                "mostrar_flecha": false}]}
```

- Un ítem por incendio con focos (sin industria marcada) en los 3 días hasta `ultimo_dato`; `lat`/`lon` = centro de sus
  focos más recientes. Valores del ejemplo ilustrativos.
- Dibujar **dos círculos** centrados ahí: `radio_km_70` ("~70 % de los avances del día siguiente cae dentro") y
  `radio_km_85` ("~85 %"). Son la zona probable de avance; **no dibujar un cono**.
- Flecha hacia `viento.hacia_grados` (0 = norte, 90 = este) **solo si `mostrar_flecha` es `true`** (viento fuerte):
  "el avance siguió el viento el 36 % de las veces (al azar, 25 %)". Con viento suave, sin flecha.
- Mostrar `nota` cerca del mapa. Reemplaza el cono inventado del modo visión.

## v0.8 · Clima, motivos y recomendaciones de todas las comunas (`comunas.json`)

```json
{"contrato": "0.8", "ejemplo": false, "valido_para": "2026-11-15", "ultimo_dato_focos": "2026-11-14",
 "fecha_clima": "2026-11-11", "nota": "Clima observado del último día con datos (NASA POWER) ...",
 "comunas": [{"region_id": "09202", "nombre": "Collipulli", "region": "Región de La Araucanía",
              "riesgo": {"24": {"prob_foco": 0.285, "nivel": "alto"}, "48": {...}, "168": {...}},
              "clima_ultimo_dia": {"fecha_clima": "2026-11-11", "tmax": 23.2, "hrmin": 53.0, "viento_max_kmh": 11.5,
                                   "dias_sin_lluvia": 6, "condiciones": [], "...": "percentiles"},
              "recomendaciones_clima": [], "recomendaciones": {"24": ["avisar_130"], "48": [...], "168": [...]},
              "fuego_activo": true, "dias_con_fuego_7d": 1, "ultimo_fuego": "2026-11-14", "pct_dias_con_fuego_mes": 17.0,
              "motivos": ["Fuego activo: focos en los últimos 3 días (último el 14-11-2026)", "..."]}]}
```

- Una entrada por comuna (345), con la **misma forma** que `alertas/{codigo_region}.json → comunas` del piloto, más
  `region` y `recomendaciones` por horizonte. Para las 36 comunas de Valparaíso los valores coinciden con
  `alertas/05.json` (salvo `pct_dias_con_fuego_mes`, que aquí cuenta los focos por polígono de comuna y allá por sector).
- `recomendaciones[h]`: códigos de `recomendaciones.json` para el horizonte `h`, por el clima del último día y, si el
  nivel de la comuna es alto o muy alto, "avisar al 130". La restricción de quemas solo se nombra en la región que la
  tiene (05); en el resto, el calendario de quemas de CONAF. Lista vacía si no corresponde ninguna (no se inventan).
- `motivos`: hechos verificables que acompañan el nivel (no son el peso de cada variable en el modelo). Fuera de
  Valparaíso los focos pueden incluir alguna fuente industrial no marcada por FIRMS (lo dice `nota`).
- `fuego_activo` marca toda comuna con algún foco en los 3 días; `avance/activos.json` ubica cada incendio en la comuna
  de su centro, por eso puede haber una comuna con fuego activo sin incendio propio en ese archivo.
