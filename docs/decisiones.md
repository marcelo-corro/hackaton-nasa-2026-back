# Decisiones del equipo

Registro corto de qué se decidió, cuándo y por qué. Lo nuevo va arriba.

## 2026-11-14

- **Desafío:** se trabaja *Harmonization of MODIS and VIIRS Hot Spots* (8B) y no *Dancing with the SARs* (5D).
  Motivo: 8B tiene datos de Chile ya descargados, ~430 mil focos para entrenar y riesgo técnico bajo; 5D no tiene
  datos NISAR de un sismo chileno ni etiquetas de daño. Detalle en los informes del Drive.
  Pendiente: cambiar el desafío registrado en la página del equipo (todavía figura *Trend Detective*).
- **Repos:** back (este) y front por separado, unidos por `contracts/`. El back publica archivos estáticos.
- **Alcance:** modelo local de Chile primero. Segunda región para comparar (Argentina o California): por decidir.
- **Pitch:** el modelo se presenta fuerte en armonización, anomalías y propagación; se declara el límite en
  predecir dónde empieza un incendio.
