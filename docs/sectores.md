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

## 3b. Recomendaciones

Cada sector recibe, por horizonte, las recomendaciones de sus rasgos y del nivel de la comuna, más las del clima del
último día en la comuna (`firecal.sectores.recomendaciones`; textos y fuentes en `recomendaciones.json` y
`docs/fuentes.md`, sección 3c).

| Disparador | Recomendación (fuente) |
|---|---|
| Comuna en nivel alto o muy alto, o cualquier condición de clima | Avisar al 130, 132 o 133 (CONAF Valparaíso) |
| Interfaz | Alrededores de la vivienda despejados de vegetación y desechos que se puedan quemar (SENAPRED) |
| Interfaz con bosque o matorral | Poda: árboles enfermos, secos o a menos de 3 m de las casas; 2 a 3 m entre ramas bajas, suelo y viviendas (MINVU) |
| Vegetación o interfaz | No hacer quemas (CONAF: restringidas en la región hasta el 31-05-2027); no botar colillas (SENAPRED) |
| Interfaz con riesgo alto, historial o pendiente | Plan de barrio con zonas seguras y rutas de evacuación (MINVU); informarse del programa Comunidad Preparada (CONAF) |
| Calor o viento (mes o umbral DMC) | Faena Cero: nada de herramientas que hagan chispas, en especial de 12:00 a 18:00 (CONAF) |
| Calor, aire seco o viento | Evitar fuentes de calor cerca de la vegetación, globos de los deseos y fuegos artificiales (CONAF/SENAPRED) |

Condiciones del clima: relativas al mes (`calor`, `aire_seco`, `viento`, `sin_lluvia`: entre el 10 % más extremo) y
absolutas con los umbrales de la Dirección Meteorológica de Chile (> 30 °C, < 30 % de humedad, > 30 km/h; los tres
juntos = `condicion_30_30_30`). Con NASA POWER (~50 km, humedad mínima aproximada) son una referencia, no una medición
local. Ejemplo: la víspera del incendio de 2024 (2-3 de febrero), Viña del Mar, Quilpué y Villa Alemana tenían calor,
aire seco y viento entre el 10 % más extremo del mes, y más de 30 °C con humedad bajo 30 %; el viento de NASA POWER no
pasó los 30 km/h, así que no se marca 30-30-30.

## 3c. Alertas v0.5 (`firecal.sectores.alertas`, validación en `12d_validar_alertas.py`)

| Tipo | Qué comunas | Orden de sus sectores |
|---|---|---|
| Fuego activo | Focos (sin industria) en los 3 días previos, cualquiera sea su nivel | Cercanía al foco reciente (hasta 5) |
| Alerta | Nivel alto o muy alto | Días con fuego previos, luego interfaz (hasta 5) |
| Vigilancia | Nivel medio | Igual (hasta 3) |

Nivel bajo no entra; la lista puede ir vacía. A 7 días: "Prioridades de la semana (orientativo)". Simulación de la
lista de cada día (lo conocido hasta t contra los focos de t+1; `docs/alertas_validacion.md`):

| | v0.4 (25 sectores fijos) | v0.5 |
|---|---|---|
| Sectores por día | 25 | ~12 (0 el 21 % de los días) |
| Fuego del día siguiente en la lista, prueba 2022-2025 | 4,7 % | **6,9 %** |
| Ídem, calibración 2020-2021 | 3,7 % | **14,3 %** |
| % de sectores listados que tuvo fuego (prueba) | 0,18 % | **0,55 %** |
| Comunas con fuego al día siguiente que estaban en la lista (prueba) | 30,5 % | 27,7 % |

Con 0,07 % del territorio por día, la v0.5 concentra ~100 veces más fuego que el azar. Pero a nivel de sector la
lista diaria atrapa poco del fuego nuevo: el producto fuerte sigue siendo el riesgo por comuna. El 92 % de los días en
alto o muy alto ya tenía fuego activo. Caso 4-feb-2024 con las reglas v0.5: 3 de los sectores listados tuvieron
focos ese día (con la regla anterior, 0).

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

## 6. Modelo B: probabilidad por sector (`12c_modelo_sectores.py`, `firecal.sectores.modelo_b`)

Pregunta: **si hay fuego en la comuna un día, ¿en qué sectores cae?** Una fila por sector y por día con fuego en su
comuna (1,6 millones de filas, 5.165 sector-días con fuego). Variables, todas conocidas el día anterior: qué hay en el
sector (vegetación, interfaz, pendiente, caminos de OpenStreetMap, distancia a lo construido), su historial y el de
sus 8 vecinos, y el fuego de los 3 días previos (en la celda, en las vecinas y distancia al foco más cercano).
Gradient boosting, entrena 2012-2019, calibra 2020-2021 (isotónica), 3 semillas.

Punto de control fijado antes de mirar la prueba: superar al orden del A+ en calibración. **Pasó.** % del fuego que
cae en el 10 % de sectores con mayor puntaje de su comuna (azar 10 %):

| Período | Días | Orden A+ (historial, luego interfaz) | Cerca del fuego reciente | **Modelo B** |
|---|---|---|---|---|
| Calibración 2020-2021 | todos (602) | 33,6 % | 49,7 % | **57,7 %** |
| | ignición (383) | 36,6 % | 29,5 % | **41,8 %** |
| | propagación (219) | 26,5 % | **88,1 %** | 85,5 % |
| Prueba 2022-2025 | todos (1.388) | 39,3 % | 42,4 % | **44,5 %** |
| | ignición (1.087) | **44,9 %** | 37,2 % | 41,4 % |
| | propagación (301) | 18,6 % | **59,5 %** | 55,8 % |

(Los porcentajes del orden A+ difieren de la sección 4 porque aquí el historial se actualiza cada día.)

- **Lectura honesta:** en la prueba el modelo B gana en el total, pero no en cada tipo de día. Con fuego nuevo, el
  orden por historial fue mejor (en calibración había sido al revés); con fuego activo, "cerca del fuego de ayer" fue
  algo mejor. Su valor es combinar ambas cosas, no anticipar dónde empieza un incendio. Por eso la **lista de
  alertas mantiene el orden del A+** y el B se publica como capa adicional.
- **Incendio grande** (si hay fuego en el sector, ¿es parte de un incendio de más de 10 focos?): AUC 0,915 en
  calibración y **0,866 en prueba**; en fuegos nuevos 0,825 → **0,830** (estable). Comparado con lo observado en
  2012-2025 cuadra en sectores silvestres (0,78 vs 73 % de los focos), de interfaz y urbanos; **sobreestima en
  cultivos** (0,41 vs 10 %).
- Probabilidad publicada por sector: `prob_si_fuego_en_comuna` (calibrada) y `prob_fuego_24h` = probabilidad de la
  comuna a 24 h × la anterior. Para 48 h y 7 días se publica solo la condicional (sumarlas no da la de la semana).
- Límite: las capas fijas son de ~2020-2021, contemporáneas con calibración; la prueba 2022-2025 no tiene ese problema.

## 7. Qué faltaría para mejorar la probabilidad por sector
Pronóstico del tiempo (aporta poco: con un pronóstico perfecto la vista de 7 días pasa de ×1,10 a ×1,12 sobre la
climatología, ver `docs/decisiones.md`), vegetación que separe plantación de bosque
nativo (MapBiomas Chile), área quemada para medir el tamaño en hectáreas (MapBiomas Fuego) y datos oficiales de
ignición con ubicación (CONAF), que ayudarían justo donde el modelo B no supera al historial: los fuegos nuevos.
