# Sectores dentro de la comuna (piloto A+, Región de Valparaíso)

Qué hay en cada sector de 1 km de las 36 comunas continentales de la Región de Valparaíso, cómo se prioriza y qué
**no** se afirma. Scripts: `11_descargar_capas.py` → `12_sectores.py` → `12b_validar_sectores.py` →
`13_exportar_sectores.py` (después de `09_exportar.py`). Código en `src/firecal/sectores/`.

## Resumen
- **Riesgo con probabilidad: por comuna** (modelo validado, `docs/riesgo.md`), a 24 h, 48 h y 7 días.
- **Sectores: descriptivos.** 17.953 sectores (celdas de 1 km recortadas a la comuna, 15.960 km²) con historial de
  focos, vegetación, interfaz con viviendas y pendiente. El sector **no** tiene probabilidad propia: no hay datos
  que varíen dentro de la comuna día a día (el clima es por comuna) ni etiquetas de tipo de incendio.
- **Prioridad:** dentro de las comunas con más riesgo, los sectores con más días con fuego previos y, a igualdad,
  más interfaz. En la prueba 2022-2025, el 10 % de sectores mejor puntuados de cada comuna concentró el **29 %** del
  fuego (el azar daría 10 %). Útil para ordenar, no para asegurar dónde será el próximo incendio.
- **Recomendaciones:** textos generales de CONAF, SENAPRED y MINVU según los rasgos del sector y el nivel de riesgo
  de la comuna (`docs/fuentes.md`, sección 3c).

## 1. Sectores y capas

| Capa | Fuente | Resumen en la región (promedio por sector) |
|---|---|---|
| Historial de focos | FIRMS VIIRS Suomi NPP `uso_base`, 2012-2025 | 10.293 focos en sectores; 16,6 % de los sectores tuvo algún fuego |
| Vegetación | ESA WorldCover 2021 (10 m) | combustible (árboles + matorral + pastizal) 71 %, pastizal 25 %, construido 2,5 % |
| Interfaz con viviendas | WUI global, Schug et al. 2023 (10 m, ~2020) | 13 % (Viña del Mar 54 %, El Quisco 70 %) |
| Pendiente | Copernicus DEM (30 m) | 18,6° (Los Andes 29°) |

- Celda de 1 km porque la ubicación de un foco VIIRS tiene un error del orden de su píxel (375 m).
- Incendio = focos a menos de 2 km y 2 días (`firecal.events`); "grande" = más de 10 focos (`docs/eventos.md`).
- La WUI usa 0 en bordes con mar (fuera de su leyenda): se trata como sin dato; 56 sectores quedan sin interfaz.

## 2. Fuentes persistentes (no son incendios)

FIRMS marca algunas fuentes fijas (`tipo` 2, ya excluidas en `uso_base`), pero no todas. En la región, 17 sectores
tienen detecciones en muchos años, sobre todo de noche y con poca energía (FRP mediano 0,6-2,3 MW), parejas todo el
año: el patrón de una refinería, fundición o cementera, no de un incendio. En la región el 39 % de los focos es
nocturno; en esos sectores, 61-100 %.

Regla: ≥ 10 días con detección, en ≥ 5 años, ≥ 60 % de noche y nunca parte de un incendio de más de 10 focos. Se
marcan (`fuente_persistente`) y sus 595 detecciones no cuentan como historial de incendios. Pendiente: el modelo por
comuna todavía las incluye en su objetivo (por ejemplo, Concón suma 130 días con detección en un solo sector).

## 3. Rasgos (criterio del proyecto)

| Rasgo | Regla |
|---|---|
| `interfaz` | ≥ 25 % del sector es interfaz casas-vegetación (WUI 1-4) |
| `pastizal` | ≥ 40 % pastizal |
| `bosque_matorral` | ≥ 50 % árboles + matorral (WorldCover no separa bosque nativo de plantación) |
| `pendiente` | pendiente media ≥ 15° |
| `historial` | fuego en ≥ 2 días desde 2012 o algún incendio grande |
| `fuente_persistente` | sección 2 |

## 4. ¿Ordena bien la prioridad? (validación sin fuga)

¿Qué % de los días-sector con fuego cae en el 10 % de sectores de su comuna con mayor puntaje? Historial contado solo
antes de cada período; los umbrales de los rasgos se fijaron antes de la prueba. El orden de la app se eligió con
calibración 2020-2021; la prueba 2022-2025 se miró una vez (`docs/sectores_validacion.md`).

| Período | Días-sector con fuego | Azar | Historial previo | Interfaz | N.º de factores | **Historial, luego interfaz** |
|---|---|---|---|---|---|---|
| Calibración 2020-2021 | 602 | 10 % | 24 % | 17 % | 12 % | **26 %** |
| Prueba 2022-2025 | 1.388 | 10 % | 27 % | 19 % | 17 % | **29 %** |

- El fuego tiende a volver donde ya estuvo, y la interfaz agrega algo cuando no hay historial.
- Contar factores de exposición (interfaz + vegetación + pendiente + historial) **no** ordena mejor: se publica
  como descripción (`exposicion`), no como orden.
- Mirando solo la comuna de Valparaíso, el historial por celda no ubicaba el fuego mejor que el azar (medido con
  2012-2019 → 2020-2021): en zonas urbanas de interfaz el fuego aparece a menudo donde no había estado.

## 5. Caso: incendio de febrero de 2024 (Viña del Mar, Quilpué, Villa Alemana)

- **Descriptivo:** de los 78 sectores con focos entre el 2 y el 6 de febrero en esas tres comunas, el 54 % tiene el
  rasgo `interfaz`, contra el 32 % del total de sectores de esas comunas.
- **Lista de prioridad del 4 de febrero (24 h, historial previo, sin fuga):** las cinco comunas de la lista quedaron
  en `muy_alto` (Viña del Mar 88 %), pero **ninguno** de los 25 sectores priorizados tuvo focos ese día (26 sectores
  de la región sí). El grueso del incendio en Viña fue el 3 de febrero (97 focos; el 4, 5 focos). Muestra el límite:
  el riesgo por comuna funciona mejor que la ubicación dentro de la comuna.

## 6. Qué haría falta para una probabilidad por sector
Pronóstico del tiempo (aporta poco: con un pronóstico perfecto la vista de 7 días pasa de ×1,10 a ×1,12 sobre la
climatología, ver `docs/decisiones.md`), vegetación que separe plantación de bosque
nativo (MapBiomas Chile), área quemada para clasificar por tamaño (MapBiomas Fuego), caminos (OpenStreetMap) y datos
oficiales de ignición con ubicación (CONAF), además de validarla contra el historial (29 % en prueba).
