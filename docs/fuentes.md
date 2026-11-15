# Fuentes de datos y cómo citarlas

Regla del equipo: **todo dato externo que use el back se registra acá** con la URL exacta, la fecha de descarga,
cómo se verificó y la cita que corresponde. Lo que no esté en esta lista no se usa en la demo ni en el pitch.

## 1. NASA FIRMS: focos de calor (datos principales)

| Campo | Valor |
|---|---|
| Qué es | Focos activos MODIS Collection 6.1 (Terra y Aqua) y VIIRS 375 m Collection 2 (Suomi NPP y NOAA-20), archivos anuales por país |
| URL de descarga | `https://firms.modaps.eosdis.nasa.gov/data/country/{carpeta}/{año}/{carpeta}_{año}_Chile.csv` |
| Carpetas | `modis` (2000-2025), `viirs-snpp` (2012-2025), `viirs-jpss1` = NOAA-20 (2018-2025; 2017 y 2026 dan 404) |
| Cómo se baja | `scripts/01_descargar_datos.py` (público, sin cuenta) |
| Versión en los archivos | MODIS `61.03`, VIIRS `2` (columna `version`) |
| Verificación (14-11-2026) | Los 40 archivos MODIS y Suomi NPP que el equipo tenía en el Drive coinciden en tamaño, byte a byte, con el servidor oficial. Los 8 de NOAA-20 se bajaron directo de FIRMS. Tamaño y SHA-256 de cada archivo: [registro_descargas_2026-11-14.csv](registro_descargas_2026-11-14.csv). La ingesta reproduce las cifras del equipo (tipo 0 desde mar-2012: MODIS 94.325, VIIRS-SNPP 335.116) |
| Contenido | 821.539 focos: MODIS 189.717 (2000-11 a 2025), Suomi NPP 416.813 (2012-01 a 2025), NOAA-20 215.009 (2018-04 a 2025) |
| Ojo | Los archivos `viirs-noaa20_*` del Drive son respuestas 404 guardadas como `.csv`: esa carpeta no existe en FIRMS. NOAA-20 está en `viirs-jpss1` |

**Agradecimiento que pide FIRMS** (texto oficial, de https://www.earthdata.nasa.gov/data/tools/firms):

> We acknowledge the use of data and/or imagery from NASA's Fire Information for Resource Management System
> (FIRMS) (https://earthdata.nasa.gov/firms), part of NASA's Land, Atmosphere Near real-time Capability for Earth
> observations (LANCE) (https://earthdata.nasa.gov/lance) and NASA's Earth Science Data and Information System
> (ESDIS).

**Algoritmos de detección** (referencias que lista la misma página):

- Giglio, L., Schroeder, W., & Justice, C. O. (2016). The collection 6 MODIS active fire detection algorithm and
  fire products. *Remote Sensing of Environment*, 178, 31-41. https://doi.org/10.1016/j.rse.2016.02.054
- Schroeder, W., Oliva, P., Giglio, L., & Csiszar, I. A. (2014). The New VIIRS 375m active fire detection data
  product: algorithm description and initial assessment. *Remote Sensing of Environment*, 143, 85-96.
  https://doi.org/10.1016/j.rse.2013.12.008

## 1b. NASA FIRMS API (año en curso, con MAP_KEY)

| Campo | Valor |
|---|---|
| Qué es | Focos VIIRS de Suomi NPP y NOAA-20 de 2026: versión estándar (SP) hasta el 31-07 y casi en tiempo real (NRT) después |
| URL | `https://firms.modaps.eosdis.nasa.gov/api/area/csv/[MAP_KEY]/[FUENTE]/-76,-56,-66,-17/[1..5]/[fecha]` (la llave va en `.env`, nunca en el repo) |
| Código | `scripts/01b_firms_reciente.py` → `data/raw/firms/viirs-snpp_2026_Chile.csv` y `viirs-jpss1_2026_Chile.csv` |
| Bajado | 15-11-2026: Suomi NPP hasta el 01-11-2026 (FIRMS no tiene más), NOAA-20 hasta el 14-11-2026 |
| Límites | 5.000 transacciones cada 10 minutos por llave; 5 días por consulta (área). Se usaron ~130 consultas |
| `type` | NRT no lo trae: se infiere con la máscara de focos históricos no vegetales (< 0,3 km). Probado a ciegas en 2025: 99,0 % de los no vegetales detectados, 1,0 % de la vegetación marcada por error |

Misma cita y agradecimiento que la sección 1.

## 2. Open-Meteo (ERA5): clima de la prueba de predicción

| Campo | Valor |
|---|---|
| Qué es | Clima diario histórico (temperatura máxima, humedad mínima, viento máximo, precipitación) |
| URL | `https://archive-api.open-meteo.com/v1/archive` (parámetros en `prueba_prediccion.py` del Drive) |
| Alcance | 40 celdas de 0,5° en Chile centro-sur, 2016-2025 |
| Copia del equipo | Drive, `informes/datos_8B/prediccion/clima_cache.json` |
| Condición | El plan gratis de Open-Meteo es para uso no comercial |

**Citas que pide Open-Meteo** (de https://open-meteo.com/en/docs/historical-weather-api):

- Zippenfenig, P. (2023). Open-Meteo.com Weather API [Computer software]. Zenodo. https://doi.org/10.5281/ZENODO.7970649
- Hersbach, H., et al. (2023). ERA5 hourly data on single levels from 1940 to present [Data set]. ECMWF.
  https://doi.org/10.24381/cds.adbb2d47
- Muñoz Sabater, J. (2019). ERA5-Land hourly data from 2001 to present [Data set]. ECMWF.
  https://doi.org/10.24381/CDS.E2161BAC
- "Generated using Copernicus Climate Change Service information."

## 2b. NASA POWER: clima diario por comuna (insumo del riesgo a 24-48 h)

Se usa **en lugar de Open-Meteo** para las 345 comunas: el plan gratis de Open-Meteo agotó su cupo diario tras
30 comunas (el rango 2012-2025 consume ~365 de un cupo de 10 000 por comuna y día).

| Campo | Valor |
|---|---|
| Qué es | Reanálisis MERRA-2 y datos de la NASA, a escala diaria, vía la API de POWER |
| URL | `https://power.larc.nasa.gov/api/temporal/daily/point` (`community=AG`, `format=JSON`) |
| Alcance | Un punto dentro de cada una de las 345 comunas (`representative_point`), 2012-01-01 a 2025-12-31 |
| Variables | `T2M_MAX` (°C), `T2MDEW` (°C), `RH2M` (%, media diaria), `WS10M_MAX` (m/s), `PRECTOTCORR` (mm/día) |
| Código | `src/firecal/ingest/clima.py`, `scripts/05b_clima_diario.py` → `data/interim/clima_diario.parquet` |
| Consultado | 2026-11-14 |
| Licencia | Datos abiertos de la NASA; pide citar el origen (abajo) |

**Viento para la zona de avance (paso 5d):** mismas consultas POWER con `WD10M` (dirección media diaria del viento a
10 m, de dónde viene) y `WS10M` (velocidad media, m/s), 2012-01-01 a 2026-11-12, caché `data/raw/viento_power/`,
salida `data/interim/viento_diario.parquet`.

**Límites que hay que decir en la demo o el informe**
- **`hrmin` es una aproximación.** POWER no entrega humedad mínima. Se estima como
  `100 · e(rocío medio) / e(temperatura máxima)` con la fórmula de Magnus. En una prueba (Viña del Mar) quedó
  siempre bajo la humedad media (correlación 0,95). La humedad media medida va aparte, en `hr_media`.
- **Resolución gruesa:** la grilla es de ~0,5° × 0,625° (~50 km); comunas vecinas pequeñas comparten valores.
- **Hora:** POWER entrega hora solar local (`LST`), no la hora civil de Chile; a escala diaria el desfase es
  despreciable.
- **Viento en m/s** (Open-Meteo lo daba en km/h).

**Referencia que pide POWER** (https://power.larc.nasa.gov/docs/referencing/): incluir ambas frases y la fecha de acceso.

- The data was obtained from National Aeronautics and Space Administration (NASA) Langley Research Center's
  Prediction Of Worldwide Energy Resources (POWER) project funded through the NASA Earth Science Division.
- The data was obtained from the POWER Project's Daily 2.10.3 version on 2026/11/14.
  *(Versión leída de la propia respuesta de la API: `header.api` = `POWER Daily API`, `v2.10.3`; fuentes `MERRA2` y
  `POWER`; título `NASA/POWER Source Native Resolution Daily Data`.)*

## 3. Biblioteca del Congreso Nacional (BCN): límites comunales

| Campo | Valor |
|---|---|
| Qué es | Polígonos de las comunas de Chile (shapefile), sección "Mapas vectoriales" de la BCN |
| Página | https://www.bcn.cl/siit/mapas_vectoriales |
| URL de descarga | `https://www.bcn.cl/obtienearchivo?id=repositorio/10221/10396/5/comunas_final.zip` |
| Descargado | 14-11-2026 con `scripts/01_descargar_datos.py` (SHA-256 en el registro) |
| Contenido | 346 polígonos: 345 comunas + 1 "Zona sin demarcar" (`cod_comuna = 0`, se excluye). Proyección EPSG:3857. `cod_comuna` es numérico: hay que rellenarlo a 5 dígitos para el CUT (5109 → `"05109"`). 16 geometrías inválidas (hay que repararlas antes de cruzar con los focos) |
| Estado de los datos | Según la BCN, síntesis de fuentes oficiales con versiones de 2014, 2017 y diciembre de 2018 |
| Condiciones de uso | Uso libre **señalando como fuente a la Biblioteca del Congreso Nacional de Chile**. Material referencial, no apto para trabajos de precisión geodésica |

**Cita:** Biblioteca del Congreso Nacional de Chile. *División comunal: polígonos de las comunas de Chile*
[shapefile]. Mapas vectoriales, https://www.bcn.cl/siit/mapas_vectoriales (consultado el 14-11-2026).

## 3b. Capas del piloto de sectores (Región de Valparaíso)

Bajadas el 14-11-2026 con `scripts/11_descargar_capas.py` (URL, tamaño y SHA-256 en `data/raw/registro_descargas.csv`).
Solo los bloques que tocan las 36 comunas continentales de la región.

| Capa | Qué es | URL | Licencia / condición |
|---|---|---|---|
| ESA WorldCover 2021 v200 | Cobertura del suelo a 10 m, 11 clases (árboles, matorral, pastizal, cultivo, construido...). No separa bosque nativo de plantación | `https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/` (bloques S36W072 y S33W072) | CC BY 4.0 |
| Copernicus DEM GLO-30 | Elevación a 30 m (para la pendiente) | `https://copernicus-dem-30m.s3.amazonaws.com/` (6 bloques de 1°) | Licencia Copernicus DEM: uso libre con la atribución de abajo |
| WUI global (Schug et al. 2023) v1.1 | Interfaz urbano-forestal a 10 m, ~2020, 8 clases (1-4 WUI) | `https://zenodo.org/records/7941460` (zip `SA.zip`; se leyeron solo 9 bloques por rango HTTP, 12 MB de 1,7 GB) | CC BY 4.0 |
| OpenStreetMap (caminos) | 66.243 vías de la Región de Valparaíso (autopista a huella rural), datos al 15-11-2026, para el modelo B | Overpass API `https://overpass-api.de/api/interpreter`, por límite administrativo `ISO3166-2=CL-VS` (consulta exacta en el registro) | ODbL: citar "© colaboradores de OpenStreetMap" |

**Citas:**
- Zanaga, D. et al. (2022). *ESA WorldCover 10 m 2021 v200*. Zenodo. https://doi.org/10.5281/zenodo.7254221
- Copernicus DEM: "produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH
  2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved".
- Schug, F. et al. (2023). The global wildland–urban interface. *Nature*. https://doi.org/10.1038/s41586-023-06320-0 ·
  datos: https://doi.org/10.5281/zenodo.7941460

## 3c. Recomendaciones oficiales (textos de la app)

Las recomendaciones por sector (`src/firecal/sectores/recomendaciones.py`, publicadas en `recomendaciones.json`) son
textos tomados de estas fuentes. Las que no se pudieron leer en el PC del hackatón (PDF) las verificaron Seba y
Kathy contra el documento (página y frase literal abajo); con eso se ajustaron dos textos y se sumó la poda (MINVU).

| Fuente | URL | Qué se toma | Leído |
|---|---|---|---|
| CONAF, situación del uso del fuego como quema controlada | https://www.conaf.cl/actualizacion-situacion-uso-del-fuego-en-regiones/ | Región de Valparaíso: uso del fuego restringido en toda la región hasta el 31-05-2027; Comprobante de Aviso de Quema; sin quemas fines de semana y festivos | Completo (14-11-2026) |
| CONAF, sitio oficial | https://www.conaf.cl/ | Número de emergencias 130 (pie de página) | Sí (14-11-2026) |
| CONAF y Ministerio de Agricultura, llamado a aplicar Faena Cero (31-12-2025) | https://www.conaf.cl/ministerio-de-agricultura-y-conaf-realizan-un-llamado-preventivo-a-aplicar-faena-cero-para-reducir-el-riesgo-de-incendios-forestales/ | Medida voluntaria: restringir faenas con maquinaria o herramientas que produzcan chispas o calor en las horas de mayor temperatura, en especial 12:00-18:00; respetar la prohibición de quemas; SENAPRED: evitar fuentes de calor cerca de la vegetación, globos de los deseos y fuegos artificiales | Completo (14-11-2026) |
| CONAF, llamado a prevenir incendios en Valparaíso (11-12-2025) | https://www.conaf.cl/subsecretario-de-agricultura-refuerza-el-llamado-a-prevenir-incendios-forestales-en-valparaiso/ | Evitar galleteras, soldadoras y desbrozadoras en las horas de mayor temperatura, viento y menor humedad; despejar el perímetro de las viviendas; avisar al 130 (CONAF), 132 (Bomberos) o 133 (Carabineros) | Completo (14-11-2026) |
| Dirección Meteorológica de Chile, variables asociadas al riesgo de incendios | https://climatologia.meteochile.gob.cl/application/diarioc/mapaRiesgoIncendiosHoy | Umbrales: temperatura > 30 °C, humedad relativa < 30 %, viento > 30 km/h ("30-30-30"); aclara que el producto no pronostica incendios | Completo (14-11-2026) |
| SENAPRED, *Prepárate con SENAPRED: incendios forestales* (sin fecha impresa; archivo de dic. 2024) | https://bibliogrd.senapred.gob.cl/bitstream/handle/1671/8866/06_preparate_con_senapred_incendios_forestales_esp.pdf | Pág. 2: «Mantén los alrededores de tu vivienda despejados de vegetación y desechos que se puedan quemar.» · «Evita fumar en lugares con vegetación que puedan arder. Nunca arrojes residuos de cigarrillos ni fósforos.» | Verificado por Seba y Kathy (15-11-2026) |
| MINVU, *Chile se prepara: barrios* (con recomendaciones de CONAF; sin fecha impresa, archivo de dic. 2024) | https://www.minvu.gob.cl/wp-content/uploads/2024/12/DIPTICO-chile-se-prepara-BARRIOS.pdf | Pág. 1: conformar comité de prevención con juntas de vecinos, plan de acción, zonas seguras y vías de evacuación despejadas; poda de árboles enfermos, secos o a menos de 3 m de edificaciones. Pág. 2: «manteniendo un espacio de 2 a 3 metros entre árboles, ramas inferiores, el suelo y las viviendas o edificaciones» (son indicaciones de poda, no un radio de despeje) | Verificado por Seba y Kathy (15-11-2026) |
| CONAF, programa Comunidad Preparada (nota de CONAF Región de O'Higgins, 2-5-2025) | https://www.conaf.cl/conaf-desarrolla-el-programa-comunidad-preparada-frente-a-los-incendios-forestales-con-vecinos-y-vecinas-de-zonas-de-interfaz/ | Sección "Fortaleciendo vulnerabilidades": «el programa consta de cuatro talleres» para comunidades de zonas de interfaz | Verificado por Seba y Kathy (15-11-2026) |

**Dato para el pitch** (verificado por Seba y Kathy): «En Chile, el 99% de los incendios forestales son originados por
causas humanas» (SENAPRED, *Prepárate con SENAPRED: incendios forestales*, pág. 6).

## 4. Fuentes documentales de los informes

Los informes del equipo citan noticias, leyes, planes comunales y documentación técnica. Su registro completo
(URL, fecha de consulta, código HTTP, hash SHA-256 y copia local) está en el Drive:
`informes/fuentes_8B/registro_fuentes.csv` y `informes/fuentes_5D/`.

## 5. Por registrar cuando se usen

Cada una entra a esta lista recién cuando se descargue y se use:

- Focos casi en tiempo real de 2026 (FIRMS Area API, requiere MAP_KEY).
- NDVI y temperatura de superficie (cobertura de suelo y relieve ya están: sección 3b).
- Pronóstico del tiempo (Open-Meteo o ECMWF Open Data): medido, a 7 días no se justifica (`docs/decisiones.md`); a
  24 h, solo con focos en tiempo real.
- MapBiomas Chile (cobertura con plantaciones forestales) y MapBiomas Fuego (área quemada), para separar plantación
  de bosque nativo y clasificar incendios por tamaño.
- Catálogo de focos y áreas quemadas de CONAE (autor del desafío).

## 6. Herramientas de IA

Parte del código y del análisis se hizo con asistentes de IA (Claude, de Anthropic). Revisar en la
*Project Submission Guide* de Space Apps si hay que declararlo y dónde.
