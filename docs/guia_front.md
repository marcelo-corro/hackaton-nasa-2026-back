# Guía del front · AIVital

Para José, que construye la app web. El back entrega **archivos estáticos en una URL** (no hay servidor): el front
solo los lee con `fetch`. Contexto completo del proyecto en [trabajo_en_equipo.md](trabajo_en_equipo.md).

## 1. Qué construimos y para quién

Una app que muestra, para cada **comuna de Chile**, cuánta actividad de fuego hubo cada mes desde 2000, con una
serie que corrige el cambio de satélite (MODIS → VIIRS). Dice qué meses fueron anómalos contra la historia de
esa comuna, deja descargar los focos y, si alcanza, muestra el riesgo para mañana.

**Usuarios:** equipos municipales de prevención, SENAPRED, brigadistas, gestores del territorio.
**El jurado** (local en Santiago y luego global) tiene que entender en 20 segundos qué problema resolvemos.

## 2. Qué pide el desafío al front (resumen del texto oficial)

- Una **aplicación web** donde el usuario **elige un área y un rango de fechas**.
- Un **calendario de actividad de quema**: cantidad de focos por mes y año desde inicios de los 2000.
- Ver qué meses y años tuvieron más actividad y **comparar el mes actual con la mediana histórica**.
- **Rampas de color accesibles** para representar las diferencias entre meses.
- **Descargar en CSV** los focos de la búsqueda.
- Sugerido: un **mapa interactivo** para elegir el área.

## 3. Pantallas del MVP

### P1 · Mapa e inicio
- Mapa de Chile con las comunas (`regiones.geojson`) y un **buscador por nombre**.
- Clic en una comuna → abre su ficha (P2).
- Color del mapa: el `nivel` de riesgo de mañana (`riesgo/ultimo.json`) o, si no hay modelo, el nivel del último
  mes del calendario.

### P2 · Ficha de comuna (la pantalla principal de la demo)
- **Calendario**: grilla años (filas) × meses (columnas) coloreada por `armonizado`. Al pasar el mouse:
  `modis`, `viirs`, `armonizado` con su intervalo (`armonizado_p05`-`armonizado_p95`), `mediana_historica`,
  `percentil` y `nivel`.
- **Selector de serie: Armonizada / MODIS crudo / VIIRS crudo.** Es la parte más importante para el pitch: deja
  ver con los ojos que sin armonizar la serie "salta" en 2012 cuando entra VIIRS.
- **Selector de rango de años.**
- **Tarjeta "este mes contra lo normal"**: `armonizado / mediana_historica` (por ejemplo "×4,2 sobre lo normal")
  y el `nivel` con texto, no solo color.
- **Gráfico anual**: total por año, para ver los años extremos (2017, 2023).
- **Botón "Descargar CSV"** de `focos/{region_id}.csv`, filtrado en el navegador por el rango de fechas elegido.

### P3 · Riesgo a 24-48 h (si el back lo entrega)
- Mapa por `nivel` (`bajo`, `medio`, `alto`, `muy_alto`) y lista de las comunas con mayor riesgo.
- Bloque de **desempeño** con `metricas.json` y la `nota`. Si las métricas vienen en `null`, mostrar
  "Modelo en validación".
- Aviso visible: el modelo anticipa bien la **propagación** de incendios activos, no dónde **empieza** uno.

### P4 · Acerca de y fuentes
- Qué hace la app y el método en 4-5 líneas (por qué hay que armonizar: los satélites MODIS se desvían de órbita
  y VIIRS ve más; el conteo cambia por el satélite, no por el fuego).
- **Fuentes y citas obligatorias**: copiar las de [fuentes.md](fuentes.md) (el agradecimiento oficial de NASA
  FIRMS, la Biblioteca del Congreso Nacional por los límites comunales y, si se muestra el riesgo, Open-Meteo/ERA5).
- Equipo y limitaciones.

## 4. Propuesta de producto (idea para partir; José decide)

### Concepto
- **Nombre tentativo:** *Calendario de Fuego · Chile* (en inglés, *Chile Fire Calendar*).
- **Pregunta que responde:** *¿Es normal el fuego de este mes en mi comuna?*
- **En una frase:** buscas tu comuna y en segundos ves si hay más fuego de lo normal, sobre 25 años de datos que ya
  corrigen el cambio de satélites.

### Recorrido del usuario (3 pasos)
1. **Busca o toca su comuna** en el mapa.
2. **Ve la ficha:** la tarjeta "contra lo normal" y el calendario de 25 años.
3. **Descarga los focos** en CSV o mira el riesgo para mañana.

### Boceto de la ficha de comuna (escritorio)
Los números del boceto son ilustrativos; los reales vienen del back.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Calendario de Fuego · Chile        [ Buscar comuna...      ]   ES | EN  (i) │
├─────────────────────────┬───────────────────────────────────────────────────┤
│                         │ Viña del Mar · Región de Valparaíso               │
│   MAPA DE CHILE         │ ┌──────────────────────┐ ┌──────────────────────┐ │
│   comunas coloreadas    │ │ Febrero 2024         │ │ Riesgo para mañana   │ │
│   por nivel             │ │ EXTREMA              │ │ ALTO                 │ │
│                         │ │ ×4,2 sobre un        │ │ "Modelo en           │ │
│   [la comuna elegida    │ │ febrero normal       │ │  validación" si no   │ │
│    queda destacada]     │ └──────────────────────┘ │  hay métricas        │ │
│                         │                          └──────────────────────┘ │
│                         │ Serie: (•) Armonizada  ( ) MODIS crudo  ( ) VIIRS │
│                         │ Años:  2000 [=========================] 2025      │
│                         │                                                   │
│                         │        E  F  M  A  M  J  J  A  S  O  N  D         │
│                         │  2025  ▓  ▓  ░  ░  ·  ·  ·  ·  ·  ░  ▓  ▓         │
│                         │  2024  ▓  █  ▓  ░  ·  ·  ·  ·  ·  ░  ▓  ▓         │
│                         │  ...                       (calendario de calor)  │
│                         │                                                   │
│                         │  Total por año: ▁▂▁▃▁▁▂▂▁▂▁▁▁▁▁▁█▂▂▁▂▁▃█▂▁        │
│                         │                                                   │
│                         │ [ Descargar focos (CSV) ]    Fuentes: NASA FIRMS… │
└─────────────────────────┴───────────────────────────────────────────────────┘
```

En el **teléfono**: el mapa pasa arriba (plegable), la ficha abajo, y el calendario se desplaza en horizontal.

### El "momento wow" para el jurado
Un botón **"Ver sin armonizar"**. Al activarlo, el calendario muestra los datos crudos de los satélites y se ve
un **salto artificial en 2012**, cuando entra VIIRS. Al volver a "Armonizada", el salto desaparece. Sugerencia:
una transición suave de colores entre ambas vistas y una anotación sobre 2012: *"aquí cambió el satélite, no el
fuego"*. Es la explicación del desafío en un solo gesto.

### Componentes y de dónde sale cada dato

| Componente | Archivo | Campos |
|---|---|---|
| Buscador de comunas | `manifest.json`, `regiones.geojson` | `region_id`, `nombre` |
| Mapa por colores | `regiones.geojson` + `riesgo/ultimo.json` (o el último mes del calendario) | `nivel` |
| Tarjeta "contra lo normal" | `calendario/{region_id}.json`, último mes con datos | `armonizado`, `mediana_historica`, `nivel` |
| Tarjeta de riesgo | `riesgo/ultimo.json`, `metricas.json` | `prob_foco`, `nivel`, `nota` |
| Calendario de calor | `calendario/{region_id}.json` | `armonizado` (o `modis` / `viirs` según el selector), `percentil`, `nivel` |
| Total por año | `calendario/{region_id}.json` | suma de `armonizado` por año |
| Descarga | `focos/{region_id}.csv` | se filtra por el rango de años elegido |
| Fuentes | texto fijo | copiar de [fuentes.md](fuentes.md) |

### Textos sugeridos (español / inglés para la demo)

| Dónde | Español | English |
|---|---|---|
| Título | ¿Es normal el fuego de este mes en tu comuna? | Is this month's fire activity normal in your commune? |
| Tarjeta | Febrero 2024: 4,2 veces un febrero normal en Viña del Mar | February 2024: 4.2× a typical February in Viña del Mar |
| Botón | Ver sin armonizar | Show raw satellite data |
| Ayuda de la unidad | Focos equivalentes MODIS: los dos satélites en una misma escala, para comparar 2005 con 2025 | MODIS-equivalent hotspots: both satellites on one scale, so 2005 and 2025 are comparable |
| Aviso del riesgo | Anticipa bien cómo se propaga un incendio activo; no predice dónde empieza uno | Good at anticipating how active fires spread; it does not predict where a new fire starts |

### Paleta sugerida
- **Calendario:** *cividis* (apta para daltonismo), con escala por cuantiles.
- **Niveles:** baja `#4575b4` (azul), normal `#bdbdbd` (gris), alta `#fdae61` (naranja), extrema `#a50026`
  (rojo oscuro). **Siempre acompañados del texto**, nunca solo el color.

### Si sobra tiempo (en este orden)
1. **Enlace compartible:** `?comuna=05109` abre directo esa ficha (sirve para la demo).
2. **Comparar dos comunas** lado a lado.
3. **Ranking:** comunas con más meses "extrema" en la última temporada.
4. **Modo presentación:** pantalla completa con Viña del Mar ya cargada.

### Fuera de alcance (no gastar tiempo)
Inicio de sesión, base de datos, dibujar polígonos, editar datos, notificaciones.

### Guion de la demo de 30 segundos

| Segundos | En pantalla | Narración (inglés) |
|---|---|---|
| 0-5 | Mapa de Chile | *Satellites have tracked fires since 2000, but the sensors changed.* |
| 5-13 | Viña del Mar con "Ver sin armonizar": salto en 2012 | *Raw data jumps in 2012. That's a new satellite, not more fire.* |
| 13-22 | Vuelta a "Armonizada"; febrero de 2024 en EXTREMA | *Harmonized, February 2024 stands out: several times a normal February.* |
| 22-30 | Tarjeta de riesgo, descarga de CSV y fuentes | *All 345 communes of Chile, with open data and an honest risk outlook.* |

## 5. Cómo conectarse a los datos

### Una sola variable, y ya es la definitiva

Todo el front depende de **una URL base**, por ejemplo `DATA_BASE_URL`:

```
https://marcelo-corro.github.io/aivital-incendios-datos
```

**Ya funciona** (repo público [aivital-incendios-datos](https://github.com/marcelo-corro/aivital-incendios-datos)) y
permite leer los archivos desde cualquier dominio (CORS abierto). Prueba:
https://marcelo-corro.github.io/aivital-incendios-datos/manifest.json

La URL no cambia nunca: lo que cambia es el contenido. No tienes que tocar nada en el front para pasar de
ejemplo a datos reales; basta recargar.

| Fase | Qué hay en esa URL | Cuándo |
|---|---|---|
| 0 · Ejemplos | Forma definitiva (contrato v0.2), **2 comunas con números inventados** (`"ejemplo": true`): `05101` Valparaíso y `05109` Viña del Mar | **Disponible ahora** |
| 1 · Provisional | Las 345 comunas con datos reales y serie provisional (`metodo` empieza con `provisional`) | Sábado en la noche (lo publica David) |
| 2 · Armonizada | La serie armonizada definitiva | Domingo en la mañana |

### Rutas (detalle de cada campo en el [contrato v0.2](../contracts/README.md))

| Ruta | Contenido |
|---|---|
| `/manifest.json` | Versión, fecha de generación, período y lista de comunas. **Leerlo primero.** |
| `/regiones.geojson` | Contornos simplificados de las comunas |
| `/calendario/{region_id}.json` | Matriz mes × año de una comuna |
| `/riesgo/ultimo.json` | Riesgo de mañana por comuna |
| `/focos/{region_id}.csv` | Focos de la comuna para descargar |
| `/metricas.json` | Desempeño del modelo |

`region_id` es el código de comuna de 5 dígitos como texto (`"05109"` = Viña del Mar). Úsalo siempre como texto:
como número se pierde el 0 inicial.

### Ejemplo

```js
const BASE = import.meta.env.VITE_DATA_BASE_URL; // o una constante en tu config

const manifest = await fetch(`${BASE}/manifest.json`).then((r) => r.json());
if (manifest.contrato !== "0.2") console.warn("El back publicó otra versión del contrato:", manifest.contrato);

const regiones = await fetch(`${BASE}/regiones.geojson`).then((r) => r.json());

async function cargarCalendario(regionId) {
  const r = await fetch(`${BASE}/calendario/${regionId}.json`);
  if (!r.ok) throw new Error(`Sin calendario para ${regionId}`);
  return r.json();
}

async function descargarCsv(regionId, nombre) {
  // fetch + Blob: el atributo download no funciona bien entre dominios distintos
  const texto = await fetch(`${BASE}/focos/${regionId}.csv`).then((r) => r.text());
  const enlace = document.createElement("a");
  enlace.href = URL.createObjectURL(new Blob([texto], { type: "text/csv" }));
  enlace.download = `focos_${nombre}.csv`;
  enlace.click();
}
```

### Casos que el front debe manejar
- `"ejemplo": true` en un archivo → banner "Datos de ejemplo".
- `metodo` empieza con `provisional` → etiqueta "Serie provisional".
- Valores `null` → mostrar "—" (por ejemplo `viirs` antes de 2012 o el intervalo en la versión provisional).
- Métricas en `null` → "Modelo en validación".
- Cargar el GeoJSON una vez y cada calendario **solo cuando se abre** la comuna (son 345 archivos).

## 6. Diseño

- **Rampa del calendario:** secuencial y apta para daltonismo (viridis o cividis). Escala logarítmica o por
  cuantiles: hay meses con 0 y meses con cientos de focos.
- **Niveles:** colores distinguibles para daltonismo y **siempre con texto** (`baja`, `normal`, `alta`, `extrema`).
- **Unidad:** "focos equivalentes MODIS", con un ícono de ayuda que explique qué significa.
- **Responsive:** el jurado puede abrirla en el teléfono.
- **Idioma:** interfaz en español; para la demo y el juicio global hace falta una versión en inglés (basta un
  diccionario de textos).

## 7. Tecnología (decide José)

- **Opción A:** React + Vite, mapa con MapLibre GL o Leaflet, calendario con ECharts, Plotly o D3. Se publica en
  GitHub Pages, Vercel o Netlify.
- **Opción B:** Streamlit (Python), leyendo la misma URL. Se publica en Streamlit Community Cloud (en el kit del
  equipo ya se probó un deploy).
- En cualquier caso: hosting estático y **ninguna llave ni secreto en el front**.

## 8. Listo para la demo

- [ ] Abre en una URL pública, en computador y en teléfono.
- [ ] Buscar una comuna, ver su calendario y cambiar entre serie armonizada y crudas.
- [ ] Tarjeta "este mes contra lo normal" con nivel en texto.
- [ ] Descarga de CSV que respeta el rango de fechas.
- [ ] Riesgo y métricas, o la leyenda "Modelo en validación".
- [ ] Página de fuentes con las citas.
- [ ] Textos en inglés para la demo.
- [ ] Sin banner de "Datos de ejemplo" (o sea, conectada a los datos reales).

**Demo obligatoria de Space Apps:** video de 30 segundos o menos, o hasta 7 láminas, en inglés y con enlace
público. Caso sugerido para mostrar: Viña del Mar, febrero de 2024.

## 9. Coordinación

- **Dudas sobre los datos o la URL:** David (B). **Sobre qué significa un número:** Marcelo (A).
- Si necesitas un campo nuevo o un cambio de forma, pídelo en el chat del equipo: se sube la versión del contrato
  y se avisa antes de publicarlo.
- Puntos de control y horario de cierre: [trabajo_en_equipo.md](trabajo_en_equipo.md#9-ritmo-hora-de-chile).
