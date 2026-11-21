# Decisiones del equipo

Registro corto de qué se decidió, cuándo y por qué. Lo nuevo va arriba.

## 2026-11-21: pronóstico del tiempo (Open-Meteo) en el riesgo publicado (modelo v4)

- **Problema:** NASA POWER llega con ~4 días de rezago y no tiene los días que se predicen. Al publicar se repetía el
  último clima disponible: en las 80 comunas con más fuego (2024-2025) la precisión media a 24 h de lo publicado era
  0,248, contra 0,308 con el clima del día.
- **Cota medida primero** (prueba 2022-2025, todas las comunas): con el clima real de los días que se predicen la
  precisión media sube 0,283 → 0,313 a 24 h, 0,322 → 0,353 a 48 h y solo 0,470 → 0,490 a 7 días (ventaja sobre la
  climatología ×1,09 → ×1,14). **A 7 días no se usa pronóstico.**
- **Con pronósticos reales** (Open-Meteo, archivo por plazo desde 2024; `08b_validar_pronostico.py`,
  [detalle](pronostico_validacion.md)): 24 h 0,248 → 0,297 rellenando el rezago → **0,318** con el pronóstico de t+1;
  48 h 0,315 → 0,358 → **0,389**. El modelo entrenado con POWER funciona casi igual con Open-Meteo (sin corrección de
  sesgos).
- **Adoptado:** paso 5e diario (Open-Meteo, mismo punto por comuna que POWER, hasta 50 comunas por petición) y modelo
  v4 con el clima de t+1 (24 h) y de t+1 y t+2 (48 h); al entrenar, el observado. Si Open-Meteo falla, todo vuelve a v3
  ese día. NASA POWER sigue siendo el clima histórico. Fuente y licencia (CC BY 4.0, enlace visible) en
  [fuentes.md](fuentes.md).

## 2026-11-21: fuentes persistentes fuera del conteo en todo Chile

- **Problema:** refinerías, fundiciones, faenas mineras, rellenos y volcanes que FIRMS no marca se contaban como
  incendios. Lo «normal» de noviembre en Copiapó era 16,9 % de los días con focos y salía en riesgo alto casi siempre;
  la regla de fuentes persistentes de los sectores (`firecal.sectores.historial`) solo corría en Valparaíso y, como es
  nocturna, no veía las fuentes diurnas del desierto.
- **Medición:** de 156 celdas de 1 km del norte con fuego repetido (>= 10 días de >= 5 años), 149 tienen < 10 % de
  vegetación en ESA WorldCover; en el sur, 7 de 865 (volcanes). La regla nocturna sola marcaba refinerías y fundiciones
  (Concón 95 % de sus días con focos, Quintero 81 %), pero dejaba Copiapó en 13 %.
- **Regla adoptada** (`firecal.fuentes_persistentes`, paso 4b): fuego repetido y (sin vegetación < 10 % o nocturna
  >= 60 % que no se propaga: nunca en un incendio de > 10 focos o de más de 2 km), en dos grillas (0 y 500 m). 470
  celdas; 3,2 % de las detecciones Suomi NPP 2012-2025; 5,8 % de los días-comuna con focos. Sale de `uso_base`, así que
  afecta serie, calendario, riesgo, incendios activos y lo «normal». Las comunas forestales y el altiplano no cambian
  (Collipulli 0,4 %; Curicó, Ovalle, Los Ángeles, Linares, Putre 0 %).
- **Modelo de riesgo reentrenado** (prueba 2022-2025): 24 h AUC 0,845 → 0,847, precisión media 0,282 → 0,283, captura
  del 10 % superior 52,0 → 52,9 %; 48 h igual o mejor; 7 días precisión media 0,490 → 0,470 con tasa base 16,3 → 15,2 %
  (ventaja sobre la climatología ×1,10 → ×1,09). Serie armonizada casi igual (razón global SNPP/Aqua 3,184 → 3,183).
- **La máscara se versiona** (`ref/fuentes_persistentes.csv`, ~470 filas, derivada de datos públicos): el paso diario
  no vuelve a leer WorldCover. Repetir el paso 4b una vez al año. Detalle: [fuentes_persistentes.md](fuentes_persistentes.md).

## 2026-11-15: zona probable de avance (no cono)

- **Se midió si se puede anticipar hacia dónde avanza un incendio** (`14_validar_avance.py`, 6.674 avances día a día en
  Chile 2012-2026, viento diario de NASA POWER). A ±45° (azar 25 %): viento a favor 29 % (calibración) y 31 % (prueba
  2022-2026); con viento fuerte 34 % y 36 %; con viento suave, azar; persistencia (hacia donde avanzó ayer), azar; ni
  el viento perfecto del día siguiente mejora. Un cono que contuviera la mitad de los avances abriría ±84°: **no se
  publica cono**.
- **Se publica la zona probable de avance:** círculos de 2,5 km (69 % de los avances del día siguiente en la prueba) y
  3,6 km (85 %), con flecha de viento solo cuando es fuerte (desde 3,2 m/s). `avance/activos.json`, contrato 0.7.
  Reemplaza el cono inventado del modo visión del front.

## 2026-11-15: datos de 2026 con la MAP_KEY (riesgo real para mañana)

- **Focos 2026 por la API de FIRMS** (`01b_firms_reciente.py`) y **clima 2026 de NASA POWER** (`05c_clima_reciente.py`):
  el pipeline ya no termina el 31-12-2025, sino el último día con focos y clima.
- **Suomi NPP no tiene datos desde el 2-nov-2026** (FIRMS: NRT hasta el 01-11). Para los días siguientes el modelo usa
  **NOAA-20** (mismo instrumento VIIRS). Medido antes de decidir, en 2022-2025: con variables de NOAA-20 el modelo
  rinde igual (AUC 0,845 vs 0,846; precisión media 0,282 en ambos); los conteos de 7 días tienen correlación 0,986 y
  NOAA-20 ve ~5 % menos (`completar_con_noaa20`).
- **`type` en NRT:** se infiere con los focos históricos no vegetales (< 0,3 km); probado a ciegas en 2025 (99,0 %
  detectados, 1,0 % de falsos).
- **Prueba nueva 2026:** enero a octubre de 2026 se evalúa aparte (datos que no existían al elegir el modelo).
  Riesgo por comuna a 24 h: **AUC 0,873** (climatología 0,818), precisión media 0,328, captura top 10 % 59 %; muy alto
  acertó el 48 %; alto o muy alto = 5,9 % de los días-comuna con el 48 % del fuego. Rinde igual o mejor que 2022-2025.
- **Alertas en 2026 (honesto):** la lista anterior (v0.4, 25 sectores fijos) cubrió más fuego del día siguiente que
  la v0.5 (11,6 % vs 8,2 %; comunas 33 % vs 25 %), aunque la v0.5 sigue siendo más eficiente por sector (0,5 % vs
  0,2 % de los sectores listados con fuego) y marca menos (8,7 vs 25 por día). 2026 tiene poco fuego (146
  sector-días): no se cambia la regla por esto, pero no se puede decir que la v0.5 cubra más fuego en todos los años.
- **Riesgo publicado para hoy:** valido_para 15-11-2026 con focos hasta el 14-11 (NOAA-20 desde el 2-nov) y clima
  hasta el 11-11 (último clima repetido 3 días; medido: AUC 0,846 → 0,824 con 3 días de rezago).

## 2026-11-15: alertas v0.5

- **Alertas por tipo:** fuego activo (focos sin industria en los 3 días previos, sectores por cercanía al foco),
  alerta (alto o muy alto) y vigilancia (medio); nivel bajo no entra y la lista puede ir vacía. A 7 días se llama
  "Prioridades de la semana (orientativo)". Motivo: la lista anterior siempre llenaba 25 sectores, incluso con riesgo
  bajo, y no miraba el fuego del día. La regla de cercanía se eligió con calibración (88 % vs 27 % en días con fuego).
- **Simulación de la lista completa 2020-2025** (`12d_validar_alertas.py`, `docs/alertas_validacion.md`): en la prueba
  2022-2025 la v0.5 marcó ~12 sectores por día (0,07 % del territorio) con el 6,9 % del fuego del día siguiente,
  contra 4,7 % de la v0.4 con 25 sectores; 21 % de los días sin alertas. A cambio, cubre algo menos de comunas con
  fuego al día siguiente (27,7 % vs 30,5 %), porque ya no rellena con comunas en riesgo bajo. Límite honesto: a nivel
  de sector la lista diaria atrapa poco del fuego nuevo; el producto fuerte es el riesgo por comuna.
- **El 92 % de los días en alto o muy alto ya tenía fuego activo.** Los pocos sin fuego son de comunas con industria
  (Concón, Catemu, Quillota), que el modelo por comuna todavía cuenta: refuerza el pendiente de sacarla del objetivo.
- **Motivos por comuna:** hechos verificables (fuego activo o reciente, clima del día, % de días con focos en ese mes).

## 2026-11-15 (madrugada): modelo B por sector

- **Modelo B publicado como capa adicional (contrato v0.4):** P(fuego en el sector | fuego en la comuna) con caminos
  de OpenStreetMap, capas fijas, historial propio y de vecinos y fuego de los 3 días previos. Pasó el punto de control
  fijado antes (superar al orden del A+ en calibración: 57,7 % vs 33,6 % del fuego en el 10 % de sectores). Prueba
  2022-2025: 44,5 % vs 39,3 % (azar 10 %). Pero por tipo de día no gana: con fuego nuevo el orden por historial fue
  mejor (44,9 % vs 41,4 %) y con fuego activo "cerca del fuego de ayer" fue algo mejor. Por eso las alertas siguen con
  el orden del A+ y el B no se presenta como "predice dónde empieza un incendio". Detalle en `docs/sectores.md`, §6.
- **Incendio grande:** si hay fuego en el sector, probabilidad de que sea parte de un incendio de más de 10 focos.
  AUC 0,866 en prueba y 0,83 en fuegos nuevos (estable entre calibración y prueba). Sobreestima en cultivos.

## 2026-11-14 (noche): piloto por sector y modelo v3

- **Piloto A+ por sector (Región de Valparaíso, 36 comunas continentales):** el equipo quería un mapa por sector con
  probabilidad por tipo de incendio. Medido antes de decidir: no hay datos para una probabilidad por sector ni por
  tipo (el clima es por comuna, el satélite no ve conatos, CONAF SIDCO pide usuario). Se hace la versión que los
  datos sostienen: riesgo **por comuna** (modelo validado) y, dentro, sectores de 1 km **descriptivos** (historial
  de focos, vegetación ESA WorldCover, interfaz con viviendas WUI, pendiente Copernicus DEM) con recomendaciones
  oficiales citadas y una lista de prioridad. Detalle en `docs/sectores.md`.
- **Orden de prioridad dentro de la comuna:** días con fuego previos y, a igualdad, interfaz. Elegido en calibración
  2020-2021 entre cuatro alternativas (26 % del fuego en el 10 % de sectores, azar 10 %); prueba 2022-2025: 29 %.
  Contar factores de exposición no ordenaba mejor que el azar en calibración (12 %): queda solo como descripción.
- **Fuentes persistentes:** 17 sectores con detecciones nocturnas todo el año (refinería, fundiciones, cementera;
  FIRMS no las marca como fuente fija) se excluyen del historial de incendios. Regla: ≥ 10 días, ≥ 5 años, ≥ 60 %
  de noche y nunca parte de un incendio de más de 10 focos. El modelo por comuna todavía las cuenta en su objetivo
  (pendiente).
- **Modelo v3 (`hgb_firms_clima_v3`) con 14 variables en todos los horizontes:** se sacan `n_hoy`, `n_3d`,
  `vecinos_hoy`, `vecinos_3d`, `doy_sin`, `doy_cos`, `dia_semana`, `area_km2` y `dias_sin_lluvia` (se siguen calculando
  para líneas base y backtest). Calibración: +0,0043 de AP a 24 h (3 de 3 semillas), empate a 48 h, −0,0014 a 7 días.
  Prueba 2022-2025 a 24 h: AUC 0,850 → 0,846, AP 0,280 → 0,282, captura top 10 % 52,7 % → 52,0 %. Lo decidió el
  usuario ("14 para todo") tras ver estos números.
- **Horizontes 48 h y 7 días publicados:** a 7 días el modelo supera poco a la climatología (AP ×1,10; a 24 h ×1,88)
  porque usa el clima observado del último día: la vista semanal va rotulada "orientativa". Umbrales de nivel por
  horizonte: los de 24 h se trasladan para que cada nivel agrupe la misma proporción de días-comuna en calibración.
- **Pronóstico del tiempo: no se integra por ahora (medido).** Cota superior en calibración 2020-2021 entrenando con
  el clima OBSERVADO de los días futuros (un pronóstico perfecto): a 7 días la precisión media sube solo de 0,571 a
  0,585 (×1,10 → ×1,12 sobre la climatología); a 24 h, de 0,321 a 0,344 (+7 %). Un pronóstico real rinde menos. A 7
  días no lo justifica; a 24 h podría servir cuando haya focos en tiempo real (MAP_KEY). Script:
  `_retomar/pronostico_cota.py` (fuera del repo).
- **Recomendaciones por clima:** además de las de cada sector, se suman las del clima del último día en la comuna:
  Faena Cero con calor o viento, evitar fuentes de calor con calor, aire seco o viento, y avisar al 130/132/133. Las
  fuentes son CONAF (Faena Cero, llamado en Valparaíso) y la Dirección Meteorológica de Chile (umbrales 30-30-30),
  leídas completas. Las condiciones combinan percentiles del mes y los umbrales absolutos de la DMC; con NASA POWER
  son una referencia.
- **Contrato v0.3 (aditivo):** suma `riesgo/48h.json`, `riesgo/7d.json`, `sectores/{id}.geojson`,
  `sectores/{id}_focos.csv`, `alertas/{región}.json` y `recomendaciones.json`. Los archivos de la v0.2 no cambian.

## 2026-11-14

- **Fuga de objetivo en la climatología (corregida, modelo v2):** al evaluar las variables se vio que
  `clim_comuna_mes` era la más importante por permutación (0,171) pero quitarla mejoraba el modelo en calibración
  (+0,0088 de AP, 7 veces el ruido entre semillas). Causa: en el entrenamiento se calculaba con los mismos días que
  se predecían. Ahora, para cada año de entrenamiento se calcula con los otros años. Prueba 2022-2025: AUC
  0,837 → 0,850, precisión media 0,271 → 0,280, captura del 10 % de mayor riesgo 51,6 % → 52,7 %; el gradient
  boosting ahora supera claramente a la regresión logística (0,850 vs 0,831). Tests de no-fuga en
  `tests/test_riesgo.py`.
- **Riesgo con clima (NASA POWER, B5 de David):** se suma el bloque de clima (temperatura máxima, humedad mínima
  aproximada, viento, lluvia, lluvia de 7 días y días sin llover). Ganó en el período de calibración y queda como
  modelo publicado: `hgb_firms_clima_v1`. En prueba 2022-2025: AUC 0,827 → **0,837**, precisión media 0,253 →
  **0,271**, captura del 10 % de mayor riesgo 50 % → **52 %**; en nivel muy alto acierta 45 % (antes 44 %) y cubre
  22 % (antes 19 %). Mejora modesta pero en todas las métricas y segmentos; la lluvia es la variable de clima que más
  pesa. No anticipa el salto del incendio de Viña 2024 a otra comuna: el clima eleva el riesgo de la zona, no indica
  hacia dónde avanza el fuego.
- **Riesgo (A3), versión base:** comuna × día, objetivo = foco Suomi NPP al día siguiente. Entrena 2012-2019, calibra
  2020-2021, prueba 2022-2025. Gradient boosting con variables FIRMS: AUC 0,827 (climatología 0,789, persistencia
  0,811; regresión logística 0,832, prácticamente igual). El 10 % de mayor riesgo captura el 50 % de los días con
  fuego. Alertas (≥ 12 %): aciertan 30 % donde ya hay fuego (base 16 %) y 14 % para incendios nuevos (base 2,4 %), pero
  81 % de los incendios nuevos empieza sin alerta. Probabilidad topada en 95 %. Se parte sin clima ni vegetación para
  medir cuánto aporta cada fuente al sumarla. Detalle: `docs/riesgo.md`.
- **Eventos (A2):** la hipótesis de que contar incendios en vez de focos iguala los sensores se cumple solo en
  parte: la razón Suomi NPP / MODIS baja de 3,2 a 2,3 (2013-2017) y queda entre 1,8 y 2,3 con cualquier
  definición razonable. La diferencia es sobre todo sensibilidad: MODIS ve el 11 % de los incendios de un foco que ve
  VIIRS y el 100 % de los de más de 50. La deriva de MODIS también se ve en incendios grandes (92 % → 78 % entre
  2012-2020 y 2024-2025). Se mantiene la armonización por calibración; los eventos quedan como evidencia para el
  pitch. Detalle: `docs/eventos.md`.
- **Armonización (A1):** unidad "focos equivalentes MODIS". Regla por período: Terra convertido a Terra + Aqua
  hasta 2002-06; MODIS observado 2002-07 a 2017-12; VIIRS Suomi NPP convertido desde 2018-01 (MODIS cambia de
  procesamiento en 2018 y su órbita se desvía: cuenta 8-24 % menos de lo esperado). Se compararon 8 métodos fuera
  de muestra (calibra 2012-2015, prueba 2016-2017); ganó el factor único calibrado en 2012-2017 (razón 3,18; sesgo
  −2,9 %, error región-mes 16,6 %, cobertura del intervalo del 90 % = 92 %). Los efectos por región o temporada no
  son estables entre años. La cifra 3,55 de los informes previos estaba contaminada por la deriva de MODIS.
  Detalle: `docs/armonizacion.md`.
- **Validación:** se cambió el plan inicial (calibrar 2012-2018, probar 2019-2025) porque desde 2018 MODIS ya no es
  una referencia confiable; probar contra él habría medido su deriva, no el error del método.
- **Conexión con el front:** el back publica archivos estáticos (contrato v0.2) en GitHub Pages, en un repo
  público aparte (`aivital-incendios-datos`, renombrado `hackaton-nasa-2026-datos` el 16-11-2026) que solo lleva archivos generados; el código sigue privado hasta la
  entrega. Creado el mismo día con datos de ejemplo: URL base https://marcelo-corro.github.io/hackaton-nasa-2026-datos
  (CORS abierto verificado), para que el front use la URL definitiva desde el inicio. Sin servidor: nada que se caiga en la demo. Un área dibujada libre (API) queda fuera del MVP.
- **Reparto:** A (ciencia de datos: armonización, eventos, riesgo), B (producto de datos: serie provisional,
  calendario, exportación, publicación, clima) y F (front). Se unen por `contracts/interno.md` y `contracts/README.md`,
  con validadores en `firecal.contratos`. Detalle en `docs/trabajo_en_equipo.md`.
- **Contrato v0.2:** el calendario agrega `mediana_historica` (el desafío pide comparar con la mediana histórica).
- **Unidad de la serie armonizada:** "focos equivalentes MODIS" (provisional: permite comparar con la historia
  desde 2000; se puede revisar).
- **Calidad de datos:** no se borran focos, se marcan (paso 4). Conteo por defecto = `uso_base` (vegetación +
  confianza nominal/alta), por día local de Chile. Se verificó que la razón VIIRS/MODIS cambia con los años por
  la deriva de órbita de Terra y Aqua: la armonización calibra por satélite y en el tiempo. La cifra "3,3 estable"
  de los informes previos se reemplaza por esta medición.
- **Sensores:** solo MODIS (Terra, Aqua) y VIIRS (Suomi NPP, NOAA-20). No se suman satélites que ven los mismos
  incendios. GOES y Sentinel-3 quedan como visión.
- **Desafío:** se trabaja *Harmonization of MODIS and VIIRS Hot Spots* (8B) y no *Dancing with the SARs* (5D).
  Motivo: 8B tiene datos de Chile ya descargados, ~430 mil focos para entrenar y riesgo técnico bajo; 5D no tiene
  datos NISAR de un sismo chileno ni etiquetas de daño. Detalle en los informes del Drive.
  Pendiente: cambiar el desafío registrado en la página del equipo (todavía figura *Trend Detective*).
- **Repos:** back (este) y front por separado, unidos por `contracts/`. El back publica archivos estáticos.
- **Alcance:** modelo local de Chile primero. Segunda región para comparar (Argentina o California): por decidir.
- **Pitch:** el modelo se presenta fuerte en armonización, anomalías y propagación; se declara el límite en
  predecir dónde empieza un incendio.
