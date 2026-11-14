# Contrato back → front · versión 0.2

> Guía para quien hace el front: [docs/guia_front.md](../docs/guia_front.md).

**Cambios**
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
  "contrato": "0.2",
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
  "contrato": "0.2",
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
  "contrato": "0.2",
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
- `nivel` (provisional): `bajo` | `medio` | `alto` | `muy_alto`.

## focos/{region_id}.csv

Columnas, en este orden: `fecha,hora_utc,lat,lon,sensor,satelite,confianza,frp,tipo`

- `fecha` en formato `YYYY-MM-DD`, `hora_utc` como `HHMM`.
- `sensor`: `MODIS` | `VIIRS`. `satelite`: `Terra` | `Aqua` | `SNPP` | `NOAA20` | `NOAA21`.
- `confianza`: `baja` | `nominal` | `alta` (misma escala para ambos sensores).

## metricas.json

```json
{
  "contrato": "0.2",
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
