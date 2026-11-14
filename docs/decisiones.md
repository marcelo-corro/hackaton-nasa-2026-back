# Decisiones del equipo

Registro corto de qué se decidió, cuándo y por qué. Lo nuevo va arriba.

## 2026-11-14

- **Conexión con el front:** el back publica archivos estáticos (contrato v0.2) en GitHub Pages, en un repo
  público aparte (`aivital-incendios-datos`) que solo lleva archivos generados; el código sigue privado hasta la
  entrega. Sin servidor: nada que se caiga en la demo. Un área dibujada libre (API) queda fuera del MVP.
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
