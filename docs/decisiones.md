# Decisiones del equipo

Registro corto de qué se decidió, cuándo y por qué. Lo nuevo va arriba.

## 2026-11-14

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
  público aparte (`aivital-incendios-datos`) que solo lleva archivos generados; el código sigue privado hasta la
  entrega. Creado el mismo día con datos de ejemplo: URL base https://marcelo-corro.github.io/aivital-incendios-datos
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
